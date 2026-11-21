import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { createStandardAssetLoader } from './gltf-asset-loader.mjs';
import { createCustomRuntimeAdapter } from './gltf-runtime-adapter.mjs';

// This lab shares the official parse path. Only the drawing backend changes.
const $ = id => document.getElementById(id);
const manual = new URLSearchParams(location.search).get('manual') === '1';
const loader = createStandardAssetLoader({ THREE, GLTFLoader });
const DEFAULT_URL = 'assets/interchange/footballer.blender.glb';
const keys = ['custom', 'three'];
const states = Object.fromEntries(keys.map(key => [key, {
  backend: key, canvas: $(`${key}-canvas`), status: 'idle', stage: 'idle', generation: 0,
  count: 1, actors: [], clip: 'idle', time: 0, frozen: false, error: null,
  asset: null, metadata: null, renderer: null, gl: null, adapter: null, lastFrame: null,
  features: key === 'custom'
    ? { parser: 'Three.js GLTFLoader r180 (shared)', webgl: 1, skinning: 'dual quaternion', materials: 'opaque base color + roughness; custom PBR lighting', adaptiveQuality: false, lod: false, geometryShared: true, proceduralAppearance: false }
    : { parser: 'Three.js GLTFLoader r180 (shared)', webgl: 2, skinning: 'linear blend skinning', materials: 'official Three.js MeshStandardMaterial / glTF PBR', adaptiveQuality: false, lod: false, geometryShared: true, proceduralAppearance: false }
}]));
const ui = { clip: 'idle', time: 0, count: 1, view: 'full', playing: !manual, automatic: !manual, raf: 0, lastTick: 0, lastMetrics: 0, benchmarking: false };
let dimensions = { width: 600, height: 560, pixelRatio: 1 };

function backendState(key) {
  if (!states[key]) throw new TypeError(`Unknown backend: ${key}`);
  return states[key];
}
function errorRecord(error, source, stage = 'load') {
  return { name: error?.name || 'Error', message: error?.message || String(error), stage: error?.stage || stage, url: error?.url || source || '', code: error?.code || 'INTEROP_ERROR' };
}
function sourceName(url) {
  try { return new URL(url, location.href).pathname.split('/').pop(); } catch { return String(url); }
}
function absoluteSource(url) { try { return new URL(url, location.href).href; } catch { return String(url); } }
function updateStatus(state) {
  const status = $(`${state.backend}-status`), message = $(`${state.backend}-message`);
  status.dataset.state = state.status;
  status.textContent = ({ idle: 'Bekliyor', loading: 'Yükleniyor', ready: 'Hazır', error: 'Açılamadı' })[state.status] || state.status;
  message.hidden = state.status === 'ready';
  if (state.status === 'loading') message.textContent = `${sourceName(state.url)} · ${state.stage}`;
  else if (state.status === 'error') message.textContent = `${state.error.stage}: ${state.error.message}`;
  else message.textContent = manual ? 'Manuel ölçüm modu · model yüklenmedi.' : 'Model bekleniyor…';
  updateDiagnostics(state);
}
function updateDiagnostics(state) {
  const m = state.metadata, lines = [
    `Durum: ${state.status} / ${state.stage}`,
    `Kaynak: ${state.url ? absoluteSource(state.url) : '—'}`,
    `Çizim tamponu: ${state.canvas.width} × ${state.canvas.height} px`,
    `Çizici: ${state.backend === 'custom' ? 'Mevcut WebGL 1 / DQS / tam kalite' : `Three.js r${THREE.REVISION} / WebGL 2 / LBS`}`
  ];
  if (m) {
    lines.push(`Model: ${m.vertices.toLocaleString('tr-TR')} köşe · ${m.triangles.toLocaleString('tr-TR')} üçgen`,
      `İskelet: ${m.jointCount} eklem · ${m.skinnedMeshCount} derili ağ`,
      `Malzeme: ${m.materialCount} · çözülen doku: ${m.textureCount}`,
      `Klipler: ${m.clips.map(clip => `${clip.name} (${clip.duration.toFixed(3)} s)`).join(', ')}`,
      `Sahne: ${state.count} futbolcu · ${state.clip} / ${state.time.toFixed(3)} s`,
      `Ortak yükleme/ayrıştırma: ${state.loadTimes?.sharedLoadMs.toFixed(2) || '—'} ms`,
      `Çizici hazırlığı: ${state.loadTimes?.backendSetupMs.toFixed(2) || '—'} ms`,
      `Harici kaynaklar: ${(m.resourcePaths || []).join(', ')}`);
    if (state.adapter?.warnings?.length) lines.push(`Köprü notu: ${state.adapter.warnings.join('; ')}`);
    if (m.warnings?.length) lines.push(`Kaynak notu: ${m.warnings.join('; ')}`);
  }
  if (state.lastFrame) lines.push(`Son CPU güncellemesi: ${state.lastFrame.cpuUpdateMs.toFixed(3)} ms`, `Son gönderim: ${state.lastFrame.submitMs.toFixed(3)} ms`, `GPU bitişi beklenen kare: ${state.lastFrame.completedFrameMs === null ? 'bu karede ölçülmedi' : `${state.lastFrame.completedFrameMs.toFixed(3)} ms`}`);
  if (state.error) lines.push(`Hata: ${state.error.code}`, `Aşama: ${state.error.stage}`, `Dosya: ${state.error.url}`, state.error.message);
  $(`${state.backend}-diagnostics`).textContent = lines.join('\n');
}
function updateMetrics(state) {
  const stats = renderStats(state), timing = state.lastFrame;
  $(`${state.backend}-cost`).innerHTML = timing ? `${(timing.completedFrameMs ?? timing.submitMs).toFixed(2)} <small>ms${timing.completedFrameMs === null ? ' gönderim' : ''}</small>` : '— <small>ms</small>';
  $(`${state.backend}-draws`).textContent = state.status === 'ready' ? String(stats.drawCalls) : '—';
  $(`${state.backend}-triangles`).textContent = state.status === 'ready' ? stats.triangles.toLocaleString('tr-TR') : '—';
  updateDiagnostics(state);
}

