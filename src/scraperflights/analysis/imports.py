"""Read local tabular data without executing formulas or external workbook links."""
import csv
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import json
import posixpath
from zipfile import ZipFile, BadZipFile
import xml.etree.ElementTree as ET

MAX_ROWS = 20000
MAX_BYTES = 32 * 1024 * 1024
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def table_rows(rows):
    rows = iter(rows)
    headers = next(rows, [])
    names = [str(cell or '').strip() or f'column_{i + 1}' for i, cell in enumerate(headers)]
    if len(names) != len(set(names)):
        raise ValueError('La tabla contiene cabeceras duplicadas.')
    result = []
    for row in rows:
        if len(result) >= MAX_ROWS:
            raise ValueError('El límite por tabla es de 20.000 filas.')
        if any(value not in (None, '') for value in row):
            if len(row) > len(names) and any(row[len(names):]):
                raise ValueError('Una fila tiene más columnas que la cabecera.')
            result.append(dict(zip(names, list(row) + [None] * max(0, len(names) - len(row)))))
    return result


def xlsx_tables(data):
    try:
        book = ZipFile(BytesIO(data))
        with book:
            if sum(info.file_size for info in book.infolist()) > MAX_BYTES:
                raise ValueError('El Excel descomprimido supera 32 MB.')
            def xml(path):
                return ET.fromstring(book.read(path))
            shared = []
            if 'xl/sharedStrings.xml' in book.namelist():
                for item in xml('xl/sharedStrings.xml').findall('s:si', NS):
                    shared.append(''.join(item.itertext()))
            workbook = xml('xl/workbook.xml')
            properties = workbook.find('s:workbookPr', NS)
            base_date = datetime(1904, 1, 1) if properties is not None and properties.get('date1904') in ('1', 'true') else datetime(1899, 12, 30)
            relations = {r.get('Id'): r.get('Target') for r in xml('xl/_rels/workbook.xml.rels')
                          if r.get('TargetMode') != 'External'}
            result = []
            for sheet in workbook.findall('s:sheets/s:sheet', NS):
                target = relations.get(sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'))
                if not target:
                    continue
                path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
                values = []
                for row in xml(path).findall('s:sheetData/s:row', NS):
                    cells = {}
                    for cell in row.findall('s:c', NS):
                        ref = cell.get('r', '')
                        letters = ''.join(c for c in ref if c.isalpha()).upper()
                        column = 0
                        for char in letters:
                            column = column * 26 + ord(char) - 64
                        if not 0 < column <= 256:
                            raise ValueError('El Excel admite hasta 256 columnas.')
                        kind = cell.get('t')
                        text = cell.findtext('s:v', default='', namespaces=NS)
                        if kind == 's':
                            value = shared[int(text)]
                        elif kind == 'inlineStr':
                            inline = cell.find('s:is', NS)
                            value = ''.join(inline.itertext()) if inline is not None else ''
                        elif kind in ('e', 'b'):
                            value = None
                        else:
                            value = text
                        cells[column - 1] = value
                    values.append([cells.get(i) for i in range(max(cells, default=-1) + 1)])
                    if len(values) > MAX_ROWS + 1:
                        raise ValueError('El límite por hoja es de 20.000 filas.')
                rows = table_rows(values)
                # Date columns are converted during explicit mapping, not guessed from numeric prices.
                result.append({'name': sheet.get('name'), 'rows': rows, 'excel_epoch': base_date.isoformat()})
            return result
    except (BadZipFile, KeyError, ET.ParseError, IndexError) as exc:
        raise ValueError('No se pudo leer este XLSX. Revisa su formato.') from exc


def report_rows(report):
    if isinstance(report, dict) and report.get('kind') == 'lodging':
        return []  # Accommodation has its own price basis and occupancy, never flight series.
    if isinstance(report, list):
        return report
    if not isinstance(report, dict):
        raise ValueError('El JSON debe contener un informe o una lista de filas.')
    if 'pairs' in report:
        result = []
        for pair in report['pairs']:
            for name, run in pair.get('runs', {}).items():
                for row in report_rows(run):
                    result.append(row | {'profile': json.dumps(report.get('profiles', {}).get(name, {}), sort_keys=True)})
        return result
    if 'search' in report and 'sources' in report:
        profile = report['search']
        observations = report.get('observations')
        if not observations:
            observations = report.get('ranked', []) + report.get('pending', [])
        return [profile | row | {'scope': next((w for w in row.get('warnings', []) if w.startswith('indicative_')), 'unclassified'),
                                 'profile': row.get('profile', ''),
                                 'transport_mode': row.get('transport_mode', 'flight'),
                                 'sandbox': row.get('sandbox', False)}
                for row in observations]
    raise ValueError('JSON sin filas o informe reconocible.')


def read_tables(name, data):
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('El archivo supera 8 MB.')
    extension = name.rsplit('.', 1)[-1].lower()
    if extension == 'xlsx':
        return xlsx_tables(data)
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('cp1252')
    if extension == 'json':
        rows = report_rows(json.loads(text))
        if len(rows) > MAX_ROWS:
            raise ValueError('El archivo supera 20.000 observaciones.')
    elif extension in ('csv', 'tsv', 'txt'):
        delimiter = '\t' if extension == 'tsv' else None
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(text[:8192], delimiters=',;\t').delimiter
            except csv.Error:
                delimiter = ','
        rows = table_rows(csv.reader(StringIO(text), delimiter=delimiter))
    else:
        raise ValueError('Admite XLSX, CSV, TSV, TXT tabular y JSON. Guarda los XLS antiguos como XLSX.')
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError('Cada observación debe ser un objeto con columnas.')
    return [{'name': name, 'rows': rows}]
