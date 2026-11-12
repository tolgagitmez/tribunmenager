"""Stage 10 Chromium check for live attack analysis and its JSON export.

Run only after the observer, presentation and UI sources have settled. This
checks the actual match page; headless scenario measurements live elsewhere.
"""
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
parser.add_argument('--output', default='docs/validation/attack-chain-browser.json')
parser.add_argument('--chromium', default=shutil.which('chromium'), help='Chromium executable; defaults to PATH chromium, then the Playwright executable')
parser.add_argument('--seconds', type=int, default=20, help='Natural fixed-step match exposure per rendering mode (15–60 seconds)')
args = parser.parse_args()
assert 15 <= args.seconds <= 60
runtime = root / 'work/stage10'
runtime.mkdir(parents=True, exist_ok=True)
source_files = ['football-sim.js', 'player-perception.js', 'team-intent.js', 'humanoid-rig.js', 'scene3d.js', 'player-renderer.js', 'attack-diagnostics.js', 'attack-analysis-ui.js', 'match3d.js', 'match.html', 'match3d.css', Path(__file__).relative_to(root).as_posix()]
source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}
assert source_hashes['football-sim.js'] == 'b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3', 'This check observes the retained stage9 engine without changing its rules'


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(root)))
Thread(target=server.serve_forever, daemon=True).start()
port = server.server_port
results = []

state_script = r"""(() => {
 const api=window.TRIBUN_MATCH_TEST,m=api.getState(),report=api.attackReport(),summary=api.attackSummary(),panel=document.getElementById('attackAnalysis');
 const keys=['gain','pressureEscape','lineBreak','finalThird','box','shot'],format=new Intl.NumberFormat('tr-TR',{maximumFractionDigits:1});
 const rows=[...panel.querySelectorAll('tbody tr')],uiRows=rows.map(row=>[...row.querySelectorAll('td')].map(cell=>({value:cell.firstChild?.textContent||'',text:cell.textContent})));
 const close=(a,b)=>Math.abs(a-b)<=1e-7;
 const c=report.clock,activeBins=c.controlledSeconds.reduce((a,b)=>a+b,0)+c.flightSeconds.reduce((a,b)=>a+b,0)+c.looseSeconds;
 const cellsAgree=keys.every((key,index)=>report.teams.every((team,i)=>{
  const eligible=team.stageEligibility[key],reached=team.eligibleReached[key],expected=eligible>0?format.format(reached)+' / '+format.format(eligible):'—';
  return uiRows[index]?.[i]?.value===expected && reached<=eligible && (!team.startedBeyond[key] || uiRows[index][i].text.includes('Başlangıçta ileride: '+format.format(team.startedBeyond[key]))) && (!team.notRequired[key] || uiRows[index][i].text.includes('Gerekmedi: '+format.format(team.notRequired[key])));
 }));
 const reportAndSummaryAgree=JSON.stringify(summary.teams)===JSON.stringify(report.teams)&&JSON.stringify(summary.clock)===JSON.stringify(report.clock)&&summary.episodes.length===0;
 return {time:m.time,players:m.players.filter(p=>p.active&&!p.referee).length,score:m.score,passes:m.passes,shots:m.shots,webgl:!!document.getElementById('stadiumCanvas').getContext('webgl'),playerQuality:document.querySelector('[data-player-quality]')?.textContent,clock:c,teams:report.teams,coverage:report.coverage,valid:report.valid,errors:report.errors,episodeCount:report.episodes.length,ui:{rows:rows.length,tableValues:uiRows,overview:panel.querySelector('.attack-overview').textContent,heading:panel.querySelector('header').textContent,stageCellsAgree:cellsAgree,reportAndSummaryAgree},checks:{clockAddsUp:close(c.observedSeconds,c.inPlaySeconds+c.deadBallSeconds+c.unobservedSeconds),deadClockAddsUp:close(c.deadBallSeconds,c.restartSeconds+c.goalPauseSeconds),inPlayBinsAddUp:close(c.inPlaySeconds,activeBins),clockMatchesMatch:close(c.observedSeconds,m.time),releasedPassesMatch:report.teams.every((team,i)=>team.passes.attempted===m.passes[i]),physicalShotsMatch:report.teams.every((team,i)=>team.shots===m.shots[i])}};
})()"""

