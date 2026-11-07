"""Price observations from public agency and comparison landing pages."""
from datetime import date, datetime, timezone
from decimal import InvalidOperation
import json
import re
from urllib.parse import parse_qs, urlsplit

from ...core import money
from .routes import CITIES, DECODER, JSON_LD, RoutePage


def structured_nodes(html):
    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for script in JSON_LD.findall(html):
        try:
            value = json.loads(script)
        except ValueError:
            continue
        yield from walk(value)


def euros(value):
    try:
        return money(value)
    except (InvalidOperation, ValueError):
        return None


def airport(value):
    if not isinstance(value, dict):
        return None
    identifier = value.get('@id', '')
    return value.get('iataCode') or (identifier.rsplit('/', 1)[-1] if '/#airport/' in identifier else None)


class TripComWeb(RoutePage):
    name, seller = 'tripcom-web', 'Trip.com'
    route_url = 'https://es.trip.com/flights/airport-{o}-{d}/'

    def extract(self, html, search):
        groups = {}
        seen = False
        for flight in structured_nodes(html):
            if flight.get('@type') != 'Flight':
                continue
            offer = flight.get('offers')
            if not isinstance(offer, dict) or offer.get('priceCurrency') != 'EUR':
                continue
            url = offer.get('url', '')
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.netloc != 'es.trip.com':
                continue
            seen = True
            query = parse_qs(parsed.query)
            if (query.get('flighttype'), query.get('ddate'), query.get('rdate')) != (
                ['d' if search.return_date else 's'], [search.departure],
                [search.return_date] if search.return_date else None
            ):
                continue
            valid_until = offer.get('priceValidUntil')
            if valid_until:
                try:
                    if date.fromisoformat(valid_until) < datetime.now(timezone.utc).date():
                        continue
                except ValueError:
                    continue
            route = (airport(flight.get('departureAirport')), airport(flight.get('arrivalAirport')))
            if route == (search.origin, search.destination):
                leg = 0
            elif search.return_date and route == (search.destination, search.origin):
                leg = 1
            else:
                continue
            if search.direct and flight.get('isNonstop') is not True:
                continue
            if not flight.get('flightNumber') or not flight.get('departureTime'):
                continue
            segment = {'leg': leg, 'origin': route[0], 'destination': route[1],
                       'departure': flight['departureTime'], 'arrival': flight.get('arrivalTime'),
                       'flight': flight['flightNumber'], 'operator': flight.get('provider', {}).get('name'),
                       'nonstop': flight.get('isNonstop')}
            groups.setdefault(url, {})[leg] = (euros(offer.get('price')), segment)
        result = []
        for url, legs in groups.items():
            if set(legs) != ({0, 1} if search.return_date else {0}):
                continue
            price = legs[0][0]
            if price is not None and (1 not in legs or legs[1][0] in (None, price)):
                result.append((price, [legs[i][1] for i in sorted(legs)], url))
        return result if seen else None


class RumboWeb(RoutePage):
    name, seller = 'rumbo-web', 'Rumbo'
    route_url = 'https://www.rumbo.es/vuelos/r_{origin}--{destination}'

    def extract(self, html, search):
        seen = False
        results = {}
        for marker in re.finditer(r'\{\s*"airlineLogo"\s*:', html):
            try:
                row, _ = DECODER.raw_decode(html, marker.start())
            except ValueError:
                continue
            data = row.get('customData')
            if row.get('brand') != 'rumbo' or not isinstance(data, dict):
                continue
            seen = True
            if (row.get('departure', {}).get('airportCode'), row.get('arrival', {}).get('airportCode'),
                data.get('departureDate'), row.get('withReturnFlight')) != (
                    search.origin, search.destination, search.departure, bool(search.return_date)):
                continue
            if search.return_date and data.get('arrivalDate') != search.return_date:
                continue
            fare = data.get('price', {})
            price = euros(fare.get('amount')) if fare.get('currency') == 'EUR' else None
            if price is None:
                continue
            schedule = [(search.origin, search.destination, search.departure, row.get('departureInfo', {}))]
            if search.return_date:
                schedule.append((search.destination, search.origin, search.return_date, row.get('arrivalInfo', {})))
            if search.direct and any(info.get('stops') != 0 for _, _, _, info in schedule):
                continue
            legs = []
            for i, (origin, destination, day, info) in enumerate(schedule):
                takeoff = info.get('takeoff')
                airline = next(iter(info.get('airlinesInfo', [])), {})
                legs.append({'leg': i, 'origin': origin, 'destination': destination,
                             'departure': f'{day}T{takeoff}:00' if takeoff else day,
                             'operator': airline.get('name'), 'stops': info.get('stops')})
            key = (price, tuple((leg['departure'], leg['operator'], leg['stops']) for leg in legs))
            results[key] = (price, legs, None)
        return list(results.values()) if seen else None


