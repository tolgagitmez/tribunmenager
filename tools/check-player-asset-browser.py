"""Positive GPU skinning and visible model checks, plus handled loading failures.

Uses the real documented local launcher and actual match/studio pages. WebGL
instrumentation reads draw calls, bone uniforms and framebuffer pixels; it does
not replace model geometry or advance physics. These checks are not a visual
quality rating or a device performance benchmark.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', default='docs/validation/player-asset-browser.json')
parser.add_argument('--chromium', default=shutil.which('chromium'))
parser.add_argument('--capture-suffix', default='', help='Suffix for screenshot filenames')
parser.add_argument('--preview-only', action='store_true', help='Normal-page screenshots only; saves a scoped preview report under work/stage13')
args = parser.parse_args()
RUNTIME = ROOT / 'work/stage13'
RUNTIME.mkdir(parents=True, exist_ok=True)

SOURCE_PATHS = [
    'start.py', 'player-renderer.js', 'player-asset-status.js', 'scene3d.js',
    'match3d.js', 'match.html', 'player-studio.js', 'player-studio.html', 'animation-lab.js', 'animation-lab.html',
    'humanoid-rig.js', 'animation-scenarios.js', 'player-studio.css', 'ui-shell.js', 'ui-shell.css', 'match3d.css',
    'football-sim.js', 'match-rules.js', 'referee-laws.js', 'pitch-laws.js',
    'player-perception.js', 'team-intent.js', 'tactics.js', 'club-data.js',
    'player-model.js', 'player-model-profiles.js', 'player-model-profiles.json',
    'attack-diagnostics.js', 'attack-analysis-ui.js', 'transfer-client.js', 'match-config.js',
    'tools/check-player-asset-browser.py',
]
ASSET_PATHS = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'assets/player').rglob('*')) if p.is_file()]
SOURCE_PATHS += ASSET_PATHS
assert (ROOT / 'assets/player/player-model-data.js').is_file(), 'Real model bundle is required; no fallback-only pass is allowed'
HASHES = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCE_PATHS}
MODEL_PATH = '/assets/player/player-model-data.js'

INSTRUMENT = r"""(() => {
 const qa=window.__playerAssetQA={frames:[],frame:null,contexts:[],capture:false,captured:null,programCount:0,textureUploads:[]};
 const originalContext=HTMLCanvasElement.prototype.getContext;
 HTMLCanvasElement.prototype.getContext=function(type,...rest){
  const gl=originalContext.call(this,type,...rest);
  if(gl&&/^webgl/.test(type)&&!qa.contexts.some(c=>c.gl===gl))qa.contexts.push({gl,canvas:this});
  return gl;
 };
 const shaderSources=new WeakMap(),attached=new WeakMap(),skinPrograms=new WeakSet(),locations=new WeakMap(),uniforms=new WeakMap();
 const hashNumbers=values=>{let h=2166136261;for(const n of values){h=Math.imul(h^(Number.isFinite(n)?Math.round(n*1000):0),16777619);}return (h>>>0).toString(16);};
 function jointShape(values){
  if(values.length<32)return null;
  const m=[values[0],values[4],values[8],values[1],values[5],values[9],values[2],values[6],values[10]],
   [a,b,c,d,e,f,g,h,i]=m,det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
  if(Math.abs(det)<1e-8)return null;
  const inv=[e*i-f*h,c*h-b*i,b*f-c*e,f*g-d*i,a*i-c*g,c*d-a*f,d*h-e*g,b*g-a*h,a*e-b*d].map(n=>n/det),relative=[];
  for(let o=16;o<values.length;o+=16)for(let r=0;r<3;r++)for(let column=0;column<3;column++){
   let n=0;for(let k=0;k<3;k++)n+=inv[r*3+k]*values[o+column*4+k];relative.push(n);
  }return hashNumbers(relative);
 }
 function install(proto){
  if(!proto||proto.__playerAssetQAInstalled)return;Object.defineProperty(proto,'__playerAssetQAInstalled',{value:true});
  for(const [name,wrap]of Object.entries({
   shaderSource:original=>function(shader,source){shaderSources.set(shader,source);return original.call(this,shader,source);},
   attachShader:original=>function(program,shader){const list=attached.get(program)||[];list.push(shader);attached.set(program,list);return original.call(this,program,shader);},
   linkProgram:original=>function(program){const result=original.call(this,program);if((attached.get(program)||[]).some(s=>/uBones\s*\[/.test(shaderSources.get(s)||''))){skinPrograms.add(program);qa.programCount++;}return result;},
   getUniformLocation:original=>function(program,name){const result=original.call(this,program,name);if(result)locations.set(result,name);return result;},
   uniformMatrix4fv:original=>function(location,transpose,values){const result=original.call(this,location,transpose,values);if((locations.get(location)||'').startsWith('uBones')){const p=this.getParameter(this.CURRENT_PROGRAM),u=uniforms.get(p)||{};u.paletteHash=hashNumbers(values);u.jointShape=jointShape(values);u.matrixCount=values.length/16;uniforms.set(p,u);}return result;},
   uniform3fv:original=>function(location,values){const result=original.call(this,location,values),p=this.getParameter(this.CURRENT_PROGRAM);if(p){const u=uniforms.get(p)||{};u[locations.get(location)||'unknown']=[...values];uniforms.set(p,u);}return result;},
   uniform1i:original=>function(location,value){const result=original.call(this,location,value),p=this.getParameter(this.CURRENT_PROGRAM);if(p){const u=uniforms.get(p)||{};u[locations.get(location)||'unknown']=value;uniforms.set(p,u);}return result;},
   texImage2D:original=>function(...args){const result=original.apply(this,args),img=args.length===6?args[5]:null;if(img?.naturalWidth)qa.textureUploads.push({path:new URL(img.src,location.href).pathname,width:img.naturalWidth,height:img.naturalHeight});return result;},
   drawElements:original=>function(...values){const result=original.apply(this,values),p=this.getParameter(this.CURRENT_PROGRAM);if(qa.frame&&skinPrograms.has(p)){qa.frame.skinDraws++;qa.frame.indexCount+=values[1];qa.frame.draws.push({...uniforms.get(p)});}return result;}
  })){const original=proto[name];if(typeof original==='function')proto[name]=wrap(original);}
 }
 install(window.WebGLRenderingContext?.prototype);install(window.WebGL2RenderingContext?.prototype);
 const raf=window.requestAnimationFrame;
 window.requestAnimationFrame=function(callback){return raf.call(window,now=>{
  const frame={skinDraws:0,indexCount:0,draws:[]};qa.frame=frame;callback(now);qa.frame=null;
  if(frame.skinDraws){qa.frames.push(frame);if(qa.frames.length>40)qa.frames.shift();}
  if(qa.capture){
   qa.capture=false;frame.buffers=[];
   for(const {gl,canvas}of qa.contexts){
    const width=gl.drawingBufferWidth,height=gl.drawingBufferHeight;if(!width||!height)continue;
    const pixels=new Uint8Array(width*height*4);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
    let h=2166136261,nonzero=0;for(let k=0;k<pixels.length;k+=4){h=Math.imul(h^pixels[k],16777619);h=Math.imul(h^pixels[k+1],16777619);h=Math.imul(h^pixels[k+2],16777619);if(pixels[k]||pixels[k+1]||pixels[k+2])nonzero++;}
    frame.buffers.push({canvasId:canvas.id,width,height,pixelHash:(h>>>0).toString(16),nonzeroPixels:nonzero,error:gl.getError()});
   }qa.captured=frame;
  }
 });};
})();"""

STATUS = r"""() => {
 const element=document.querySelector('[data-player-asset-state]'),api=window.TribunPlayerAssetStatus,
  validation=api?.validate(window.TribunPlayerAssets);
 return {state:element?.dataset.playerAssetState||null,text:element?.textContent||'',
  details:element?.querySelector('details')?.textContent||'',
  validation:validation?{ok:validation.ok,errors:validation.errors,summary:validation.summary}:null,
  studio:window.TribunPlayerStudio?.getState()||null};
}"""

CANONICAL = r"""() => {
 const api=window.TRIBUN_MATCH_TEST;api.restart();api.advance(2);document.getElementById('playButton').click();
 const state={...api.getState(),motion:null};const seen=new Map();
 const encode=v=>{
  if(v===null)return ['null'];if(v===undefined)return ['undefined'];
  if(typeof v==='number')return ['number',Number.isNaN(v)?'NaN':v===Infinity?'Infinity':v===-Infinity?'-Infinity':Object.is(v,-0)?'-0':v];
  if(typeof v!=='object')return [typeof v,String(v)];
  if(seen.has(v))return ['ref',seen.get(v)];const id=seen.size;seen.set(v,id);
  if(v instanceof Map)return ['map',id,[...v].map(([a,b])=>[encode(a),encode(b)])];
  if(v instanceof Set)return ['set',id,[...v].map(encode)];
  return [Array.isArray(v)?'array':'object',id,Object.keys(v).sort().filter(k=>k!=='contextId').map(k=>[k,encode(v[k])])];
 };return JSON.stringify(encode(state));
}"""


def capture(page):
    page.evaluate('window.__playerAssetQA.captured=null;window.__playerAssetQA.capture=true')
    page.wait_for_function('window.__playerAssetQA.captured!==null')
    return page.evaluate('window.__playerAssetQA.captured')


def image_record(page, canvas, filename):
    name = Path(filename)
    target = RUNTIME / (name.stem + args.capture_suffix + name.suffix)
    page.locator(canvas).screenshot(path=str(target))
    return {'path': str(target.relative_to(ROOT)), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def wait_status(page, wanted):
    page.wait_for_function("state=>document.querySelector('[data-player-asset-state]')?.dataset.playerAssetState===state", arg=wanted)
    status = page.evaluate(STATUS)
    assert status['state'] == wanted
    assert page.locator('[data-player-asset-state]').is_visible(), 'The loading result must be visible on the actual page'
    assert status['text'].strip(), 'Status must be visible text, not a badge-only boolean'
    return status


def prepare(browser, base, route, fault=None):
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.set_default_timeout(30000)
    errors, responses, model_responses = [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('response', lambda r: responses.append({'path': urlsplit(r.url).path, 'status': r.status}))
    page.on('response', lambda r: model_responses.append(r) if urlsplit(r.url).path == MODEL_PATH else None)
    page.add_init_script(INSTRUMENT)
    if route == 'match.html':
        page.add_init_script('window.MATCH_CFG={seed:21,matchMinutes:5};')
    if fault == 'missing':
        page.route('**' + MODEL_PATH, lambda r: r.fulfill(status=404, content_type='application/javascript', body=''))
    elif fault == 'invalid':
        page.route('**' + MODEL_PATH, lambda r: r.fulfill(status=200, content_type='application/javascript', body="window.TribunPlayerAssets={bones:[],lods:[],metadata:{id:'qa-broken'}};"))
    elif fault == 'webgl-unavailable':
        page.add_init_script("const getContext=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /^webgl/.test(kind)?null:getContext.call(this,kind,...args);};")
    elif fault == 'texture-missing':
        page.route('**/assets/player/textures/skin-detail.png', lambda r: r.fulfill(status=404, content_type='image/png', body=''))
    elif fault == 'renderer-error':
        page.add_init_script(r"""(() => {for(const proto of [window.WebGLRenderingContext?.prototype,window.WebGL2RenderingContext?.prototype]){if(!proto)continue;const sources=new WeakMap(),shaderSource=proto.shaderSource,get=proto.getShaderParameter,info=proto.getShaderInfoLog;proto.shaderSource=function(shader,text){sources.set(shader,text);return shaderSource.call(this,shader,text);};proto.getShaderParameter=function(shader,parameter){if(parameter===this.COMPILE_STATUS&&/uBones\s*\[/.test(sources.get(shader)||''))return false;return get.call(this,shader,parameter);};proto.getShaderInfoLog=function(shader){return /uBones\s*\[/.test(sources.get(shader)||'')?'QA forced skinning shader compilation failure':info.call(this,shader);};}})();""")
    page.goto(base + '/' + route)
    if route == 'match.html':
        page.wait_for_function('window.TRIBUN_MATCH_TEST && window.TRIBUN_MATCH_TEST.getState().players?.length===23')
    return page, errors, responses, model_responses


def loaded_bundle(model_responses):
    assert len(model_responses) == 1 and model_responses[0].status == 200
    payload = model_responses[0].body()
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == HASHES['assets/player/player-model-data.js'], 'The browser must execute the packaged model bytes'
    return {'path': MODEL_PATH, 'bytes': len(payload), 'sha256': digest}


with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
base = f'http://127.0.0.1:{port}'
log = (RUNTIME / 'asset-browser-server.log').open('w')
server = subprocess.Popen([sys.executable, str(ROOT / 'start.py'), '--port', str(port)], cwd=ROOT, stdout=log, stderr=log)
normal, failures = [], []
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
        browser = playwright.chromium.launch(executable_path=args.chromium or playwright.chromium.executable_path, headless=True,
            args=['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        match, errors, responses, model_responses = prepare(browser, base, 'match.html')
        status = wait_status(match, 'ready')
        assert status['validation']['ok']
        model_id = status['validation']['summary']['metadata']['id']
        assert model_id, 'The actual loaded model must identify itself'
        match_bundle = loaded_bundle(model_responses)
        match.wait_for_function('window.__playerAssetQA.frames.some(f=>f.skinDraws===23)')
        baseline = match.evaluate(CANONICAL)
        baseline_hash = hashlib.sha256(baseline.encode()).hexdigest()
        match.locator('#camButton').click()
        assert 'Yakın' in match.locator('#camButton').inner_text()
        match.wait_for_timeout(350)
        frame = capture(match)
        assert frame['skinDraws'] == 23 and frame['indexCount'] > 0
        textures = match.evaluate('window.__playerAssetQA.textureUploads')
        assert {r['path'] for r in textures} == {'/assets/player/textures/skin-detail.png', '/assets/player/textures/fabric-detail.png'}
        assert all(r['width'] == 256 and r['height'] == 256 for r in textures)
        assert all(d['uSkinTexture'] == 0 and d['uFabricTexture'] == 1 for d in frame['draws'])
        assert all(d['matrixCount'] == 19 and d['jointShape'] for d in frame['draws'])
        assert frame['buffers'][0]['nonzeroPixels'] > 1000 and frame['buffers'][0]['error'] == 0
        before = match.evaluate('({time:TRIBUN_MATCH_TEST.getState().time,seed:TRIBUN_MATCH_TEST.getState().seed})')
        capture(match)
        assert before == match.evaluate('({time:TRIBUN_MATCH_TEST.getState().time,seed:TRIBUN_MATCH_TEST.getState().seed})')
        shots = [image_record(match, '#stadiumCanvas', 'model-match-close.png')]
        match.set_viewport_size({'width': 390, 'height': 844})
        match.locator('[data-player-asset-state] details').evaluate('(e)=>e.open=true')
        match.wait_for_timeout(100)
        assert not match.evaluate('document.documentElement.scrollWidth>innerWidth+1')
        shots.append(image_record(match, '#stadiumCanvas', 'model-match-mobile.png'))
        assert any(r['path'] == MODEL_PATH and r['status'] == 200 for r in responses)
        assert not errors, errors
        normal.append({'page': 'match.html', 'status': status, 'loadedModelResponse': match_bundle, 'frame': frame, 'physicalStateSHA256': baseline_hash,
            'physicalStateBytes': len(baseline.encode()), 'textureUploads': textures, 'pausedRenderingPreservesTimeAndRNG': True, 'mobile390NoOverflowWithTechnicalDetails': True, 'screenshots': shots, 'scriptErrors': errors})
        match.close()

        studio, errors, responses, model_responses = prepare(browser, base, 'player-studio.html')
        status = wait_status(studio, 'ready')
        assert status['validation']['summary']['metadata']['id'] == model_id
        studio_bundle = loaded_bundle(model_responses)
        assert studio_bundle == match_bundle
        studio.wait_for_function('window.TribunPlayerStudio && window.__playerAssetQA.frames.some(f=>f.skinDraws===1)')
        front = capture(studio)
        assert front['skinDraws'] == 1 and front['buffers'][0]['nonzeroPixels'] > 1000
        shots = [image_record(studio, '#playerCanvas', 'model-studio-full.png')]
        studio.locator('[data-kit="away"]').click()
        away = capture(studio)
        assert away['buffers'][0]['pixelHash'] != front['buffers'][0]['pixelHash']
        assert away['draws'][0]['uShirt'] != front['draws'][0]['uShirt']
        studio.locator('[data-identity="3"]').click()
        identity = capture(studio)
        assert identity['draws'][0]['uSkin'] != away['draws'][0]['uSkin']
        assert identity['buffers'][0]['pixelHash'] != away['buffers'][0]['pixelHash']
        studio.locator('[data-view="face"]').click()
        face = capture(studio)
        assert face['buffers'][0]['pixelHash'] != identity['buffers'][0]['pixelHash']
        shots.append(image_record(studio, '#playerCanvas', 'model-studio-face.png'))
        studio.locator('[data-view="full"]').click()
        studio.select_option('#pose', 'run')
        moving_a = capture(studio)
        studio.wait_for_timeout(300)
        moving_b = capture(studio)
        assert moving_a['draws'][0]['jointShape'] != moving_b['draws'][0]['jointShape'], 'Relative bone transforms must change, not only whole-body translation'
        studio.locator('#pause').click()
        paused_a = capture(studio)
        studio.wait_for_timeout(150)
        paused_b = capture(studio)
        assert paused_a['draws'][0]['paletteHash'] == paused_b['draws'][0]['paletteHash']
        shots.append(image_record(studio, '#playerCanvas', 'model-studio-run.png'))
        studio.set_viewport_size({'width': 390, 'height': 844})
        studio.locator('[data-player-asset-state] details').evaluate('(e)=>e.open=true')
        studio.wait_for_timeout(100)
        assert not studio.evaluate('document.documentElement.scrollWidth>innerWidth+1')
        shots.append(image_record(studio, '#playerCanvas', 'model-studio-mobile.png'))
        assert not errors, errors
        normal.append({'page': 'player-studio.html', 'status': status, 'loadedModelResponse': studio_bundle, 'frontFrame': front, 'awayFrame': away,
            'identityFrame': identity, 'faceFrame': face, 'movingFrames': [moving_a, moving_b], 'pausedPaletteStable': True,
            'sameModelAsMatch': True, 'mobile390NoOverflowWithTechnicalDetails': True, 'screenshots': shots, 'scriptErrors': errors})
        studio.close()

        for fault in ([] if args.preview_only else ['missing', 'invalid', 'renderer-error', 'texture-missing', 'webgl-unavailable']):
            for route in ['match.html', 'player-studio.html']:
                page, errors, responses, model_responses = prepare(browser, base, route, fault)
                status = wait_status(page, 'renderer-error' if fault == 'texture-missing' else fault)
                if fault == 'texture-missing':
                    assert 'skin-detail.png' in status['details']
                elif fault == 'renderer-error':
                    assert 'QA forced skinning shader compilation failure' in status['details']
                elif fault == 'invalid':
                    assert 'BONE_COUNT' in status['details'] and 'LOD_MISSING' in status['details']
                elif fault == 'missing':
                    assert 'assets/player/player-model-data.js' in status['details']
                    assert any(r['path'] == MODEL_PATH and r['status'] == 404 for r in responses)
                assert status['details'].strip(), 'A technical explanation must be inspectable'
                page.locator('[data-player-asset-state] details').evaluate('(e)=>e.open=true')
                assert page.locator('[data-player-asset-state] details').is_visible()
                diagnostic_shot = image_record(page, '[data-player-asset-state]', f'model-failure-{route[:-5]}-{fault}.png')
                assert page.evaluate('window.__playerAssetQA.frames.every(f=>f.skinDraws===0)')
                state_hash = None
                if route == 'match.html':
                    state = page.evaluate(CANONICAL)
                    assert state == baseline, (fault, 'Rendering failure changed actual match state')
                    state_hash = hashlib.sha256(state.encode()).hexdigest()
                else:
                    assert not page.locator('#errorMessage').is_hidden()
                assert not errors, (route, fault, errors)
                failures.append({'page': route, 'fault': fault, 'status': status, 'noSkinnedDraws': True,
                    'physicalStateSHA256': state_hash, 'matchesNormalPhysicalState': route == 'match.html',
                    'scriptErrors': errors, 'resourceErrors': [r for r in responses if r['status'] >= 400], 'diagnosticScreenshot': diagnostic_shot})
                page.close()
        browser.close()
    changed = [p for p, sha in HASHES.items() if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != sha]
    current_assets = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'assets/player').rglob('*') if p.is_file()}
    added_assets = sorted(current_assets - set(ASSET_PATHS))
    assert not changed and not added_assets, f'Sources changed while validating: {changed}; added assets: {added_assets}'
    report = {'scope': 'normal-preview-only' if args.preview_only else 'complete-normal-and-fault-matrix', 'generatedAt': datetime.now(timezone.utc).isoformat(), 'sources': HASHES,
        'method': 'Actual start.py local launcher and Chromium SwiftShader. Reads WebGL skin shader drawElements calls, uploaded bone palettes and framebuffer pixels inside requestAnimationFrame; only failure cases override asset responses, shader compile status, texture responses or WebGL creation. Relative-bone signatures remove the root basis. No engine or animation methods are mocked.',
        'physicalEqualityScope': 'Canonical complete serializable match snapshot after restart and 2 seconds, preserving Maps/Sets/references/numeric edge cases; excludes immutable motion module and opaque launch contextId only. Full canonical strings compare exactly before their SHA256 is recorded.',
        'limits': 'Confirms bundle identity, actual skinning, material/control response, pose deformation and handled loading failures. Screenshots require human visual inspection; these checks do not certify human likeness, animation quality or real-device FPS.',
        'normal': normal, 'failures': failures, 'verified': True}
    target = RUNTIME / 'player-asset-preview.json' if args.preview_only else ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'verified': True, 'normalPages': len(normal), 'failureCases': len(failures), 'modelId': model_id,
        'screenshots': [s['path'] for r in normal for s in r['screenshots']]}))
finally:
    server.terminate()
    server.wait(timeout=10)
    log.close()
