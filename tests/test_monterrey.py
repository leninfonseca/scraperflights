from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch

from scraperflights.airports import destination_for, direct_for
from scraperflights.cli import main, run_search
from scraperflights.core import Search
from scraperflights.connectors.web.routes import KiwiWeb
from scraperflights.http import Client, ProviderError


class MonterreyTests(TestCase):
    def setUp(self):
        self.day = (date.today() + timedelta(days=40)).isoformat()

    def test_routes_and_defaults(self):
        for origin, destination in [('BCN', 'MTY'), ('MTY', 'BCN'), ('MAD', 'MTY'), ('MTY', 'MAD')]:
            search = Search(origin, destination, self.day, direct=direct_for(origin, destination))
            self.assertFalse(search.direct)
            self.assertTrue(direct_for(origin, destination, direct_only=True))
        self.assertEqual(destination_for('MAD'), 'BCN')
        self.assertEqual(destination_for('BCN'), 'MAD')
        with self.assertRaises(ValueError):
            Search('MTY', 'MTY', self.day)

    def test_cli_reverse_routes(self):
        class FakeStore:
            def __init__(self, path): pass
            def save(self, run): pass

        def fake_search(search, *args):
            return {'search': {'origin': search.origin, 'destination': search.destination},
                    'sources': [], 'winner': None, 'lowest_dated_reference': None,
                    'supplemental_prices': [], 'lowest_observed': None, 'pending': []}

        with patch('scraperflights.cli.Store', FakeStore), patch('scraperflights.cli.export', return_value='test.json'), patch('scraperflights.cli.run_search', side_effect=fake_search) as query, patch('builtins.print'):
            main(['search', '--origin', 'BCN', '--destination', 'MTY', '--date', self.day, '--both-directions'])
        self.assertEqual([(c.args[0].origin, c.args[0].destination) for c in query.call_args_list],
                         [('BCN', 'MTY'), ('MTY', 'BCN')])
        self.assertTrue(all(not c.args[0].direct for c in query.call_args_list))

    def test_unsupported_domestic_connectors_do_not_send_requests(self):
        report = run_search(Search('BCN', 'MTY', self.day, direct=False),
                            ['vueling-web', 'aireuropa-web', 'rumbo-web', 'wego-web'], {})
        self.assertEqual(report['http_requests'], 0)
        self.assertTrue(all(s['status'] == 'unsupported_route' for s in report['sources']))

    def test_kiwi_uses_mexico_slug(self):
        connector = KiwiWeb(Client())
        with patch.object(connector, 'fetch', return_value='') as fetch:
            with self.assertRaises(ProviderError):
                connector.search(Search('MTY', 'BCN', self.day, direct=False))
        self.assertEqual(fetch.call_args.args[0],
                         'https://www.kiwi.com/es/cheap-flights/monterrey-mexico/barcelona-spain/')
