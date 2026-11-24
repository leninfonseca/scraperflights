"""Serve the report dashboard and the selected report directory on localhost."""
import argparse
from contextlib import closing
from datetime import date
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
from sqlite3 import Error as DatabaseError
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from .analysis.service import handle as handle_analysis
from .catalog import sources
from .airports import AIRPORTS, destination_for, direct_for
from .cli import MODES, WEB_CONNECTORS, providers_for, export, run_search
from .core import Search, Store
from .profiles import DEVICES
from .experiment import compare_devices
from .lodging.catalog import catalog as lodging_catalog
from .lodging.service import run_lodging, export_lodging, search_from_payload

MAX_REPORT = 32 * 1024 * 1024
REPORT_TYPES = {'.json': 'application/json', '.csv': 'text/csv'}
ASSETS = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
          '/style.css': ('style.css', 'text/css'),
          '/analysis.js': ('analysis.js', 'text/javascript'),
          '/devices.js': ('devices.js', 'text/javascript'),
          '/lodging.js': ('lodging.js', 'text/javascript')}


class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, directory, database=None, search_lock=None, **kwargs):
        self.directory = directory
        self.database = database
        self.search_lock = search_lock
        super().__init__(*args, **kwargs)

    def send_data(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        port = self.server.server_port
        return self.headers.get('Host') in {f'127.0.0.1:{port}', f'localhost:{port}'}

    def send_json(self, value, status=200):
        self.send_data(json.dumps(value, ensure_ascii=False).encode(), 'application/json', status)

    def do_GET(self):
        if not self.valid_host():
            self.send_error(403)
            return
        url = urlsplit(self.path)
        if url.path in ASSETS:
            name, content_type = ASSETS[url.path]
            asset = files('scraperflights').joinpath('dashboard', name)
            self.send_data(asset.read_bytes(), content_type)
        elif url.path == '/lodging/catalog':
            self.send_json(lodging_catalog())
        elif url.path == '/devices':
            self.send_json({'devices': DEVICES, 'providers': [c.name for c in WEB_CONNECTORS]})
        elif url.path == '/catalog':
            self.send_json(sources())
        elif url.path == '/reports':
            reports = []
            if self.directory.is_dir():
                for path in self.directory.iterdir():
                    if path.suffix.lower() not in REPORT_TYPES or path.is_symlink():
                        continue
                    try:
                        if path.is_file():
                            reports.append({'name': path.name, 'modified': path.stat().st_mtime})
                    except OSError:
                        continue
            reports.sort(key=lambda item: (-item['modified'], item['name']))
            self.send_data(json.dumps(reports).encode(), 'application/json')
        elif url.path == '/report':
            name = parse_qs(url.query).get('name', [''])[0]
            path = self.directory / name
            content_type = REPORT_TYPES.get(path.suffix.lower())
            if not content_type or name != path.name or path.is_symlink() or not path.is_file():
                self.send_error(404)
                return
            try:
                with path.open('rb') as report:
                    data = report.read(MAX_REPORT + 1)
            except OSError:
                self.send_error(404)
                return
            if len(data) > MAX_REPORT:
                self.send_error(413)
                return
            self.send_data(data, content_type)
        else:
            self.send_error(404)


    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') != f"http://{self.headers.get('Host')}":
            self.send_json({'error': 'Abre el visor desde su dirección local.'}, 403)
            return
        if self.path == '/lodging/search':
            self.lodging_request()
            return
        if self.path == '/compare-devices':
            self.compare_devices_request()
            return
        if self.path.startswith('/analysis/'):
            if self.headers.get_content_type() != 'application/json':
                self.send_json({'error': 'Formato JSON requerido.'}, 415)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 32 * 1024 * 1024:
                    raise ValueError('La petición supera el límite de 32 MB.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Petición inválida.')
                self.send_json(handle_analysis(self.path, data, self.directory, self.database))
            except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
                self.send_json({'error': str(exc)}, 400)
            return
        if self.path != '/search' or self.search_lock is None:
            self.send_error(404)
            return
        if self.headers.get_content_type() != 'application/json':
            self.send_json({'error': 'Formato de búsqueda inválido.'}, 415)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2048:
                raise ValueError
            profile = json.loads(self.rfile.read(length))
            if not isinstance(profile, dict):
                raise ValueError
            origin = profile.get('origin')
            departure = profile.get('departure')
            return_date = profile.get('return_date')
            if origin not in AIRPORTS or not isinstance(departure, str):
                raise ValueError
            if return_date is not None and not isinstance(return_date, str):
                raise ValueError
            dates = [departure] + ([return_date] if return_date else [])
            if any(date.fromisoformat(value).isoformat() != value for value in dates):
                raise ValueError
            destination = destination_for(origin, profile.get('destination'))
            if destination not in AIRPORTS:
                raise ValueError
            direct_only = profile.get('direct_only', False)
            if not isinstance(direct_only, bool):
                raise ValueError
            modes = profile.get('modes', list(MODES))
            if not isinstance(modes, list) or not modes or any(mode not in MODES for mode in modes):
                raise ValueError
            search = Search(origin, destination, departure, return_date or None,
                            direct=direct_for(origin, destination, direct_only=direct_only))
        except (ValueError, UnicodeError):
            self.send_json({'error': 'Indica una salida válida y, si hay regreso, una fecha igual o posterior.'}, 400)
            return
        if not self.search_lock.acquire(blocking=False):
            self.send_json({'error': 'Ya hay una búsqueda en curso. Espera a que termine.'}, 409)
            return
        try:
            run = run_search(search, providers_for(search, modes), {})
            name = export(run, self.directory).name
            self.database.parent.mkdir(parents=True, exist_ok=True)
            store = Store(self.database)
            with closing(store.db):
                store.save(run)
        except (OSError, DatabaseError):
            self.send_json({'error': 'No se pudo guardar la búsqueda. Revisa la carpeta de salida y el histórico.'}, 500)
            return
        finally:
            self.search_lock.release()
        self.send_json({'name': name})

    def lodging_request(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if self.headers.get_content_type() != 'application/json' or not 0 < length <= 8192:
                raise ValueError('Petición JSON inválida.')
            search,providers=search_from_payload(json.loads(self.rfile.read(length)))
        except (ValueError,TypeError,UnicodeError) as exc:
            self.send_json({'error':str(exc)},400)
            return
        if self.search_lock is None or not self.search_lock.acquire(blocking=False):
            self.send_json({'error':'Ya hay una búsqueda en curso.'},409)
            return
        try:
            report=run_lodging(search,providers)
            path=export_lodging(report,self.directory)
        except OSError:
            self.send_json({'error':'No se pudo guardar el informe de alojamiento.'},500)
            return
        finally:
            self.search_lock.release()
        self.send_json({'name':path.name,'report':report})

    def compare_devices_request(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.headers.get_content_type() != 'application/json' or not 0 < length <= 8192:
                raise ValueError('Petición JSON inválida.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Petición inválida.')
            devices, providers = data.get('devices'), data.get('providers')
            if not isinstance(devices, list) or not all(isinstance(v, str) and v in DEVICES for v in devices):
                raise ValueError('Dispositivos inválidos.')
            allowed = {c.name for c in WEB_CONNECTORS}
            if not isinstance(providers, list) or not 1 <= len(providers) <= 4 or any(not isinstance(v, str) or v not in allowed for v in providers):
                raise ValueError('Elige entre 1 y 4 fuentes web.')
            rounds, baseline = data.get('rounds', 2), data.get('baseline', 'desktop')
            if type(rounds) is not int or not 1 <= rounds <= 3 or not isinstance(baseline, str) or baseline not in DEVICES or not set(devices) - {baseline}:
                raise ValueError('Elige 1–3 rondas y un dispositivo distinto del control.')
            direct = data.get('direct_only', False)
            if type(direct) is not bool or not isinstance(data.get('departure'), str):
                raise ValueError('Parámetros de búsqueda inválidos.')
            if data.get('return_date') is not None and not isinstance(data['return_date'], str):
                raise ValueError('Regreso inválido.')
            search = Search(data.get('origin'), data.get('destination'), data['departure'],
                            data.get('return_date') or None,
                            direct=direct_for(data.get('origin'), data.get('destination'), direct_only=direct))
        except (ValueError, TypeError, UnicodeError) as exc:
            self.send_json({'error': str(exc)}, 400)
            return
        if self.search_lock is None or not self.search_lock.acquire(blocking=False):
            self.send_json({'error': 'Ya hay una búsqueda o comparación en curso.'}, 409)
            return
        try:
            report = compare_devices(search, providers, devices, rounds, run_search, baseline)
            self.directory.mkdir(parents=True, exist_ok=True)
            name = 'comparison-' + report['id'] + '.json'
            (self.directory / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError:
            self.send_json({'error': 'No se pudo guardar la comparación.'}, 500)
            return
        finally:
            self.search_lock.release()
        self.send_json({'name': name, 'report': report})


def main(argv=None):
    parser = argparse.ArgumentParser(description='Visor local de informes de scraperflights')
    parser.add_argument('--output', type=Path, default=Path('output'), help='Carpeta de informes')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', type=Path, default=Path('data/flights.sqlite'))
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('El puerto debe estar entre 0 y 65535.')
    handler = partial(DashboardHandler, directory=args.output.resolve(),
                      database=args.db.resolve(), search_lock=Lock())
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as exc:
        parser.error(f'No se pudo iniciar el visor: {exc}')
    with server:
        print(f'Abre http://127.0.0.1:{server.server_port} en el navegador. Ctrl+C para cerrar.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
