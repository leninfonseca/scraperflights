import json
import time
import random
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


class ProviderError(Exception):
    pass


class Client:
    def __init__(self, budget=40, timeout=20):
        self.budget, self.timeout, self.calls = budget, timeout, 0

    def request(self, method, url, *, headers=None, data=None, form=None, params=None):
        if params:
            url += '?' + urlencode(params)
        headers = {'User-Agent': 'scraperflights/0.1', **(headers or {})}
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        if form is not None:
            body = urlencode(form).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        for attempt in range(3):
            if self.calls >= self.budget:
                raise ProviderError('request_budget_exhausted')
            self.calls += 1
            try:
                with urlopen(Request(url, data=body, headers=headers, method=method), timeout=self.timeout) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise ProviderError(f'http_{exc.code}') from None
                retry = exc.headers.get('Retry-After', '')
                delay = float(retry) if retry.isdigit() else 2 ** attempt + random.random()
                if delay > 30:
                    raise ProviderError('retry_after_exceeds_wait_budget') from None
                time.sleep(delay)
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise ProviderError('network_error') from None
                time.sleep(2 ** attempt)
            except (ValueError, UnicodeError):
                raise ProviderError('invalid_json') from None
