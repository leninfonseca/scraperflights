"""Public Vueling route calendar. Monthly minima are indicative."""
import gzip
import re
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from ...core import Offer
from ...http import ProviderError

MONTHS = dict(zip(
    'jan feb mar apr may jun jul aug sep oct nov dec'.split(), range(1, 13)))
MONTHS.update(ene=1, abr=4, ago=8, dic=12)
MONTH_PRICE = re.compile(
    r'\b([a-z]{3})\.?\s+(20\d\d)\s+Desde\s+(\d+(?:[,.]\d{1,2})?)\s*(?:EUR|€)\s*\*?'
    r'\s+(?:Visto\s+hace\s+.{1,80}?\s+)?Solo\s+ida\b', re.I)
MAX_HTML = 5_000_000


# Compatibility name retained for existing callers.
from .html import Document as VisibleText, amount


class VuelingWeb:
    name = 'vueling-web'
    readiness_error = 'unavailable'

    def __init__(self, client):
        self.client = client

    def ready(self):
        return True

    def fetch(self, url):
        profile = self.client.profile
        cache = getattr(self.client, '_html_cache', {})
        if profile is None and url in cache:
            html, metadata = cache[url]
            self.fetch_diagnostics = metadata | {'cache_hit': True}
            return html
        headers = profile.headers() if profile else {
            'User-Agent': 'scraperflights/0.1', 'Accept-Language': 'es-ES'}
        request = Request(url, headers=headers)
        warm = profile is not None and profile.session == 'warm'
        opener = build_opener(HTTPCookieProcessor(CookieJar())).open if profile else urlopen
        started = time.monotonic()
        self.fetch_diagnostics = {'cache_hit': False}

        def open_page():
            if self.client.calls >= self.client.budget:
                raise ProviderError('request_budget_exhausted')
            self.client.calls += 1
            return opener(request, timeout=self.client.timeout)

        def read_page(response):
            if response.headers.get('cf-mitigated') == 'challenge':
                raise ProviderError('web_access_blocked')
            content_type = response.headers.get_content_type()
            if content_type not in ('text/html', 'application/xhtml+xml'):
                raise ProviderError('web_unexpected_content_type')
            encoding = response.headers.get('Content-Encoding', '').lower()
            if encoding not in ('', 'identity', 'gzip'):
                raise ProviderError('web_unsupported_encoding')
            stream = gzip.GzipFile(fileobj=response) if encoding == 'gzip' else response
            content = stream.read(MAX_HTML + 1)
            if len(content) > MAX_HTML:
                raise ProviderError('web_page_too_large')
            charset = response.headers.get_content_charset() or 'utf-8'
            try:
                html = content.decode(charset)
            except (UnicodeError, LookupError):
                # Legacy Spanish pages commonly omit their Windows-1252 charset.
                charset = 'windows-1252'
                html = content.decode('cp1252', errors='replace')
            text = html.casefold()
            if 'cf_chl_' in text or 'just a moment...' in text or '<title>access denied' in text:
                raise ProviderError('web_access_blocked')
            self.fetch_diagnostics.update(http_status=getattr(response, 'status', 200),
                bytes=len(content), charset=charset, content_type=content_type)
            return html

        try:
            if warm:
                with open_page() as response:
                    read_page(response)
            with open_page() as response:
                html = read_page(response)
        except HTTPError as exc:
            self.fetch_diagnostics['http_status'] = exc.code
            raise ProviderError(f'http_{exc.code}') from None
        except (URLError, TimeoutError, OSError, EOFError):
            raise ProviderError('web_network_error') from None
        finally:
            self.fetch_diagnostics['elapsed_ms'] = round((time.monotonic() - started) * 1000)
        if profile is None and len(cache) < 8:
            cache[url] = (html, dict(self.fetch_diagnostics))
            self.client._html_cache = cache
        return html

    def search(self, search):
        if 'MTY' in (search.origin, search.destination):
            return [], 'unsupported_route'
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
                parsed = amount(price)
                if parsed is not None:
                    prices.append(parsed)
        if not prices:
            return [], 'indicative'
        return [Offer(self.name, f'{search.origin}-{search.destination}-{month}', 'Vueling',
                      [], str(min(prices)), 'EUR', link=url,
                      warnings=['indicative_monthly_minimum', 'exact_flight_not_confirmed'])], 'indicative'

    def refresh(self, offer, search):
        raise ProviderError('revalidation_unsupported')
