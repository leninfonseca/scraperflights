from datetime import date,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
from scraperflights.lodging.models import LodgingSearch
from scraperflights.lodging.catalog import catalog, search_url
from scraperflights.lodging.extract import html_properties
from scraperflights.lodging.service import run_lodging, export_lodging, search_from_payload
from scraperflights.analysis.imports import report_rows
from scraperflights.http import ProviderError


def page(value):
    return '<script type="application/ld+json">'+json.dumps(value)+'</script>'


class LodgingTests(TestCase):
    def setUp(self):
        day=date.today()+timedelta(days=30)
        self.search=LodgingSearch('MTY',day.isoformat(),(day+timedelta(days=5)).isoformat())
        self.hotel={'@type':'Hotel','name':'Hotel de prueba','url':'https://www.booking.com/hotel/mx/test.html',
                    'aggregateRating':{'ratingValue':'8,5','bestRating':10,'reviewCount':25}}

    def test_dates_rooms_and_missing_checkout(self):
        self.assertEqual(self.search.nights,5)
        for change in [{'checkout':None},{'checkout':self.search.checkin},{'adults':True},{'adults':1,'rooms':2},{'destination':[]}]:
            values=vars(self.search)|change
            with self.assertRaises(ValueError):LodgingSearch(**values)
        with self.assertRaises(ValueError):search_from_payload({'destination':'MTY','checkin':self.search.checkin})

    def test_dated_urls_and_manual_directory_are_distinct(self):
        sources=catalog(self.search)
        self.assertEqual(sum(row['method']=='html' for row in sources),5)
        self.assertGreaterEqual(sum(row['method']=='manual' for row in sources),30)
        for row in sources:
            if row['method']=='html':
                self.assertIn(self.search.checkin,row['url']);self.assertIn(self.search.checkout,row['url'])
            else:self.assertFalse(row['dates_in_url'])

    def test_undated_price_is_not_stay_total_or_comparable(self):
        hotel=self.hotel|{'priceRange':'72 €'}
        report=run_lodging(self.search,['booking'],fetch=lambda p,u:page(hotel))
        row=report['observations'][0]
        self.assertEqual(row['amount'],'72');self.assertEqual(row['price_basis'],'unknown')
        self.assertEqual(row['scope'],'undated_reference');self.assertIsNone(report['lowest_comparable_reference'])
        self.assertEqual(row['rating_10'],8.5)
        self.assertEqual(report_rows(report),[])

    def test_only_explicit_dates_occupancy_and_basis_are_comparable(self):
        offer={'@type':'Offer','price':250,'priceCurrency':'EUR','priceBasis':'stay',
               'checkinDate':self.search.checkin,'checkoutDate':self.search.checkout,'adults':1,'rooms':1}
        for change,expected in [({},True),({'rooms':2},False),({'checkoutDate':'2030-01-01'},False),({'priceCurrency':'MXN'},False),({'priceBasis':'night'},False)]:
            hotel=self.hotel|{'offers':offer|change}
            report=run_lodging(self.search,['booking'],fetch=lambda p,u:page(hotel))
            self.assertEqual(bool(report['comparable_stays']),expected)
            self.assertEqual(report['observations'][0]['amount'],'250')

    def test_trip_html_nightly_price_merges_with_schema_rating(self):
        url='https://es.trip.com/hotels/monterrey-hotel-detail-123/test/'
        hotel=self.hotel|{'url':url}
        html=page(hotel)+f'<a href="{url}" class="Template-Grid-Hotel-Cards-hotel-card"><h3>Hotel de prueba</h3><div class="Template-Grid-Hotel-Cards-hotel-price"><span>1 noche</span>72 €</div></a>'
        rows=html_properties(html,'tripcom',self.search,search_url('tripcom',self.search))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['amount'],'72')
        self.assertEqual(rows[0]['price_basis'],'night');self.assertEqual(rows[0]['rating_10'],8.5)
        self.assertIsNone(rows[0]['checkout'])

    def test_no_fake_currency_or_external_script_links(self):
        hotel=self.hotel|{'priceRange':'$72','starRating':{'ratingValue':5},'aggregateRating':{}}
        rows=html_properties(page(hotel),'booking',self.search,search_url('booking',self.search))
        self.assertIsNone(rows[0]['amount']);self.assertIsNone(rows[0]['rating_10'])
        for url in ['javascript:alert(1)','https://attacker.example/hotel','https://user@www.booking.com/hotel']:
            self.assertEqual(html_properties(page(hotel|{'url':url}),'booking',self.search,search_url('booking',self.search)),[])

    def test_source_error_isolated_and_json_csv_export(self):
        def fetch(provider,url):
            if provider=='expedia':raise ProviderError('http_403')
            return page(self.hotel|{'priceRange':'72 €','name':'=unsafe'})
        report=run_lodging(self.search,['booking','expedia'],fetch=fetch)
        self.assertEqual(report['sources'][1]['error'],'http_403')
        self.assertEqual(len(report['observations']),1)
        with TemporaryDirectory() as folder:
            path=export_lodging(report,Path(folder))
            self.assertEqual(json.loads(path.read_text())['kind'],'lodging')
            self.assertIn("'=unsafe",path.with_suffix('.csv').read_text(encoding='utf-8-sig'))
            self.assertIn('requested_checkout',path.with_suffix('.csv').read_text(encoding='utf-8-sig'))

    def test_booking_property_card_does_not_invent_night_or_total(self):
        html='<div data-testid="property-card"><a href="/hotel/mx/test.html"><div data-testid="title">Hotel X</div></a><span data-testid="price-and-discounted-price">1.234,56 €</span></div>'
        row=html_properties(html,'booking',self.search,search_url('booking',self.search))[0]
        self.assertEqual(row['amount'],'1234.56');self.assertEqual(row['price_basis'],'unknown')
        self.assertEqual(row['scope'],'undated_reference')

    def test_dashboard_http_and_cli_preserve_dates(self):
        from functools import partial
        from http.server import ThreadingHTTPServer
        from threading import Lock,Thread
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        from scraperflights.viewer import DashboardHandler
        from scraperflights.cli import main
        from contextlib import redirect_stdout
        from io import StringIO
        report=run_lodging(self.search,['booking'],fetch=lambda p,u:page(self.hotel))
        with TemporaryDirectory() as folder, patch('scraperflights.viewer.run_lodging',return_value=report) as fake:
            handler=partial(DashboardHandler,directory=Path(folder),database=Path(folder)/'db.sqlite',search_lock=Lock())
            with ThreadingHTTPServer(('127.0.0.1',0),handler) as server:
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                base=f'http://127.0.0.1:{server.server_port}'
                payload=vars(self.search)|{'providers':['booking']}
                def post(value):
                    return urlopen(Request(base+'/lodging/search',data=json.dumps(value).encode(),headers={'Origin':base,'Content-Type':'application/json'}))
                try:
                    with post(payload) as response:result=json.load(response)
                    self.assertTrue((Path(folder)/result['name']).is_file())
                    self.assertEqual(fake.call_args.args[0],self.search)
                    with self.assertRaises(HTTPError) as error:post(payload|{'checkout':None})
                    self.assertEqual(error.exception.code,400);error.exception.close()
                    with urlopen(base+'/lodging/catalog') as response:self.assertGreater(len(json.load(response)),30)
                finally:server.shutdown();thread.join()
            with patch('scraperflights.cli.run_lodging',return_value=report) as cli,redirect_stdout(StringIO()):
                code=main(['lodging','--destination','MTY','--date',self.search.checkin,'--return-date',self.search.checkout,'--output',folder])
            self.assertEqual(code,0);self.assertEqual(cli.call_args.args[0],self.search)

    def test_editorial_links_outside_city_are_excluded(self):
        html='<a href="https://www.expedia.es/Saltillo-Hoteles-Test.h123.Informacion-Hotel">Hotel Saltillo</a><a href="https://www.expedia.es/Monterrey-Hoteles-Test.h456.Informacion-Hotel">Hotel Monterrey</a>'
        rows=html_properties(html,'expedia',self.search,search_url('expedia',self.search))
        self.assertEqual([row['property'] for row in rows],['Hotel Monterrey'])
