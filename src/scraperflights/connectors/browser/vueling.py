"""Read the same public calendar after Chromium renders its JavaScript."""
from importlib.util import find_spec
from pathlib import Path
from shutil import which

from ...http import ProviderError
from ..web.vueling import VuelingWeb


class VuelingBrowser(VuelingWeb):
    name = 'vueling-browser'
    readiness_error = 'playwright_missing'

    def ready(self):
        return find_spec('playwright') is not None

    def fetch(self, url):
        profile = self.client.profile
        warm = profile is not None and profile.session == 'warm'
        if self.client.calls + (2 if warm else 1) > self.client.budget:
            raise ProviderError('request_budget_exhausted')
        from playwright.sync_api import Error, TimeoutError, sync_playwright

        try:
            with sync_playwright() as playwright:
                bundled = Path(playwright.chromium.executable_path)
                system = which('chromium') or which('chromium-browser')
                browser = playwright.chromium.launch(
                    executable_path=system if not bundled.is_file() else None)
                try:
                    options = profile.browser_options() if profile else {'locale': 'es-ES'}
                    page = browser.new_page(**options)
                    timeout = self.client.timeout * 1000
                    for _ in range(2 if warm else 1):
                        self.client.calls += 1
                        response = page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                        if response and response.status >= 400:
                            raise ProviderError(f'http_{response.status}')
                        if response and response.headers.get('cf-mitigated') == 'challenge':
                            raise ProviderError('web_access_blocked')
                    try:
                        page.get_by_text('Solo ida', exact=True).first.wait_for(timeout=timeout)
                    except TimeoutError:
                        pass  # Let the shared parser diagnose challenges or missing calendars.
                    return page.content()
                finally:
                    browser.close()
        except Error:
            raise ProviderError('browser_navigation_or_installation_error') from None
