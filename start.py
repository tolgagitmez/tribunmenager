#!/usr/bin/env python3
"""Standard-library launcher. Local matches work without economy catalogue files."""
import argparse
import json
import shutil
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent


class LocalHandler(SimpleHTTPRequestHandler):
    def reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/api/health':
            return self.reply(200, {'ok': True, 'mode': 'local', 'transfers': False, 'dailyLeague': False})
        if path.startswith('/api/'):
            return self.reply(503, {'error': 'Yerel maç modu açık. Günlük lig için --mode league, transferler için --mode full kullan.'})
        parts = Path(path).parts
        if any(p.startswith('.') or p in ('work', 'node_modules', '__pycache__') for p in parts if p not in ('/', '')) or path.endswith(('.py', '.db', '.sqlite', '.sqlite3', '-wal', '-shm', '.key', '.pem')):
            return self.reply(403, {'error': 'Dosya erişime kapalı.'})
        return super().do_GET()

    def do_POST(self):
        self.reply(503, {'error': 'Yerel maç modu açık. Lig hesabı için --mode league, transfer hesabı için --mode full kullan.'})


def main(argv=None):
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 veya daha yeni bir sürüm gerekli.')
    parser = argparse.ArgumentParser(description='Tribün Manager başlatıcısı')
    parser.add_argument('--mode', choices=['local', 'league', 'full', 'original'], default='local')
    parser.add_argument('--original-build-only', action='store_true', help='Orijinal motoru hazırla, başlatma.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args(argv)
    if args.original_build_only and args.mode != 'original':
        parser.error('--original-build-only yalnızca --mode original ile kullanılabilir.')
    if args.mode == 'original':
        import original_engine
        try:
            return original_engine.main(build_only=args.original_build_only)
        except (RuntimeError, OSError, ValueError, original_engine.subprocess.CalledProcessError) as exc:
            parser.exit(1, f'Orijinal League-Soccer açılamadı: {exc}. KURULUM.md dosyasına bak.\n')
    if not 1 <= args.port <= 65535:
        parser.error('Port 1–65535 arasında olmalı.')
    if args.mode == 'full':
        missing = [p for p in ['data/transfer-rules.json', 'data/player-catalog.json', 'data/club-seed.json'] if not (ROOT / p).is_file()]
        if missing:
            parser.error('Tam mod için eksik dosyalar: ' + ', '.join(missing) + '. Yerel maç için --mode local kullan. Ayrıntılar KURULUM.md içinde.')
        import server
        return server.run(host=args.host, port=args.port)
    if args.mode == 'league':
        if not shutil.which('node'):
            parser.error('Canlı lig için Node.js kurulu olmalı.')
        import server
        return server.run(host=args.host, port=args.port, with_transfers=False)
    print(f'Tribün Manager · YEREL MAÇ: http://{args.host}:{args.port}/', flush=True)
    print('Kadro → Taktik → Maçı başlat. Transfer/günlük lig bu modda kapalı. Kapatmak için Ctrl+C.', flush=True)
    try:
        with ThreadingHTTPServer((args.host, args.port), partial(LocalHandler, directory=str(ROOT))) as service:
            service.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        raise SystemExit(f'Sunucu açılamadı: {exc}. Örneğin --port 8001 ile başka port dene.')


if __name__ == '__main__':
    sys.exit(main())
