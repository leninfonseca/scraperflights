import json
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch

from scraperflights.cli import run_search
from scraperflights.connectors.web.agency import TripComWeb, WegoWeb
from scraperflights.core import Search
from scraperflights.http import Client


class AgencyPageTests(TestCase):
    def setUp(self):
        day = date.today() + timedelta(days=30)
        self.search = Search('MAD', 'BCN', day.isoformat(), (day + timedelta(days=4)).isoformat())

    def test_trip_package_must_have_both_legs(self):
        search = self.search
        url = ('https://es.trip.com/flights/test/?flighttype=d&ddate=' + search.departure
               + '&rdate=' + search.return_date)

        def leg(origin, destination, day, number, price):
            return {'@type': 'Flight', 'departureAirport': {'iataCode': origin},
                    'arrivalAirport': {'iataCode': destination}, 'departureTime': day + 'T12:00:00Z',
                    'isNonstop': True, 'flightNumber': number,
                    'offers': {'url': url, 'priceCurrency': 'EUR', 'price': price}}

        outbound = leg('MAD', 'BCN', search.departure, 'IB1', 51)
        inbound = leg('BCN', 'MAD', search.return_date, 'IB2', None)

        def html(rows):
            return '<script type="application/ld+json">' + json.dumps({'@graph': rows}) + '</script>'

        parser = TripComWeb(Client())
        self.assertEqual(parser.extract(html([outbound]), search), [])
        [(amount, segments, _)] = parser.extract(html([inbound, outbound]), search)
        self.assertEqual(str(amount), '51')
        self.assertEqual([segment['flight'] for segment in segments], ['IB1', 'IB2'])

    def test_wego_history_cannot_be_the_current_dated_minimum(self):
        search = self.search
        row = {'id': 'MAD-BCN-example', 'fareType': 'historical', 'departureCityCode': 'MAD',
               'arrivalCityCode': 'BCN', 'departureDate': search.departure,
               'returnDate': search.return_date, 'cabinClass': 'economy', 'tripType': 'roundtrip',
               'stopsCount': 0, 'price': 57.42}
        data = json.dumps({'currentCurrencyCode': 'EUR', 'fares': [row]})
        html = '<script>self.__next_f.push(' + json.dumps([1, data]) + ')</script>'
        with patch.object(WegoWeb, 'fetch', return_value=html):
            report = run_search(search, ['wego-web'], {})
        self.assertEqual(report['supplemental_prices'][0]['amount'], '57.42')
        self.assertIsNone(report['lowest_dated_reference'])
        self.assertIsNone(report['winner'])
