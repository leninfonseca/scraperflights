import json
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase
from zipfile import ZipFile

from scraperflights.analysis.imports import read_tables
from scraperflights.analysis.metrics import analyze, normalize
from scraperflights.analysis.service import history


def row(amount, observed='2026-11-01T10:00:00Z', **changes):
    return dict(amount=amount, observed_at=observed, origin='BCN', destination='MTY',
                departure='2027-01-15', currency='EUR', transport_mode='flight',
                scope='user_reference', **changes)


class AnalysisTests(TestCase):
    def test_percentages_and_duplicate_sources(self):
        clean, rejected = normalize([row('100'), row('80','2026-11-02T10:00:00Z')],source='a')
        self.assertFalse(rejected)
        result = analyze(clean + [dict(clean[0],source='b')])
        group = result['groups'][0]
        self.assertEqual(result['duplicates'],1)
        self.assertEqual(group['change_pct'],'-20.0')
        self.assertEqual(group['median'],'90')
        self.assertEqual(group['range_pct'],'25.00')
        self.assertEqual(group['points'][0]['sources'],['a','b'])

    def test_unknown_values_can_be_revalidated(self):
        clean, rejected = normalize([row(0)])
        self.assertFalse(rejected)
        again, rejected = normalize(clean)
        self.assertFalse(rejected)
        self.assertEqual(len(again),1)
        result = analyze(again + [dict(again[0], amount='20', observed_at='2026-11-02T10:00:00+00:00')])
        self.assertIsNone(result['groups'][0]['change_pct'])

    def test_scope_currency_and_return_dates_are_separate(self):
        data = [row('100'),dict(row('100'), currency='MXN'),
                dict(row('100'), scope='indicative_route_minimum'),
                row('100', return_date='2027-02-01')]
        clean, _ = normalize(data)
        self.assertEqual(len(analyze(clean)['groups']),4)

    def test_conflicting_simultaneous_prices_have_no_temporal_percentage(self):
        clean, _ = normalize([row('100'),row('90')])
        group = analyze(clean)['groups'][0]
        self.assertTrue(group['ambiguous_timestamps'])
        self.assertIsNone(group['change_pct'])

    def test_spanish_csv_mapping_and_invalid_rows(self):
        tabs=read_tables('precios.csv','precio;observado\n1.234,50;01/11/2026\nmal;02/11/2026'.encode())
        clean,rejected=normalize(tabs[0]['rows'],mapping={'amount':'precio','observed_at':'observado'},
                                defaults={'origin':'BCN','destination':'MTY','departure':'2027-01-15',
                                          'currency':'EUR','transport_mode':'avión','scope':'user_reference'})
        self.assertEqual(clean[0]['amount'],'1234.50')
        self.assertEqual(len(rejected),1)

    def test_old_report_history_defaults_to_flight_and_deduplicates(self):
        sample={'search':{'origin':'BCN','destination':'MAD','departure':'2026-12-10'},
                'sources':[], 'observations':[{'amount':'50','currency':'EUR',
                'observed_at':'2026-11-01T10:00:00Z','warnings':['indicative_dated_reference']}]}
        with TemporaryDirectory() as root:
            path=Path(root)
            (path/'one.json').write_text(json.dumps(sample))
            (path/'two.json').write_text(json.dumps(sample))
            result=history(path,None)
        self.assertEqual(len(result['records']),2)
        self.assertEqual(analyze(result['records'])['observations'],1)

    def test_minimal_xlsx_and_excel_dates(self):
        output=BytesIO()
        with ZipFile(output,'w') as archive:
            archive.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Precios" sheetId="1" r:id="rId1"/></sheets></workbook>')
            archive.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            archive.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>amount</t></is></c><c r="B1" t="inlineStr"><is><t>observed_at</t></is></c></row><row r="2"><c r="A2"><v>25</v></c><c r="B2"><v>46327</v></c></row></sheetData></worksheet>')
        tabs=read_tables('prices.xlsx',output.getvalue())
        self.assertEqual(tabs[0]['rows'][0]['amount'],'25')
        clean,rejected=normalize(tabs[0]['rows'],defaults={'origin':'BCN','destination':'MAD',
           'departure':'2027-01-15','currency':'EUR','transport_mode':'train','scope':'user_reference'},
           epoch=tabs[0]['excel_epoch'])
        self.assertFalse(rejected)
        self.assertTrue(clean[0]['observed_at'].startswith('2026-10-31T23:00:00'))
