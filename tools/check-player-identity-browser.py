"""Stage 11: actual browser roster cards, normal launches and both-team profiles.

The league endpoint is intercepted with an explicitly authored API fixture. This
checks browser transport/presentation, not production catalogue availability or
natural match balance. Endpoint authorization/storage have separate server tests.
"""
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
import argparse
import hashlib
import json
import shutil
import subprocess

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', default='docs/validation/player-identity-browser.json')
parser.add_argument('--chromium', default=shutil.which('chromium'))
args = parser.parse_args()
runtime = root / 'work/stage11'
runtime.mkdir(parents=True, exist_ok=True)
source_files = ['player-model-profiles.json', 'player-model-profiles.js', 'player-model.js',
                'club-data.js', 'football-sim.js', 'transfer-client.js', 'match-config.js',
                'manager.js', 'tactics-page.js', 'match3d.js', 'index.html', 'tactics.html',
                'match.html', 'style.css', 'match3d.css', Path(__file__).relative_to(root).as_posix()]
source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}
seed = json.loads(subprocess.check_output(['node', '-e',
    'console.log(JSON.stringify(require("./club-data.js").createRoster()))'], cwd=root))
own = [{**p, 'name': f"Tarayıcı Oyuncusu {p['id']}", 'rating': 80} for p in seed]
own[8].update(fitness=65, form=55, preferredFoot='left')
own[2].update(fitness=84, form=72)
# A striker deliberately occupies one defender's generic role and vice versa.
starters = [8, 9, 10, 7, 5, 6, 4, 2, 3, 1, 0]
starters[1], starters[7] = starters[7], starters[1]
away = [{**p, 'id': p['id'] + 100, 'name': f"Kayıtlı Rakip {p['id']}",
         'rating': 80, 'preferredFoot': 'left' if p['id'] % 2 else 'right'} for p in seed]
away_starters = [109, 116, 108, 107, 105, 110, 104, 102, 103, 101, 100]
saved = {'players': own, 'starters': starters, 'formation': '4-3-3', 'matchMinutes': 5,
         'tactics': {'playstyle': 'possession', 'tempo': 47}, 'special': {'captain': 7, 'penalty': 9, 'free': 7, 'corner': 8}}
fixture = {'version': 1, 'snapshotAt': 1800000000,
           'fixture': {'league': 'BROWSER', 'round': 2, 'home': 1, 'away': 0,
                       'kickoff': 1800000300, 'isHome': False, 'state': 'scheduled'},
           'ownTeam': {'slot': 0, 'name': 'Tarayıcı SK'},
           'opponent': {'slot': 1, 'name': 'Kayıtlı Rakip SK', 'source': 'linked-roster',
                        'formation': '4-4-2', 'tactics': {'playstyle': 'direct', 'tempo': 76},
                        'revision': 17, 'players': away, 'starters': away_starters}}
fixture_next = json.loads(json.dumps(fixture))
fixture_next['fixture'].update(league='BROWSER-NEXT', round=3, isHome=True, home=0, away=1)
fixture_next['ownTeam']['name'] = 'Yeni Lig Takımı'
fixture_next['opponent']['name'] = 'Yeni Lig Rakibi'
for player in fixture_next['opponent']['players']:
    player['name'] = 'Yeni Lig / ' + player['name']


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(root)))
Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
results = []

