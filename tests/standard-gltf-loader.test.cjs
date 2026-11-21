'use strict';
const { test, before } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
let THREE, GLTFLoader, loaderModule, adapterModule;
before(async () => {
  [THREE, { GLTFLoader }, loaderModule, adapterModule] = await Promise.all([
    import('three'), import('three/addons/loaders/GLTFLoader.js'),
    import('../gltf-asset-loader.mjs'), import('../gltf-runtime-adapter.mjs')
  ]);
  // Node has no DOM ProgressEvent; official FileLoader uses only these fields.
  globalThis.ProgressEvent ||= class ProgressEvent extends Event {
    constructor(type, fields = {}) { super(type); Object.assign(this, fields); }
  };
});
function container(document, binary) {
  const json = Buffer.from(JSON.stringify(document));
  const padded = Buffer.alloc(Math.ceil(json.length / 4) * 4, 0x20); json.copy(padded);
  const bin = Buffer.alloc(Math.ceil(binary.length / 4) * 4); binary.copy(bin);
  const output = Buffer.alloc(28 + padded.length + bin.length);
  output.writeUInt32LE(0x46546c67, 0); output.writeUInt32LE(2, 4); output.writeUInt32LE(output.length, 8);
  output.writeUInt32LE(padded.length, 12); output.writeUInt32LE(0x4e4f534a, 16); padded.copy(output, 20);
  output.writeUInt32LE(bin.length, 20 + padded.length); output.writeUInt32LE(0x004e4942, 24 + padded.length); bin.copy(output, 28 + padded.length);
  return output;
}
function triangleDocument() {
  const data = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
  return { document: { asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ mesh: 0, name: 'triangle' }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0 } }] }], buffers: [{ uri: 'geometry.bin', byteLength: data.byteLength }],
    bufferViews: [{ buffer: 0, byteLength: data.byteLength }], accessors: [{ bufferView: 0, componentType: 5126, count: 3, type: 'VEC3', min: [0, 0, 0], max: [1, 1, 0] }] }, binary: Buffer.from(data.buffer) };
}
function fixtureWithoutMaps() {
  const bytes = fs.readFileSync(path.join(__dirname, '../assets/interchange/footballer.blender.glb'));
  const length = bytes.readUInt32LE(12), document = JSON.parse(bytes.subarray(20, 20 + length));
  const offset = 20 + length, binary = bytes.subarray(offset + 8, offset + 8 + bytes.readUInt32LE(offset));
  for (const material of document.materials) {
    delete material.pbrMetallicRoughness.baseColorTexture; delete material.normalTexture;
    delete material.emissiveTexture; delete material.occlusionTexture;
  }
  delete document.images; delete document.textures;
  return { document, binary };
}
function animatedTriangle({ property = 'translation', interpolation = 'LINEAR', outputCount, times = [0, 1] } = {}) {
  const source = triangleDocument(), document = source.document, factor = interpolation === 'CUBICSPLINE' ? 3 : 1;
  const isWeights = property === 'weights', width = isWeights ? 1 : property === 'rotation' ? 4 : 3;
  const count = outputCount ?? times.length * factor * (isWeights ? 2 : 1);
  const input = Buffer.from(new Float32Array(times).buffer), output = Buffer.from(new Float32Array(count * width).buffer);
  const binary = Buffer.concat([source.binary, input, output]);
  document.buffers[0].byteLength = binary.length;
  document.bufferViews.push({ buffer: 0, byteOffset: source.binary.length, byteLength: input.length }, { buffer: 0, byteOffset: source.binary.length + input.length, byteLength: output.length });
  document.accessors.push({ bufferView: 1, componentType: 5126, count: times.length, type: 'SCALAR' }, { bufferView: 2, componentType: 5126, count, type: isWeights ? 'SCALAR' : property === 'rotation' ? 'VEC4' : 'VEC3' });
  if (isWeights) { document.meshes[0].primitives[0].targets = [{ POSITION: 0 }, { POSITION: 0 }]; document.meshes[0].weights = [0, 0]; }
  document.animations = [{ name: 'triangle-animation', channels: [{ sampler: 0, target: { node: 0, path: property } }], samplers: [{ input: 1, output: 2, interpolation }] }];
  return { document, binary };
}
function response(data, status = 200) { return new Response(data, { status, headers: { 'content-type': 'application/octet-stream' } }); }
function inMemoryLoader(routes, requests = []) {
  return loaderModule.createStandardAssetLoader({ THREE, GLTFLoader, fetchImpl: async (url, options) => {
    requests.push({ url, signal: options.signal });
    const route = routes[url]; return typeof route === 'function' ? route(options) : response(route ?? 'missing', route === undefined ? 404 : 200);
  } });
}

