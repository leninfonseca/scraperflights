"""Explicit synthetic device signals; these do not reproduce physical hardware."""
from dataclasses import dataclass

CHROME = 'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0'
def android(model, width, height, scale, brand, tier):
    return dict(label=model, brand=brand, tier=tier, mobile=True, width=width, height=height,
                scale=scale, user_agent=f'Mozilla/5.0 (Linux; Android 14; {model}) {CHROME} Mobile Safari/537.36')

DEVICES = {
    'desktop': dict(label='Linux · ordenador de control', brand='Genérico', tier='sin clasificar', mobile=False,
                    width=1440, height=900, scale=1, user_agent=f'Mozilla/5.0 (X11; Linux x86_64) {CHROME} Safari/537.36'),
    'mobile': android('Pixel 7', 393, 851, 2, 'Google', 'referencia'),
    'windows': dict(label='Windows · ordenador genérico', brand='Genérico', tier='sin clasificar', mobile=False,
                    width=1440, height=900, scale=1, user_agent=f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) {CHROME} Safari/537.36'),
    'mac': dict(label='Mac · ordenador Apple', brand='Apple', tier='sin clasificar', mobile=False,
                width=1440, height=900, scale=2, user_agent=f'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) {CHROME} Safari/537.36'),
    'redmi': android('Redmi Note 13', 393, 873, 2.75, 'Xiaomi', 'económica'),
    'galaxy-a': android('SM-A145F', 412, 915, 2.625, 'Samsung', 'económica'),
    'galaxy-s': android('SM-S921B', 360, 780, 3, 'Samsung', 'alta'),
    'iphone': dict(label='iPhone · Safari iOS 17', brand='Apple', tier='alta (hipótesis)', mobile=True,
                   width=393, height=852, scale=3,
                   user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'),
}
USER_AGENTS = {key: row['user_agent'] for key, row in DEVICES.items()}

@dataclass(frozen=True)
class WebProfile:
    device: str = 'desktop'
    locale: str = 'es-ES'
    session: str = 'fresh'

    def __post_init__(self):
        if self.device not in DEVICES or self.locale not in ('es-ES', 'es-MX') or self.session not in ('fresh', 'warm'):
            raise ValueError('Perfil desconocido.')

    def headers(self):
        return {'User-Agent': USER_AGENTS[self.device], 'Accept-Language': self.locale}

    def browser_options(self):
        row = DEVICES[self.device]
        return {'locale': self.locale, 'user_agent': row['user_agent'],
                'viewport': {'width': row['width'], 'height': row['height']},
                'is_mobile': row['mobile'], 'has_touch': row['mobile'], 'device_scale_factor': row['scale']}

    def metadata(self):
        from dataclasses import asdict
        return asdict(self) | DEVICES[self.device] | {'http_headers': self.headers(),
                'simulation': 'synthetic_headers_and_viewport', 'ip_changed': False,
                'engine_note': 'Chromium only for browser connector; iOS Safari is a partial signal simulation.'}
