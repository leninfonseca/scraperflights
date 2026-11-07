import json
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch

from scraperflights.cli import run_search
from scraperflights.core import Search
from scraperflights.connectors.web.routes import AirEuropaWeb, KiwiWeb


class RoutePageTests(TestCase):
    def test_exact_date_and_non_checkout_price(self):
        day = date.today() + timedelta(days=30)
        trip = Search('MAD', 'BCN', day.isoformat(), (day + timedelta(days=3)).isoformat())
        fare = {'__typename': 'Fare', 'originAirportCode': 'MAD', 'destinationAirportCode': 'BCN',
                'departureDate': trip.departure, 'returnDate': trip.return_date, 'currencyCode': 'EUR',
                'travelClass': 'ECONOMY', 'flightType': 'ROUND_TRIP', 'totalPrice': 89.95}
        wrong_date = dict(fare, departureDate=(day + timedelta(days=1)).isoformat(), totalPrice=1)
        with patch.object(AirEuropaWeb, 'fetch', return_value=json.dumps([fare, wrong_date])):
            report = run_search(trip, ['aireuropa-web'], {})
        self.assertEqual(report['lowest_dated_reference']['amount'], '89.95')
        self.assertIsNone(report['winner'])
        self.assertIsNone(report['lowest_observed'])

    def test_conflicting_stops_are_not_treated_as_direct(self):
        day = (date.today() + timedelta(days=30)).isoformat()
        trip = Search('MAD', 'BCN', day)
        flight = {'departureAirport': {'iataCode': 'MAD'}, 'arrivalAirport': {'iataCode': 'BCN'},
                  'departureTime': day + 'T08:30:00', 'description': 'Sin escalas (directo)'}
        offer = {'price': 20, 'priceCurrency': 'EUR', 'name': 'Vuelo con escalas',
                 'itemOffered': {'itinerary': {'itemListElement': [flight]}},
                 'url': f'https://www.kiwi.com/es/search/results/madrid/barcelona/{day}/no-return/'}
        page = {'@type': 'CollectionPage', 'mainEntity': {'itemListElement': [{'item': offer}]}}
        html = '<script type="application/ld+json">' + json.dumps(page) + '</script>'
        with patch.object(KiwiWeb, 'fetch', return_value=html):
            report = run_search(trip, ['kiwi-web'], {})
        self.assertEqual(report['sources'][0]['status'], 'indicative')
        self.assertIsNone(report['lowest_dated_reference'])
