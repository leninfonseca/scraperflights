"""Serve the report dashboard and the selected report directory on localhost."""
import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_REPORT = 32 * 1024 * 1024
REPORT_TYPES = {'.json': 'application/json', '.csv': 'text/csv'}
ASSETS = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
          '/style.css': ('style.css', 'text/css')}


class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, directory, **kwargs):
        self.directory = directory
        super().__init__(*args, **kwargs)

    def send_data(self, data, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        port = self.server.server_port
        if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            self.send_error(403)
            return
        url = urlsplit(self.path)
        if url.path in ASSETS:
            name, content_type = ASSETS[url.path]
            asset = files('scraperflights').joinpath('dashboard', name)
            self.send_data(asset.read_bytes(), content_type)
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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Visor local de informes de scraperflights')
    parser.add_argument('--output', type=Path, default=Path('output'), help='Carpeta de informes')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('El puerto debe estar entre 0 y 65535.')
    handler = partial(DashboardHandler, directory=args.output.resolve())
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
