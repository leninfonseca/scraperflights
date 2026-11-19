"""Airport identifiers, route validation and defaults shared by UI and CLI."""
AIRPORTS = {
    'BCN': {'city': 'Barcelona', 'country': 'spain', 'timezone': 'Europe/Madrid'},
    'MAD': {'city': 'Madrid', 'country': 'spain', 'timezone': 'Europe/Madrid'},
    'MTY': {'city': 'Monterrey', 'country': 'mexico', 'timezone': 'America/Monterrey'},
}


def destination_for(origin, destination=None):
    return destination or ('BCN' if origin == 'MAD' else 'MAD')


def direct_for(origin, destination, allow_stops=False, direct_only=False):
    if direct_only:
        return True
    return not allow_stops and 'MTY' not in (origin, destination)
