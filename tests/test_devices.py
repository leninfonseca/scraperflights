from datetime import date, timedelta
from unittest import TestCase
from scraperflights.core import Search
from scraperflights.profiles import DEVICES, WebProfile
from scraperflights.experiment import compare_devices
from scraperflights.analysis.imports import report_rows

class DeviceTests(TestCase):
    def test_distinct_signals_and_partial_safari(self):
        self.assertEqual(len({WebProfile(device=k).headers()['User-Agent'] for k in DEVICES}), len(DEVICES))
        self.assertTrue(WebProfile(device='redmi').browser_options()['is_mobile'])
        self.assertFalse(WebProfile(device='mac').browser_options()['is_mobile'])
        self.assertFalse(WebProfile(device='iphone').metadata()['ip_changed'])
        with self.assertRaises(ValueError):
            WebProfile(device='unknown')

    def test_repeated_control_order_percentage_and_import(self):
        calls = []
        def fake(search, providers, sellers, budget, profile):
            calls.append(profile.device)
            offer = {'amount': '80' if profile.device == 'redmi' else '100', 'currency': 'EUR',
                     'observed_at': '2026-11-19T12:00:00+00:00', 'warnings': ['indicative_dated_reference']}
            return {'search': {'origin': 'BCN', 'destination': 'MAD'}, 'sources': [],
                    'supplemental_prices': [offer], 'observations': [offer]}
        search = Search('BCN', 'MAD', (date.today()+timedelta(days=1)).isoformat())
        report = compare_devices(search, ['iberia-web'], ['redmi', 'iphone'], 2, fake)
        self.assertEqual(calls, ['desktop','redmi','iphone','desktop','desktop','iphone','redmi','desktop'])
        self.assertEqual(len(report['pairs']), 4)
        self.assertEqual(report['pairs'][0]['comparisons'][0]['change_pct'], -20)
        self.assertEqual(report['pairs'][0]['control_comparisons'][0]['change_pct'], 0)
        self.assertEqual(len(report_rows(report)), 8)
        self.assertIn('Redmi', report_rows(report)[1]['profile'])
        with self.assertRaises(ValueError):
            compare_devices(search, ['a']*5, ['desktop'], 2, fake)

    def test_dashboard_endpoint_saves_comparison_and_validates(self):
        from contextlib import closing
        from functools import partial
        from http.server import ThreadingHTTPServer
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from threading import Lock, Thread
        from unittest.mock import patch
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        import json
        from scraperflights.viewer import DashboardHandler
        def fake(search, providers, sellers, budget, profile):
            return {'supplemental_prices': []}
        with TemporaryDirectory() as temp, patch('scraperflights.viewer.run_search', fake):
            handler = partial(DashboardHandler, directory=Path(temp), database=Path(temp)/'history.sqlite', search_lock=Lock())
            with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
                thread = Thread(target=server.serve_forever, daemon=True); thread.start()
                base = f'http://127.0.0.1:{server.server_port}'
                payload = {'origin':'BCN', 'destination':'MTY', 'departure':(date.today()+timedelta(days=2)).isoformat(),
                           'devices':['redmi','iphone'], 'providers':['iberia-web'], 'rounds':1}
                def post(value):
                    return urlopen(Request(base+'/compare-devices', data=json.dumps(value).encode(),
                        headers={'Origin':base,'Content-Type':'application/json'}))
                try:
                    with post(payload) as response:
                        result = json.load(response)
                    self.assertTrue((Path(temp)/result['name']).is_file())
                    self.assertEqual(len(result['report']['pairs']),2)
                    self.assertTrue(all(p['status']=='no_comparable_observations' for p in result['report']['pairs']))
                    with self.assertRaises(HTTPError) as error:
                        post(payload | {'providers':['unknown']})
                    self.assertEqual(error.exception.code,400)
                    error.exception.close()
                    with self.assertRaises(HTTPError) as error:
                        post(payload | {'rounds':True})
                    self.assertEqual(error.exception.code,400)
                    error.exception.close()
                finally:
                    server.shutdown(); thread.join()
