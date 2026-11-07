from datetime import date, timedelta
from unittest import TestCase

from scraperflights.core import Search
from scraperflights.experiment import compare_profiles, compare_runs


def run(amount, scope='indicative_dated_reference'):
    return {'supplemental_prices': [{'amount': amount, 'currency': 'EUR',
        'warnings': [scope], 'observed_at': '2026-11-07T12:00:00+00:00'}]}


class ExperimentTests(TestCase):
    def test_order_alternates_and_delta_keeps_profile_direction(self):
        search = Search('MAD', 'BCN', (date.today() + timedelta(days=1)).isoformat())
        calls = []

        def fake_search(search, providers, sellers, budget, profile):
            calls.append((profile.device, profile.locale, profile.session))
            return run('31.20' if profile.device == 'mobile' else '30.10')

        result = compare_profiles(search, ['vueling-web'], 'device', 2, fake_search)
        self.assertEqual([c[0] for c in calls], ['desktop', 'mobile', 'mobile', 'desktop'])
        self.assertEqual({c[1:] for c in calls}, {('es-ES', 'fresh')})
        self.assertEqual([p['comparisons'][0]['delta_b_minus_a'] for p in result['pairs']],
                         ['1.10', '1.10'])

    def test_different_price_scopes_stay_unpaired(self):
        comparisons = compare_runs(run('30'), run('25', 'indicative_monthly_minimum'))
        self.assertEqual(len(comparisons), 2)
        self.assertTrue(all(c['status'] == 'unpaired' and c['delta_b_minus_a'] is None
                            for c in comparisons))
