from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch
import json

from scraperflights.cli import providers_for, run_search
from scraperflights.connectors.web.ground import OmioTrainWeb, BlaBlaCarWeb
from scraperflights.core import Search


class GroundTests(TestCase):
    def test_transport_routes(self):
        day = (date.today() + timedelta(days=20)).isoformat()
        self.assertEqual(providers_for(Search('BCN', 'MAD', day), ['carpool']), ['blablacar-web'])
        self.assertEqual(providers_for(Search('BCN', 'MTY', day), ['train']), [])

    def test_return_train_prices_remain_separate(self):
        day = date.today() + timedelta(days=20)
        search = Search('BCN', 'MAD', day.isoformat(), (day + timedelta(days=3)).isoformat())
        def page(url):
            reverse = '/madrid/barcelona' in url
            origin, target, departure = ('Madrid', 'Barcelona', search.return_date) if reverse else ('Barcelona', 'Madrid', search.departure)
            row = {'@type': 'TrainTrip', 'potentialAction': {'fromLocation': {'name': origin},
                   'toLocation': {'name': target}}, 'departureTime': departure + 'T10:00:00+01:00',
                   'offers': {'price': '30' if reverse else '25', 'priceCurrency': 'EUR'},
                   'provider': {'name': 'iryo'}}
            return '<script type="application/ld+json">' + json.dumps([row, row]) + '</script>'
        with patch.object(OmioTrainWeb, 'fetch', side_effect=page):
            result = run_search(search, ['omio-train-web'], {})
        self.assertEqual([(o['amount'], o['journey_leg'], o['transport_mode']) for o in result['supplemental_prices']],
                         [('25', 'outbound', 'train'), ('30', 'return', 'train')])
        self.assertIsNone(result['lowest_dated_reference'])
        self.assertIsNone(result['winner'])

    def test_carpool_minimum_is_not_a_specific_departure(self):
        search = Search('BCN', 'MAD', (date.today() + timedelta(days=20)).isoformat())
        row = {'@type': 'Product', 'name': 'Viaje en coche compartido de Barcelona a Madrid',
               'offers': {'@type': 'AggregateOffer', 'lowPrice': '21.79', 'priceCurrency': 'EUR'}}
        with patch.object(BlaBlaCarWeb, 'fetch', return_value='<script type="application/ld+json">' + json.dumps(row) + '</script>'):
            result = run_search(search, ['blablacar-web'], {})
        self.assertEqual(result['supplemental_prices'][0]['transport_mode'], 'carpool')
        self.assertIsNone(result['lowest_dated_reference'])
