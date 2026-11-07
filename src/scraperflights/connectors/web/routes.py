"""Dated references published in public route pages, without inventory API calls."""
import json
import re
from datetime import datetime
from urllib.parse import urlsplit

from ...core import Offer, money
from ...http import ProviderError
from .vueling import VisibleText, VuelingWeb

CITIES = {'MAD': 'Madrid', 'BCN': 'Barcelona'}
JSON_LD = re.compile(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
EUR = re.compile(r'(\d+(?:[,.]\d{1,2})?)\s*€')
DECODER = json.JSONDecoder()


def visible_text(html):
    parser = VisibleText()
    parser.feed(html)
    return ' '.join(' '.join(parser.parts).split())


class RoutePage(VuelingWeb):
    def search(self, search):
        if search.adults != 1 or search.cabin_bags or search.checked_bags:
            return [], 'unsupported_profile'
        origin, destination = CITIES[search.origin], CITIES[search.destination]
        url = self.route_url.format(origin=origin, destination=destination,
                                    o=search.origin, d=search.destination)
        if self.lowercase_path:
            url = url.lower()
        html = self.fetch(url)
        if 'cf_chl_' in html or 'Just a moment...' in html:
            raise ProviderError('web_access_blocked')
        prices = self.extract(html, search)
        if prices is None:
            raise ProviderError('web_offers_not_found')
        offers = []
        for i, (price, details, link) in enumerate(prices):
            offers.append(Offer(
                self.name, f'{search.origin}-{search.destination}-{search.departure}-{search.return_date}-{i}',
                self.seller, details, str(money(str(price).replace(',', '.'))), 'EUR', link=link or url,
                warnings=[self.scope, 'availability_and_checkout_unverified'] +
                         (['stops_unconfirmed'] if not details else [])))
        return offers, 'indicative'

    lowercase_path = True
    scope = 'indicative_dated_reference'


class IberiaWeb(RoutePage):
    name, seller = 'iberia-web', 'Iberia'
    route_url = 'https://www.iberia.com/es/vuelos-baratos/{origin}-{destination}/'
    lowercase_path = False

    def extract(self, html, search):
        cards = re.findall(r'<article\b[^>]*>.*?</article>', html, re.S)
        result = []
        seen = False
        for card in cards:
            if 'cards-block-column--article__content-dates--start' not in card:
                continue
            seen = True
            if re.findall(r'class="iata"[^>]*>\s*([A-Z]{3})', card) != [search.origin, search.destination]:
                continue
            text = visible_text(card)
            dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text)
            expected = [search.departure] + ([search.return_date] if search.return_date else [])
            trip = 'ida y vuelta' if search.return_date else 'solo ida'
            match = EUR.search(text)
            if dates == expected and trip in text.lower() and match:
                result.append((match[1], [], None))
        return result if seen else None


class AirEuropaWeb(RoutePage):
    name, seller = 'aireuropa-web', 'Air Europa'
    route_url = 'https://www.aireuropa.com/es-es/ofertas-de-vuelos-desde-{origin}-a-{destination}'

    def extract(self, html, search):
        markers = list(re.finditer(r'\{\s*"__typename"\s*:\s*"Fare"\s*,', html))
        results = set()
        for marker in markers:
            try:
                row, _ = DECODER.raw_decode(html, marker.start())
            except ValueError:
                continue
            if (row.get('originAirportCode'), row.get('destinationAirportCode'),
                row.get('departureDate'), row.get('returnDate'), row.get('currencyCode'),
                row.get('travelClass'), row.get('flightType')) == (
                    search.origin, search.destination, search.departure, search.return_date,
                    'EUR', 'ECONOMY', 'ROUND_TRIP' if search.return_date else 'ONE_WAY'):
                if row.get('totalPrice') is not None and row.get('redemption') is None:
                    results.add(money(row['totalPrice']))
        return [(price, [], None) for price in sorted(results)] if markers else None


class KiwiWeb(RoutePage):
    name, seller = 'kiwi-web', 'Kiwi.com'
    route_url = 'https://www.kiwi.com/es/cheap-flights/{origin}-spain/{destination}-spain/'

    def extract(self, html, search):
        results = {}
        seen = False
        for script in JSON_LD.findall(html):
            try:
                block = json.loads(script)
            except ValueError:
                continue
            if not isinstance(block, dict) or block.get('@type') != 'CollectionPage':
                continue
            seen = True
            if search.return_date:
                return []
            for entry in block.get('mainEntity', {}).get('itemListElement', []):
                offer = entry.get('item', {})
                if offer.get('priceCurrency') != 'EUR' or offer.get('price') is None:
                    continue
                legs = offer.get('itemOffered', {}).get('itinerary', {}).get('itemListElement', [])
                if len(legs) != 1:
                    continue
                leg = legs[0]
                dep = leg.get('departureTime', '')
                if (leg.get('departureAirport', {}).get('iataCode'),
                    leg.get('arrivalAirport', {}).get('iataCode'), dep[:10]) != (
                        search.origin, search.destination, search.departure):
                    continue
                datetime.fromisoformat(dep)
                direct = 'sin escalas' in leg.get('description', '').lower()
                if search.direct and (not direct or 'con escalas' in offer.get('name', '').lower()):
                    continue
                link = offer.get('url', '')
                parsed = urlsplit(link)
                if (parsed.scheme != 'https' or parsed.netloc != 'www.kiwi.com'
                        or not parsed.path.endswith(f'/{search.departure}/no-return/')):
                    continue
                price = money(offer['price'])
                results[(dep, price)] = (price, [{'leg': 0, 'origin': search.origin,
                    'destination': search.destination, 'departure': dep}], link)
        return list(results.values()) if seen else None


class TrabberWeb(RoutePage):
    name, seller = 'trabber-web', 'Trabber'
    route_url = 'https://www.trabber.es/vuelos-{origin}-{destination}-{o}-{d}/'
    scope = 'indicative_route_minimum'

    def extract(self, html, search):
        for script in JSON_LD.findall(html):
            try:
                block = json.loads(script)
            except ValueError:
                continue
            if not isinstance(block, dict) or block.get('@type') != 'Product':
                continue
            if f'{CITIES[search.origin]} - {CITIES[search.destination]}' not in block.get('name', ''):
                continue
            fare = block.get('offers', {})
            if fare.get('@type') == 'AggregateOffer' and fare.get('priceCurrency') == 'EUR':
                return [(fare['lowPrice'], [], None)] if fare.get('lowPrice') is not None else []
        return None
