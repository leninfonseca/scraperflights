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
from .connectors.web.ground import BlaBlaCarWeb, TrainlineWeb, OmioTrainWeb, OmioBusWeb, ground_links
from .catalog import sources
from .airports import AIRPORTS, destination_for, direct_for
from .profiles import DEVICES
from .experiment import FACTORS, compare_profiles, compare_devices
from .connectors.web.vueling import VuelingWeb
from .connectors.browser.vueling import VuelingBrowser
from .connectors.feeds.file import FileFeed

from .connectors.web.mexico import AeromexicoWeb, LufthansaWeb
from .connectors.web.agency import TripComWeb, RumboWeb, LiligoWeb, KayakWeb, MomondoWeb, WegoWeb
from .connectors.web.routes import IberiaWeb, AirEuropaWeb, KiwiWeb, TrabberWeb

WEB_CONNECTORS = (VuelingWeb, IberiaWeb, AirEuropaWeb, KiwiWeb, TrabberWeb,
                  TripComWeb, RumboWeb, LiligoWeb, KayakWeb, MomondoWeb, WegoWeb, AeromexicoWeb, LufthansaWeb, VuelingBrowser)
DEFAULT_WEB_PROVIDERS = tuple(c.name for c in WEB_CONNECTORS if c is not VuelingBrowser)
GROUND_CONNECTORS = (BlaBlaCarWeb, TrainlineWeb, OmioTrainWeb, OmioBusWeb)
CONNECTORS = (Amadeus, Skyscanner, *WEB_CONNECTORS, *GROUND_CONNECTORS)
MODES = ('flight', 'train', 'bus', 'carpool')


def providers_for(search, modes=MODES):
    providers = list(DEFAULT_WEB_PROVIDERS) if 'flight' in modes else []
    if {search.origin, search.destination} == {'BCN', 'MAD'}:
        providers.extend(c.name for c in GROUND_CONNECTORS if c.transport_mode in modes)
    return providers



def run_search(search, provider_names, sellers, budget=40, top=5, feed=None, profile=None):
    started = now()
    client = Client(budget=budget, profile=profile)
    observations, offers, sources, changes = [], [], [], []
    for cls in (*CONNECTORS, FileFeed):
        if cls.name not in provider_names:
            continue
        provider = cls(feed if cls is FileFeed else client)
        status = {'provider': cls.name, 'started_at': now()}
        sources.append(status)
        if not provider.ready():
            status.update(status=getattr(provider, 'readiness_error', 'credentials_missing'), finished_at=now())
            continue
        try:
            found, complete = provider.search(search)
            observations.extend(o.public() for o in found)
            status.update(status=complete, results=len(found))
            if complete in ('indicative', 'imported', 'unsupported_profile', 'unsupported_route'):
                offers.extend(found)
                status['finished_at'] = now()
                continue
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
    supplemental = [o for o in offers if any(flag in o.warnings for flag in (
        'indicative_monthly_minimum', 'indicative_dated_reference', 'indicative_route_minimum',
        'indicative_historical_dated_reference', 'indicative_leg_reference', 'imported_snapshot'))]
    dated = [o for o in supplemental if 'indicative_dated_reference' in o.warnings and o.transport_mode == 'flight']
    return {'id': str(uuid4()), 'started_at': started, 'finished_at': now(), 'search': asdict(search),
        'sources': sources, 'http_requests': client.calls, 'request_budget': budget,
        'coverage_complete': all(s['status'] == 'complete' for s in sources),
        'winner': accepted[0] if accepted else None, 'ranked': accepted, 'pending': pending,
        'lowest_observed': min((o.public() for o in offers if not o.sandbox and o.provider in ('amadeus', 'skyscanner')), key=lambda o: money(o['amount']), default=None),
        'supplemental_prices': [o.public() for o in supplemental],
        'lowest_dated_reference': min((o.public() for o in dated), key=lambda o: money(o['amount']), default=None),
        'transport_links': ground_links(search),
        'price_changes': changes, 'observations': observations,
        'notice': 'Price observations are not a guarantee of final checkout price or whole-market coverage.'}


