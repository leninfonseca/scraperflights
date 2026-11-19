"""Public ground-transport references for the Barcelona–Madrid corridor."""
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from ...core import Offer
from .agency import euros, structured_nodes
from .routes import CITIES, RoutePage


class GroundPage(RoutePage):
    def search(self, search):
        if {search.origin, search.destination} != {'BCN', 'MAD'}:
            return [], 'unsupported_route'
        found, status = super().search(search)
        for offer in found:
            offer.transport_mode = self.transport_mode
            offer.journey_leg = 'unspecified'
        return found, status


class BlaBlaCarWeb(GroundPage):
    name, seller = 'blablacar-web', 'BlaBlaCar'
    route_url = 'https://www.blablacar.es/carpool/routes/{origin}/{destination}'
    scope = 'indicative_route_minimum'
    transport_mode = 'carpool'

    def extract(self, html, search):
        for row in structured_nodes(html):
            if row.get('@type') != 'Product':
                continue
            name = row.get('name', '').casefold()
            if 'coche compartido' not in name or not all(CITIES[c].casefold() in name for c in (search.origin, search.destination)):
                continue
            fare = row.get('offers', {})
            if fare.get('@type') == 'AggregateOffer' and fare.get('priceCurrency') == 'EUR':
                price = euros(fare.get('lowPrice'))
                return [(price, [], None)] if price is not None else []
        return None


class TrainlineWeb(GroundPage):
    name, seller = 'trainline-web', 'Trainline'
    route_url = 'https://www.thetrainline.com/es/horarios-trenes/{origin}-a-{destination}'
    scope = 'indicative_route_minimum'
    transport_mode = 'train'

    def extract(self, html, search):
        for row in structured_nodes(html):
            if row.get('@type') != 'Product':
                continue
            name = row.get('name', '').casefold()
            if not all(CITIES[c].casefold() in name for c in (search.origin, search.destination)):
                continue
            fare = row.get('offers', {})
            if fare.get('@type') == 'AggregateOffer' and fare.get('priceCurrency') == 'EUR':
                price = euros(fare.get('lowPrice'))
                return [(price, [], None)] if price is not None else []
        return None


class OmioGround(GroundPage):
    scope = 'indicative_leg_reference'
    route_url = 'https://www.omio.es/viajes/{origin}/{destination}'

    def search(self, search):
        if {search.origin, search.destination} != {'BCN', 'MAD'}:
            return [], 'unsupported_route'
        if search.adults != 1 or search.cabin_bags or search.checked_bags:
            return [], 'unsupported_profile'
        # Published departures are per leg. Preserve return prices as separate observations.
        profiles = [('outbound', replace(search, return_date=None))]
        if search.return_date:
            profiles.append(('return', replace(search, origin=search.destination,
                                               destination=search.origin, departure=search.return_date,
                                               return_date=None)))
        offers = []
        for leg, profile in profiles:
            found, status = super().search(profile)
            for offer in found:
                offer.journey_leg = leg
                offer.reference += '-' + leg
            offers.extend(found)
        return offers, 'indicative'

    def extract(self, html, search):
        results = {}
        seen = False
        for row in structured_nodes(html):
            if row.get('@type') != self.schema_type:
                continue
            action = row.get('potentialAction', {})
            route = (action.get('fromLocation', {}).get('name'), action.get('toLocation', {}).get('name'))
            if route != (CITIES[search.origin], CITIES[search.destination]):
                continue
            seen = True
            try:
                departure = datetime.fromisoformat(row.get('departureTime', ''))
            except ValueError:
                continue
            if departure.tzinfo:
                departure = departure.astimezone(ZoneInfo('Europe/Madrid'))
            if departure.date().isoformat() != search.departure:
                continue
            fare = row.get('offers', {})
            if fare.get('priceCurrency') != 'EUR':
                continue
            price = euros(fare.get('price'))
            if price is None:
                continue
            operator = row.get('provider', {}).get('name')
            stops = [row.get(k, {}).get('name') for k in self.station_keys]
            segment = {'leg': 0, 'origin': search.origin, 'destination': search.destination,
                       'departure': departure.isoformat(), 'arrival': row.get('arrivalTime'),
                       'operator': operator, 'departure_station': stops[0], 'arrival_station': stops[1]}
            key = (departure.isoformat(), operator, tuple(stops), price)
            results[key] = (price, [segment], row.get('url'))
        return list(results.values()) if seen else None


class OmioTrainWeb(OmioGround):
    name, seller = 'omio-train-web', 'Omio · tren'
    transport_mode = 'train'
    schema_type = 'TrainTrip'
    station_keys = ('departureStation', 'arrivalStation')


class OmioBusWeb(OmioGround):
    name, seller = 'omio-bus-web', 'Omio · autobús'
    transport_mode = 'bus'
    schema_type = 'BusTrip'
    station_keys = ('departureBusStop', 'arrivalBusStop')


def ground_links(search):
    if {search.origin, search.destination} != {'BCN', 'MAD'}:
        return []
    cities = [CITIES[c].lower() for c in (search.origin, search.destination)]
    a, b = cities
    return [
        {'name': 'ALSA', 'transport_mode': 'bus', 'url': f'https://www.alsa.es/ruta/{a}-{b}'},
        {'name': 'BlaBlaCar', 'transport_mode': 'carpool', 'url': f'https://www.blablacar.es/carpool/routes/{a}/{b}'},
        {'name': 'Renfe · AVE / Avlo', 'transport_mode': 'train', 'url': 'https://www.renfe.com/es/es'},
        {'name': 'OUIGO', 'transport_mode': 'train', 'url': 'https://www.ouigo.com/es/'},
        {'name': 'iryo', 'transport_mode': 'train', 'url': 'https://iryo.eu/es/'},
        {'name': 'Trainline', 'transport_mode': 'train', 'url': f'https://www.thetrainline.com/es/horarios-trenes/{a}-a-{b}'},
        {'name': 'Omio', 'transport_mode': 'train_bus', 'url': f'https://www.omio.es/viajes/{a}/{b}'},
    ]
