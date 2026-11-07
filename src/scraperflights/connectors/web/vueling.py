"""Public Vueling route calendar. Monthly minima are indicative."""
import gzip
import re
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from ...core import Offer, money
from ...http import ProviderError

MONTHS = dict(zip(
    'jan feb mar apr may jun jul aug sep oct nov dec'.split(), range(1, 13)))
MONTHS.update(ene=1, abr=4, ago=8, dic=12)
MONTH_PRICE = re.compile(
    r'\b([a-z]{3})\.?\s+(20\d\d)\s+Desde\s+(\d+(?:[,.]\d{1,2})?)\s*(?:EUR|€)\s*\*?'
    r'\s+(?:Visto\s+hace\s+.{1,80}?\s+)?Solo\s+ida\b', re.I)
MAX_HTML = 5_000_000


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = False

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class VuelingWeb:
    name = 'vueling-web'
    readiness_error = 'unavailable'

    def __init__(self, client):
        self.client = client

    def ready(self):
        return True

    def fetch(self, url):
        profile = self.client.profile
        headers = profile.headers() if profile else {
            'User-Agent': 'scraperflights/0.1', 'Accept-Language': 'es-ES'}
        request = Request(url, headers=headers)
        warm = profile is not None and profile.session == 'warm'
        opener = build_opener(HTTPCookieProcessor(CookieJar())).open if profile else urlopen

        def open_page():
            if self.client.calls >= self.client.budget:
                raise ProviderError('request_budget_exhausted')
            self.client.calls += 1
            return opener(request, timeout=self.client.timeout)

        try:
            if warm:
                with open_page() as response:
                    if response.headers.get('cf-mitigated') == 'challenge':
                        raise ProviderError('web_access_blocked')
            with open_page() as response:
                if response.headers.get('cf-mitigated') == 'challenge':
                    raise ProviderError('web_access_blocked')
                stream = (gzip.GzipFile(fileobj=response)
                          if response.headers.get('Content-Encoding') == 'gzip' else response)
                html = stream.read(MAX_HTML + 1)
        except HTTPError as exc:
            raise ProviderError(f'http_{exc.code}') from None
        except (URLError, TimeoutError, OSError, EOFError):
            raise ProviderError('web_network_error') from None
        if len(html) > MAX_HTML:
            raise ProviderError('web_page_too_large')
        return html.decode('utf-8', errors='replace')

    def search(self, search):
        if search.return_date or search.adults != 1 or search.cabin_bags or search.checked_bags:
            return [], 'unsupported_profile'
        cities = {'MAD': 'madrid', 'BCN': 'barcelona'}
        route = f'{cities[search.origin]}-a-{cities[search.destination]}'
        url = f'https://www.vueling.com/es/vuelos-baratos-de-{route}?currency=EUR'
        html = self.fetch(url)
        if 'cf_chl_' in html or 'Just a moment...' in html:
            raise ProviderError('web_access_blocked')
        parser = VisibleText()
        parser.feed(html)
        visible = ' '.join(' '.join(parser.parts).split())
        matches = list(MONTH_PRICE.finditer(visible))
        if not matches:
            raise ProviderError('web_calendar_not_found')
        prices = []
        month = search.departure[:7]
        for match in matches:
            name, year, price = match.groups()
            number = MONTHS.get(name.lower())
            if number and f'{year}-{number:02}' == month:
                prices.append(money(price.replace(',', '.')))
        if not prices:
            return [], 'indicative'
        return [Offer(self.name, f'{search.origin}-{search.destination}-{month}', 'Vueling',
                      [], str(min(prices)), 'EUR', link=url,
                      warnings=['indicative_monthly_minimum', 'exact_flight_not_confirmed'])], 'indicative'

    def refresh(self, offer, search):
        raise ProviderError('revalidation_unsupported')
