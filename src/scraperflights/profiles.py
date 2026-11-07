"""Fixed browser profiles for controlled comparisons."""
from dataclasses import dataclass

USER_AGENTS = {
    'desktop': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'mobile': 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
}


@dataclass(frozen=True)
class WebProfile:
    device: str = 'desktop'
    locale: str = 'es-ES'
    session: str = 'fresh'

    def headers(self):
        return {'User-Agent': USER_AGENTS[self.device], 'Accept-Language': self.locale}

    def browser_options(self):
        mobile = self.device == 'mobile'
        return {'locale': self.locale, 'user_agent': USER_AGENTS[self.device],
                'viewport': {'width': 393, 'height': 851} if mobile else {'width': 1440, 'height': 900},
                'is_mobile': mobile, 'has_touch': mobile, 'device_scale_factor': 2 if mobile else 1}