class RouteMinimumWeb(RoutePage):
    scope = 'indicative_route_minimum'

    def extract(self, html, search):
        for node in structured_nodes(html):
            name = node.get('name', '')
            if str(node.get('@type', '')).lower() != 'product' or not isinstance(name, str):
                continue
            if not all(city.casefold() in name.casefold() for city in (CITIES[search.origin], CITIES[search.destination])):
                continue
            offer = node.get('offers')
            if not isinstance(offer, dict) or offer.get('@type') != 'AggregateOffer' or offer.get('priceCurrency') != 'EUR':
                continue
            price = euros(offer.get('lowPrice'))
            return [(price, [], None)] if price is not None else []
        return None


class LiligoWeb(RouteMinimumWeb):
    name, seller = 'liligo-web', 'Liligo'
    route_url = 'https://www.liligo.es/vuelos/rutas/{origin}/{destination}'


class KayakWeb(RouteMinimumWeb):
    name, seller = 'kayak-web', 'KAYAK'
    lowercase_path = False

    def search(self, search):
        airport_slugs = {'MAD': 'Madrid-Adolfo-Suarez-Madrid-Barajas-MAD', 'BCN': 'Barcelona-El-Prat-BCN'}
        self.route_url = f'https://www.kayak.es/vuelos/{airport_slugs[search.origin]}/{airport_slugs[search.destination]}'
        return super().search(search)


class MomondoWeb(RouteMinimumWeb):
    name, seller = 'momondo-web', 'momondo'

    def search(self, search):
        paths = {'MAD': 'madrid/aeropuerto-de-barcelona-el-prat-bcn',
                 'BCN': 'aeropuerto-de-barcelona-el-prat-bcn/madrid'}
        self.route_url = 'https://www.momondo.es/vuelos/' + paths[search.origin]
        return super().search(search)


class WegoWeb(RoutePage):
    name, seller = 'wego-web', 'Wego'
    scope = 'indicative_historical_dated_reference'

    def search(self, search):
        paths = {
            'MAD': 'mad/bcn/vuelos-mas-baratos-desde-madrid-a-barcelona-649',
            'BCN': 'bcn/mad/vuelos-mas-baratos-desde-barcelona-649-a-madrid',
        }
        self.route_url = 'https://www.wego.com.es/vuelos/' + paths[search.origin]
        return super().search(search)

    def extract(self, html, search):
        chunks = []
        for marker in re.finditer(r'self\.__next_f\.push\(\s*(?=\[)', html):
            try:
                chunk, _ = DECODER.raw_decode(html, marker.end())
            except ValueError:
                continue
            if len(chunk) > 1 and chunk[0] == 1 and isinstance(chunk[1], str):
                chunks.append(chunk[1])
        data = ''.join(chunks)
        if set(re.findall(r'"currentCurrencyCode"\s*:\s*"([A-Z]{3})"', data)) != {'EUR'}:
            return None
        route_prefix = f'{search.origin}-{search.destination}-'
        prices = set()
        seen = False
        for marker in re.finditer(r'\{\s*"id"\s*:\s*"' + route_prefix, data):
            try:
                row, _ = DECODER.raw_decode(data, marker.start())
            except ValueError:
                continue
            if row.get('fareType') != 'historical':
                continue
            seen = True
            if (row.get('departureCityCode'), row.get('arrivalCityCode'), row.get('departureDate'),
                row.get('returnDate') or None, row.get('cabinClass'), row.get('tripType')) != (
                    search.origin, search.destination, search.departure, search.return_date,
                    'economy', 'roundtrip' if search.return_date else 'oneway'):
                continue
            if search.direct and row.get('stopsCount') != 0:
                continue
            price = euros(row.get('price'))
            if price is not None:
                prices.add(price)
        return [(price, [], None) for price in sorted(prices)] if seen else None