cards_script = r"""(() => {
 const C=TribunClubData,M=TribunPlayerModel,s=JSON.parse(localStorage.getItem(C.key));
 const cards=[...document.querySelectorAll('#pitchPlayers .player')].map((card,i)=>{
  const p=s.players[+card.dataset.id],slot=M.slotFor(s.formation,i),effective=M.forSlot(p,slot);
  return {id:p.id,slot:slot.role,shown:+card.querySelector('.cardtop b').textContent,
   expected:effective.skill,title:card.title,factors:effective.model.factors,foot:M.footLabel(p)};
 });
 const probe=s.players[8],changed={...probe,id:900,number:99};
 const identityFields=[...M.attributes,'preferredFoot'];
 const normalized=M.normalize(probe),other=M.normalize(changed);
 const full=M.forSlot({...probe,fitness:100,form:100},'ATT'),low=M.forSlot({...probe,fitness:45,form:30},'ATT'),off=M.forSlot({...probe,fitness:100,form:100},'DEF');
 return {cards,displayAverage:+document.getElementById('topTeamRating').textContent,
  expectedAverage:Math.round(cards.reduce((a,c)=>a+c.expected,0)/cards.length),
  checks:{elevenCards:cards.length===11,allCardsUseSharedQuality:cards.every(c=>c.shown===c.expected),
   descriptionsExplainProfileAndFoot:cards.every(c=>c.title.includes(c.foot)&&c.title.includes('mevki uyumu')&&c.title.includes('form')),
   idAndNumberDoNotChangeFootballIdentity:identityFields.every(k=>normalized[k]===other[k]),
   lowFormReducesTechnique:low.passing<full.passing&&low.composure<full.composure,
   lowConditionReducesPace:low.pace<full.pace&&low.acceleration<full.acceleration,
   offRoleReducesTechnique:off.passing<full.passing&&off.skill<full.skill,
   intrinsicStrengthDoesNotChangeWithRole:off.strength===full.strength,
   actualOffRoleCardsPresent:cards.filter(c=>c.factors.position<1).length===2}};
})()"""

