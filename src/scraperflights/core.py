from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import sqlite3


def now():
    return datetime.now(timezone.utc).isoformat()


def money(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid price')
    return result


@dataclass(frozen=True)
class Search:
    origin: str
    destination: str
    departure: str
    return_date: str | None = None
    adults: int = 1
    cabin_bags: int = 0
    checked_bags: int = 0
    direct: bool = True
    currency: str = 'EUR'

    def __post_init__(self):
        if {self.origin, self.destination} != {'MAD', 'BCN'}:
            raise ValueError('Only MAD ↔ BCN is supported')
        dep = date.fromisoformat(self.departure)
        if dep < datetime.now(timezone.utc).date():
            raise ValueError('Departure is in the past')
        if self.return_date and date.fromisoformat(self.return_date) < dep:
            raise ValueError('Return precedes departure')
        if not 1 <= self.adults <= 9 or min(self.cabin_bags, self.checked_bags) < 0:
            raise ValueError('Invalid traveler/baggage counts')
        if self.currency != 'EUR':
            raise ValueError('Initial implementation compares EUR only')


@dataclass
class Offer:
    provider: str
    reference: str
    seller: str
    segments: list[dict]
    amount: str
    currency: str
    observed_at: str = field(default_factory=now)
    verified_at: str | None = None
    total: str | None = None
    warnings: list[str] = field(default_factory=list)
    link: str | None = None
    sandbox: bool = False
    baggage: dict = field(default_factory=dict)
    # Provider payload is ephemeral, never exported or persisted.
    raw: dict = field(default_factory=dict, repr=False)

    def public(self):
        return {k: v for k, v in asdict(self).items() if k != 'raw'}

    def key(self):
        return hashlib.sha256(json.dumps([self.provider, self.reference, self.seller,
            self.segments, self.baggage], sort_keys=True).encode()).hexdigest()


def eligible(offer, search, sellers, ttl=300):
    reasons = list(offer.warnings)
    if offer.sandbox:
        reasons.append('sandbox')
    review = sellers.get(offer.seller, {})
    if review.get('status') != 'approved':
        reasons.append('seller_reputation_unapproved')
    else:
        try:
            age = (date.today() - date.fromisoformat(review['reviewed_at'])).days
            if not 0 <= age <= 90 or not review.get('evidence_url'):
                reasons.append('seller_review_expired')
        except (ValueError, KeyError):
            reasons.append('seller_review_missing')
    if offer.total is None:
        reasons.append('total_incomplete')
    if not offer.verified_at or (datetime.now(timezone.utc) - datetime.fromisoformat(offer.verified_at)).total_seconds() > ttl:
        reasons.append('not_freshly_revalidated')
    if offer.currency != search.currency:
        reasons.append('currency_mismatch')
    return sorted(set(reasons))


def rank(offers, search, sellers):
    unique = {o.key(): o for o in offers}
    accepted, pending = [], []
    for o in unique.values():
        reasons = eligible(o, search, sellers)
        item = o.public() | {'exclusion_reasons': reasons}
        (pending if reasons else accepted).append(item)
    accepted.sort(key=lambda x: (money(x['total']), x['seller']))
    pending.sort(key=lambda x: money(x['amount']))
    return accepted, pending


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS observations (run_id TEXT, ordinal INTEGER, payload TEXT, PRIMARY KEY(run_id,ordinal))')

    def save(self, run):
        with self.db:
            self.db.execute('INSERT INTO runs VALUES (?,?)', (run['id'], json.dumps(run)))
            for i, o in enumerate(run['observations']):
                self.db.execute('INSERT INTO observations VALUES (?,?,?)', (run['id'], i, json.dumps(o)))

    def history(self, limit=20):
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM runs ORDER BY rowid DESC LIMIT ?', (limit,))]
