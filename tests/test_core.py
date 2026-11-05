import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from scraperflights.core import Search, Offer, Store, rank, now, money
from scraperflights.providers import Amadeus, sky_price
from scraperflights.http import Client, ProviderError
from scraperflights.cli import run_search, export

FUTURE = (date.today() + timedelta(days=30)).isoformat()

class Tests(unittest.TestCase):
    def setUp(self):
        self.search = Search('MAD', 'BCN', FUTURE)

    def test_invalid_search(self):
        for args in [('BCN', 'BCN', FUTURE), ('MAD', 'BCN', '2000-01-01')]:
            with self.assertRaises(ValueError): Search(*args)
        with self.assertRaises(ValueError): Search('MAD', 'BCN', FUTURE, adults=0)

    def test_money(self):
        for value in ['NaN', 'Infinity', '-1']:
            with self.assertRaises(ValueError): money(value)
        self.assertEqual(sky_price({'amount': '129990000', 'unit': 'PRICE_UNIT_MICRO'}), '129.99')
        with self.assertRaises(ValueError): sky_price({'amount': '1', 'unit': 'unknown'})

    def test_unknown_cost_reputation_sandbox(self):
        o = Offer('fake', '1', 'Seller', [], '10', 'EUR', verified_at=now())
        sellers = {'Seller': {'status': 'approved', 'reviewed_at': date.today().isoformat(), 'evidence_url': 'https://example.org'}}
        self.assertFalse(rank([o], self.search, sellers)[0])
        o.total = '10'
        self.assertEqual(len(rank([o, o], self.search, sellers)[0]), 1)
        o.sandbox = True
        self.assertFalse(rank([o], self.search, sellers)[0])

    def test_missing_credentials(self):
        with patch.dict('os.environ', {}, clear=True):
            run = run_search(self.search, ['amadeus', 'skyscanner'], {})
        self.assertEqual(run['http_requests'], 0)
        self.assertFalse(run['coverage_complete'])
        self.assertIsNone(run['winner'])
        self.assertTrue(all(s['status'] == 'credentials_missing' for s in run['sources']))

    def test_history_and_exports(self):
        with patch.dict('os.environ', {}, clear=True):
            run = run_search(self.search, ['amadeus'], {})
        with tempfile.TemporaryDirectory() as d:
            db = Store(str(Path(d) / 'test.db'))
            db.save(run)
            self.assertEqual(db.history()[0]['id'], run['id'])
            target = export(run, Path(d))
            self.assertEqual(json.loads(target.read_text())['id'], run['id'])
            self.assertTrue(target.with_suffix('.csv').exists())

    def test_raw_not_persisted(self):
        o = Offer('fake', '1', 'Seller', [], '10', 'EUR', raw={'token': 'secret'})
        self.assertNotIn('secret', json.dumps(o.public()))

    def test_group_price_not_multiplied(self):
        raw = {'id': '1', 'price': {'total': '120.50', 'currency': 'EUR'}, 'itineraries': [
            {'segments': [{'departure': {'iataCode': 'MAD', 'at': FUTURE+'T10:00:00'},
            'arrival': {'iataCode': 'BCN', 'at': FUTURE+'T11:15:00'}, 'carrierCode': 'IB', 'number': '1'}]}]}
        result = Amadeus(Client()).parse([raw], Search('MAD', 'BCN', FUTURE, adults=2))
        self.assertEqual(result[0].amount, '120.50')
        self.assertIsNone(result[0].total)

    def test_reprice_change_and_isolation(self):
        a = Offer('amadeus', '1', 'Seller', [], '20', 'EUR')
        b = Offer('amadeus', '1', 'Seller', [], '25', 'EUR', verified_at=now())
        with patch.object(Amadeus, 'ready', return_value=True), patch.object(Amadeus, 'search', return_value=([a], 'complete')), patch.object(Amadeus, 'refresh', return_value=b):
            run = run_search(self.search, ['amadeus'], {})
        self.assertEqual(run['price_changes'][0]['delta'], '5')
        self.assertEqual(len(run['observations']), 2)

    def test_request_budget(self):
        with self.assertRaises(ProviderError): Client(budget=0).request('GET', 'https://example.org')

class SkyscannerTests(unittest.TestCase):
    def test_parse_sellers_and_price_units(self):
        from scraperflights.providers import Skyscanner
        p = Skyscanner(Client())
        d = date.fromisoformat(FUTURE)
        dt = {'year': d.year, 'month': d.month, 'day': d.day, 'hour': 10}
        p.results = {
            'places': {'a': {'iata': 'MAD'}, 'b': {'iata': 'BCN'}},
            'carriers': {'c': {'name': 'Iberia', 'iata': 'IB'}},
            'agents': {'v': {'name': 'Agency'}},
            'segments': {'s': {'originPlaceId': 'a', 'destinationPlaceId': 'b',
                'departureDateTime': dt, 'arrivalDateTime': dt | {'hour': 11},
                'marketingCarrierId': 'c', 'operatingCarrierId': 'c', 'marketingFlightNumber': '123'}},
            'legs': {'l': {'stopCount': 0, 'segmentIds': ['s']}},
            'itineraries': {'i': {'legIds': ['l'], 'pricingOptions': [{'id': 'p',
                'price': {'amount': '4999', 'unit': 'PRICE_UNIT_CENTI'},
                'agentIds': ['v'], 'items': [{'deepLink': 'https://example.org/book'}]}]}}}
        found = p.parse(Search('MAD', 'BCN', FUTURE))
        self.assertEqual(found[0].amount, '49.99')
        self.assertEqual(found[0].seller, 'Agency')
        self.assertIsNone(found[0].verified_at)
        # Removed inventory must not remain available after refresh.
        p.session = 'session'
        found[0].raw['session'] = 'session'
        with patch.object(p, 'call', return_value={'status': 'RESULT_STATUS_COMPLETE', 'content': {'results': {}}}):
            self.assertIsNone(p.refresh(found[0], Search('MAD', 'BCN', FUTURE)))
