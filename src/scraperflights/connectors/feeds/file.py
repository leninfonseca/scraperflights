"""Import provider-supplied snapshots from local JSON or CSV files."""
from csv import DictReader
from dataclasses import asdict
from datetime import datetime, timezone
import json

from ...core import Offer, money
from ...http import ProviderError


class FileFeed:
    name = 'file-feed'

    def __init__(self, path):
        self.path = path

    def ready(self):
        return self.path is not None

    def search(self, search):
        try:
            with self.path.open(encoding='utf-8-sig', newline='') as file:
                if self.path.suffix.lower() == '.csv':
                    rows = [
                        dict(row, search=json.loads(row['search']), segments=json.loads(row['segments']))
                        for row in DictReader(file)
                    ]
                elif self.path.suffix.lower() == '.json':
                    rows = json.load(file)
                else:
                    raise ProviderError('feed_extension_unsupported')
        except OSError:
            raise ProviderError('feed_read_error') from None
        if not isinstance(rows, list):
            raise ProviderError('feed_expected_array')
        results = []
        profile = asdict(search)
        for row in rows:
            if row['search'] != profile:
                continue
            if row['currency'] != search.currency or not row['segments']:
                raise ProviderError('feed_invalid_offer')
            legs = [(search.origin, search.destination, search.departure)]
            if search.return_date:
                legs.append((search.destination, search.origin, search.return_date))
            if {segment['leg'] for segment in row['segments']} != set(range(len(legs))):
                raise ProviderError('feed_itinerary_mismatch')
            for leg, (origin, destination, day) in enumerate(legs):
                segments = [segment for segment in row['segments'] if segment['leg'] == leg]
                if (segments[0]['origin'], segments[-1]['destination'],
                        segments[0]['departure'][:10]) != (origin, destination, day):
                    raise ProviderError('feed_itinerary_mismatch')
                if search.direct and len(segments) != 1:
                    raise ProviderError('feed_itinerary_mismatch')
            observed = datetime.fromisoformat(row['observed_at'])
            if observed.tzinfo is None or observed > datetime.now(timezone.utc):
                raise ProviderError('feed_invalid_timestamp')
            results.append(Offer(self.name, row['reference'], row['seller'], row['segments'],
                                 str(money(row['amount'])), row['currency'],
                                 observed_at=observed.astimezone(timezone.utc).isoformat(),
                                 warnings=['imported_snapshot', 'checkout_unverified']))
        return results, 'imported'

    def refresh(self, offer, search):
        raise ProviderError('revalidation_unsupported')
