#!/usr/bin/env python3
"""Standard-library launcher. Local matches work without economy catalogue files."""
import argparse
import json
import shutil
import subprocess
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


NATIVE_BRANCH = 'experiment/native-wsl-gpu-stage171'
WSL_BOOTSTRAP = r'''
set -eu
cd ~
repo=tribun-manager-native-alpha-stage171
url=https://github.com/tolgagitmez/tribunmenager.git
branch=experiment/native-wsl-gpu-stage171
command -v git >/dev/null || { echo 'Ubuntu icinde sudo apt-get install git komutunu calistir.' >&2; exit 2; }
if [ ! -e "$repo" ]; then
    git clone --single-branch --branch "$branch" "$url" "$repo"
fi
cd "$repo"
[ "$(git config --get remote.origin.url)" = "$url" ] &&
[ "$(git branch --show-current)" = "$branch" ] &&
[ -z "$(git status --porcelain --untracked-files=no)" ] ||
    { echo 'Alfa kaynak klasoru degismis; elle kontrol et.' >&2; exit 2; }
if [ "$1" = update ]; then git pull --ff-only origin "$branch"; fi
test -f integrations/league-soccer/native_alpha.py
'''

def native_command(args, platform=None):
    platform = platform or sys.platform
    if args.host not in ('127.0.0.1','localhost'):
        raise ValueError('Yeni motor yalnizca yerel ozel alfa olarak calisir.')
    options=['--port',str(args.port or 8765),'--delay',str(args.native_delay)]
    if args.native_install_deps:options.append('--install-deps')
    if getattr(args,'native_wsl_gpu',False):options.append('--wsl-gpu')
    if args.native_runtime:options+=['--runtime',args.native_runtime]
    if args.native_session_root:options+=['--session-root',args.native_session_root]
    if args.native_prepare_only:options.append('--prepare-only')
    if platform.startswith('linux'):
        if args.native_update:raise ValueError('Linux kaynak kodunu git ile acikca guncelle.')
        return [sys.executable,str(ROOT/'integrations/league-soccer/native_alpha.py'),'--private-diagnostic',*options]
    if platform=='win32':
        if not shutil.which('wsl.exe'):raise ValueError('Windows icin WSL2 Ubuntu gerekli. wsl --install -d Ubuntu')
        return ['wsl.exe','--distribution','Ubuntu','--cd','~','--exec','python3',
                'tribun-manager-native-alpha-stage171/integrations/league-soccer/native_alpha.py',
                '--private-diagnostic',*options]
    raise ValueError('Native alfa su anda Linux veya WSL2 Ubuntu yolu ile calisir.')

def wsl_prepare(args):
    # Send Bash program as bytes on stdin, not a Windows command-line argument.
    # Separate setup from interactive dependency installation and match launch.
    command=['wsl.exe','--distribution','Ubuntu','--cd','~','--exec','bash','-s','--',
             'update' if args.native_update else 'keep']
    return subprocess.run(command,input=WSL_BOOTSTRAP.encode('utf-8'),cwd=ROOT).returncode

def main(argv=None):
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 veya daha yeni bir sürüm gerekli.')
    parser = argparse.ArgumentParser(description='Tribün Manager başlatıcısı')
    parser.add_argument('--mode', choices=['native', 'local', 'league', 'full'], default='native', help='native: League-Soccer alfa; local: eski motor')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int)
    parser.add_argument('--native-install-deps', action='store_true')
    parser.add_argument('--native-wsl-gpu', action='store_true',help='Private WSLg D3D12 local GPU trial')
    parser.add_argument('--native-update', action='store_true')
    parser.add_argument('--native-prepare-only', action='store_true')
    parser.add_argument('--native-runtime')
    parser.add_argument('--native-session-root')
    parser.add_argument('--native-delay', type=int, default=120)
    args = parser.parse_args(argv)
    if args.port is None:args.port=8765 if args.mode=='native' else 8000
    if not 1 <= args.port <= 65535:
        parser.error('Port 1–65535 arasında olmalı.')
    if args.mode=='native':
        try:
            command=native_command(args)
            print('TRIBUN MANAGER | LEAGUE-SOCCER yerel alfa. Eski motor otomatik acilmaz.',flush=True)
            if sys.platform=='win32':
                status=wsl_prepare(args)
                if status:return status
            return subprocess.call(command,cwd=ROOT)
        except (OSError,ValueError) as exc:
            print('Yeni motor baslatilamadi: '+str(exc),file=sys.stderr)
            return 2
        except KeyboardInterrupt:return 130
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
    raise SystemExit(main())
