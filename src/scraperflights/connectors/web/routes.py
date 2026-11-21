"""Dated references published in public route pages, without inventory API calls."""
import json
import re
from datetime import datetime
from urllib.parse import urlsplit

from ...core import Offer, money
from ...airports import AIRPORTS
from ...http import ProviderError
from .vueling import VuelingWeb
from .html import document, visible_text, structured_nodes, embedded_nodes, amount, has_type, object_value, route_name_matches

CITIES = {'MAD': 'Madrid', 'BCN': 'Barcelona', 'MTY': 'Monterrey'}
EUR = re.compile(r'(?<![\w.,-])(\d{1,3}(?:[.\s\u00a0\u202f]\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*€')
DECODER = json.JSONDecoder()


class RoutePage(VuelingWeb):
    def search(self, search):
        if 'MTY' in (search.origin, search.destination) and not self.supports_mty:
            return [], 'unsupported_route'
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
        rejected = 0
        unique = set()
        for i, (price, details, link) in enumerate(prices):
            parsed = amount(price)
            if parsed is None:
                rejected += 1
                continue
            signature = (parsed, json.dumps(details, sort_keys=True), link)
            if signature in unique:
                continue
            unique.add(signature)
            offers.append(Offer(
                self.name, f'{search.origin}-{search.destination}-{search.departure}-{search.return_date}-{i}',
                self.seller, details, str(parsed), 'EUR', link=link or url,
                warnings=[self.scope, 'availability_and_checkout_unverified'] +
                         (['stops_unconfirmed'] if not details else [])))
        self.parse_diagnostics = {'parsed_rows': len(prices), 'invalid_prices': rejected, 'offers': len(offers)}
        return offers, 'indicative'

    supports_mty = True
    lowercase_path = True
    scope = 'indicative_dated_reference'


class IberiaWeb(RoutePage):
    name, seller = 'iberia-web', 'Iberia'
    route_url = 'https://www.iberia.com/es/vuelos-baratos/{origin}-{destination}/'
    lowercase_path = False

    def extract(self, html, search):
        cards = document(html).articles
        result = []
        seen = False
        for card in cards:
            if 'cards-block-column--article__content-dates--start' not in card:
                continue
            seen = True
            if re.findall(r'class=["\'][^"\']*\biata\b[^"\']*["\'][^>]*>\s*([A-Z]{3})', card, re.I) != [search.origin, search.destination]:
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
    supports_mty = False
    route_url = 'https://www.aireuropa.com/es-es/ofertas-de-vuelos-desde-{origin}-a-{destination}'

    def extract(self, html, search):
        results = set()
        seen = False
        for row in embedded_nodes(html):
            if row.get('__typename') != 'Fare':
                continue
            seen = True
            if (row.get('originAirportCode'), row.get('destinationAirportCode'),
                row.get('departureDate'), row.get('returnDate'), row.get('currencyCode'),
                row.get('travelClass'), row.get('flightType')) == (
                    search.origin, search.destination, search.departure, search.return_date,
                    'EUR', 'ECONOMY', 'ROUND_TRIP' if search.return_date else 'ONE_WAY'):
                price = amount(row.get('totalPrice'))
                if price is not None and row.get('redemption') is None:
                    results.add(price)
        return [(price, [], None) for price in sorted(results)] if seen else None


class KiwiWeb(RoutePage):
    name, seller = 'kiwi-web', 'Kiwi.com'

    def search(self, search):
        if search.return_date:
            return [], 'unsupported_profile'
        origin = AIRPORTS[search.origin]
        destination = AIRPORTS[search.destination]
        self.route_url = ('https://www.kiwi.com/es/cheap-flights/'
                          + origin['city'] + '-' + origin['country'] + '/'
                          + destination['city'] + '-' + destination['country'] + '/')
        return super().search(search)

    def extract(self, html, search):
        results = {}
        seen = False
        for block in structured_nodes(html):
            if not has_type(block, 'CollectionPage'):
                continue
            seen = True
            entries = object_value(block.get('mainEntity')).get('itemListElement')
            for entry in entries if isinstance(entries, list) else []:
                offer = object_value(object_value(entry).get('item'))
                if offer.get('priceCurrency') != 'EUR' or offer.get('price') is None:
                    continue
                legs = object_value(object_value(offer.get('itemOffered')).get('itinerary')).get('itemListElement')
                if not isinstance(legs, list) or len(legs) != 1:
                    continue
                leg = object_value(legs[0])
                dep = leg.get('departureTime')
                if not isinstance(dep, str):
                    continue
                if (object_value(leg.get('departureAirport')).get('iataCode'),
                    object_value(leg.get('arrivalAirport')).get('iataCode'), dep[:10]) != (
                        search.origin, search.destination, search.departure):
                    continue
                try:
                    datetime.fromisoformat(dep)
                except (ValueError, TypeError):
                    continue
                direct = 'sin escalas' in str(leg.get('description') or '').lower()
                if search.direct and (not direct or 'con escalas' in str(offer.get('name') or '').lower()):
                    continue
                link = offer.get('url')
                if not isinstance(link, str):
                    continue
                parsed = urlsplit(link)
                if (parsed.scheme != 'https' or parsed.netloc != 'www.kiwi.com'
                        or not parsed.path.endswith(f'/{search.departure}/no-return/')):
                    continue
                price = amount(offer['price'])
                if price is None:
                    continue
                results[(dep, price)] = (price, [{'leg': 0, 'origin': search.origin,
                    'destination': search.destination, 'departure': dep}], link)
        return list(results.values()) if seen else None


class TrabberWeb(RoutePage):
    name, seller = 'trabber-web', 'Trabber'
    route_url = 'https://www.trabber.es/vuelos-{origin}-{destination}-{o}-{d}/'
    scope = 'indicative_route_minimum'

    def extract(self, html, search):
        for block in structured_nodes(html):
            if not has_type(block, 'Product'):
                continue
            if not route_name_matches(block.get('name'), CITIES[search.origin], CITIES[search.destination]):
                continue
            fare = object_value(block.get('offers'))
            if fare.get('@type') == 'AggregateOffer' and fare.get('priceCurrency') == 'EUR':
                return [(fare['lowPrice'], [], None)] if fare.get('lowPrice') is not None else []
        return None
