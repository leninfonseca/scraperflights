"""Compatibility imports; API implementations live in connectors/api."""
from .connectors.api.providers import Amadeus, Skyscanner, sky_price, sky_time

__all__ = ['Amadeus', 'Skyscanner', 'sky_price', 'sky_time']