def export(run, directory):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (run['id'] + '.json')
    target.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['origin', 'destination', 'departure', 'return_date', 'adults', 'cabin_bags',
              'checked_bags', 'scope', 'transport_mode', 'journey_leg', 'provider', 'seller', 'amount', 'currency', 'total', 'observed_at', 'verified_at', 'link', 'exclusion_reasons']
    with target.with_suffix('.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for offer in run['ranked'] + run['pending']:
            row = run['search'] | offer
            row['scope'] = next((warning for warning in offer.get('warnings', [])
                                 if warning.startswith('indicative_')), 'unclassified')
            # Protect spreadsheet consumers from formula injection.
            writer.writerow({k: ("'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v)
                             for k, v in row.items() if k in fields})
    return target


def main(argv=None):
    p = argparse.ArgumentParser(description='BCN, MAD and MTY: flight observations and history')
    sub = p.add_subparsers(dest='command', required=True)
    catalog = sub.add_parser('sources', help='List candidate sources; does not execute searches')
    catalog.add_argument('--category', choices=['airline', 'agency', 'metasearch', 'distribution', 'rail', 'coach', 'rideshare', 'multimodal'])
    catalog.add_argument('--method', choices=['api', 'web', 'browser', 'feeds'])
    catalog.add_argument('--status', choices=['implemented', 'candidate'])
    sub.add_parser('doctor', help='Show credential availability without exposing values')
    history = sub.add_parser('history')
    history.add_argument('--db', default='data/flights.sqlite')
    history.add_argument('--limit', type=int, default=10)
    compare = sub.add_parser('compare', help='Compare fixed web profiles without flight APIs')
    compare.add_argument('--origin', choices=list(AIRPORTS), default='MAD')
    compare.add_argument('--destination', choices=list(AIRPORTS))
    compare.add_argument('--direct-only', action='store_true')
    compare.add_argument('--date', required=True)
    compare.add_argument('--return-date')
    compare.add_argument('--allow-stops', action='store_true')
    compare.add_argument('--devices', nargs='+', choices=list(DEVICES), help='Named synthetic profiles; enables multi-device experiment')
    compare.add_argument('--baseline', default='desktop', choices=list(DEVICES))
    compare.add_argument('--factor', choices=FACTORS, default='device')
    compare.add_argument('--rounds', type=int, choices=range(1, 6), default=2)
    compare.add_argument('--providers', nargs='+', choices=[c.name for c in WEB_CONNECTORS],
                         default=None)
    compare.add_argument('--output', type=Path, default=Path('output'))
    q = sub.add_parser('search')
    q.add_argument('--origin', choices=list(AIRPORTS), default='MAD')
    q.add_argument('--destination', choices=list(AIRPORTS))
    q.add_argument('--direct-only', action='store_true')
    q.add_argument('--date', required=True)
    q.add_argument('--return-date')
    q.add_argument('--both-directions', action='store_true', help='Independent searches, not a return ticket')
    q.add_argument('--flex-days', type=int, default=0, help='Shift outbound; return stays fixed')
    q.add_argument('--adults', type=int, default=1)
    q.add_argument('--cabin-bags', type=int, default=0, help='Required pieces per person')
    q.add_argument('--checked-bags', type=int, default=0, help='Required pieces per person')
    q.add_argument('--allow-stops', action='store_true')
    q.add_argument('--providers', nargs='+', choices=[c.name for c in (*WEB_CONNECTORS, *GROUND_CONNECTORS, FileFeed)])
    q.add_argument('--modes', nargs='+', choices=MODES, default=list(MODES))
    q.add_argument('--feed', type=Path, help='Import a local provider snapshot in JSON or CSV')
    q.add_argument('--budget', type=int, default=40, help='HTTP request limit per search; retries count')
    q.add_argument('--top', type=int, default=5)
    q.add_argument('--sellers', default='config/sellers.json')
    q.add_argument('--db', default='data/flights.sqlite')
    q.add_argument('--output', default='output')
    args = p.parse_args(argv)
    if args.command == 'sources':
        print(json.dumps(sources(args.category, args.method, args.status), ensure_ascii=False, indent=2))
        return 0
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
    if args.command == 'compare':
        try:
            destination = destination_for(args.origin, args.destination)
            search = Search(args.origin, destination, args.date, args.return_date,
                            direct=direct_for(args.origin, destination, args.allow_stops, args.direct_only))
        except ValueError as exc:
            p.error(str(exc))
        try:
            providers = args.providers or list(DEFAULT_WEB_PROVIDERS[:2] if args.devices else DEFAULT_WEB_PROVIDERS)
            report = (compare_devices(search, providers, args.devices, args.rounds, run_search, args.baseline)
                      if args.devices else compare_profiles(search, list(dict.fromkeys(providers)),
                                                            args.factor, args.rounds, run_search))
        except ValueError as exc:
            p.error(str(exc))
        args.output.mkdir(parents=True, exist_ok=True)
        path = args.output / ('comparison-' + report['id'] + '.json')
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        paired = sum(pair['status'] == 'paired' for pair in report['pairs'])
        changed = sum(c['status'] == 'different_minimum' for pair in report['pairs'] for c in pair['comparisons'])
        print(json.dumps({'report': str(path), 'paired': paired, 'pairs': len(report['pairs']),
                          'different_minima': changed}, ensure_ascii=False))
        return 0 if paired else 2
    if not 0 <= args.flex_days <= 7 or not 1 <= args.budget <= 200 or not 1 <= args.top <= 20:
        p.error('flex-days: 0..7; budget: 1..200; top: 1..20')
    try:
        sellers = json.loads(Path(args.sellers).read_text(encoding='utf-8'))
        base = date.fromisoformat(args.date)
        searches = []
        destination = destination_for(args.origin, args.destination)
        routes = [(args.origin, destination)]
        if args.both_directions:
            routes.append((destination, args.origin))
        for shift in range(-args.flex_days, args.flex_days + 1):
            for origin, target in routes:
                searches.append(Search(origin, target,
                    (base + timedelta(days=shift)).isoformat(), args.return_date, args.adults,
                    args.cabin_bags, args.checked_bags,
                    direct_for(origin, target, args.allow_stops, args.direct_only)))
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.db)
    selected = args.providers or []
    if {'vueling-web', 'vueling-browser'} <= set(selected):
        p.error('choose one Vueling method per search')
    if FileFeed.name in selected and not args.feed:
        p.error('file-feed requires --feed')

    any_response = False
    for search in searches:
        selected = list(args.providers) if args.providers is not None else providers_for(search, args.modes)
        if args.feed and FileFeed.name not in selected:
            selected.append(FileFeed.name)
        run = run_search(search, selected, sellers, args.budget, args.top, args.feed)
        store.save(run)
        path = export(run, Path(args.output))
        any_response |= any(s['status'] in ('complete', 'partial', 'indicative', 'imported') for s in run['sources'])
        print(json.dumps({'search': run['search'], 'sources': run['sources'],
            'winner': run['winner'], 'lowest_dated_reference': run['lowest_dated_reference'], 'supplemental_prices': run['supplemental_prices'], 'lowest_observed': run['lowest_observed'], 'pending_offers': len(run['pending']), 'report': str(path)}, ensure_ascii=False))
    return 0 if any_response else 2


if __name__ == '__main__':
    raise SystemExit(main())