test('official parser loads external glTF buffers relative to the source URL', async () => {
  const { document, binary } = triangleDocument(), requests = [], stages = [];
  const loader = inMemoryLoader({ 'http://test/models/triangle.gltf': JSON.stringify(document), 'http://test/models/geometry.bin': binary }, requests);
  const asset = await loader.load({ url: 'http://test/models/triangle.gltf', onProgress: progress => stages.push(progress.stage) });
  assert.equal(asset.metadata.triangles, 1); assert.equal(asset.metadata.meshCount, 1);
  assert.deepEqual(asset.resources, ['http://test/models/geometry.bin']);
  assert.deepEqual(requests.map(request => request.url), ['http://test/models/triangle.gltf', 'http://test/models/geometry.bin']);
  assert.equal(stages.at(-1), 'ready'); assert(requests.every(request => request.signal instanceof AbortSignal));
  assert.equal(adapterModule.createCustomRuntimeAdapter(asset, { THREE }).supported, false, 'a static arbitrary mesh remains outside the custom humanoid subset');
  asset.dispose(); asset.dispose();
});

test('percent-encoded binary data URIs preserve bytes outside the UTF-8 range', async () => {
  const { document, binary } = animatedTriangle();
  document.buffers[0].uri = 'data:application/octet-stream,' + [...binary].map(value => `%${value.toString(16).padStart(2, '0')}`).join('');
  assert(document.buffers[0].uri.includes('%80'), 'fixture includes a non-UTF-8 byte');
  const requests = [], asset = await inMemoryLoader({ 'http://test/inline.gltf': JSON.stringify(document) }, requests).load({ url: 'http://test/inline.gltf' });
  assert.equal(asset.metadata.clipCount, 1); assert.equal(requests.length, 1);
  const mixer = new THREE.AnimationMixer(asset.scene); mixer.clipAction(asset.animations[0]).play(); mixer.setTime(0.5);
  mixer.stopAllAction(); mixer.uncacheRoot(asset.scene); asset.dispose();
});

test('missing GLB, BIN and PNG reject with the actual resource and loading stage', async () => {
  await assert.rejects(inMemoryLoader({}).load({ url: 'http://test/missing.glb' }), error => error.code === 'GLTF_HTTP' && error.stage === 'fetch' && error.url.endsWith('/missing.glb'));
  const { document } = triangleDocument();
  await assert.rejects(inMemoryLoader({ 'http://test/model.gltf': JSON.stringify(document) }).load({ url: 'http://test/model.gltf' }), error => error.code === 'GLTF_HTTP' && error.stage === 'buffer' && error.url.endsWith('/geometry.bin'));
  document.buffers = []; document.images = [{ uri: 'textures/missing.png' }];
  await assert.rejects(inMemoryLoader({ 'http://test/model.gltf': JSON.stringify(document) }).load({ url: 'http://test/model.gltf' }), error => error.code === 'GLTF_HTTP' && error.stage === 'image' && error.url.endsWith('/textures/missing.png'));
});

test('malformed containers, cycles and unsupported required decoder extensions fail clearly', () => {
  const invalid = Buffer.from('not glTF');
  assert.throws(() => loaderModule.readGLTFDocument(invalid, 'bad.glb'), /Invalid glTF JSON/);
  const { document, binary } = triangleDocument(); delete document.buffers[0].uri;
  const glb = container(document, binary); glb.writeUInt32LE(glb.length - 1, 8);
  assert.throws(() => loaderModule.readGLTFDocument(glb, 'short.glb'), /byte length/);
  assert.throws(() => loaderModule.readGLTFDocument(Buffer.from(JSON.stringify({ asset: { version: '2.0' }, nodes: [{ children: [1] }, { children: [0] }] }))), /cycle/);
  assert.throws(() => loaderModule.readGLTFDocument(Buffer.from(JSON.stringify({ asset: { version: '2.0' }, extensionsRequired: ['KHR_draco_mesh_compression'] }))), /decoder\/plugin/);
});