state_script = r"""(() => {
 const m=TRIBUN_MATCH_TEST.getState(),M=TribunPlayerModel,cfg=m.cfg;
 const rows=m.players.filter(p=>!p.referee).map(p=>{
  const raw=(p.team===0?cfg.players:cfg.awayPlayers).find(q=>q.id===p.rosterId);
  const e=M.forSlot(raw,M.slotFor(p.team===0?cfg.formation:cfg.awayFormation,p.index));
  return {team:p.team,id:p.rosterId,name:p.name,skill:p.skill,expected:e.skill,foot:p.preferredFoot,
   expectedFoot:e.preferredFoot,model:p.model,
   attrsAgree:M.attributes.every(k=>Math.abs(p[k]-e[k])<1e-10)};
 });
 const scripts=[...document.scripts].map(s=>new URL(s.src).pathname);
 return {rows,time:m.time,paused:m.paused,ownCount:rows.filter(p=>p.team===0).length,
  awayCount:rows.filter(p=>p.team===1).length,ownIds:rows.filter(p=>p.team===0).map(p=>p.id),
  awayIds:rows.filter(p=>p.team===1).map(p=>p.id),opponentSource:cfg.opponentSource,fixture:cfg.fixture,
  ui:{own:document.querySelector('.scoreboard .club:not(.away)').textContent,
      away:document.querySelector('.scoreboard .club.away').textContent,
      notice:document.querySelector('.bottom-note').textContent,title:document.getElementById('sessionTitle').textContent},
  scripts,webgl:!!document.getElementById('stadiumCanvas').getContext('webgl'),
  checks:{allProfilesMatchCommonContract:rows.every(p=>p.skill===p.expected&&p.foot===p.expectedFoot&&p.attrsAgree),
   modulesBeforeEngine:scripts.indexOf('/player-model.js')<scripts.indexOf('/football-sim.js'),
   bothRostersMaterialized:rows.length===22&&rows.every(p=>p.model?.version===1)}};
})()"""

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium or playwright.chromium.executable_path,
            headless=True, args=['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        for mode in ['webgl-procedural', '2d']:
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            errors, missing, requests = [], set(), []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: missing.add(urlsplit(response.url).path) if response.status >= 400 else None)
            if mode == '2d':
                page.add_init_script("const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind==='webgl'||kind==='webgl2'?null:get.call(this,kind,...args)}")
            else:
                page.add_init_script("Object.defineProperty(window,'TribunPlayerAssets',{configurable:true,get:()=>null,set:()=>{}})")
            page.add_init_script('if(!sessionStorage.getItem("identityQALoaded")){localStorage.setItem("tribun-manager-pro09",'+json.dumps(json.dumps(saved, ensure_ascii=False))+');localStorage.setItem("tribun-league-token","browser-fixture-token");sessionStorage.setItem("identityQALoaded","1");}')

            def fixture_route(route):
                requests.append({'url': route.request.url, 'authorization': route.request.headers.get('authorization')})
                value = fixture_next if route.request.headers.get('authorization') == 'Bearer browser-fixture-token-next' else fixture
                route.fulfill(status=200, content_type='application/json', body=json.dumps(value, ensure_ascii=False))

            page.route('**/api/league/local-match', fixture_route)
            page.goto(base+'/index.html', wait_until='networkidle')
            cards = page.evaluate(cards_script)
            assert all(cards['checks'].values()), cards
            assert cards['displayAverage'] == cards['expectedAverage'], cards
            page.set_viewport_size({'width': 390, 'height': 844})
            squad_mobile = page.evaluate('({viewport:innerWidth,width:document.documentElement.scrollWidth})')
            assert squad_mobile['width'] <= squad_mobile['viewport'] + 1, squad_mobile
            page.set_viewport_size({'width': 1280, 'height': 800})
            page.locator('#demoMatch').click()
            page.wait_for_function('(() => {try{return TRIBUN_MATCH_TEST.getState().players.length>0}catch{return false}})()')
            page.locator('#playButton').click()
            linked = page.evaluate(state_script)
            assert all(linked['checks'].values()), linked
            assert linked['ownIds'] == starters and linked['awayIds'] == away_starters, linked
            assert linked['ownCount'] == linked['awayCount'] == 11, linked
            assert linked['webgl'] == (mode == 'webgl-procedural'), linked
            assert linked['opponentSource'] == 'linked-roster' and linked['fixture']['isHome'] is False, linked
            assert 'Tarayıcı SK' in linked['ui']['own'] and 'DEPLASMAN' in linked['ui']['own'], linked['ui']
            assert 'Kayıtlı Rakip SK' in linked['ui']['away'] and '4-4-2' in linked['ui']['away'], linked['ui']
            assert 'FİKSTÜR KADROSU' in linked['ui']['title'] and 'günlük lig sonucu değişmez' in linked['ui']['notice'], linked['ui']
            assert len(requests) == 1 and requests[0]['authorization'] == 'Bearer browser-fixture-token', requests
            # Pausing and opening a replacement must not re-normalize any existing identity.
            freeze = page.evaluate("""(() => {const a=TRIBUN_MATCH_TEST,b=JSON.stringify(a.getState().players.map(p=>({id:p.id,skill:p.skill,pace:p.pace,model:p.model}))),t=a.getState().time;a.advance(1);return {sameIdentity:b===JSON.stringify(a.getState().players.map(p=>({id:p.id,skill:p.skill,pace:p.pace,model:p.model}))),sameTime:t===a.getState().time,paused:a.getState().paused};})()""")
            assert all(freeze.values()), freeze
            substitution = page.evaluate("""(() => {const a=TRIBUN_MATCH_TEST,m=a.getState(),M=TribunPlayerModel;const b=a.benchPlayers().find(p=>p.pos==='ATT');const out=m.players.find(p=>p.team===0&&p.role==='DEF'&&p!==m.owner&&p!==m.kickTask?.p&&p!==m.flight?.target);const expected=M.forSlot(b,M.slotFor(m.cfg.formation,out.index)),result=a.substitute(out.index,b.id),p=a.getState().players[out.id];return {result,id:p.rosterId,expectedId:b.id,skill:p.skill,expectedSkill:expected.skill,foot:p.preferredFoot,expectedFoot:expected.preferredFoot,attrsAgree:M.attributes.every(k=>p[k]===expected[k]),benchContainsUsed:a.benchPlayers().some(q=>q.id===b.id),fit:p.roleFit};})()""")
            assert substitution['result']['ok'] and substitution['id'] == substitution['expectedId'], substitution
            assert substitution['skill'] == substitution['expectedSkill'] and substitution['foot'] == substitution['expectedFoot'], substitution
            assert substitution['attrsAgree'] and not substitution['benchContainsUsed'] and substitution['fit'] < 1, substitution
            page.set_viewport_size({'width': 390, 'height': 844})
            match_mobile = page.evaluate('({viewport:innerWidth,width:document.documentElement.scrollWidth})')
            assert match_mobile['width'] <= match_mobile['viewport'] + 1, match_mobile
            page.screenshot(path=str(runtime/f'identity-{mode}-mobile.png'), full_page=True)
            page.set_viewport_size({'width': 1280, 'height': 800})
            # A prepared snapshot belongs to its launch context. Directly revisiting
            # match.html after a league switch must replace the old opponent.
            page.evaluate('localStorage.setItem("tribun-league-token","browser-fixture-token-next")')
            page.goto(base+'/match.html', wait_until='networkidle')
            page.wait_for_function('(() => {try{return TRIBUN_MATCH_TEST.getState().players.length>0}catch{return false}})()')
            page.locator('#playButton').click()
            switched = page.evaluate(state_script)
            assert all(switched['checks'].values()), switched
            assert len(requests) == 2 and requests[-1]['authorization'] == 'Bearer browser-fixture-token-next', requests
            assert switched['fixture']['league'] == 'BROWSER-NEXT' and switched['fixture']['isHome'] is True, switched
            assert 'Yeni Lig Takımı' in switched['ui']['own'] and 'Yeni Lig Rakibi' in switched['ui']['away'], switched['ui']
            assert all(p['name'].startswith('Yeni Lig / ') for p in switched['rows'] if p['team'] == 1), switched
            # A fresh tactics launch with no league must explicitly disclose demo data.
            page.evaluate('localStorage.removeItem("tribun-league-token")')
            page.goto(base+'/tactics.html', wait_until='networkidle')
            page.locator('#startMatch').click()
            page.wait_for_function('(() => {try{return TRIBUN_MATCH_TEST.getState().players.length>0}catch{return false}})()')
            page.locator('#playButton').click()
            demo = page.evaluate(state_script)
            assert all(demo['checks'].values()) and demo['opponentSource'] == 'demo', demo
            assert 'DENEME KADROSU' in demo['ui']['title'] and 'Deneme' in demo['ui']['notice'], demo['ui']
            assert not errors, errors
            results.append({'mode': mode, 'cards': cards, 'linkedMatch': linked, 'substitution': substitution,
                'paused': freeze, 'demoMatch': {'opponentSource': demo['opponentSource'], 'ui': demo['ui'], 'checks': demo['checks']},
                'changedLeagueDirectEntry': {'fixture': switched['fixture'], 'ui': switched['ui'], 'replacedOpponentNames': True},
                'endpointFixtureRequests': requests, 'squadMobile': squad_mobile, 'matchMobile': match_mobile,
                'scriptErrors': list(errors), 'missingResources': sorted(missing),
                'assertedChecks': {'sharedQualityOnEveryCard': True, 'averageMatchesCards': True,
                    'identityDoesNotDependOnIds': True, 'formConditionAndGenericRoleHaveEffects': True,
                    'normalManagerLaunchFetchesOfficialFixtureOnce': True, 'authenticatedFixtureRequest': True,
                    'bothStartingRostersAndFootPreferencesPreserved': True, 'bothTeamsUseEffectiveProfiles': True,
                    'awayVenueAndFormationLabels': True, 'normalTacticsLaunchDisclosesDemo': True,
                    'directEntryAfterLeagueSwitchReplacesPreparedOpponent': True,
                    'substitutionUsesSameContractAndCannotReturnUsedBench': True, 'pausedIdentityAndClockStable': True,
                    'expectedRenderer': True, 'mobileSquadAndMatchHaveNoHorizontalOverflow': True, 'noScriptErrors': True}})
            page.close()
        browser.close()
finally:
    server.shutdown()
    server.server_close()

changed_sources = [name for name in source_files if hashlib.sha256((root / name).read_bytes()).hexdigest() != source_hashes[name]]
assert not changed_sources, f'Sources changed during browser QA; rerun after changes settle: {changed_sources}'
report = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'sources': source_hashes,
          'method': 'Actual Chromium with SwiftShader procedural WebGL and forced canvas2D. Authored browser API fixture for league/local-match; production endpoint storage and authorization are tested separately. Actual manager cards and manager→match navigation, both rosters and substitutions, actual tactics→demo navigation, paused state, mobile390 layout. No natural match-balance inference.',
          'runs': results, 'verified': True}
output = root / args.output
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'verified': True, 'runs': [{'mode': r['mode'], 'assertedChecks': r['assertedChecks'], 'scriptErrors': r['scriptErrors']} for r in results]}, ensure_ascii=False))