function shader(gl, type, source) {
  const result = gl.createShader(type); gl.shaderSource(result, source); gl.compileShader(result);
  if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) { const message = gl.getShaderInfoLog(result); gl.deleteShader(result); throw new Error(message); }
  return result;
}
function createCustomFloor(gl) {
  const program = gl.createProgram(), shaders = [
    shader(gl, gl.VERTEX_SHADER, 'attribute vec3 aPosition; uniform mat4 uVP; void main(){ gl_Position=uVP*vec4(aPosition,1.); }'),
    shader(gl, gl.FRAGMENT_SHADER, 'precision highp float; void main(){ gl_FragColor=vec4(0.0823529412,0.1568627451,0.2,1.); }')
  ];
  for (const item of shaders) gl.attachShader(program, item);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-60,-.015,-60,60,-.015,-60,60,-.015,60,-60,-.015,-60,60,-.015,60,-60,-.015,60]), gl.STATIC_DRAW);
  return { program, shaders, buffer, position: gl.getAttribLocation(program, 'aPosition'), vp: gl.getUniformLocation(program, 'uVP') };
}
function initBackend(state) {
  if (state.initialized && state.gl && !state.gl.isContextLost()) return;
  if (state.backend === 'custom') {
    const gl = state.canvas.getContext('webgl', { antialias: true, alpha: false, preserveDrawingBuffer: true });
    if (!gl) throw Object.assign(new Error('WebGL 1 bağlamı açılamadı. Diğer çiziciyi kullanabilirsiniz.'), { stage: 'context' });
    state.gl = gl; state.floor = createCustomFloor(gl);
  } else {
    const gl = state.canvas.getContext('webgl2', { antialias: true, alpha: false, preserveDrawingBuffer: true });
    if (!gl) throw Object.assign(new Error('WebGL 2 bağlamı açılamadı. Mevcut WebGL önizlemesini kullanabilirsiniz.'), { stage: 'context' });
    state.gl = gl;
    state.renderer = new THREE.WebGLRenderer({ canvas: state.canvas, context: gl, antialias: true, alpha: false, preserveDrawingBuffer: true });
    state.renderer.setPixelRatio(dimensions.pixelRatio); state.renderer.setSize(dimensions.width, dimensions.height, false);
    state.renderer.outputColorSpace = THREE.SRGBColorSpace; state.renderer.toneMapping = THREE.ACESFilmicToneMapping; state.renderer.toneMappingExposure = 1.03;
    state.renderer.setClearColor('#101b24', 1); state.renderer.shadowMap.enabled = false;
    state.stageScene = new THREE.Scene();
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(120, 120), new THREE.MeshBasicMaterial({ color: '#152833', toneMapped: false }));
    floor.rotation.x = -Math.PI / 2; floor.position.y = -.015; floor.name = 'comparison-floor'; state.floorMesh = floor; state.stageScene.add(floor);
    const sky = new THREE.Color().setRGB(.72 * .34, .81 * .34, .34), ground = new THREE.Color().setRGB(.72 * .12, .81 * .12, .12);
    state.stageScene.add(new THREE.HemisphereLight(sky, ground, 1));
    for (const [position, color] of [[[3.5,5,4],[3.2,3.05,2.85]],[[-4,2,2],[.65,.82,1.1]],[[-2,3,-4],[.7,.82,1.05]]]) {
      const light = new THREE.DirectionalLight(new THREE.Color().setRGB(...color), 1); light.position.set(...position); state.stageScene.add(light);
    }
  }
  state.camera = new THREE.PerspectiveCamera(31, state.canvas.width / state.canvas.height, .025, 160);
  state.initialized = true;
  state.canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault(); state.controller?.abort(new Error('Graphics context lost'));
    state.status = 'error'; state.stage = 'context'; state.error = errorRecord(new Error('Grafik bağlamı kesildi; sayfayı yeniden yükleyin.'), state.url, 'context'); updateStatus(state);
  });
}
function removeActors(state) {
  const skeletons = new Set();
  for (const actor of state.actors) {
    actor.mixer.stopAllAction(); actor.mixer.uncacheRoot(actor.scene);
    actor.scene.removeFromParent(); actor.scene.traverse(object => { if (object.skeleton) skeletons.add(object.skeleton); });
  }
  for (const skeleton of skeletons) skeleton.dispose();
  state.actors = [];
}
function releaseAsset(state) {
  removeActors(state);
  if (state.backend === 'custom') { state.renderer?.dispose(); state.renderer = null; }
  state.asset?.dispose(); state.asset = null; state.adapter = null; state.metadata = null; state.lastFrame = null;
}
function createActors(state, count) {
  removeActors(state); state.count = count;
  for (let index = 0; index < count; index++) {
    // clone() duplicates the graph and skeleton, retaining shared geometry/materials.
    const scene = cloneSkeleton(state.asset.scene);
    const x = count === 1 ? 0 : (index % 6 - 2.5) * 1.5, z = count === 1 ? 0 : (Math.floor(index / 6) - 1.5) * 1.8;
    scene.position.x += x; scene.position.z += z; scene.updateMatrixWorld(true);
    const bones = []; scene.traverse(object => { if (object.isBone) bones.push(object); });
    const actor = { id: index, index, scene, bones, head: bones.find(bone => bone.name === 'head'), pelvis: bones.find(bone => bone.name === 'pelvis'), x, z, active: true, mixer: new THREE.AnimationMixer(scene), action: null, actionClip: null };
    state.actors.push(actor); if (state.backend === 'three') state.stageScene.add(scene);
  }
}
function animationClip(state, name) {
  if (!state.asset.animations.length) return null;
  const clip = state.asset.animations.find(item => item.name === name);
  if (!clip) throw Object.assign(new Error(`Klip bulunamadı: ${name}. Klipler: ${state.asset.animations.map(item => item.name).join(', ')}`), { stage: 'animation' });
  return clip;
}
function updatePose(state, clipName, time) {
  const clip = animationClip(state, clipName), sampleTime = Math.max(0, Number(time) || 0);
  state.clip = clip?.name || '(bind pose)'; state.time = clip ? Math.min(sampleTime, clip.duration) : sampleTime;
  for (const actor of state.actors) {
    if (clip) {
      if (actor.actionClip !== clip) {
        actor.mixer.stopAllAction(); actor.action = actor.mixer.clipAction(clip); actor.actionClip = clip;
      }
      // Reset per sample so a previous endpoint/clamped action cannot affect seeking.
      actor.action.reset().setLoop(THREE.LoopOnce, 1); actor.action.clampWhenFinished = true; actor.action.play(); actor.mixer.setTime(state.time);
    }
    actor.scene.updateMatrixWorld(true);
  }
}
function updateCamera(state) {
  const camera = state.camera, group = state.count > 1;
  let target, position;
  if (group) { target = [0,.8,0]; position = ui.view === 'side' ? [14,7,1.2] : [0,8,15]; camera.fov = 40; }
  else {
    const actor = state.actors[0], pelvis = actor?.pelvis?.matrixWorld.elements, head = actor?.head?.matrixWorld.elements;
    const x = pelvis?.[12] || 0, z = pelvis?.[14] || 0;
    // The exported fixture faces +X. Both cameras follow the same imported bones.
    if (ui.view === 'face') { target = head ? [head[12],head[13] + .07,head[14]] : [0,1.68,0]; position = [target[0] + 1.16,target[1] + .04,target[2] + .12]; camera.fov = 24; }
    else if (ui.view === 'side') { target = [x,.95,z]; position = [x + .12,1.38,z + 4.8]; camera.fov = 31; }
    else { target = [x,.94,z]; position = [x + 4.25,1.5,z + 2.25]; camera.fov = 31; }
  }
  camera.aspect = state.canvas.width / state.canvas.height; camera.position.set(...position); camera.lookAt(...target); camera.updateProjectionMatrix(); camera.updateMatrixWorld(true);
  state.vp = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse); state.eye = camera.position.toArray();
}
function draw(state) {
  updateCamera(state);
  if (state.backend === 'three') { state.renderer.render(state.stageScene, state.camera); return; }
  const gl = state.gl, floor = state.floor;
  gl.viewport(0, 0, state.canvas.width, state.canvas.height); gl.clearColor(16 / 255, 27 / 255, 36 / 255, 1);
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.disable(gl.BLEND); gl.disable(gl.CULL_FACE); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.useProgram(floor.program); gl.uniformMatrix4fv(floor.vp, false, state.vp.elements); gl.bindBuffer(gl.ARRAY_BUFFER, floor.buffer);
  gl.enableVertexAttribArray(floor.position); gl.vertexAttribPointer(floor.position, 3, gl.FLOAT, false, 12, 0); gl.drawArrays(gl.TRIANGLES, 0, 6); gl.disableVertexAttribArray(floor.position);
  gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK); gl.frontFace(gl.CCW);
  state.renderer.draw(state.actors, state.vp.elements, state.eye, 'portrait', 0, null, { paletteForPlayer: actor => state.adapter.getPalette(actor.scene) });
}
function renderStats(state) {
  if (state.status !== 'ready') return { drawCalls: 0, modelDrawCalls: 0, floorDrawCalls: 0, triangles: 0, modelTriangles: 0, players: 0 };
  if (state.backend === 'three') {
    const info = state.renderer.info.render;
    return { drawCalls: info.calls, modelDrawCalls: Math.max(0, info.calls - 1), floorDrawCalls: 1, triangles: info.triangles, modelTriangles: Math.max(0, info.triangles - 2), players: state.actors.length, geometryCount: state.renderer.info.memory.geometries, textureCount: state.renderer.info.memory.textures };
  }
  const actual = state.renderer.lastRenderStats;
  return { ...actual, drawCalls: actual.players + 1, modelDrawCalls: actual.players, floorDrawCalls: 1, triangles: actual.triangles + 2, modelTriangles: actual.triangles, geometryCount: state.renderer.lods.filter(Boolean).length };
}
function stats(backend) {
  const state = backendState(backend);
  return { backend, status: state.status, stage: state.stage, source: state.url || null, metadata: state.metadata, error: state.error,
    clip: state.clip, time: state.time, count: state.count, features: { ...state.features }, loadTimes: state.loadTimes || null,
    drawBuffer: { width: state.canvas.width, height: state.canvas.height, pixelRatio: dimensions.pixelRatio },
    drawBufferWidth: state.canvas.width, drawBufferHeight: state.canvas.height, camera: state.camera ? { view: ui.view, position: state.camera.position.toArray(), projectionMatrix: state.camera.projectionMatrix.toArray(), viewMatrix: state.camera.matrixWorldInverse.toArray() } : null,
    render: renderStats(state), lastFrame: state.lastFrame ? { ...state.lastFrame } : null };
}
function renderFrame({ backend, clip, time, finish = true, freeze = true }) {
  const state = backendState(backend);
  if (state.status !== 'ready') return { status: state.status, error: state.error, stats: stats(backend) };
  if (freeze) state.frozen = true;
  // Chromium can queue work past finish(); a synchronous pixel read is the
  // completion fence. Time the same four-byte readback on both backends.
  const complete = () => {
    state.completionPixel ||= new Uint8Array(4);
    state.gl.finish();
    state.gl.readPixels(0, 0, 1, 1, state.gl.RGBA, state.gl.UNSIGNED_BYTE, state.completionPixel);
  };
  if (finish) complete();
  const start = performance.now(); updatePose(state, clip ?? state.clip, time ?? state.time); const updated = performance.now();
  draw(state); const submitted = performance.now(); if (finish) complete(); const completed = performance.now();
  const result = { cpuUpdateMs: updated - start, submitMs: submitted - updated, completedFrameMs: finish ? completed - start : null, completionFence: finish ? 'synchronous-readPixels-4-bytes' : null };
  state.lastFrame = result;
  if (freeze) updateMetrics(state);
  return { status: 'ready', ...result, stats: renderStats(state) };
}
async function load({ backend, url = DEFAULT_URL, count = 1, timeoutMs = 12000, signal } = {}) {
  const state = backendState(backend), generation = ++state.generation;
  state.controller?.abort(new Error('A newer model load replaced this request'));
  const controller = new AbortController(); state.controller = controller;
  const externalAbort = () => controller.abort(signal.reason);
  signal?.addEventListener('abort', externalAbort, { once: true }); if (signal?.aborted) externalAbort();
  releaseAsset(state); state.status = 'loading'; state.stage = 'context'; state.error = null; state.url = url; state.count = Number(count); state.frozen = manual; state.loadTimes = null; updateStatus(state);
  const started = performance.now();
  try {
    if (![1, 22].includes(Number(count))) throw new Error('Futbolcu sayısı 1 veya 22 olmalıdır.');
    initBackend(state);
    const sharedStart = performance.now(), asset = await loader.load({ url, timeoutMs, signal: controller.signal, onProgress: progress => {
      if (state.generation !== generation) return; state.stage = progress.stage; updateStatus(state);
    } });
    if (state.generation !== generation || controller.signal.aborted) { asset.dispose(); throw Object.assign(new Error('Model yüklemesi iptal edildi.'), { stage: 'cancel', code: 'GLTF_ABORTED' }); }
    state.asset = asset; state.metadata = asset.metadata;
    const setupStart = performance.now(); state.stage = 'backend';
    if (backend === 'custom') {
      state.adapter = createCustomRuntimeAdapter(asset, { THREE });
      if (!state.adapter.supported) throw Object.assign(new Error(state.adapter.reasons.join('\n')), { stage: 'custom-adapter', code: 'CUSTOM_UNSUPPORTED' });
      state.renderer = new window.TribunPlayerRenderer(state.gl, state.adapter.assets, { textureImages: state.adapter.textureImages, textureSettings: state.adapter.textureSettings, standardMaterials: state.adapter.standardMaterials, textureFlipY: false });
      state.renderer.studio = true; state.renderer.visualQuality = 'detailed'; await state.renderer.ready;
    }
    if (state.generation !== generation || controller.signal.aborted) throw Object.assign(new Error('Model yüklemesi iptal edildi.'), { stage: 'cancel', code: 'GLTF_ABORTED' });
    createActors(state, Number(count));
    state.clip = asset.animations.find(clip => clip.name === ui.clip)?.name || asset.animations[0]?.name || '(bind pose)';
    state.loadTimes = { sharedLoadMs: setupStart - sharedStart, backendSetupMs: performance.now() - setupStart, totalMs: performance.now() - started };
    state.status = 'ready'; state.stage = 'ready'; renderFrame({ backend, clip: state.clip, time: ui.time, finish: false, freeze: false });
    updateStatus(state); updateMetrics(state); syncTimeline();
    return { ...asset.metadata, ...stats(backend) };
  } catch (error) {
    const failure = errorRecord(error, url, state.stage);
    if (state.generation === generation) {
      // Preserve decoded metadata in the diagnostics when only the custom subset fails.
      const metadata = state.metadata; releaseAsset(state); state.metadata = metadata;
      state.status = 'error'; state.stage = failure.stage; state.error = failure; updateStatus(state); updateMetrics(state);
    }
    throw Object.assign(new Error(failure.message), failure, { backend, status: 'error', metadata: state.generation === generation ? state.metadata : null, superseded: state.generation !== generation });
  } finally { signal?.removeEventListener('abort', externalAbort); }
}
function sample({ backend, clip, time } = {}) { return renderFrame({ backend, clip, time, finish: false, freeze: true }); }
function frame(options = {}) { return renderFrame({ ...options, finish: true, freeze: true }); }
function boneWorld(backend) {
  const state = backendState(backend);
  const authored = new Map();
  state.asset?.scene.traverse(object => {
    const association = state.asset.gltf?.parser?.associations?.get(object) || state.asset.parser?.associations?.get(object);
    if (object.isBone) authored.set(object.name, state.asset.document?.nodes?.[association?.nodes]?.name || object.name);
  });
  return state.actors.map(actor => {
    actor.scene.updateMatrixWorld(true); const bones = actor.bones.map(bone => ({ name: authored.get(bone.name) || bone.name, matrix: bone.matrixWorld.toArray() }));
    return { id: actor.id, rootMatrix: actor.scene.matrixWorld.toArray(), bones };
  });
}
function pauseAll() {
  ui.automatic = false; ui.playing = false; ui.lastTick = 0;
  if (ui.raf) cancelAnimationFrame(ui.raf); ui.raf = 0; updatePlayButton();
  return { paused: true };
}
function resize({ width = 600, height = 560, pixelRatio = 1 } = {}) {
  if (![width, height, pixelRatio].every(value => Number.isFinite(value) && value > 0)) throw new TypeError('width, height and pixelRatio must be positive finite numbers');
  dimensions = { width: Math.round(width), height: Math.round(height), pixelRatio };
  for (const state of Object.values(states)) {
    if (state.backend === 'three' && state.renderer) { state.renderer.setPixelRatio(pixelRatio); state.renderer.setSize(dimensions.width, dimensions.height, false); }
    else { state.canvas.width = Math.round(dimensions.width * pixelRatio); state.canvas.height = Math.round(dimensions.height * pixelRatio); }
    state.canvas.parentElement.style.aspectRatio = `${dimensions.width} / ${dimensions.height}`;
    if (state.status === 'ready') renderFrame({ backend: state.backend, finish: false, freeze: false }); updateDiagnostics(state);
  }
  $('resolution-label').textContent = `${Math.round(dimensions.width * pixelRatio)} × ${Math.round(dimensions.height * pixelRatio)} px · Her çizici için ayrı bağlam`;
  return { ...dimensions };
}

