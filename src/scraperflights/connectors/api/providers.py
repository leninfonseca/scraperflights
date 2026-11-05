"""Official live API adapters. Credentials are read from the environment only."""
import os
import time
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from ...core import Offer, money, now
from ...http import ProviderError


def local(value):
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo('Europe/Madrid')).isoformat()


class Amadeus:
    name = 'amadeus'

    def __init__(self, client):
        self.client = client
        self.sandbox = os.getenv('AMADEUS_ENV', 'production') == 'test'
        self.base = 'https://test.api.amadeus.com' if self.sandbox else 'https://api.amadeus.com'
        self.token = None

    def ready(self):
        return bool(os.getenv('AMADEUS_CLIENT_ID') and os.getenv('AMADEUS_CLIENT_SECRET'))

    def call(self, method, path, **kwargs):
        if not self.token:
            self.token = self.client.request('POST', self.base + '/v1/security/oauth2/token', form={
                'grant_type': 'client_credentials', 'client_id': os.environ['AMADEUS_CLIENT_ID'],
                'client_secret': os.environ['AMADEUS_CLIENT_SECRET']})['access_token']
        return self.client.request(method, self.base + path, headers={'Authorization': 'Bearer ' + self.token}, **kwargs)

    def parse(self, data, search):
        result = []
        for raw in data:
            segments = []
            for leg, itinerary in enumerate(raw['itineraries']):
                if search.direct and len(itinerary['segments']) != 1:
                    break
                for s in itinerary['segments']:
                    segments.append({'leg': leg, 'origin': s['departure']['iataCode'],
                        'destination': s['arrival']['iataCode'], 'departure': local(s['departure']['at']),
                        'arrival': local(s['arrival']['at']), 'flight': s['carrierCode'] + s['number'],
                        'operator': s.get('operating', {}).get('carrierCode', s['carrierCode'])})
            else:
                amount = str(money(raw['price'].get('grandTotal', raw['price']['total'])))
                # Distribution price is not a final agency checkout price.
                o = Offer(self.name, raw['id'], 'Amadeus distribution', segments, amount,
                          raw['price']['currency'], sandbox=self.sandbox, raw=raw,
                          warnings=['final_seller_and_payment_fees_unknown'])
                details = [s for t in raw.get('travelerPricings', []) for s in t.get('fareDetailsBySegment', [])]
                o.baggage = {'fare_details': details}
                if search.cabin_bags or search.checked_bags:
                    o.warnings.append('required_baggage_total_unconfirmed')
                result.append(o)
        return result

    def search(self, s):
        params = dict(originLocationCode=s.origin, destinationLocationCode=s.destination,
            departureDate=s.departure, adults=s.adults, currencyCode=s.currency,
            travelClass='ECONOMY', nonStop=str(s.direct).lower(), max=100)
        if s.return_date:
            params['returnDate'] = s.return_date
        response = self.call('GET', '/v2/shopping/flight-offers', params=params)
        return self.parse(response['data'], s), 'partial' if len(response['data']) >= 100 else 'complete'

    def refresh(self, offer, s):
        response = self.call('POST', '/v1/shopping/flight-offers/pricing', data={
            'data': {'type': 'flight-offers-pricing', 'flightOffers': [offer.raw]}})
        parsed = self.parse(response['data']['flightOffers'], s)
        if not parsed:
            return None
        updated = parsed[0]
        updated.reference = offer.reference
        updated.verified_at = now()
        return updated


def sky_price(price):
    divisor = {'PRICE_UNIT_WHOLE': 1, 'PRICE_UNIT_CENTI': 100, 'PRICE_UNIT_MILLI': 1000,
               'PRICE_UNIT_MICRO': 1000000}.get(price['unit'])
    if divisor is None:
        raise ValueError('Unknown Skyscanner price unit')
    return str(money(price['amount']) / Decimal(divisor))


def sky_time(value):
    return datetime(**{k: value.get(k, 0) for k in ('year', 'month', 'day', 'hour', 'minute', 'second')},
                    tzinfo=ZoneInfo('Europe/Madrid')).isoformat()


