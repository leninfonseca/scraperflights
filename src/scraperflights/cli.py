import argparse
import csv
import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
from .core import Search, Store, now, rank, money
from .http import Client, ProviderError
from .providers import Amadeus, Skyscanner


def run_search(search, provider_names, sellers, budget=40, top=5):
    started = now()
    client = Client(budget=budget)
    observations, offers, sources, changes = [], [], [], []
    for cls in (Amadeus, Skyscanner):
        if cls.name not in provider_names:
            continue
        provider = cls(client)
        status = {'provider': cls.name, 'started_at': now()}
        sources.append(status)
        if not provider.ready():
            status.update(status='credentials_missing', finished_at=now())
            continue
        try:
            found, complete = provider.search(search)
            observations.extend(o.public() for o in found)
            status.update(status=complete, results=len(found))
            # Cheapest candidates first, then replacements until budget is consumed.
            found.sort(key=lambda o: money(o.amount))
            refreshed_count = 0
            for o in found:
                if refreshed_count >= top:
                    offers.append(o)
                    continue
                try:
                    updated = provider.refresh(o, search)
                    if updated is None:
                        changes.append({'reference': o.reference, 'provider': cls.name, 'status': 'unavailable'})
                        continue
                    delta = money(updated.amount) - money(o.amount)
                    changes.append({'reference': o.reference, 'provider': cls.name, 'status': 'changed' if delta else 'unchanged',
                        'old_amount': o.amount, 'new_amount': updated.amount, 'delta': str(delta),
                        'checked_at': updated.verified_at})
                    observations.append(updated.public())
                    offers.append(updated)
                    refreshed_count += 1
                except (ProviderError, ValueError, KeyError, TypeError, OverflowError):
                    o.warnings.append('revalidation_failed')
                    offers.append(o)
                    status['revalidation_partial'] = True
            status['refreshed'] = refreshed_count
        except (ProviderError, ValueError, KeyError, TypeError, OverflowError) as exc:
            # Never log response payload, URLs, tokens or credentials.
            status.update(status='error', error=str(exc) if isinstance(exc, ProviderError) else 'schema_validation_failed')
        status['finished_at'] = now()
    accepted, pending = rank(offers, search, sellers)
    return {'id': str(uuid4()), 'started_at': started, 'finished_at': now(), 'search': asdict(search),
        'sources': sources, 'http_requests': client.calls, 'request_budget': budget,
        'coverage_complete': all(s['status'] == 'complete' for s in sources),
        'winner': accepted[0] if accepted else None, 'ranked': accepted, 'pending': pending,
        'lowest_observed': min((o.public() for o in offers if not o.sandbox), key=lambda o: money(o['amount']), default=None),
        'price_changes': changes, 'observations': observations,
        'notice': 'API observations are not a guarantee of final checkout price or whole-market coverage.'}


def export(run, directory):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (run['id'] + '.json')
    target.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['provider', 'seller', 'amount', 'currency', 'total', 'observed_at', 'verified_at', 'link', 'exclusion_reasons']
    with target.with_suffix('.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in run['ranked'] + run['pending']:
            # Protect spreadsheet consumers from formula injection.
            writer.writerow({k: ("'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v)
                             for k, v in row.items() if k in fields})
    return target


def main(argv=None):
    p = argparse.ArgumentParser(description='MAD ↔ BCN: live API flight observations, repricing and history')
    sub = p.add_subparsers(dest='command', required=True)
    check = sub.add_parser('doctor', help='Show credential availability without exposing values')
    history = sub.add_parser('history')
    history.add_argument('--db', default='data/flights.sqlite')
    history.add_argument('--limit', type=int, default=10)
    q = sub.add_parser('search')
    q.add_argument('--origin', choices=['MAD', 'BCN'], default='MAD')
    q.add_argument('--date', required=True)
    q.add_argument('--return-date')
    q.add_argument('--both-directions', action='store_true', help='Independent searches, not a return ticket')
    q.add_argument('--flex-days', type=int, default=0, help='Shift outbound; return stays fixed')
    q.add_argument('--adults', type=int, default=1)
    q.add_argument('--cabin-bags', type=int, default=0, help='Required pieces per person')
    q.add_argument('--checked-bags', type=int, default=0, help='Required pieces per person')
    q.add_argument('--allow-stops', action='store_true')
    q.add_argument('--providers', nargs='+', choices=['amadeus', 'skyscanner'], default=['amadeus', 'skyscanner'])
    q.add_argument('--budget', type=int, default=40, help='HTTP request limit per search; retries count')
    q.add_argument('--top', type=int, default=5)
    q.add_argument('--sellers', default='config/sellers.json')
    q.add_argument('--db', default='data/flights.sqlite')
    q.add_argument('--output', default='output')
    args = p.parse_args(argv)
    if args.command == 'doctor':
        print(json.dumps({c.name: 'configured' if c(Client()).ready() else 'credentials_missing'
                          for c in (Amadeus, Skyscanner)}, indent=2))
        return 0
    if args.command == 'history':
        if not Path(args.db).exists():
            print('[]')
            return 0
        print(json.dumps(Store(args.db).history(max(1, min(args.limit, 100))), ensure_ascii=False, indent=2))
        return 0
    if not 0 <= args.flex_days <= 7 or not 1 <= args.budget <= 200 or not 1 <= args.top <= 20:
        p.error('flex-days: 0..7; budget: 1..200; top: 1..20')
    try:
        sellers = json.loads(Path(args.sellers).read_text(encoding='utf-8'))
        base = date.fromisoformat(args.date)
        searches = []
        for shift in range(-args.flex_days, args.flex_days + 1):
            for origin in ([args.origin, 'BCN' if args.origin == 'MAD' else 'MAD'] if args.both_directions else [args.origin]):
                searches.append(Search(origin, 'BCN' if origin == 'MAD' else 'MAD',
                    (base + timedelta(days=shift)).isoformat(), args.return_date, args.adults,
                    args.cabin_bags, args.checked_bags, not args.allow_stops))
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.db)
    any_response = False
    for search in searches:
        run = run_search(search, args.providers, sellers, args.budget, args.top)
        store.save(run)
        path = export(run, Path(args.output))
        any_response |= any(s['status'] in ('complete', 'partial') for s in run['sources'])
        print(json.dumps({'search': run['search'], 'sources': run['sources'],
            'winner': run['winner'], 'lowest_observed': run['lowest_observed'], 'pending_offers': len(run['pending']), 'report': str(path)}, ensure_ascii=False))
    return 0 if any_response else 2


if __name__ == '__main__':
    raise SystemExit(main())
