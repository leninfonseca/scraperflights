"""Paired public-price observations with one controlled factor per experiment."""
from dataclasses import asdict, replace
from datetime import datetime
from uuid import uuid4

from .core import money, now
from .profiles import WebProfile

FACTORS = {
    'device': ('desktop', 'mobile'),
    'locale': ('es-ES', 'es-MX'),
    'session': ('fresh', 'warm'),
}
SCOPES = ('indicative_dated_reference', 'indicative_monthly_minimum', 'indicative_route_minimum')


def observations_by_scope(run):
    grouped = {}
    for offer in run['supplemental_prices']:
        for scope in SCOPES:
            if scope in offer['warnings']:
                grouped.setdefault((scope, offer['currency']), []).append(offer)
    return grouped


def compare_runs(a, b):
    left, right = observations_by_scope(a), observations_by_scope(b)
    comparisons = []
    for scope, currency in sorted(left.keys() | right.keys()):
        key = (scope, currency)
        options_a, options_b = left.get(key, []), right.get(key, [])
        first = min(options_a, key=lambda o: money(o['amount']), default=None)
        second = min(options_b, key=lambda o: money(o['amount']), default=None)
        delta = None
        gap = None
        if first is not None and second is not None:
            delta = money(second['amount']) - money(first['amount'])
            gap = abs((datetime.fromisoformat(second['observed_at'])
                       - datetime.fromisoformat(first['observed_at'])).total_seconds())
        comparisons.append({
            'scope': scope, 'currency': currency, 'a_minimum': first, 'b_minimum': second,
            'a_observation_count': len(options_a), 'b_observation_count': len(options_b),
            'status': ('unpaired' if delta is None else 'same_minimum' if delta == 0 else 'different_minimum'),
            'delta_b_minus_a': str(delta) if delta is not None else None,
            'observation_gap_seconds': gap,
        })
    return comparisons


def compare_profiles(search, providers, factor, rounds, run_search):
    started = now()
    profiles = {label: replace(WebProfile(), **{factor: value})
                for label, value in zip(('a', 'b'), FACTORS[factor])}
    pairs = []
    for index in range(rounds):
        order = ['a', 'b'] if index % 2 == 0 else ['b', 'a']
        for provider in providers:
            runs = {}
            for label in order:
                runs[label] = run_search(search, [provider], {}, budget=2, profile=profiles[label])
            comparisons = compare_runs(runs['a'], runs['b'])
            pairs.append({'round': index + 1, 'provider': provider, 'order': order,
                          'runs': runs, 'comparisons': comparisons,
                          'status': 'paired' if any(c['delta_b_minus_a'] is not None for c in comparisons)
                          else 'no_comparable_observations'})
    return {'id': str(uuid4()), 'factor': factor, 'search': asdict(search),
            'started_at': started, 'finished_at': now(),
            'profiles': {label: asdict(profile) | {'http_headers': profile.headers()}
                         for label, profile in profiles.items()},
            'pairs': pairs,
            'notice': 'Compares public minima by scope. Matching dates do not prove identical flights, fares, or checkout prices. Differences do not establish causation.'}
