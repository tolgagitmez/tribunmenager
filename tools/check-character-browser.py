"""Character anatomy and GPU skinning evidence, plus handled loading failures.

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
parser.add_argument('--output', default='docs/validation/character-browser.json')
parser.add_argument('--chromium', default=shutil.which('chromium'))
parser.add_argument('--capture-suffix', default='', help='Suffix for screenshot filenames')
parser.add_argument('--preview-only', action='store_true', help='Normal-page screenshots only; saves a scoped preview report under work/stage14')
parser.add_argument('--publish-previews', action='store_true', help='After a complete successful run, copy the captures into docs/previews and reference those public artifacts')
args = parser.parse_args()
assert not (args.preview_only and args.publish_previews), 'Review preview captures before publishing a complete run'
RUNTIME = ROOT / 'work/stage14'
RUNTIME.mkdir(parents=True, exist_ok=True)

SOURCE_PATHS = [
    'start.py', 'player-renderer.js', 'player-skinning.js', 'player-asset-status.js', 'scene3d.js',
    'match-animation-bridge.js', 'character-palette-constraints.js', 'character-blend-controller.js', 'animation-lab.css',
    'humanoid-rig-procedural.js', 'player-renderer-procedural.js',
    'player-studio-procedural.js', 'player-studio-procedural.html',
    'match3d.js', 'match.html', 'player-studio.js', 'player-studio.html', 'animation-lab.js', 'animation-lab.html',
    'humanoid-rig.js', 'animation-scenarios.js', 'player-studio.css', 'ui-shell.js', 'ui-shell.css', 'match3d.css',
    'football-sim.js', 'match-rules.js', 'referee-laws.js', 'pitch-laws.js',
    'player-perception.js', 'team-intent.js', 'tactics.js', 'club-data.js',
    'player-model.js', 'player-model-profiles.js', 'player-model-profiles.json',
    'attack-diagnostics.js', 'attack-analysis-ui.js', 'transfer-client.js', 'match-config.js',
    'tools/check-character-browser.py', 'tools/build-player-assets.py',
]
ASSET_PATHS = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'assets/player').rglob('*')) if p.is_file()]
SOURCE_PATHS += ASSET_PATHS
assert (ROOT / 'assets/player/player-model-data.js').is_file(), 'Real model bundle is required; no fallback-only pass is allowed'
HASHES = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCE_PATHS}
MODEL_PATH = '/assets/player/player-model-data.js'

INSTRUMENT = r"""(() => {
 const qa=window.__playerAssetQA={frames:[],frame:null,contexts:[],capture:false,captured:null,programCount:0,programs:[],textureUploads:[]};
 const originalContext=HTMLCanvasElement.prototype.getContext;
 HTMLCanvasElement.prototype.getContext=function(type,...rest){
  const gl=originalContext.call(this,type,...rest);
  if(gl&&/^webgl/.test(type)&&!qa.contexts.some(c=>c.gl===gl))qa.contexts.push({gl,canvas:this});
  return gl;
 };
 const shaderSources=new WeakMap(),attached=new WeakMap(),skinPrograms=new WeakSet(),locations=new WeakMap(),uniforms=new WeakMap();
 const hashNumbers=values=>{let h=2166136261;for(const n of values){h=Math.imul(h^(Number.isFinite(n)?Math.round(n*1000):0),16777619);}return (h>>>0).toString(16);};
 const multiply=(a,b)=>[a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
 const conjugate=q=>[-q[0],-q[1],-q[2],q[3]];
 function jointShape(real,dual){
  if(real.length!==76||dual.length!==76)return null;
  const translation=i=>multiply(dual.slice(i,i+4),conjugate(real.slice(i,i+4))).slice(0,3).map(n=>2*n),root=translation(0),inverseRoot=conjugate(real.slice(0,4)),out=[];
  for(let i=0;i<real.length;i+=4){
   const q=multiply(inverseRoot,real.slice(i,i+4)),sign=q[3]<0?-1:1;
   out.push(...q.map(n=>n*sign));
   const offset=translation(i).map((n,j)=>n-root[j]),relative=multiply(multiply(inverseRoot,[...offset,0]),real.slice(0,4));
   out.push(...relative.slice(0,3));
  }return hashNumbers(out);
 }
 function quaternionShape(values){
  const out=[],a=[-values[0],-values[1],-values[2],values[3]];
  for(let i=0;i<values.length;i+=4){
   const b=values.slice(i,i+4),q=multiply(a,b);
   const sign=q[3]<0?-1:1;for(const n of q)out.push(n*sign);
  }return hashNumbers(out);
 }
 const realPalettes=new WeakMap();
 function install(proto){
  if(!proto||proto.__playerAssetQAInstalled)return;Object.defineProperty(proto,'__playerAssetQAInstalled',{value:true});
  for(const [name,wrap]of Object.entries({
   shaderSource:original=>function(shader,source){shaderSources.set(shader,source);return original.call(this,shader,source);},
   attachShader:original=>function(program,shader){const list=attached.get(program)||[];list.push(shader);attached.set(program,list);return original.call(this,program,shader);},
   linkProgram:original=>function(program){
    const result=original.call(this,program),sources=(attached.get(program)||[]).map(s=>shaderSources.get(s)||'');
    if(sources.some(s=>/uniform\s+vec4\s+uBoneReal\s*\[\s*19\s*\]/.test(s)&&/uniform\s+vec4\s+uBoneDual\s*\[\s*19\s*\]/.test(s))&&this.getProgramParameter(program,this.LINK_STATUS)){
     const active=[];for(let i=0;i<this.getProgramParameter(program,this.ACTIVE_UNIFORMS);i++){const u=this.getActiveUniform(program,i);active.push({name:u.name,size:u.size,type:u.type});}
     const metadata={activeUniforms:active,real19:active.some(u=>u.name==='uBoneReal[0]'&&u.size===19&&u.type===this.FLOAT_VEC4),dual19:active.some(u=>u.name==='uBoneDual[0]'&&u.size===19&&u.type===this.FLOAT_VEC4),activeLegacyBones:active.some(u=>/^uBones(?:\[|$)/.test(u.name))};
     skinPrograms.add(program);qa.programs.push(metadata);qa.programCount++;
    }return result;
   },
   getUniformLocation:original=>function(program,name){const result=original.call(this,program,name);if(result)locations.set(result,name);return result;},
   uniformMatrix4fv:original=>function(location,transpose,values){const result=original.call(this,location,transpose,values);if((locations.get(location)||'').startsWith('uBones')){const p=this.getParameter(this.CURRENT_PROGRAM),u=uniforms.get(p)||{};u.legacyBoneUpload=values.length;uniforms.set(p,u);}return result;},
   uniform4fv:original=>function(location,values){
    const result=original.call(this,location,values),p=this.getParameter(this.CURRENT_PROGRAM),name=locations.get(location)||'';
    if(p&&name.startsWith('uBoneReal')){
     const u=uniforms.get(p)||{};realPalettes.set(p,[...values]);u.skinning='dual-quaternion';u.realCount=values.length/4;u.realFloatCount=values.length;u.realHash=hashNumbers(values);u.jointRotation=quaternionShape(values);u.maxQuaternionNormError=0;u.realQuaternions=[...values];
     for(let i=0;i<values.length;i+=4)u.maxQuaternionNormError=Math.max(u.maxQuaternionNormError,Math.abs(Math.hypot(...values.slice(i,i+4))-1));uniforms.set(p,u);
    }else if(p&&name.startsWith('uBoneDual')){
     const u=uniforms.get(p)||{},real=realPalettes.get(p);u.dualCount=values.length/4;u.dualFloatCount=values.length;u.dualHash=hashNumbers(values);u.paletteHash=u.realHash+':'+u.dualHash;u.maxRealDualDot=0;u.finiteDualValues=[...values].every(Number.isFinite);u.dualQuaternions=[...values];u.jointShape=real?jointShape(real,[...values]):null;
     if(real)for(let i=0;i<values.length;i+=4)u.maxRealDualDot=Math.max(u.maxRealDualDot,Math.abs(real[i]*values[i]+real[i+1]*values[i+1]+real[i+2]*values[i+2]+real[i+3]*values[i+3]));uniforms.set(p,u);
    }return result;
   },
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
  if(qa.capture&&frame.skinDraws){
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


def assert_palette(frame):
    assert frame['skinDraws'] > 0 and frame['draws']
    for draw in frame['draws']:
        assert draw['skinning'] == 'dual-quaternion'
        assert draw['realCount'] == draw['dualCount'] == 19
        assert draw['realFloatCount'] == draw['dualFloatCount'] == 76
        assert not draw.get('legacyBoneUpload'), 'Legacy matrix skinning upload must not remain active'
        assert draw['jointShape'] and draw['paletteHash']
        assert draw['maxQuaternionNormError'] < 2e-6, draw
        assert draw['maxRealDualDot'] < 1e-4 and draw['finiteDualValues'], draw


def skin_programs(page):
    programs = page.evaluate('window.__playerAssetQA.programs')
    assert programs and all(p['real19'] and p['dual19'] and not p['activeLegacyBones'] for p in programs), programs
    return programs


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
        page.add_init_script(r"""(() => {for(const proto of [window.WebGLRenderingContext?.prototype,window.WebGL2RenderingContext?.prototype]){if(!proto)continue;const sources=new WeakMap(),shaderSource=proto.shaderSource,get=proto.getShaderParameter,info=proto.getShaderInfoLog;proto.shaderSource=function(shader,text){sources.set(shader,text);return shaderSource.call(this,shader,text);};proto.getShaderParameter=function(shader,parameter){if(parameter===this.COMPILE_STATUS&&/uBoneReal\s*\[/.test(sources.get(shader)||''))return false;return get.call(this,shader,parameter);};proto.getShaderInfoLog=function(shader){return /uBoneReal\s*\[/.test(sources.get(shader)||'')?'QA forced skinning shader compilation failure':info.call(this,shader);};}})();""")
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
log = (RUNTIME / 'character-browser-server.log').open('w')
server = subprocess.Popen([sys.executable, str(ROOT / 'start.py'), '--port', str(port)], cwd=ROOT, stdout=log, stderr=log)
normal, stresses, failures = [], [], []
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
        browser_version = browser.version
        match, errors, responses, model_responses = prepare(browser, base, 'match.html')
        status = wait_status(match, 'ready')
        assert status['validation']['ok']
        model_id = status['validation']['summary']['metadata']['id']
        assert model_id, 'The actual loaded model must identify itself'
        match_bundle = loaded_bundle(model_responses)
        match.wait_for_function('window.__playerAssetQA.frames.some(f=>f.skinDraws===23)')
        match_programs = skin_programs(match)
        graphics = match.evaluate("""() => window.__playerAssetQA.contexts.map(({gl,canvas})=>{
            const debug=gl.getExtension('WEBGL_debug_renderer_info');
            return {canvasId:canvas.id,version:gl.getParameter(gl.VERSION),renderer:gl.getParameter(gl.RENDERER),
                unmaskedRenderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):null,
                shadingLanguage:gl.getParameter(gl.SHADING_LANGUAGE_VERSION)};
        })""")
        match.locator('#camButton').click()
        assert 'Yakın' in match.locator('#camButton').inner_text()
        # Camera easing uses live frame delta; settle it through the real UI
        # before pausing the deterministic canonical match snapshot.
        match.wait_for_timeout(1400)
        baseline = match.evaluate(CANONICAL)
        baseline_hash = hashlib.sha256(baseline.encode()).hexdigest()
        assert 'Yakın' in match.locator('#camButton').inner_text()
        frame = capture(match)
        assert 0 < frame['skinDraws'] <= 23 and frame['indexCount'] > 0
        textures = match.evaluate('window.__playerAssetQA.textureUploads')
        assert {r['path'] for r in textures} == {'/assets/player/textures/skin-detail.png', '/assets/player/textures/fabric-detail.png'}
        assert all(r['width'] == 256 and r['height'] == 256 for r in textures)
        assert all(d['uSkinTexture'] == 0 and d['uFabricTexture'] == 1 for d in frame['draws'])
        assert_palette(frame)
        assert frame['buffers'][0]['nonzeroPixels'] > 1000 and frame['buffers'][0]['error'] == 0
        before = match.evaluate('({time:TRIBUN_MATCH_TEST.getState().time,seed:TRIBUN_MATCH_TEST.getState().seed})')
        capture(match)
        assert before == match.evaluate('({time:TRIBUN_MATCH_TEST.getState().time,seed:TRIBUN_MATCH_TEST.getState().seed})')
        shots = [image_record(match, '#stadiumCanvas', 'character-match-close.png')]
        fast_stats = match.evaluate('TRIBUN_MATCH_TEST.performanceStats()')
        bridge_stats = match.evaluate('TRIBUN_MATCH_TEST.animationStats()')
        assert fast_stats['mode'] == 'performance' and fast_stats['players']['active'] == 23
        assert fast_stats['players']['players'] + fast_stats['players']['culled'] == 23
        assert fast_stats['players']['fast'] == frame['skinDraws'] == fast_stats['players']['players'] and fast_stats['players']['detailed'] == 0
        assert bridge_stats['enabled'] and bridge_stats['players'] == 23, bridge_stats
        match.locator('#qualityButton').click()
        match.wait_for_function("TRIBUN_MATCH_TEST.performanceStats().mode==='quality'")
        quality_frame = capture(match)
        assert_palette(quality_frame)
        quality_stats = match.evaluate('TRIBUN_MATCH_TEST.performanceStats()')
        assert quality_stats['players']['active'] == 23
        assert quality_stats['players']['players'] + quality_stats['players']['culled'] == 23
        assert quality_stats['players']['detailed'] == quality_frame['skinDraws'] == frame['skinDraws'] and quality_stats['players']['fast'] == 0
        assert quality_frame['indexCount'] > frame['indexCount'], 'Actual GPU submissions must use runtime reduced LODs in performance mode'
        assert quality_stats['canvas'][0] > fast_stats['canvas'][0]
        assert 'FPS' in match.locator('#qualityButton').inner_text()
        match.locator('#qualityButton').click()
        match.wait_for_function("TRIBUN_MATCH_TEST.performanceStats().mode==='balanced'")
        balanced_frame = capture(match)
        assert_palette(balanced_frame)
        balanced_stats = match.evaluate('TRIBUN_MATCH_TEST.performanceStats()')
        match.locator('#qualityButton').click()
        match.wait_for_function("TRIBUN_MATCH_TEST.performanceStats().mode==='performance'")
        capture(match)
        performance_checks = {'defaultPerformance': fast_stats, 'quality': quality_stats, 'balanced': balanced_stats,
            'performanceIndexCount': frame['indexCount'], 'qualityIndexCount': quality_frame['indexCount'],
            'matchBridge': bridge_stats, 'qualityButtonModesAndFPSLabel': True,
            'scope': 'Confirms real UI profile, drawing-buffer and GPU LOD behavior in Chromium SwiftShader; not a real-device FPS measurement.'}
        match.set_viewport_size({'width': 390, 'height': 844})
        match.locator('[data-player-asset-state] details').evaluate('(e)=>e.open=true')
        match.wait_for_timeout(100)
        assert not match.evaluate('document.documentElement.scrollWidth>innerWidth+1')
        shots.append(image_record(match, '#stadiumCanvas', 'character-match-mobile.png'))
        assert any(r['path'] == MODEL_PATH and r['status'] == 200 for r in responses)
        assert not errors, errors
        normal.append({'page': 'match.html', 'status': status, 'loadedModelResponse': match_bundle, 'frame': frame, 'physicalStateSHA256': baseline_hash,
            'physicalStateBytes': len(baseline.encode()), 'activeSkinPrograms': match_programs, 'textureUploads': textures,
            'performanceAndLOD': performance_checks, 'pausedRenderingPreservesTimeAndRNG': True,
            'mobile390NoOverflowWithTechnicalDetails': True, 'screenshots': shots, 'scriptErrors': errors})
        match.close()

        studio, errors, responses, model_responses = prepare(browser, base, 'player-studio.html')
        status = wait_status(studio, 'ready')
        assert status['validation']['summary']['metadata']['id'] == model_id
        studio_bundle = loaded_bundle(model_responses)
        assert studio_bundle == match_bundle
        studio.wait_for_function('window.TribunPlayerStudio && window.__playerAssetQA.frames.some(f=>f.skinDraws===1)')
        studio_programs = skin_programs(studio)
        front = capture(studio)
        assert_palette(front)
        assert front['skinDraws'] == 1 and front['buffers'][0]['nonzeroPixels'] > 1000
        shots = [image_record(studio, '#playerCanvas', 'character-studio-full.png')]
        assert studio.evaluate('TribunPlayerStudio.getState().mode') == 'idle'
        for _ in range(5):
            studio.locator('#playerCanvas').press('ArrowLeft')
        front_camera = capture(studio)
        assert front_camera['buffers'][0]['pixelHash'] != front['buffers'][0]['pixelHash']
        shots.append(image_record(studio, '#playerCanvas', 'character-studio-front.png'))
        for _ in range(12):
            studio.locator('#playerCanvas').press('ArrowRight')
        side_camera = capture(studio)
        assert side_camera['buffers'][0]['pixelHash'] != front_camera['buffers'][0]['pixelHash']
        shots.append(image_record(studio, '#playerCanvas', 'character-studio-side.png'))
        studio.locator('[data-view="face"]').click()
        idle_face = capture(studio)
        assert_palette(idle_face)
        shots.append(image_record(studio, '#playerCanvas', 'character-studio-face.png'))
        studio.locator('[data-view="full"]').click()
        capture(studio)
        studio.locator('[data-kit="away"]').click()
        away = capture(studio)
        assert_palette(away)
        assert away['buffers'][0]['pixelHash'] != front['buffers'][0]['pixelHash']
        assert away['draws'][0]['uShirt'] != front['draws'][0]['uShirt']
        studio.locator('[data-identity="3"]').click()
        identity = capture(studio)
        assert_palette(identity)
        assert identity['draws'][0]['uSkin'] != away['draws'][0]['uSkin']
        assert identity['buffers'][0]['pixelHash'] != away['buffers'][0]['pixelHash']
        studio.locator('[data-view="face"]').click()
        face = capture(studio)
        assert face['buffers'][0]['pixelHash'] != identity['buffers'][0]['pixelHash']
        shots.append(image_record(studio, '#playerCanvas', 'character-studio-identity-face.png'))
        studio.locator('[data-view="full"]').click()
        studio.select_option('#pose', 'run')
        moving_a = capture(studio)
        assert_palette(moving_a)
        studio.wait_for_timeout(300)
        moving_b = capture(studio)
        assert_palette(moving_b)
        assert moving_a['draws'][0]['jointShape'] != moving_b['draws'][0]['jointShape'], 'Relative bone transforms must change, not only whole-body translation'
        studio.locator('#pause').click()
        paused_a = capture(studio)
        studio.wait_for_timeout(150)
        paused_b = capture(studio)
        assert paused_a['draws'][0]['paletteHash'] == paused_b['draws'][0]['paletteHash']
        shots.append(image_record(studio, '#playerCanvas', 'character-studio-run.png'))
        studio.set_viewport_size({'width': 390, 'height': 844})
        studio.locator('[data-player-asset-state] details').evaluate('(e)=>e.open=true')
        studio.wait_for_timeout(100)
        assert not studio.evaluate('document.documentElement.scrollWidth>innerWidth+1')
        shots.append(image_record(studio, '#playerCanvas', 'character-studio-mobile.png'))
        assert not errors, errors
        normal.append({'page': 'player-studio.html', 'status': status, 'loadedModelResponse': studio_bundle, 'frontFrame': front, 'awayFrame': away,
            'activeSkinPrograms': studio_programs, 'identityFrame': identity, 'idleFaceFrame': idle_face,
            'faceFrame': face, 'movingFrames': [moving_a, moving_b], 'pausedPaletteStable': True,
            'keyboardCameraControlsVerified': True, 'sameModelAsMatch': True,
            'mobile390NoOverflowWithTechnicalDetails': True, 'screenshots': shots, 'scriptErrors': errors})
        studio.close()

        workshop, errors, responses, model_responses = prepare(browser, base, 'animation-lab.html')
        workshop_status = wait_status(workshop, 'ready')
        workshop_bundle = loaded_bundle(model_responses)
        assert workshop_bundle == match_bundle
        workshop.wait_for_function('window.__playerAssetQA.frames.some(f=>f.skinDraws===1)')
        workshop_programs = skin_programs(workshop)
        for mode, at in [('run', 1.2), ('turn', 2.9), ('pass', .31), ('shoot', .38), ('dive-left', .34), ('dive-right', .34)]:
            workshop.locator('[data-mode="' + mode + '"]').click()
            actual_at = workshop.locator('#timeline').evaluate('(element,time)=>{element.value=time;element.dispatchEvent(new Event("input",{bubbles:true}));return Number(element.value);}', at)
            assert workshop.locator('[data-mode="' + mode + '"]').get_attribute('aria-pressed') == 'true'
            assert abs(actual_at - at) <= 1 / 120 + 1e-8, 'Range input must seek the nearest supported animation frame'
            assert abs(float(workshop.locator('#timeline').input_value()) - actual_at) < 1e-8
            assert workshop.locator('#timeStatus').inner_text() == f'{actual_at:.2f} sn'
            assert workshop.locator('#play').inner_text() == 'Devam et'
            # The pose remains frozen; let the real camera ease to the newly
            # sought player position before recording the rendered evidence.
            workshop.wait_for_timeout(1400)
            frame = capture(workshop)
            assert frame['skinDraws'] == 1
            assert_palette(frame)
            assert frame['buffers'][0]['nonzeroPixels'] > 1000 and frame['buffers'][0]['error'] == 0
            frozen_a = capture(workshop)
            workshop.wait_for_timeout(80)
            frozen_b = capture(workshop)
            assert frozen_a['draws'][0]['paletteHash'] == frozen_b['draws'][0]['paletteHash']
            screenshot = image_record(workshop, '#animationCanvas', 'character-stress-' + mode + '.png')
            stresses.append({'page': 'animation-lab.html', 'mode': mode, 'requestedTimelineSeconds': at, 'timelineSeconds': actual_at,
                'frame': frame, 'activeSkinPrograms': workshop_programs, 'pausedPaletteStable': True, 'screenshot': screenshot})
        assert len({s['frame']['draws'][0]['jointShape'] for s in stresses}) == len(stresses), 'Stress controls must produce distinct relative joint shapes'
        assert len({s['frame']['buffers'][0]['pixelHash'] for s in stresses}) == len(stresses), 'Stress poses must change the real framebuffer'
        assert not errors, errors
        assert workshop.locator('#renderMode').inner_text() == workshop.locator('[data-player-asset-state] summary').inner_text()
        normal.append({'page': 'animation-lab.html', 'status': workshop_status, 'loadedModelResponse': workshop_bundle,
            'activeSkinPrograms': workshop_programs, 'sameModelAsMatch': True,
            'modeButtonsAndPausedTimelineVerified': True, 'screenshots': [s['screenshot'] for s in stresses], 'scriptErrors': errors})
        workshop.close()

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
                diagnostic_shot = image_record(page, '[data-player-asset-state]', f'character-failure-{route[:-5]}-{fault}.png')
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
        'browser': {'name': 'Chromium', 'version': browser_version, 'headless': True, 'graphics': graphics},
        'method': 'Actual start.py local launcher and Chromium SwiftShader. Inspects linked active DQS vec4 uniforms (19 real and 19 dual, no active legacy uBones), reads real drawElements calls, records both uploaded 76-float arrays and framebuffer pixels inside requestAnimationFrame. Relative DQ signatures remove root rotation and translation. Only failure cases override asset responses, shader compile status, texture responses or WebGL creation. Workshop stress captures use existing mode buttons and paused timeline controls; no engine, rig or animation methods are mocked. Match graphics button checks profile, drawing-buffer and actual index-count changes; source hashes also guard the match animation bridge and procedural lab.',
        'physicalEqualityScope': 'Canonical complete serializable match snapshot after restart and 2 seconds, preserving Maps/Sets/references/numeric edge cases; excludes immutable motion module and opaque launch contextId only. Full canonical strings compare exactly before their SHA256 is recorded.',
        'limits': 'Confirms bundle identity, actual skinning, material/control response, pose deformation and handled loading failures. Screenshots require human visual inspection; these checks do not certify human likeness, animation quality or real-device FPS.',
        'normal': normal, 'stressPoses': stresses, 'failures': failures, 'verified': True}
    if args.publish_previews:
        public = ROOT / 'docs/previews'
        public.mkdir(parents=True, exist_ok=True)
        def publish(value):
            if isinstance(value, dict):
                if value.get('path', '').startswith('work/stage14/character-') and value['path'].endswith('.png') and value.get('sha256'):
                    source = ROOT / value['path']
                    destination = public / source.name
                    shutil.copyfile(source, destination)
                    assert hashlib.sha256(destination.read_bytes()).hexdigest() == value['sha256']
                    value['path'] = destination.relative_to(ROOT).as_posix()
                for child in value.values():
                    publish(child)
            elif isinstance(value, list):
                for child in value:
                    publish(child)
        publish(report)
    target = RUNTIME / 'character-preview.json' if args.preview_only else ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'verified': True, 'normalPages': len(normal), 'stressPoses': len(stresses), 'failureCases': len(failures), 'modelId': model_id,
        'screenshots': [s['path'] for r in normal for s in r['screenshots']]}))
finally:
    server.terminate()
    server.wait(timeout=10)
    log.close()
