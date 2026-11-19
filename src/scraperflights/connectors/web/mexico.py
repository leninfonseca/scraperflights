"""Public airline references for travel between Spain and Monterrey."""
from .routes import AirEuropaWeb, RoutePage, CITIES
from .agency import euros, structured_nodes


class AeromexicoWeb(AirEuropaWeb):
    name, seller = 'aeromexico-web', 'Aeroméxico'
    supports_mty = True
    route_url = 'https://www.aeromexico.com/es_es/vuelos-desde-{origin}-a-{destination}'

    def search(self, search):
        if 'MTY' not in (search.origin, search.destination):
            return [], 'unsupported_route'
        return super().search(search)


class LufthansaWeb(RoutePage):
    name, seller = 'lufthansa-web', 'Lufthansa'
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
            if row.get('@type') != 'Product' or row.get('brand', {}).get('name') != 'Lufthansa':
                continue
            name = row.get('name', '').casefold()
            if not all(CITIES[code].casefold() in name for code in (search.origin, search.destination)):
                continue
            seen = True
            offer = row.get('offers', {})
            if offer.get('@type') != 'Offer' or offer.get('priceCurrency') != 'EUR':
                continue
            price = euros(offer.get('price'))
            if price is not None:
                results.append((price, [], None))
        return results if seen else None