freeze_script = r"""(() => {
 const api=window.TRIBUN_MATCH_TEST;
 // Retain shared references, Maps, Sets, undefined and numeric edge cases.
 // No planner, decision or physical forecast is invoked by this snapshot.
 const fingerprint=()=>{
  const seen=new Map(),encode=v=>{
   if(v===null)return ['null'];if(v===undefined)return ['undefined'];
   if(typeof v==='number')return ['number',Number.isNaN(v)?'NaN':v===Infinity?'Infinity':v===-Infinity?'-Infinity':Object.is(v,-0)?'-0':v];
   if(typeof v!=='object')return [typeof v,String(v)];
   if(seen.has(v))return ['ref',seen.get(v)];const id=seen.size;seen.set(v,id);
   if(v instanceof Map)return ['map',id,[...v].map(([k,x])=>[encode(k),encode(x)])];
   if(v instanceof Set)return ['set',id,[...v].map(encode)];
   return [Array.isArray(v)?'array':'object',id,Object.keys(v).sort().map(k=>[k,encode(v[k])])];
  };return JSON.stringify(encode(api.getState()));
 };
 window.__attackQAFingerprint=fingerprint;
 const before=fingerprint(),first=JSON.stringify(api.attackReport());
 for(let i=0;i<3;i++){api.attackReport();api.attackSummary();}
 // Both synchronous button handlers invoke the actual metrics/render path;
 // returning to pause before the event loop allows no match tick between them.
 document.getElementById('playButton').click();document.getElementById('playButton').click();
 const after=fingerprint(),last=JSON.stringify(api.attackReport());
 window.__attackQAPhysical=after;window.__attackQAReport=JSON.parse(last);
 return {paused:api.getState().paused,reportReadIsIdempotent:first===last,queriesAndUiRenderPreserveState:before===after,snapshotBytes:before.length,report:JSON.parse(last)};
})()"""

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium or playwright.chromium.executable_path, headless=True, args=['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        for mode in ['webgl-procedural', '2d']:
            page = browser.new_page(viewport={'width': 1280, 'height': 800}, accept_downloads=True)
            page.set_default_timeout(120000)
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
                page.add_init_script("Object.defineProperty(window,'TribunPlayerAssets',{configurable:true,get:()=>null,set:()=>{}})")
            page.goto(f'http://127.0.0.1:{port}/tactics.html', wait_until='networkidle')
            page.locator('#startMatch').click()
            page.wait_for_function('(() => {try{return !!window.TRIBUN_MATCH_TEST?.attackReport && window.TRIBUN_MATCH_TEST.getState().players.length>0;}catch{return false;}})()')
            module_state = page.evaluate("""(() => {const scripts=[...document.scripts].map(s=>new URL(s.src).pathname);return {observer:typeof window.TribunAttackDiagnostics?.attach==='function',ui:typeof window.TribunAttackAnalysisUI?.mount==='function',engine:typeof window.TribunFootball?.Match==='function',scripts};})()""")
            assert all(module_state[name] for name in ['observer', 'ui', 'engine']), module_state
            for script in ['/attack-diagnostics.js', '/attack-analysis-ui.js']:
                assert loaded.get(script) == 200, (script, loaded)
                assert module_state['scripts'].index(script) < module_state['scripts'].index('/match3d.js')
            page.evaluate('(seconds) => window.TRIBUN_MATCH_TEST.advance(seconds)', args.seconds)
            page.locator('#playButton').click()
            assert page.evaluate('TRIBUN_MATCH_TEST.getState().paused')
            state = page.evaluate(state_script)
            assert state['time'] >= args.seconds and state['players'] == 22, state
            assert state['webgl'] == (mode == 'webgl-procedural'), state
            if mode == 'webgl-procedural':
                assert state['playerQuality'] == 'YEDEK OYUNCU MODELİ', state['playerQuality']
            assert state['valid'] and not state['errors'], state['errors']
            assert state['clock']['inPlaySeconds'] > 0 and state['clock']['deadBallSeconds'] > 0, state['clock']
            assert state['checks'] and all(state['checks'].values()), state['checks']
            assert state['ui']['rows'] == 6 and state['ui']['stageCellsAgree'] and state['ui']['reportAndSummaryAgree'], state['ui']
            assert sum(team['attacks'] for team in state['teams']) > 0, state['teams']
            frozen = page.evaluate(freeze_script)
            assert frozen['paused'] and frozen['reportReadIsIdempotent'] and frozen['queriesAndUiRenderPreserveState'], frozen
            before_time = page.evaluate('TRIBUN_MATCH_TEST.getState().time')
            page.evaluate('TRIBUN_MATCH_TEST.advance(1)')
            assert page.evaluate('TRIBUN_MATCH_TEST.getState().time') == before_time
            assert page.evaluate('__attackQAFingerprint() === __attackQAPhysical')

            with page.expect_download() as download_info:
                page.locator('#downloadAttackAnalysis').click()
            download = download_info.value
            download_path = runtime / f'attack-export-{mode}.json'
            download.save_as(str(download_path))
            exported = json.loads(download_path.read_text())
            assert exported == frozen['report'], 'Downloaded JSON differs from the same paused observer report'
            assert page.evaluate('__attackQAFingerprint() === __attackQAPhysical'), 'Export changed the paused match state'
            assert exported['valid'] and len(exported['episodes']) == state['episodeCount']

            panel_screenshot = runtime / f'attack-panel-{mode}.png'
            page.locator('#attackAnalysis').screenshot(path=str(panel_screenshot))
            page.set_viewport_size({'width': 390, 'height': 844})
            page.locator('#attackAnalysis').scroll_into_view_if_needed()
            mobile = page.evaluate("""(() => {const panel=document.getElementById('attackAnalysis'),table=panel.querySelector('table'),button=document.getElementById('downloadAttackAnalysis'),p=panel.getBoundingClientRect(),t=table.getBoundingClientRect(),b=button.getBoundingClientRect();return {viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,panelLeft:p.left,panelRight:p.right,tableLeft:t.left,tableRight:t.right,buttonLeft:b.left,buttonRight:b.right,buttonEnabled:!button.disabled,rows:table.querySelectorAll('tbody tr').length};})()""")
            assert mobile['documentWidth'] <= mobile['viewport'] + 1, mobile
            assert 0 <= mobile['panelLeft'] and mobile['panelRight'] <= mobile['viewport'] + 1, mobile
            assert mobile['tableLeft'] >= 0 and mobile['tableRight'] <= mobile['viewport'] + 1, mobile
            assert mobile['buttonEnabled'] and mobile['rows'] == 6, mobile
            with page.expect_download() as mobile_download_info:
                page.locator('#downloadAttackAnalysis').click()
            mobile_path = runtime / f'attack-export-{mode}-mobile.json'
            mobile_download_info.value.save_as(str(mobile_path))
            assert json.loads(mobile_path.read_text()) == exported
            mobile_screenshot = runtime / f'attack-panel-{mode}-mobile.png'
            page.locator('#attackAnalysis').screenshot(path=str(mobile_screenshot))
            assert page.evaluate('__attackQAFingerprint() === __attackQAPhysical'), 'Responsive rendering changed the paused match state'
            page.locator('#playButton').click()
            page.evaluate('TRIBUN_MATCH_TEST.advance(1)')
            assert page.evaluate('TRIBUN_MATCH_TEST.getState().time') > before_time
            page.locator('#playButton').click()
            reset = page.evaluate("""(() => {const api=TRIBUN_MATCH_TEST;api.restart();const first=api.attackReport(),m=api.getState();api.restart();const second=api.attackReport();return {time:m.time,first,second,uiRows:document.querySelectorAll('#attackAnalysis tbody tr').length};})()""")
            for report in [reset['first'], reset['second']]:
                assert report['valid'] and report['clock']['observedSeconds'] == 0 and report['clock']['inPlaySeconds'] == 0
                assert all(team['attacks'] == team['shots'] == team['passes']['attempted'] == 0 for team in report['teams'])
                assert report['episodes'] == [] and report['shots'] == [] and report['errors'] == []
            assert reset['time'] == 0 and reset['uiRows'] == 6
            assert not errors, errors
            results.append({'mode': mode, 'exposure': state, 'moduleState': module_state, 'pausedQueries': {k: v for k, v in frozen.items() if k != 'report'}, 'export': {'path': str(download_path.relative_to(root)), 'sha256': hashlib.sha256(download_path.read_bytes()).hexdigest(), 'episodeCount': len(exported['episodes']), 'matchesPausedReport': True, 'mobileMatchesDesktop': True}, 'mobile': mobile, 'reset': {'time': reset['time'], 'twoFreshObserversHaveZeroCounters': True, 'rows': reset['uiRows']}, 'scriptErrors': list(errors), 'missingResources': sorted(missing), 'screenshots': [str(panel_screenshot.relative_to(root)), str(mobile_screenshot.relative_to(root))], 'assertedChecks': {'startFromTactics': True, 'moduleScriptsLoadedBeforeAdapter': True, 'twentyTwoPlayers': True, 'expectedRenderMode': True, 'stageCellsUseEligibleNumerator': True, 'advancedStartsRemainSeparate': True, 'clockPartitionsAddUp': True, 'releasedPassesAndShotsMatchEngine': True, 'reportAndSummaryAgree': True, 'queriesAndUiRefreshLeaveFullStateUnchanged': True, 'pausedAdvanceLeavesTimeUnchanged': True, 'explicitJsonDownloadMatchesReport': True, 'mobileExportMatchesDesktop': True, 'mobilePanelHasNoHorizontalOverflow': True, 'resumeAdvancesTime': True, 'restartClearsDiagnostics': True, 'noScriptErrors': True}})
            page.close()
        browser.close()
finally:
    server.shutdown()
    server.server_close()

assert source_hashes == {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}, 'Source changed during browser QA; rerun on settled source'
output = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'sources': source_hashes, 'method': 'Actual Chromium/SwiftShader WebGL procedural drawing and forced canvas2D fallback. Start through tactics, observe natural fixed-step match exposure, compare live stage cells/rates/clock bins with the observer report and actual engine releases, pause through the real controls, prove repeated reports/UI refresh/export leave complete engine values and RNG unchanged, download exact JSON, repeat the export at 390px width, resume and create fresh observers through the real restart path. Natural short browser exposure is not full-match balance or controlled aerial/keeper quality evidence.', 'runs': results, 'verified': True}
output_path = root / args.output
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'verified': True, 'sources': source_hashes, 'runs': [{'mode': r['mode'], 'time': r['exposure']['time'], 'episodes': r['export']['episodeCount'], 'scriptErrors': r['scriptErrors'], 'assertedChecks': r['assertedChecks']} for r in results]}, ensure_ascii=False, indent=2))
