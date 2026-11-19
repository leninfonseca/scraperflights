from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch
import json

from scraperflights.cli import run_search
from scraperflights.connectors.web.mexico import AeromexicoWeb, LufthansaWeb
from scraperflights.core import Search


class MexicoAirlineTests(TestCase):
    def setUp(self):
        day = date.today() + timedelta(days=40)
        self.search = Search('BCN', 'MTY', day.isoformat(),
                             (day + timedelta(days=14)).isoformat(), direct=False)

    def test_aeromexico_matches_both_dates_and_keeps_eur_separate(self):
        s = self.search
        fare = {'__typename': 'Fare', 'originAirportCode': 'BCN', 'destinationAirportCode': 'MTY',
                'departureDate': s.departure, 'returnDate': s.return_date,
                'flightType': 'ROUND_TRIP', 'travelClass': 'ECONOMY',
                'totalPrice': 748.99, 'currencyCode': 'EUR', 'redemption': None}
        data = [fare, dict(fare, currencyCode='MXN', totalPrice=15),
                dict(fare, returnDate=s.departure, totalPrice=10)]
        with patch.object(AeromexicoWeb, 'fetch', return_value=json.dumps(data)):
            result = run_search(s, ['aeromexico-web'], {})
        self.assertEqual([r['amount'] for r in result['supplemental_prices']], ['748.99'])
        self.assertEqual(result['lowest_dated_reference']['seller'], 'Aeroméxico')
        self.assertIsNone(result['winner'])

    def test_lufthansa_minimum_cannot_be_a_dated_reference(self):
        product = {'@type': 'Product', 'name': 'Vuelo Barcelona-Monterrey',
                   'brand': {'name': 'Lufthansa'},
                   'offers': {'@type': 'Offer', 'price': 650, 'priceCurrency': 'EUR'}}
        html = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
        with patch.object(LufthansaWeb, 'fetch', return_value=html):
            result = run_search(self.search, ['lufthansa-web'], {})
        self.assertEqual(result['supplemental_prices'][0]['amount'], '650')
        self.assertIsNone(result['lowest_dated_reference'])