test('extra skin influence sets are explicitly unsupported rather than invalid or silently dropped', () => {
  const { document } = triangleDocument();
  document.meshes[0].primitives[0].attributes.WEIGHTS_1 = 0;
  assert.throws(() => loaderModule.readGLTFDocument(Buffer.from(JSON.stringify(document))), error =>
    error.code === 'GLTF_UNSUPPORTED_SKINNING' && /four skin influences/.test(error.message));
});

test('animation cardinality is validated before parsing, including cubic and morph-weight layouts', async () => {
  for (const options of [{ outputCount: 1 }, { interpolation: 'CUBICSPLINE', outputCount: 2 }, { property: 'weights', outputCount: 2 }, { property: 'weights', interpolation: 'CUBICSPLINE', outputCount: 4 }]) {
    const { document, binary } = animatedTriangle(options);
    await assert.rejects(inMemoryLoader({ 'http://test/bad.gltf': JSON.stringify(document), 'http://test/geometry.bin': binary }).load({ url: 'http://test/bad.gltf' }), error => error.stage === 'animations' && /output must/.test(error.message));
  }
  for (const options of [{}, { interpolation: 'CUBICSPLINE' }, { property: 'weights' }, { property: 'weights', interpolation: 'CUBICSPLINE' }]) {
    const { document, binary } = animatedTriangle(options);
    const asset = await inMemoryLoader({ 'http://test/good.gltf': JSON.stringify(document), 'http://test/geometry.bin': binary }).load({ url: 'http://test/good.gltf' });
    assert.equal(asset.metadata.clipCount, 1);
    const mixer = new THREE.AnimationMixer(asset.scene); mixer.clipAction(asset.animations[0]).play(); mixer.setTime(0.5);
    mixer.stopAllAction(); mixer.uncacheRoot(asset.scene); asset.dispose();
  }
  const duplicateTimes = animatedTriangle({ times: [0, 0] });
  await assert.rejects(inMemoryLoader({ 'http://test/times.gltf': JSON.stringify(duplicateTimes.document), 'http://test/geometry.bin': duplicateTimes.binary }).load({ url: 'http://test/times.gltf' }), error => error.stage === 'animations' && /strictly increasing/.test(error.message));
  const unknown = animatedTriangle({ interpolation: 'UNKNOWN' });
  assert.throws(() => loaderModule.readGLTFDocument(Buffer.from(JSON.stringify(unknown.document))), /unsupported interpolation UNKNOWN/);
});

test('cancellation and timeout are terminal and abort underlying resource requests', async () => {
  const requests = [], hanging = options => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true }));
  const loader = inMemoryLoader({ 'http://test/slow.glb': hanging }, requests), controller = new AbortController();
  const cancelled = loader.load({ url: 'http://test/slow.glb', signal: controller.signal }); controller.abort();
  await assert.rejects(cancelled, error => error.code === 'GLTF_ABORTED'); assert(requests[0].signal.aborted);
  await assert.rejects(loader.load({ url: 'http://test/slow.glb', timeoutMs: 10 }), error => error.code === 'GLTF_TIMEOUT' && error.stage === 'timeout');
  assert(requests[1].signal.aborted);
});

