"""Synthetic regression fixtures plus bounded HTTP transport contracts."""
from datetime import date, timedelta
from decimal import Decimal
from email.message import Message
from io import BytesIO
import gzip
import json
from unittest import TestCase
from unittest.mock import patch

from scraperflights.cli import run_search, DEFAULT_WEB_PROVIDERS
from scraperflights.core import Search
from scraperflights.http import Client, ProviderError
from scraperflights.profiles import WebProfile
from scraperflights.connectors.web.html import amount, visible_text, structured_nodes
from scraperflights.connectors.web.routes import AirEuropaWeb, IberiaWeb, KiwiWeb, EUR
from scraperflights.connectors.web.mexico import SwissWeb, BrusselsWeb
from scraperflights.connectors.web.vueling import VuelingWeb


def schema(value):
    return '<SCRIPT data-test="x" TYPE="application/ld+json; charset=utf-8">' + json.dumps(value) + '</SCRIPT>'


class HtmlScrapingTests(TestCase):
    def setUp(self):
        self.search = Search('BCN', 'MTY', (date.today()+timedelta(days=40)).isoformat(), direct=False)

    def test_localized_price_and_rejected_garbage(self):
        for text in ['1.234,56', '1,234.56', '1\u202f234,56', '1234.56']:
            self.assertEqual(amount(text), Decimal('1234.56'))
        self.assertEqual(amount('1.234'), Decimal(1234))
        self.assertEqual(amount(1.234), Decimal('1.234'))
        for text in ['NaN', 'Infinity', '-1', '12..34', '1.2.3', '9999999999999', True, {}, 'USD 15']:
            self.assertIsNone(amount(text))
        self.assertEqual(amount(0), Decimal(0))

    def test_price_text_does_not_include_trailing_day(self):
        self.assertEqual(EUR.search('2027-01-31 123 €')[1], '123')
        self.assertEqual(EUR.search('Desde 1.234,56 €')[1], '1.234,56')

    def test_hidden_descendants_do_not_leak_prices(self):
        html = '<div hidden><span>1 €</span>2 €</div><script>3 €</script><template>4 €</template><p>Desde <b>80 €</b></p>'
        self.assertEqual(visible_text(html), 'Desde 80 €')
        self.assertEqual(visible_text('<div style="display: none"><span>1 €</span></div>99 €'), '99 €')
        self.assertEqual(visible_text('<div aria-hidden="true">1 €</div>99 €'), '99 €')

    def test_json_graph_arrays_types_and_local_references(self):
        product = {'@type':['Thing','Product'], 'name':'Vuelo Barcelona-Monterrey',
                   'brand':{'name':'SWISS'}, 'offers':{'@id':'#fare'}}
        offer = {'@id':'#fare','@type':'Offer','priceCurrency':'EUR','price':'1.234,56'}
        html = schema([{'@graph':[product,offer]}])
        self.assertTrue(any(row.get('offers',{}).get('price') == '1.234,56' for row in structured_nodes(html)))
        with patch.object(SwissWeb,'fetch',return_value=html):
            report = run_search(self.search,['swiss-web'],{})
        self.assertEqual(report['supplemental_prices'][0]['amount'],'1234.56')
        self.assertIsNone(report['lowest_dated_reference'])
        self.assertIsNone(report['winner'])

    def test_new_airlines_currency_direction_brand_and_bad_rows(self):
        for cls,brand in [(SwissWeb,'SWISS'),(BrusselsWeb,'Brussels Airlines')]:
            good = {'@type':'Product','name':'Vuelo Barcelona-Monterrey','brand':{'name':brand},
                    'offers':{'@type':'Offer','priceCurrency':'EUR','price':653}}
            rows = [good | {'brand':None},good | {'name':None},good | {'name':'Vuelo Monterrey-Barcelona'},
                    good | {'offers':{'@type':'Offer','priceCurrency':'MXN','price':1}},
                    good | {'offers':{'@type':'Offer','priceCurrency':'EUR','price':'NaN'}}, good, good]
            with patch.object(cls,'fetch',return_value=schema({'@graph':rows})):
                report = run_search(self.search,[cls.name],{})
            self.assertEqual([r['amount'] for r in report['supplemental_prices']],['653'])
            self.assertIn(cls.name,DEFAULT_WEB_PROVIDERS)

    def test_fare_key_order_and_invalid_neighbor(self):
        search = Search('MAD','BCN',self.search.departure)
        fare = {'totalPrice':'89,95','currencyCode':'EUR','travelClass':'ECONOMY',
                'flightType':'ONE_WAY','originAirportCode':'MAD','destinationAirportCode':'BCN',
                'departureDate':search.departure,'returnDate':None,'__typename':'Fare'}
        html = '<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'fares':[fare|{'totalPrice':'bad'},fare]})+'</script>'
        with patch.object(AirEuropaWeb,'fetch',return_value=html):
            result = run_search(search,['aireuropa-web'],{})
        self.assertEqual(result['lowest_dated_reference']['amount'],'89.95')

    def test_iberia_single_quotes_uppercase_tags_and_thousands(self):
        search = Search('MAD','BCN',self.search.departure)
        html = f"<ARTICLE><div class='cards-block-column--article__content-dates--start'><span class='iata extra'>MAD</span><span class='extra iata'>BCN</span>{search.departure} Solo ida Desde 1.234,56 €</div></ARTICLE>"
        with patch.object(IberiaWeb,'fetch',return_value=html):
            result = run_search(search,['iberia-web'],{})
        self.assertEqual(result['lowest_dated_reference']['amount'],'1234.56')

    def test_malformed_kiwi_shapes_do_not_crash(self):
        parser = KiwiWeb(Client())
        for value in [None,{}, {'itemListElement':[None,{'item':None}]}]:
            self.assertEqual(parser.extract(schema({'@type':'CollectionPage','mainEntity':value}),self.search),[])


