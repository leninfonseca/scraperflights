from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from .catalog import CITIES


@dataclass(frozen=True)
class LodgingSearch:
    destination: str
    checkin: str
    checkout: str
    adults: int = 1
    rooms: int = 1

    def __post_init__(self):
        if not isinstance(self.destination,str) or self.destination not in CITIES:
            raise ValueError('Destino de alojamiento: BCN, MAD o MTY.')
        for value in (self.checkin,self.checkout):
            if not isinstance(value,str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError('Indica fechas de entrada y salida en formato YYYY-MM-DD.')
        if date.fromisoformat(self.checkin) < datetime.now(ZoneInfo('Europe/Madrid')).date() or self.checkout <= self.checkin:
            raise ValueError('La entrada debe ser futura y la salida posterior a la entrada.')
        if self.nights > 90:
            raise ValueError('Máximo 90 noches por búsqueda.')
        if type(self.adults) is not int or not 1 <= self.adults <= 9 or type(self.rooms) is not int or not 1 <= self.rooms <= self.adults:
            raise ValueError('Indica 1–9 adultos y entre 1 habitación y el número de adultos.')

    @property
    def nights(self):
        return (date.fromisoformat(self.checkout)-date.fromisoformat(self.checkin)).days
