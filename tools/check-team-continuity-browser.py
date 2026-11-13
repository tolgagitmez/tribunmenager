"""Stage 9 real Chromium smoke test. Run after engine/presentation sources settle."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
from datetime import datetime, timezone
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
import argparse
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', default='docs/validation/team-continuity-browser.json')
parser.add_argument('--chromium', default=shutil.which('chromium'), help='Chromium executable; defaults to PATH chromium, then the Playwright executable')
args = parser.parse_args()
output_path = root / args.output
runtime = root / 'work/stage9'
runtime.mkdir(parents=True, exist_ok=True)
source_files = ['football-sim.js', 'player-perception.js', 'team-intent.js', 'humanoid-rig.js', 'scene3d.js', 'player-renderer.js', 'match3d.js', 'match.html', Path(__file__).relative_to(root).as_posix()]
source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(root)))
Thread(target=server.serve_forever, daemon=True).start()
port = server.server_port
results = []
sample_script = r"""(() => {
 const api=window.TRIBUN_MATCH_TEST,rig=window.TribunHumanoidRig;
 const stats={perceptionActorSamples:0,storedRivalSamples:0,scanningActorSamples:0,drawnScanSamples:0,taskSamples:0,maxTaskActors:0,maxPerceptionActors:0,maxStoredRivals:0,maxObservedHeadYaw:0,maxDrawnHeadYaw:0,taskHistoryRecords:0,poseQueriesLeavePhysicalStateUnchanged:true,drawnHeadMatchesBodyPlusYaw:true,phaseSamples:{},firstScan:null};
 for(let tick=0;tick<15*60;tick++){
  api.advance(1/60);const m=api.getState(),players=m.players.filter(p=>p.active&&!p.referee);let tasks=0,perceptions=0,records=0;
  for(const p of players){
   if(p.task){stats.taskSamples++;tasks++;}
   if(p.perception){stats.perceptionActorSamples++;perceptions++;records+=Object.keys(p.perception.records||{}).length;}
   stats.taskHistoryRecords=Math.max(stats.taskHistoryRecords,(p.taskHistory||[]).length);
   const observed=p.perception?.headYaw||0;
   stats.maxObservedHeadYaw=Math.max(stats.maxObservedHeadYaw,Math.abs(observed));
   if(Math.abs(observed)>.1)stats.scanningActorSamples++;
   // getPose uses the cached pose already updated by the normal match tick.
   // Read it twice and verify no physical body/ball/seed field changes.
   const before=JSON.stringify([p.x,p.z,p.vx,p.vz,p.face,m.ball,m.seed]);
   const pose=rig.getPose(p);rig.getPose(p);
   const after=JSON.stringify([p.x,p.z,p.vx,p.vz,p.face,m.ball,m.seed]);
   stats.poseQueriesLeavePhysicalStateUnchanged&&=before===after;
   const drawn=pose.headYaw||0;stats.maxDrawnHeadYaw=Math.max(stats.maxDrawnHeadYaw,Math.abs(drawn));
   if(Math.abs(drawn)>.05){
    stats.drawnScanSamples++;
    stats.drawnHeadMatchesBodyPlusYaw&&=Number.isFinite(pose.headFace)&&Math.abs(pose.headFace-p.face-drawn)<1e-7&&pose.face===p.face;
    stats.firstScan??={time:m.time,id:p.id,bodyFace:p.face,observedHeadYaw:observed,drawnHeadYaw:drawn,drawnHeadFace:pose.headFace};
   }
  }
  stats.maxTaskActors=Math.max(stats.maxTaskActors,tasks);stats.maxPerceptionActors=Math.max(stats.maxPerceptionActors,perceptions);stats.maxStoredRivals=Math.max(stats.maxStoredRivals,records);stats.storedRivalSamples+=records;
  for(const [team,phase]of (m.teamPhases||[]).entries())if(phase?.phase){const key=team+':'+phase.phase;stats.phaseSamples[key]=(stats.phaseSamples[key]||0)+1;}
 }
 const m=api.getState(),canvas=document.getElementById('stadiumCanvas');
 return {time:m.time,players:m.players.filter(p=>p.active&&!p.referee).length,score:m.score,passes:m.passes,clock:document.getElementById('matchClock').textContent,teamPhases:m.teamPhases?.map(p=>({phase:p.phase,since:p.since,epoch:p.epoch,attackEpoch:p.attackEpoch})),webgl:!!canvas.getContext('webgl'),playerQuality:document.querySelector('[data-player-quality]')?.textContent,stats};
})()"""

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium or playwright.chromium.executable_path, headless=True, args=['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        for mode in ['webgl-procedural', '2d']:
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            errors = []
            missing = set()
            loaded = {}
            page.on('pageerror', lambda error: errors.append(str(error)))

            def record_response(response):
                pathname = urlsplit(response.url).path
                if response.status >= 400:
                    missing.add(pathname)
                if pathname.endswith('.js'):
                    loaded[pathname] = response.status

            page.on('response', record_response)
            if mode == '2d':
                page.add_init_script("const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind==='webgl'||kind==='webgl2'?null:get.call(this,kind,...args)}")
            else:
                # Exercise procedural drawing even when optional model assets exist.
                # This changes only renderer asset registration, never engine state.
                page.add_init_script("Object.defineProperty(window,'TribunPlayerAssets',{configurable:true,get:()=>null,set:()=>{}})")
            page.goto(f'http://127.0.0.1:{port}/tactics.html', wait_until='networkidle')
            page.locator('#startMatch').click()
            page.wait_for_function('(() => {try{return !!window.TRIBUN_MATCH_TEST && window.TRIBUN_MATCH_TEST.getState().players.length>0;}catch{return false;}})()')
            module_state = page.evaluate("""(() => {const scripts=[...document.scripts].map(s=>new URL(s.src).pathname);return {perception:typeof window.TribunPerception?.update==='function'&&typeof window.TribunPerception?.rivals==='function',intent:typeof window.TribunIntent?.resolve==='function'&&typeof window.TribunIntent?.clear==='function',engine:typeof window.TribunFootball?.Match==='function',rig:typeof window.TribunHumanoidRig?.getPose==='function',scripts};})()""")
            assert all(module_state[name] for name in ['perception', 'intent', 'engine', 'rig']), module_state
            for script in ['/player-perception.js', '/team-intent.js']:
                assert loaded.get(script) == 200, (script, loaded)
                assert module_state['scripts'].index(script) < module_state['scripts'].index('/football-sim.js')
            state = page.evaluate(sample_script)
            stats = state['stats']
            assert state['time'] >= 15 and state['players'] == 22, state
            assert state['webgl'] == (mode == 'webgl-procedural'), state
            if mode == 'webgl-procedural':
                assert state['playerQuality'] == 'YEDEK OYUNCU MODELİ', state['playerQuality']
            assert stats['maxPerceptionActors'] == 22 and stats['storedRivalSamples'] > 0, stats
            assert stats['maxTaskActors'] > 0 and stats['taskSamples'] > 0 and stats['taskHistoryRecords'] > 0, stats
            assert stats['scanningActorSamples'] > 0 and stats['drawnScanSamples'] > 0, stats
            assert stats['poseQueriesLeavePhysicalStateUnchanged'] and stats['drawnHeadMatchesBodyPlusYaw'], stats
            assert len(state['teamPhases']) == 2 and all(p['phase'] in ['win', 'possession', 'loss', 'defence'] for p in state['teamPhases']), state['teamPhases']
            assert stats['phaseSamples'], stats
            assert not errors, errors
            page.locator('#playButton').click()
            assert page.evaluate('TRIBUN_MATCH_TEST.getState().paused')
            before = page.evaluate('TRIBUN_MATCH_TEST.getState().time')
            page.evaluate('TRIBUN_MATCH_TEST.advance(1)')
            assert page.evaluate('TRIBUN_MATCH_TEST.getState().time') == before
            page.locator('#playButton').click()
            page.evaluate('TRIBUN_MATCH_TEST.advance(1)')
            assert page.evaluate('TRIBUN_MATCH_TEST.getState().time') > before
            page.evaluate('window.scrollTo(0,0)')
            screenshot = runtime / f'match-{mode}.png'
            page.screenshot(path=str(screenshot))
            results.append({'mode': mode, 'state': state, 'moduleState': module_state, 'scriptErrors': list(errors), 'missingResources': sorted(missing), 'screenshot': str(screenshot.relative_to(root)), 'assertedChecks': {'startFromTactics': True, 'moduleScriptsLoadedBeforeEngine': True, 'twentyTwoPlayers': True, 'expectedRenderMode': True, 'localPerceptionRecords': True, 'liveTeamTasksAndHistory': True, 'validTeamPhases': True, 'headScanningAndDrawnPose': True, 'poseQueryLeavesPhysicalStateUnchanged': True, 'pauseFlag': True, 'pausedAdvanceLeavesTimeUnchanged': True, 'resumeAdvancesTime': True, 'noScriptErrors': True}})
            page.close()
        browser.close()
finally:
    server.shutdown()
    server.server_close()

assert source_hashes == {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}, 'Source changed during browser QA; rerun on settled source'
output = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'sources': source_hashes, 'method': 'Actual Chromium with SwiftShader WebGL/procedural renderer plus forced canvas2D fallback. Start from tactics UI, execute normal match ticks for >=15s, inspect existing read-only test-state/cached rig poses, pause and resume through actual controls. Head orientation changes remain presentation fields; physical body/ball/seed are unchanged by pose reads. Browser smoke does not establish whole-match football balance or complete four-phase scenario coverage.', 'runs': results}
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(output, ensure_ascii=False, indent=2))
