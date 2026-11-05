"""Shared structural contract for future web, browser and feed adapters."""
from typing import Protocol
from ..core import Offer, Search


class Connector(Protocol):
    name: str

    def ready(self) -> bool: ...

    def search(self, search: Search) -> tuple[list[Offer], str]: ...

    def refresh(self, offer: Offer, search: Search) -> Offer | None: ...
