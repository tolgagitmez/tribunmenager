"""Check that the animation workshop's overlay follows asynchronous model state."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', default='docs/validation/player-asset-lab.json')
parser.add_argument('--chromium', default=shutil.which('chromium'))
args = parser.parse_args()
paths = ['start.py', 'animation-lab.html', 'animation-lab.js', 'animation-scenarios.js',
         'scene3d.js', 'humanoid-rig.js', 'pitch-laws.js', 'player-renderer.js',
         'player-asset-status.js', 'ui-shell.js', 'ui-shell.css', 'animation-lab.css',
         'tools/check-player-asset-lab.py']
paths += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'assets/player').rglob('*')) if p.is_file()]
digest = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
sources = {p: digest(p) for p in paths}
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
base = f'http://127.0.0.1:{port}'
runtime = ROOT / 'work/stage13'
runtime.mkdir(parents=True, exist_ok=True)
log = (runtime / 'asset-lab-server.log').open('w')
server = subprocess.Popen([sys.executable, str(ROOT / 'start.py'), '--port', str(port)],
                          cwd=ROOT, stdout=log, stderr=log)
rows = []
try:
    for _ in range(100):
        try:
            with urlopen(base + '/api/health', timeout=1) as response:
                assert json.load(response)['mode'] == 'local'
            break
        except OSError:
            time.sleep(.05)
    else:
        raise AssertionError('Documented local launcher did not become ready')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium or playwright.chromium.executable_path,
            headless=True, args=['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        for state in ['ready', 'missing', 'webgl-unavailable']:
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script("""window.__labSkinDraws=0;const proto=window.WebGLRenderingContext?.prototype;
                if(proto){const original=proto.drawElements;proto.drawElements=function(...args){window.__labSkinDraws++;return original.apply(this,args);};}""")
            if state == 'missing':
                page.route('**/assets/player/player-model-data.js', lambda route: route.fulfill(status=404, content_type='application/javascript', body=''))
            elif state == 'webgl-unavailable':
                page.add_init_script("""const original=HTMLCanvasElement.prototype.getContext;
                    HTMLCanvasElement.prototype.getContext=function(kind,...args){return /^webgl/.test(kind)?null:original.call(this,kind,...args);};""")
            page.goto(base + '/animation-lab.html')
            page.wait_for_function("state=>document.querySelector('[data-player-asset-state]')?.dataset.playerAssetState===state", arg=state)
            if state == 'ready':
                page.wait_for_function('window.__labSkinDraws>0')
            snapshot = page.evaluate("""()=>({state:document.querySelector('[data-player-asset-state]').dataset.playerAssetState,
                overlay:document.querySelector('#renderMode').textContent,
                diagnostic:document.querySelector('[data-player-asset-state] summary').textContent,
                skinnedDraws:window.__labSkinDraws,skeletonDisabled:document.querySelector('#skeleton').disabled})""")
            assert snapshot['state'] == state
            assert snapshot['overlay'] == snapshot['diagnostic'], snapshot
            assert (snapshot['skinnedDraws'] > 0) == (state == 'ready'), snapshot
            assert snapshot['skeletonDisabled'] == (state == 'webgl-unavailable')
            assert not errors, errors
            rows.append({**snapshot, 'scriptErrors': errors})
            page.close()
        browser.close()
    assert {p: digest(p) for p in paths} == sources, 'Sources changed during verification'
    report = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'sources': sources,
              'method': 'Actual start.py local launcher and Chromium SwiftShader. Real workshop page; missing-model and disabled-WebGL cases override only the failing resource or context creation. The overlay must equal the shared diagnostic state, with real indexed GPU skin draws only in the ready case.',
              'limits': 'Small regression check for asynchronous workshop status, not an animation-quality or performance rating.',
              'runs': rows, 'verified': True}
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'verified': True, 'states': [r['state'] for r in rows]}))
finally:
    server.terminate()
    server.wait(timeout=10)
    log.close()