class Skyscanner:
    name = 'skyscanner'
    base = 'https://partners.api.skyscanner.net/apiservices/v3/flights/live/'

    def __init__(self, client):
        self.client = client
        self.results = {}
        self.session = None

    def ready(self):
        return bool(os.getenv('SKYSCANNER_API_KEY'))

    def call(self, path, data=None):
        return self.client.request('POST', self.base + path,
            headers={'x-api-key': os.environ['SKYSCANNER_API_KEY']}, data=data or {})

    def merge(self, response):
        for key, values in response.get('content', {}).get('results', {}).items():
            if isinstance(values, dict):
                self.results.setdefault(key, {}).update(values)

    def search(self, s):
        legs = [(s.origin, s.destination, s.departure)]
        if s.return_date:
            legs.append((s.destination, s.origin, s.return_date))
        query = {'market': 'ES', 'locale': 'es-ES', 'currency': s.currency, 'adults': s.adults,
            'cabinClass': 'CABIN_CLASS_ECONOMY', 'queryLegs': [
                {'originPlaceId': {'iata': a}, 'destinationPlaceId': {'iata': b},
                 'date': dict(zip(('year', 'month', 'day'), map(int, d.split('-'))))} for a, b, d in legs]}
        response = self.call('search/create', {'query': query})
        self.session = response['sessionToken']
        self.merge(response)
        for _ in range(8):
            if response.get('status') == 'RESULT_STATUS_COMPLETE':
                break
            time.sleep(1)
            response = self.call('search/poll/' + self.session)
            self.merge(response)
        return self.parse(s), 'complete' if response.get('status') == 'RESULT_STATUS_COMPLETE' else 'partial'

    def parse(self, s, itinerary_filter=None):
        r = self.results
        offers = []
        for iid, itinerary in r.get('itineraries', {}).items():
            if itinerary_filter and iid != itinerary_filter:
                continue
            legs = [r['legs'][i] for i in itinerary['legIds']]
            if s.direct and any(l['stopCount'] for l in legs):
                continue
            segments = []
            for n, leg in enumerate(legs):
                for sid in leg['segmentIds']:
                    seg = r['segments'][sid]
                    carrier = r['carriers'][seg['marketingCarrierId']]
                    segments.append({'leg': n, 'origin': r['places'][seg['originPlaceId']]['iata'],
                        'destination': r['places'][seg['destinationPlaceId']]['iata'],
                        'departure': sky_time(seg['departureDateTime']), 'arrival': sky_time(seg['arrivalDateTime']),
                        'flight': carrier.get('iata', carrier['name']) + seg['marketingFlightNumber'],
                        'operator': r['carriers'][seg['operatingCarrierId']]['name']})
            for option in itinerary.get('pricingOptions', []):
                items = option.get('items', [])
                agent_ids = option.get('agentIds', [])
                seller = ' + '.join(r['agents'][a]['name'] for a in agent_ids)
                amount = sky_price(option['price'])
                warnings = ['final_payment_fees_unknown']
                if len(agent_ids) != 1 or len(items) != 1:
                    warnings.append('multiple_tickets_or_sellers')
                if s.cabin_bags or s.checked_bags:
                    warnings.append('required_baggage_total_unconfirmed')
                offers.append(Offer(self.name, iid + ':' + option.get('id', seller), seller,
                    segments, amount, s.currency, warnings=warnings,
                    link=items[0].get('deepLink') if len(items) == 1 else None,
                    baggage=option.get('pricingOptionFare', {}),
                    raw={'itinerary': iid, 'option': option.get('id'), 'session': self.session}))
        return offers

    def refresh(self, offer, s):
        iid = offer.raw['itinerary']
        response = self.call('itineraryrefresh/create/' + offer.raw['session'], {'itineraryId': iid})
        # Drop old pricing options so absent/removed sellers cannot survive a refresh.
        self.results['itineraries'].pop(iid, None)
        self.merge(response)
        for _ in range(5):
            if response.get('status') == 'RESULT_STATUS_COMPLETE':
                break
            token = response.get('refreshSessionToken')
            if not token:
                raise ProviderError('refresh_session_missing')
            time.sleep(1)
            response = self.call('itineraryrefresh/poll/' + token)
            self.merge(response)
        if response.get('status') != 'RESULT_STATUS_COMPLETE':
            raise ProviderError('refresh_incomplete')
        for updated in self.parse(s, iid):
            if updated.reference == offer.reference:
                updated.verified_at = now()
                return updated
        return None