// Published before auto-loading. ?manual=1 performs no network load or RAF draw.
window.TribunInteropLab = { version: 1, ready: Promise.resolve(true), load, sample, frame, stats, boneWorld, pauseAll, resize };
for (const state of Object.values(states)) updateStatus(state);
updatePlayButton();

function syncTimeline() {
  const ready = Object.values(states).find(state => state.status === 'ready');
  const clips = ready?.asset.animations || [], select = $('clip');
  if (clips.length) {
    const signature = clips.map(clip => clip.name).join('|');
    if (select.dataset.clips !== signature) {
      const labels = { idle: 'Duruş', run: 'Koşu', shoot: 'Şut', 'dive-right': 'Sağa kurtarış' };
      select.replaceChildren(...clips.map(clip => new Option(`${labels[clip.name] || clip.name} · ${clip.name}`, clip.name))); select.dataset.clips = signature;
    }
    if (!clips.some(clip => clip.name === ui.clip)) ui.clip = clips[0].name;
    select.value = ui.clip;
  }
  const duration = clips.find(clip => clip.name === ui.clip)?.duration || 2;
  $('time').max = String(duration); ui.time = Math.min(ui.time, duration); updateTimeReadout();
}
function updateTimeReadout() { $('time').value = String(ui.time); $('time-readout').value = `${ui.time.toFixed(3)} s`; }
function updatePlayButton() {
  const button = $('play-pause'); button.innerHTML = ui.playing ? 'Ⅱ <span>Durdur</span>' : '▶ <span>Oynat</span>';
  button.setAttribute('aria-pressed', String(ui.playing)); button.setAttribute('aria-label', ui.playing ? 'Hareketi durdur' : 'Hareketi oynat');
}
function drawAll() {
  for (const state of Object.values(states)) if (state.status === 'ready') {
    state.frozen = false; try { renderFrame({ backend: state.backend, clip: ui.clip, time: ui.time, finish: false, freeze: false }); updateMetrics(state); }
    catch (error) { runtimeError(state, error); }
  }
}
function runtimeError(state, error) { state.status = 'error'; state.stage = error.stage || 'draw'; state.error = errorRecord(error, state.url, 'draw'); updateStatus(state); }
function animate(now) {
  ui.raf = 0; if (!ui.automatic || ui.benchmarking) return;
  const dt = ui.lastTick ? Math.min(.1, (now - ui.lastTick) / 1000) : 0; ui.lastTick = now;
  if (ui.playing) ui.time = (ui.time + dt) % (Number($('time').max) || 2);
  for (const state of Object.values(states)) if (state.status === 'ready' && !state.frozen) {
    try { renderFrame({ backend: state.backend, clip: ui.clip, time: ui.time, finish: false, freeze: false }); }
    catch (error) { runtimeError(state, error); }
  }
  if (now - ui.lastMetrics > 300) { updateTimeReadout(); for (const state of Object.values(states)) updateMetrics(state); ui.lastMetrics = now; }
  ui.raf = requestAnimationFrame(animate);
}
function resume() { ui.automatic = true; if (!ui.raf) ui.raf = requestAnimationFrame(animate); }
async function loadBoth() {
  $('benchmark-result').textContent = 'İsteğe bağlı ölçüm: 12 ısınma + 30 kare / motor. Kareler sırayla tamamlanır; sonuç bu cihaz ve sahne içindir.';
  await Promise.allSettled(keys.map(backend => load({ backend, url: $('model-source').value, count: ui.count })));
  for (const state of Object.values(states)) if (state.status === 'ready' && state.count !== ui.count) createActors(state, ui.count);
  drawAll();
}
$('model-source').addEventListener('change', () => { ui.time = 0; loadBoth(); });
$('clip').addEventListener('change', () => { ui.clip = $('clip').value; ui.time = 0; syncTimeline(); drawAll(); });
$('time').addEventListener('input', () => { ui.time = Number($('time').value); ui.playing = false; updatePlayButton(); updateTimeReadout(); drawAll(); });
$('play-pause').addEventListener('click', () => { ui.playing = !ui.playing; for (const state of Object.values(states)) state.frozen = false; updatePlayButton(); resume(); });
document.querySelectorAll('[data-count]').forEach(button => button.addEventListener('click', () => {
  ui.count = Number(button.dataset.count); document.querySelectorAll('[data-count]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  for (const state of Object.values(states)) if (state.status === 'ready') createActors(state, ui.count); drawAll();
}));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
  ui.view = button.dataset.view; document.querySelectorAll('[data-view]').forEach(item => item.setAttribute('aria-pressed', String(item === button))); drawAll();
}));
const nextTurn = () => new Promise(resolve => setTimeout(resolve, 0));
const median = values => { const ordered = [...values].sort((a, b) => a - b); return (ordered[Math.floor((ordered.length - 1) / 2)] + ordered[Math.ceil((ordered.length - 1) / 2)]) / 2; };
$('benchmark').addEventListener('click', async () => {
  if (ui.benchmarking) return;
  const ready = keys.filter(key => states[key].status === 'ready');
  if (!ready.length) { $('benchmark-result').textContent = 'Ölçüm için önce bir modelin yüklenmesi gerekir.'; return; }
  const wasPlaying = ui.playing; pauseAll(); ui.benchmarking = true; $('benchmark').disabled = true;
  const disabledControls = [...document.querySelectorAll('.controls button,.controls select,.controls input')].map(control => [control, control.disabled]);
  for (const [control] of disabledControls) control.disabled = true;
  const snapshot = { count: ui.count, clip: ui.clip, ...dimensions, generations: Object.fromEntries(ready.map(key => [key, states[key].generation])) };
  try {
    const samples = Object.fromEntries(ready.map(key => [key, []])), duration = Number($('time').max) || 2;
    for (let index = -12; index < 30; index++) {
      // Alternate ordering; both backends sample the exact same animation time.
      for (const backend of index % 2 ? ready : [...ready].reverse()) {
        if (states[backend].generation !== snapshot.generations[backend] || states[backend].count !== snapshot.count) throw new Error('Sahne ölçüm sırasında değişti; ölçümü yeniden başlatın.');
        const result = frame({ backend, clip: snapshot.clip, time: (Math.max(0, index) / 30) * duration });
        if (result.status !== 'ready') throw new Error(`${backend}: ${result.error?.message || result.status}`);
        if (index >= 0) samples[backend].push(result.completedFrameMs);
      }
      if (index % 4 === 0) { $('benchmark-result').textContent = index < 0 ? 'Çiziciler ısınıyor…' : `Kareler ölçülüyor… ${index + 1} / 30`; await nextTurn(); }
    }
    $('benchmark-result').textContent = `${ready.map(key => `${key === 'custom' ? 'Mevcut WebGL' : 'Three.js'}: ${median(samples[key]).toFixed(2)} ms medyan`).join(' · ')}. ${snapshot.count} futbolcu, ${Math.round(snapshot.width * snapshot.pixelRatio)} × ${Math.round(snapshot.height * snapshot.pixelRatio)} px, ${snapshot.clip}. 30 kare / motor; CPU güncellemesi + gönderim + GPU bitişi.`;
  } catch (error) { $('benchmark-result').textContent = `Ölçüm tamamlanamadı: ${error.message}`; }
  finally { ui.benchmarking = false; $('benchmark').disabled = false; for (const [control, disabled] of disabledControls) control.disabled = disabled; drawAll(); ui.playing = wasPlaying; updatePlayButton(); if (!manual) resume(); }
});
window.addEventListener('pagehide', () => {
  pauseAll();
  for (const state of Object.values(states)) {
    state.controller?.abort(); releaseAsset(state);
    if (state.backend === 'three') { state.floorMesh?.geometry.dispose(); state.floorMesh?.material.dispose(); state.renderer?.dispose(); }
    else if (state.floor) { state.gl.deleteBuffer(state.floor.buffer); for (const shader of state.floor.shaders) state.gl.deleteShader(shader); state.gl.deleteProgram(state.floor.program); }
  }
}, { once: true });
if (!manual) { loadBoth(); resume(); }
