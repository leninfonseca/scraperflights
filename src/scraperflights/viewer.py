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

from .catalog import sources
from .cli import DEFAULT_WEB_PROVIDERS, export, run_search
from .core import Search, Store

MAX_REPORT = 32 * 1024 * 1024
REPORT_TYPES = {'.json': 'application/json', '.csv': 'text/csv'}
ASSETS = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
          '/style.css': ('style.css', 'text/css')}


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
            if origin not in ('MAD', 'BCN') or not isinstance(departure, str):
                raise ValueError
            if return_date is not None and not isinstance(return_date, str):
                raise ValueError
            dates = [departure] + ([return_date] if return_date else [])
            if any(date.fromisoformat(value).isoformat() != value for value in dates):
                raise ValueError
            search = Search(origin, 'BCN' if origin == 'MAD' else 'MAD', departure, return_date or None)
        except (ValueError, UnicodeError):
            self.send_json({'error': 'Indica una salida válida y, si hay regreso, una fecha igual o posterior.'}, 400)
            return
        if not self.search_lock.acquire(blocking=False):
            self.send_json({'error': 'Ya hay una búsqueda en curso. Espera a que termine.'}, 409)
            return
        try:
            run = run_search(search, DEFAULT_WEB_PROVIDERS, {})
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
