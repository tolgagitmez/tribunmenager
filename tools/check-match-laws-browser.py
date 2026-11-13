"""Actual launcher + Chromium; compressed periods exercise the real lifecycle UI."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
sources = ['start.py', 'football-sim.js', 'match-rules.js', 'referee-laws.js', 'pitch-laws.js', 'match3d.js', 'match.html', 'match3d.css', 'scene3d.js', 'attack-diagnostics.js', 'tools/check-match-laws-browser.py']
hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources}
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
runtime = root / 'work/stage12'
runtime.mkdir(parents=True, exist_ok=True)
log = (runtime / 'launcher-browser.log').open('w')
process = subprocess.Popen([sys.executable, str(root / 'start.py'), '--port', str(port)], cwd=root, stdout=log, stderr=log)
base = f'http://127.0.0.1:{port}'
runs = []
try:
    for _ in range(100):
        try:
            with urlopen(base + '/api/health', timeout=1) as response:
                assert json.load(response)['mode'] == 'local'
            break
        except OSError:
            time.sleep(.05)
    else:
        raise AssertionError('Documented launcher did not become ready')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        for mode in ['webgl-procedural', '2d']:
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            if mode == '2d':
                page.add_init_script("const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl'||type==='webgl2'?null:original.call(this,type,...args);};")
            page.add_init_script("window.MATCH_CFG={seed:21,rules:{periodSeconds:2,halftimeSeconds:5,addedTime:false,maxSubstitutions:4,substitutionWindows:2,substitutionPauseSeconds:.1}};")
            page.goto(base + '/match.html')
            page.wait_for_function('window.TRIBUN_MATCH_TEST && window.TRIBUN_MATCH_TEST.getState().players.length===23')
            result = page.evaluate("""() => {
             const api=window.TRIBUN_MATCH_TEST,$=id=>document.getElementById(id),checks={};
             if(!api.getState().paused)$('playButton').click();
             checks.startup=api.getState().players.filter(p=>p.active&&!p.referee).length===22;
             const advance=n=>{$('playButton').click();api.advance(n);if(!api.getState().paused)$('playButton').click();};
             advance(2.05);let m=api.getState();
             checks.halftime=m.lifecycle==='halftime'&&!$('halftimePanel').hidden&&$('halfLabel').textContent==='DEVRE ARASI';
             const snapshot=()=>JSON.stringify({ball:api.getState().ball,players:api.getState().players.map(p=>[p.x,p.z,p.vx,p.vz,p.face])});
             const before=snapshot(),clock=$('matchClock').textContent,homeX=m.players[10].homeX;
             advance(.5);checks.frozenPhysics=before===snapshot();checks.frozenClock=clock===$('matchClock').textContent;
             checks.halftimeExposure=api.attackReport().clock.halftimeSeconds>=.49;
             $('resumeHalf').click();m=api.getState();checks.secondKickoff=m.period===2&&m.restart?.kind==='kickoff'&&m.restart.team===1;
             checks.endsChanged=m.players[10].homeX===-homeX&&m.players[10].x>0;
             $('subButton').click();checks.competitionLabel=$('subRules').textContent.includes('4 oyuncu')&&$('subRules').textContent.includes('2 değişiklik');
             $('subOut').value='0';$('subIn').value='12';$('saveSubs').click();m=api.getState();checks.actualSubstitution=m.subCount===1&&m.subWindowsUsed===1&&m.players[0].rosterId===12;
             advance(3);m=api.getState();checks.finalWhistle=m.done&&m.finishReason==='full-time'&&!$('finishScreen').hidden&&$('halfLabel').textContent==='MAÇ SONU';
             const report=api.attackReport(),c=report.clock;
             checks.observerValid=report.valid&&Math.abs(c.observedSeconds-c.inPlaySeconds-c.deadBallSeconds-c.unobservedSeconds)<1e-6&&Math.abs(c.deadBallSeconds-c.restartSeconds-c.goalPauseSeconds-c.halftimeSeconds)<1e-6;
             window.MATCH_CFG.rules={periodSeconds:3,halftimeSeconds:1,addedTime:true,restartGraceSeconds:0};api.restart();api.advance(3.1);if(!api.getState().paused)$('playButton').click();
             checks.addedTimeAnnouncement=api.getState().matchClock.announcedAdded[0]>0&&$('halfLabel').textContent.includes('+')&&$('matchClock').textContent.includes('+');
             checks.extraTimeRemainsLive=!api.getState().done&&api.getState().lifecycle==='playing';
             const canvas=$('stadiumCanvas');checks.renderer=!!canvas.getContext('webgl');
             return {checks,time:m.time,periods:m.matchClock.periodLengths,clock:c,subCount:m.subCount,windowCount:m.subWindowsUsed,goalDimensions:window.TribunPitchLaws.dimensions};
            }""")
            renderer = result['checks'].pop('renderer')
            assert renderer == (mode == 'webgl-procedural'), (mode, 'rendering path')
            assert all(result['checks'].values()), (mode, result)
            page.set_viewport_size({'width': 390, 'height': 844})
            overflow = page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
            assert not overflow
            assert not errors, errors
            page.screenshot(path=str(runtime / (mode + '.png')), full_page=True)
            runs.append({'mode': mode, **result, 'mobile390Overflow': overflow, 'scriptErrors': errors})
            page.close()
        browser.close()
    assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == sha for p, sha in hashes.items())
    report = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'sources': hashes, 'method': 'Actual documented start.py local launcher and Chromium; two-second configured periods accelerate real lifecycle transitions. These are controlled UI checks, not natural balance samples.', 'runs': runs, 'verified': True}
    (root / 'docs/validation/match-laws-browser.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'verified': True, 'modes': len(runs), 'checksPerMode': len(runs[0]['checks']) + 3}))
finally:
    process.terminate()
    process.wait(timeout=10)
    log.close()