class Response(BytesIO):
    def __init__(self, body, content_type='text/html; charset=utf-8', encoding=None):
        super().__init__(body)
        self.status = 200
        self.headers = Message()
        self.headers['Content-Type'] = content_type
        if encoding:
            self.headers['Content-Encoding'] = encoding


class HtmlTransportTests(TestCase):
    def test_declared_charset_and_one_run_cache(self):
        client=Client(); first=VuelingWeb(client); second=VuelingWeb(client)
        with patch('scraperflights.connectors.web.vueling.urlopen',return_value=Response('<p>Avión 30 €</p>'.encode('cp1252'),'text/html; charset=windows-1252')) as fetch:
            self.assertIn('Avión 30 €',first.fetch('https://example.test/route'))
            self.assertEqual(second.fetch('https://example.test/route'),first.fetch('https://example.test/route'))
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(client.calls,1)
        self.assertTrue(second.fetch_diagnostics['cache_hit'])

    def test_profile_experiments_are_not_cached(self):
        parser=VuelingWeb(Client(profile=WebProfile(device='redmi')))
        with patch('scraperflights.connectors.web.vueling.build_opener') as build:
            build.return_value.open.side_effect=[Response(b'<p>100</p>'),Response(b'<p>90</p>')]
            self.assertNotEqual(parser.fetch('https://example.test'),parser.fetch('https://example.test'))
            self.assertEqual(build.return_value.open.call_count,2)

    def test_bounded_gzip_and_wrong_content_types(self):
        parser=VuelingWeb(Client())
        with patch('scraperflights.connectors.web.vueling.urlopen',return_value=Response(gzip.compress(b'<p>'+b'x'*200+b'</p>'),'text/html','gzip')):
            with patch('scraperflights.connectors.web.vueling.MAX_HTML',100):
                with self.assertRaisesRegex(ProviderError,'web_page_too_large'):
                    parser.fetch('https://example.test')
        for content_type,body,expected in [('application/json',b'{}','web_unexpected_content_type'),
                    ('text/html',b'<title>Access Denied</title>','web_access_blocked')]:
            with patch('scraperflights.connectors.web.vueling.urlopen',return_value=Response(body,content_type)):
                with self.assertRaisesRegex(ProviderError,expected):
                    parser.fetch('https://example.test')
