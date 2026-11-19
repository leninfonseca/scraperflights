"""Local history and upload operations used by the dashboard."""
import base64
import binascii
import json
import sqlite3

from .imports import MAX_ROWS, read_tables, report_rows
from .metrics import analyze, normalize


def history(directory, database):
    rows, issues = [], []
    # SQLite and JSON exports may contain the same observations. Metrics deduplicate them.
    if database and database.is_file():
        connection = sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)
        try:
            for index, (payload,) in enumerate(connection.execute('SELECT payload FROM runs ORDER BY rowid DESC')):
                if index >= 1000:
                    issues.append('Se cargaron los últimos 1.000 informes del histórico.')
                    break
                rows.extend(dict(row, _source='SQLite') for row in report_rows(json.loads(payload)))
                if len(rows) > MAX_ROWS:
                    raise ValueError('El histórico supera 20.000 filas. Importa archivos de un período más corto.')
        except (sqlite3.Error, ValueError) as exc:
            issues.append('Histórico SQLite: ' + str(exc))
        finally:
            connection.close()
    if directory.is_dir():
        for path in sorted(directory.glob('*.json')):
            if path.is_symlink():
                continue
            if path.stat().st_size > 8 * 1024 * 1024:
                issues.append(path.name + ': supera 8 MB')
                continue
            try:
                rows.extend(dict(row, _source=path.name) for row in report_rows(json.loads(path.read_text(encoding='utf-8-sig'))))
            except (ValueError, OSError, TypeError, KeyError) as exc:
                issues.append(path.name + ': ' + str(exc))
            if len(rows) > MAX_ROWS:
                raise ValueError('El conjunto supera 20.000 filas. Usa una carpeta con menos informes.')
    accepted, rejected = [], []
    for index, row in enumerate(rows):
        normalized, invalid = normalize([row], source=row.pop('_source', 'history'))
        accepted.extend(normalized)
        rejected.extend(dict(item, source=row.get('source', 'history'), row=index + 1) for item in invalid)
    return {'records': accepted, 'rejected': rejected, 'issues': issues}


def handle(operation, payload, directory, database):
    if operation == '/analysis/history':
        return history(directory, database)
    if operation == '/analysis/import':
        try:
            name = payload['name']
            if not isinstance(name, str) or len(name) > 255:
                raise ValueError('Nombre de archivo inválido')
            data = base64.b64decode(payload['content'], validate=True)
        except (KeyError, binascii.Error, TypeError):
            raise ValueError('Archivo inválido')
        return {'tables': read_tables(name, data)}
    if operation == '/analysis/normalize':
        rows = payload.get('rows', [])
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError('La tabla admite hasta 20.000 filas')
        records, rejected = normalize(rows, payload.get('mapping'), payload.get('defaults'),
                                      payload.get('source', 'Importación'), payload.get('epoch'))
        return {'records': records, 'rejected': rejected}
    if operation == '/analysis/calculate':
        rows = payload.get('records', [])
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError('El análisis admite hasta 20.000 filas')
        # Validate imported or edited client data again before calculating.
        accepted, rejected = normalize(rows)
        for clean, original in zip(accepted, rows):
            clean['source'] = str(original.get('source', 'Importación'))
        if rejected:
            raise ValueError('El conjunto contiene datos sin validar. Vuelve a importar las filas.')
        return analyze(accepted)
    raise ValueError('Operación desconocida')
