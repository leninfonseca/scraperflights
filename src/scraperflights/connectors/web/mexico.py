"""Public airline references for travel between Spain and Monterrey."""
from .routes import AirEuropaWeb, RoutePage, CITIES
from .html import amount as euros, structured_nodes, has_type, route_name_matches


class AeromexicoWeb(AirEuropaWeb):
    name, seller = 'aeromexico-web', 'Aeroméxico'
    supports_mty = True
    route_url = 'https://www.aeromexico.com/es_es/vuelos-desde-{origin}-a-{destination}'

    def search(self, search):
        if 'MTY' not in (search.origin, search.destination):
            return [], 'unsupported_route'
        return super().search(search)


class LufthansaGroupWeb(RoutePage):
    brand = 'Lufthansa'
    route_url = 'https://www.lufthansa.com/lhg/es/es/o-d/cy-cy/{origin}-{destination}'
    scope = 'indicative_route_minimum'

    def search(self, search):
        if 'MTY' not in (search.origin, search.destination):
            return [], 'unsupported_route'
        return super().search(search)

    def extract(self, html, search):
        results = []
        seen = False
        for row in structured_nodes(html):
            brand = row.get('brand')
            brand = brand.get('name') if isinstance(brand, dict) else brand
            if not has_type(row, 'Product') or brand != self.brand:
                continue
            name = row.get('name')
            if not isinstance(name, str):
                continue
            name = name.casefold()
            if not route_name_matches(name, CITIES[search.origin], CITIES[search.destination]):
                continue
            seen = True
            offers = row.get('offers')
            for offer in offers if isinstance(offers, list) else [offers]:
                if not isinstance(offer, dict) or not has_type(offer, 'Offer') or offer.get('priceCurrency') != 'EUR':
                    continue
                price = euros(offer.get('price'))
                if price is not None:
                    results.append((price, [], None))
        return results if seen else None


class LufthansaWeb(LufthansaGroupWeb):
    name, seller = 'lufthansa-web', 'Lufthansa'


class SwissWeb(LufthansaGroupWeb):
    name, seller, brand = 'swiss-web', 'SWISS', 'SWISS'
    route_url = 'https://www.swiss.com/lhg/es/es/o-d/cy-cy/{origin}-{destination}'


class BrusselsWeb(LufthansaGroupWeb):
    name, seller, brand = 'brussels-web', 'Brussels Airlines', 'Brussels Airlines'
    route_url = 'https://www.brusselsairlines.com/lhg/es/es/o-d/cy-cy/{origin}-{destination}'