test('Blender fixture loads real baked clips and custom palettes read imported clone bones', async () => {
  const { document, binary } = fixtureWithoutMaps(), bytes = container(document, binary);
  const asset = await inMemoryLoader({ 'http://test/footballer.glb': bytes }).load({ url: 'http://test/footballer.glb' });
  assert.equal(asset.metadata.jointCount, 19); assert.equal(asset.metadata.clipCount, 4);
  assert(asset.metadata.clips.every(clip => clip.tracks > 0 && clip.targets.length >= 19));
  const adapter = adapterModule.createCustomRuntimeAdapter(asset, { THREE });
  assert.equal(adapter.supported, true, adapter.reasons.join('; '));
  assert.equal(adapter.assets.bones.length, 19); assert(adapter.geometry.indices.length > 1000);
  const { clone } = await import('three/addons/utils/SkeletonUtils.js'), actor = clone(asset.scene), mixer = new THREE.AnimationMixer(actor);
  mixer.clipAction(asset.animations.find(clip => /run/i.test(clip.name))).play(); mixer.setTime(0.27);
  actor.position.set(4, 0, -3); actor.rotation.y = 0.4;
  const palette = adapter.getPalette(actor), bones = new Map(); actor.traverse(object => { if (object.isBone) bones.set(object.name, object); });
  for (let index = 0; index < 19; index++) {
    const sourceBone = [...bones.values()].find(bone => bone.name === asset.scene.getObjectByName(bone.name)?.name &&
      (asset.document.nodes[asset.parser.associations.get(asset.scene.getObjectByName(bone.name))?.nodes]?.name || bone.name) === adapter.boneNames[index]);
    assert(sourceBone, adapter.boneNames[index]);
    const expected = new THREE.Matrix4().multiplyMatrices(sourceBone.matrixWorld, new THREE.Matrix4().fromArray(adapter.assets.bones[index].inverseBind));
    expected.elements.forEach((value, at) => assert(Math.abs(value - palette[index * 16 + at]) < 2e-6));
  }
  const originalPalette = adapter.getPalette(); assert(Math.abs(palette[12] - originalPalette[12]) > 1, 'actor transform is part of the imported bone palette');
  mixer.stopAllAction(); mixer.uncacheRoot(actor); asset.dispose();
});

test('malformed source weights are rejected before GLTFLoader normalizes them', async () => {
  const { document, binary } = fixtureWithoutMaps();
  const index = document.meshes[0].primitives[0].attributes.WEIGHTS_0, accessor = document.accessors[index], view = document.bufferViews[accessor.bufferView];
  assert.equal(accessor.componentType, 5126);
  const modified = Buffer.from(binary), offset = (view.byteOffset || 0) + (accessor.byteOffset || 0);
  for (let axis = 0; axis < 4; axis++) modified.writeFloatLE(0, offset + axis * 4);
  await assert.rejects(inMemoryLoader({ 'http://test/bad-weights.glb': container(document, modified) }).load({ url: 'http://test/bad-weights.glb' }), /Source WEIGHTS_0.*sums to 0/);
});

test('standard PBR material loads while custom adapter explicitly rejects metallic response', async () => {
  const { document, binary } = fixtureWithoutMaps(); document.materials[0].pbrMetallicRoughness.metallicFactor = 0.5;
  const asset = await inMemoryLoader({ 'http://test/metal.glb': container(document, binary) }).load({ url: 'http://test/metal.glb' });
  const adapter = adapterModule.createCustomRuntimeAdapter(asset, { THREE });
  assert.equal(adapter.supported, false); assert(adapter.reasons.some(reason => /metallic response/.test(reason)));
  assert(asset.metadata.materials.some(material => material.metalness === 0.5)); asset.dispose();
});

test('custom adapter preserves supported nondefault samplers and rejects family conflicts or NPOT repeat', async () => {
  const { document, binary } = fixtureWithoutMaps();
  const asset = await inMemoryLoader({ 'http://test/samplers.glb': container(document, binary) }).load({ url: 'http://test/samplers.glb' });
  const image = { width: 4, height: 4 }, map = new THREE.Texture(image);
  map.colorSpace = THREE.SRGBColorSpace; map.flipY = false;
  map.wrapS = THREE.MirroredRepeatWrapping; map.wrapT = THREE.ClampToEdgeWrapping;
  map.minFilter = THREE.NearestFilter; map.magFilter = THREE.NearestFilter;
  const materials = []; asset.scene.traverse(object => { if (object.isMesh && object.material.name !== 'skin') { object.material.map = map; materials.push(object.material); } });
  const adapter = adapterModule.createCustomRuntimeAdapter(asset, { THREE });
  assert.equal(adapter.supported, true, adapter.reasons.join('; '));
  assert.deepEqual(adapter.textureSettings.fabric, { wrapS: THREE.MirroredRepeatWrapping, wrapT: THREE.ClampToEdgeWrapping, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
  const conflicting = map.clone(); conflicting.wrapS = THREE.RepeatWrapping; materials[0].map = conflicting;
  const conflict = adapterModule.createCustomRuntimeAdapter(asset, { THREE });
  assert.equal(conflict.supported, false); assert(conflict.reasons.some(reason => /different sampler/.test(reason)));
  materials[0].map = map; image.width = 3;
  const npot = adapterModule.createCustomRuntimeAdapter(asset, { THREE });
  assert.equal(npot.supported, false); assert(npot.reasons.some(reason => /non-power-of-two/.test(reason)));
  asset.dispose();
});

test('distinct standard materials sharing a semantic name cannot silently overwrite a custom color slot', async () => {
  const { document, binary } = fixtureWithoutMaps();
  const asset = await inMemoryLoader({ 'http://test/duplicate-material.glb': container(document, binary) }).load({ url: 'http://test/duplicate-material.glb' });
  const meshes = []; asset.scene.traverse(object => { if (object.isMesh) meshes.push(object); });
  const shirt = meshes.find(mesh => mesh.material.name === 'shirt').material;
  const second = meshes.find(mesh => mesh.material.name === 'shorts');
  const distinctShirt = shirt.clone(); distinctShirt.color.setRGB(1, 0, 0); second.material = distinctShirt;
  const adapter = adapterModule.createCustomRuntimeAdapter(asset, { THREE });
  assert.equal(adapter.supported, false); assert(adapter.reasons.some(reason => /share the custom semantic slot shirt/.test(reason)));
  asset.dispose();
});

test('decoded texture omissions, unbound tracks and nonfinite attributes cannot be ready', () => {
  const scene = new THREE.Scene(), geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 1, 0, 0, 0, 1, 0], 3));
  const material = new THREE.MeshStandardMaterial(), mesh = new THREE.Mesh(geometry, material); scene.add(mesh);
  material.map = new THREE.Texture();
  assert.throws(() => loaderModule.inspectStandardAsset({ scene }, { THREE }), /no decoded pixels/);
  material.map = null;
  const brokenClip = new THREE.AnimationClip('broken', 1, [new THREE.VectorKeyframeTrack('missing.position', [0, 1], [0, 0, 0, 1, 0, 0])]);
  assert.throws(() => loaderModule.inspectStandardAsset({ scene, animations: [brokenClip] }, { THREE }), /unbound/);
  mesh.name = 'Triangle';
  const fractionalClip = new THREE.AnimationClip('fractional', 1, [new THREE.VectorKeyframeTrack('Triangle.position', [0, 1], [0, 0, 0])]);
  assert.throws(() => loaderModule.inspectStandardAsset({ scene, animations: [fractionalClip] }, { THREE }), /invalid value cardinality/);
  geometry.attributes.position.setX(0, NaN);
  assert.throws(() => loaderModule.inspectStandardAsset({ scene }, { THREE }), /not finite/);
});

test('ownership disposal releases shared geometry, material, texture and bitmap once', () => {
  const scene = new THREE.Scene(), geometry = new THREE.BufferGeometry(), material = new THREE.MeshStandardMaterial(), texture = new THREE.Texture();
  let geometryDisposed = 0, materialDisposed = 0, textureDisposed = 0, imageClosed = 0;
  geometry.addEventListener('dispose', () => geometryDisposed++); material.addEventListener('dispose', () => materialDisposed++); texture.addEventListener('dispose', () => textureDisposed++);
  texture.image = { width: 1, height: 1, close() { imageClosed++; } }; material.map = texture;
  scene.add(new THREE.Mesh(geometry, material), new THREE.Mesh(geometry, material)); const asset = { scene };
  loaderModule.disposeStandardAsset(asset); loaderModule.disposeStandardAsset(asset);
  assert.deepEqual([geometryDisposed, materialDisposed, textureDisposed, imageClosed], [1, 1, 1, 1]);
});
