/* Standard glTF loading is isolated from football simulation and the legacy pack. */

const TEXTURE_SLOTS = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap',
  'emissiveMap', 'alphaMap', 'bumpMap', 'displacementMap', 'clearcoatMap',
  'clearcoatNormalMap', 'clearcoatRoughnessMap', 'transmissionMap', 'thicknessMap',
  'specularIntensityMap', 'specularColorMap', 'sheenColorMap', 'sheenRoughnessMap',
  'iridescenceMap', 'iridescenceThicknessMap', 'anisotropyMap'];
const REQUIRED_EXTENSIONS = new Set(['KHR_lights_punctual', 'KHR_materials_unlit',
  'KHR_materials_clearcoat', 'KHR_materials_dispersion', 'KHR_materials_ior',
  'KHR_materials_sheen', 'KHR_materials_transmission', 'KHR_materials_volume',
  'KHR_materials_specular', 'KHR_materials_iridescence', 'KHR_materials_anisotropy',
  'KHR_mesh_quantization', 'KHR_texture_transform', 'EXT_mesh_gpu_instancing',
  'EXT_texture_avif', 'EXT_texture_webp']);

export class StandardAssetError extends Error {
  constructor(message, { stage = 'load', url = '', code = 'GLTF_LOAD', cause } = {}) {
    super(`${stage}: ${url ? `${url}: ` : ''}${message}`, { cause });
    this.name = 'StandardAssetError';
    this.stage = stage;
    this.url = url;
    this.code = code;
  }
}

function fail(message, stage, url, code = 'GLTF_INVALID') {
  throw new StandardAssetError(message, { stage, url, code });
}
function finiteArray(array, label, url) {
  for (let i = 0; i < array.length; i++) {
    if (!Number.isFinite(array[i])) fail(`${label}[${i}] is not finite`, 'validate', url);
  }
}

/** Parse only the container/document; official GLTFLoader decodes the asset. */
export function readGLTFDocument(bytes, url = '') {
  const data = bytes instanceof ArrayBuffer ? bytes : bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const view = new DataView(data);
  let source;
  if (view.byteLength >= 4 && view.getUint32(0, true) === 0x46546c67) {
    if (view.byteLength < 20 || view.getUint32(4, true) !== 2) fail('Expected a GLB 2.0 container', 'document', url);
    if (view.getUint32(8, true) !== view.byteLength) fail('GLB byte length does not match its header', 'document', url);
    let offset = 12;
    while (offset < view.byteLength) {
      if (offset + 8 > view.byteLength) fail('Truncated GLB chunk header', 'document', url);
      const length = view.getUint32(offset, true), type = view.getUint32(offset + 4, true);
      if (offset + 8 + length > view.byteLength) fail('Truncated GLB chunk', 'document', url);
      if (type === 0x4e4f534a) {
        if (source !== undefined || offset !== 12) fail('GLB JSON must be the first and only JSON chunk', 'document', url);
        source = new TextDecoder().decode(new Uint8Array(data, offset + 8, length));
      }
      offset += 8 + length;
    }
    if (source === undefined) fail('GLB JSON chunk is missing', 'document', url);
  } else source = new TextDecoder().decode(data);
  let document;
  try { document = JSON.parse(source.replace(/^\uFEFF/, '')); }
  catch (cause) { throw new StandardAssetError(`Invalid glTF JSON: ${cause.message}`, { stage: 'document', url, cause }); }
  if (document.asset?.version !== '2.0') fail('Expected glTF asset.version 2.0', 'document', url);
  if (document.asset.minVersion && Number(document.asset.minVersion) > 2) fail('glTF requires a newer format version', 'document', url);
  const extension = (document.extensionsRequired || []).find(name => !REQUIRED_EXTENSIONS.has(name));
  if (extension) fail(`Required extension ${extension} needs a decoder/plugin that is not configured`, 'document', url, 'GLTF_EXTENSION');
  for (const [meshIndex, mesh] of (document.meshes || []).entries()) for (const primitive of mesh.primitives || []) {
    const extra = Object.keys(primitive.attributes || {}).find(name => /^(JOINTS|WEIGHTS)_[1-9][0-9]*$/.test(name));
    if (extra) fail(`Mesh ${meshIndex} declares ${extra}; this Three.js parser/render path supports at most four skin influences per vertex (JOINTS_0/WEIGHTS_0). Re-export with four influences.`, 'document', url, 'GLTF_UNSUPPORTED_SKINNING');
  }
  validateDocumentHierarchy(document, url);
  validateDocumentAnimations(document, url);
  return document;
}

function validateDocumentAnimations(document, url) {
  for (const [animationIndex, animation] of (document.animations || []).entries()) {
    if (!animation.channels?.length || !animation.samplers?.length) fail(`Animation ${animationIndex} needs channels and samplers`, 'animations', url);
    for (const sampler of animation.samplers) {
      const input = document.accessors?.[sampler.input], output = document.accessors?.[sampler.output];
      if (!input || input.type !== 'SCALAR' || input.componentType !== 5126 || input.normalized || !Number.isInteger(input.count) || input.count < 1) fail(`Animation ${animationIndex} input must be a nonempty SCALAR float accessor`, 'animations', url);
      if (!output || output.componentType !== 5126 || output.normalized || !Number.isInteger(output.count) || output.count < 1) fail(`Animation ${animationIndex} output must be a nonempty float accessor`, 'animations', url);
      if (!['LINEAR', 'STEP', 'CUBICSPLINE'].includes(sampler.interpolation || 'LINEAR')) fail(`Animation ${animationIndex} has unsupported interpolation ${sampler.interpolation}`, 'animations', url);
    }
    const targets = new Set();
    for (const channel of animation.channels) {
      const sampler = animation.samplers[channel.sampler], target = channel.target, node = document.nodes?.[target?.node];
      if (!sampler || !node || !['translation', 'rotation', 'scale', 'weights'].includes(target.path)) fail(`Animation ${animationIndex} has an invalid sampler/target/path`, 'animations', url);
      const key = `${target.node}:${target.path}`;
      if (targets.has(key)) fail(`Animation ${animationIndex} repeats target ${key}`, 'animations', url);
      targets.add(key);
      const input = document.accessors?.[sampler.input], output = document.accessors?.[sampler.output], interpolation = sampler.interpolation || 'LINEAR';
      if (!['LINEAR', 'STEP', 'CUBICSPLINE'].includes(interpolation)) fail(`Animation ${animationIndex} has unsupported interpolation ${interpolation}`, 'animations', url);
      if (!input || input.type !== 'SCALAR' || input.componentType !== 5126 || input.normalized || !Number.isInteger(input.count) || input.count < 1) fail(`Animation ${animationIndex} input must be a nonempty SCALAR float accessor`, 'animations', url);
      const type = target.path === 'rotation' ? 'VEC4' : target.path === 'weights' ? 'SCALAR' : 'VEC3';
      let width = 1;
      if (target.path === 'weights') {
        const primitives = document.meshes?.[node.mesh]?.primitives || [];
        width = primitives[0]?.targets?.length || 0;
        if (!width || primitives.some(primitive => primitive.targets?.length !== width)) fail(`Animation ${animationIndex} weight target has no consistent morph target count`, 'animations', url);
      }
      const expectedCount = input.count * width * (interpolation === 'CUBICSPLINE' ? 3 : 1);
      if (!output || output.type !== type || output.componentType !== 5126 || output.normalized || output.count !== expectedCount) fail(`Animation ${animationIndex} ${target.path} output must be ${type} float with ${expectedCount} entries (${interpolation}); got ${output?.type || 'missing'} count ${output?.count}`, 'animations', url);
    }
  }
}

function validateDocumentHierarchy(document, url) {
  const nodes = document.nodes || [], parents = new Map(), states = new Uint8Array(nodes.length);
  for (const [index, node] of nodes.entries()) {
    for (const key of ['matrix', 'translation', 'rotation', 'scale', 'weights']) {
      if (node[key]) finiteArray(node[key], `nodes[${index}].${key}`, url);
    }
    for (const child of node.children || []) {
      if (!Number.isInteger(child) || !nodes[child]) fail(`nodes[${index}] has an invalid child ${child}`, 'validate', url);
      if (parents.has(child)) fail(`Node ${child} has more than one parent`, 'validate', url);
      parents.set(child, index);
    }
  }
  function visit(index) {
    if (states[index] === 1) fail(`Node hierarchy contains a cycle at ${index}`, 'validate', url);
    if (states[index] === 2) return;
    states[index] = 1;
    for (const child of nodes[index].children || []) visit(child);
    states[index] = 2;
  }
  nodes.forEach((_, index) => visit(index));
  for (const [index, skin] of (document.skins || []).entries()) {
    if (!skin.joints?.length || new Set(skin.joints).size !== skin.joints.length) fail(`Skin ${index} needs unique joints`, 'validate', url);
    for (const joint of skin.joints) if (!nodes[joint]) fail(`Skin ${index} references missing joint ${joint}`, 'validate', url);
    if (skin.skeleton !== undefined && !nodes[skin.skeleton]) fail(`Skin ${index} references missing skeleton root`, 'validate', url);
    if (skin.inverseBindMatrices !== undefined) {
      const accessor = document.accessors?.[skin.inverseBindMatrices];
      if (!accessor || accessor.type !== 'MAT4' || accessor.count !== skin.joints.length) fail(`Skin ${index} inverse bind count must match its joints`, 'validate', url);
    }
  }
}

function imageDimensions(image) {
  return { width: image?.naturalWidth || image?.videoWidth || image?.width || 0,
    height: image?.naturalHeight || image?.videoHeight || image?.height || 0 };
}

// GLTFLoader normalizes skin weights for rendering. Check source weights before
// that repair so an all-zero or non-finite authored binding cannot appear ready.
function validateSourceData(document, rootBytes, resources, base, url) {
  const components = { 5120: [1, 'getInt8', 127], 5121: [1, 'getUint8', 255],
    5122: [2, 'getInt16', 32767], 5123: [2, 'getUint16', 65535], 5125: [4, 'getUint32', 4294967295], 5126: [4, 'getFloat32', 1] };
  let binary;
  const rootView = new DataView(rootBytes);
  if (rootView.byteLength >= 12 && rootView.getUint32(0, true) === 0x46546c67) {
    for (let offset = 12; offset < rootView.byteLength; offset += 8 + rootView.getUint32(offset, true)) {
      const length = rootView.getUint32(offset, true);
      if (rootView.getUint32(offset + 4, true) === 0x004e4942) binary = rootBytes.slice(offset + 8, offset + 8 + length);
    }
  }
  const bufferCache = new Map();
  function buffer(index) {
    if (bufferCache.has(index)) return bufferCache.get(index);
    const entry = document.buffers?.[index];
    let bytes;
    if (!entry?.uri) bytes = binary;
    else if (entry.uri.startsWith('data:')) {
      const comma = entry.uri.indexOf(','), header = entry.uri.slice(0, comma), payload = entry.uri.slice(comma + 1);
      // A data URI encodes bytes, including values that are invalid UTF-8.
      // decodeURIComponent would reject otherwise valid binary payloads such as %80.
      const encoded = new TextEncoder().encode(payload), decoded = new Uint8Array(encoded.length);
      let length = 0;
      for (let index = 0; index < encoded.length; index++) {
        const escape = encoded[index] === 37 ? String.fromCharCode(...encoded.subarray(index + 1, index + 3)) : '';
        if (/^[0-9a-f]{2}$/i.test(escape)) { decoded[length++] = parseInt(escape, 16); index += 2; }
        else decoded[length++] = encoded[index];
      }
      const payloadBytes = decoded.subarray(0, length);
      bytes = /;base64$/i.test(header)
        ? Uint8Array.from(atob(new TextDecoder().decode(payloadBytes)), character => character.charCodeAt(0)).buffer
        : payloadBytes.slice().buffer;
    } else bytes = resources.get(new URL(entry.uri, base).href)?.bytes;
    if (!bytes) fail(`Missing source buffer ${index} for skin weight validation`, 'validate', url);
    const view = new DataView(bytes); bufferCache.set(index, view); return view;
  }
  function read(bufferViewIndex, offset, componentType) {
    const bufferView = document.bufferViews?.[bufferViewIndex], component = components[componentType];
    if (!bufferView || !component) fail('Invalid skin weight accessor component/buffer view', 'validate', url);
    const view = buffer(bufferView.buffer), absoluteOffset = (bufferView.byteOffset || 0) + offset;
    if (absoluteOffset < 0 || absoluteOffset + component[0] > view.byteLength || offset + component[0] > bufferView.byteLength) fail('Skin weight accessor exceeds its buffer view', 'validate', url);
    return view[component[1]](absoluteOffset, true);
  }
  const seen = new Set();
  for (const mesh of document.meshes || []) for (const primitive of mesh.primitives || []) {
    const index = primitive.attributes?.WEIGHTS_0;
    if (index === undefined || seen.has(index)) continue;
    seen.add(index);
    const accessor = document.accessors?.[index], component = components[accessor?.componentType];
    if (!accessor || accessor.type !== 'VEC4' || !component || !accessor.count) fail(`Invalid WEIGHTS_0 accessor ${index}`, 'validate', url);
    const stride = document.bufferViews?.[accessor.bufferView]?.byteStride || component[0] * 4, sparse = new Map();
    if (accessor.sparse) for (let entry = 0; entry < accessor.sparse.count; entry++) {
      const { indices, values } = accessor.sparse, indexComponent = components[indices.componentType];
      if (!indexComponent) fail(`Invalid sparse weight indices for accessor ${index}`, 'validate', url);
      const vertex = read(indices.bufferView, (indices.byteOffset || 0) + entry * indexComponent[0], indices.componentType);
      if (vertex < 0 || vertex >= accessor.count || sparse.has(vertex)) fail(`Invalid sparse weight vertex ${vertex}`, 'validate', url);
      sparse.set(vertex, Array.from({ length: 4 }, (_, axis) => read(values.bufferView, (values.byteOffset || 0) + (entry * 4 + axis) * component[0], accessor.componentType)));
    }
    for (let vertex = 0; vertex < accessor.count; vertex++) {
      let sum = 0;
      for (let axis = 0; axis < 4; axis++) {
        let weight = sparse.get(vertex)?.[axis] ?? (accessor.bufferView === undefined ? 0 : read(accessor.bufferView, (accessor.byteOffset || 0) + vertex * stride + axis * component[0], accessor.componentType));
        if (accessor.normalized) weight /= component[2];
        if (!Number.isFinite(weight) || weight < 0 || weight > 1.00001) fail(`Source WEIGHTS_0 accessor ${index}, vertex ${vertex} has invalid weight ${weight}`, 'validate', url);
        sum += weight;
      }
      const tolerance = accessor.normalized ? 0.016 : 0.001;
      if (Math.abs(sum - 1) > tolerance) fail(`Source WEIGHTS_0 accessor ${index}, vertex ${vertex} sums to ${sum}`, 'validate', url);
    }
  }
  const timeAccessors = new Set((document.animations || []).flatMap(animation => animation.samplers.map(sampler => sampler.input)));
  for (const index of timeAccessors) {
    const accessor = document.accessors[index], view = document.bufferViews?.[accessor.bufferView], sparse = new Map();
    if (accessor.sparse) for (let entry = 0; entry < accessor.sparse.count; entry++) {
      const { indices, values } = accessor.sparse, indexComponent = components[indices.componentType];
      if (!indexComponent) fail(`Invalid sparse animation input accessor ${index}`, 'animations', url);
      const vertex = read(indices.bufferView, (indices.byteOffset || 0) + entry * indexComponent[0], indices.componentType);
      if (!Number.isInteger(vertex) || vertex < 0 || vertex >= accessor.count || sparse.has(vertex)) fail(`Invalid sparse animation input index ${vertex}`, 'animations', url);
      sparse.set(vertex, read(values.bufferView, (values.byteOffset || 0) + entry * 4, 5126));
    }
    let previous = -Infinity;
    for (let key = 0; key < accessor.count; key++) {
      const time = sparse.get(key) ?? (accessor.bufferView === undefined ? 0 : read(accessor.bufferView, (accessor.byteOffset || 0) + key * (view.byteStride || 4), 5126));
      if (!Number.isFinite(time) || time < 0 || time <= previous) fail(`Animation input accessor ${index} times must be finite, nonnegative and strictly increasing`, 'animations', url);
      previous = time;
    }
  }
}

function materialList(object) { return object.material ? (Array.isArray(object.material) ? object.material : [object.material]) : []; }

/** Idempotent ownership cleanup, including ImageBitmap storage. */
export function disposeStandardAsset(asset) {
  if (!asset || asset.__standardAssetDisposed) return;
  Object.defineProperty(asset, '__standardAssetDisposed', { value: true, configurable: true });
  const geometries = new Set(), materials = new Set(), textures = new Set(), skeletons = new Set(), images = new Set();
  for (const scene of asset.scenes || [asset.scene || asset]) scene?.traverse?.(object => {
    if (object.geometry) geometries.add(object.geometry);
    if (object.skeleton) skeletons.add(object.skeleton);
    for (const material of materialList(object)) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  for (const texture of textures) { if (texture.source?.data) images.add(texture.source.data); texture.dispose(); }
  for (const image of images) image?.close?.();
  for (const material of materials) material.dispose();
  for (const geometry of geometries) geometry.dispose();
  for (const skeleton of skeletons) skeleton.dispose?.();
}

/** Inspect the actual decoded scene. A successful result means all used maps have pixels. */
export function inspectStandardAsset(gltf, { THREE, url = '', document = gltf.parser?.json || {}, resourcePaths = [] } = {}) {
  if (!THREE?.PropertyBinding) throw new TypeError('inspectStandardAsset needs the pinned THREE module');
  const scene = gltf.scene;
  if (!scene?.traverse) fail('GLTFLoader returned no scene', 'validate', url);
  scene.updateMatrixWorld(true);
  const objects = new Set(), meshes = [], skinnedMeshes = [], materials = new Set(), textures = new Map(), joints = new Set(), warnings = [];
  scene.traverse(object => objects.add(object));
  scene.traverse(object => {
    finiteArray(object.matrixWorld.elements, `${object.name || object.type}.matrixWorld`, url);
    if (!object.isMesh) return;
    const geometry = object.geometry, position = geometry?.getAttribute('position');
    if (!position || position.itemSize !== 3 || !position.count) fail(`Mesh ${object.name} has no POSITION vertices`, 'validate', url);
    for (const [name, attribute] of Object.entries(geometry.attributes)) {
      // Interleaved and normalized accessors are read through their public API.
      for (let index = 0; index < attribute.count; index++) for (let axis = 0; axis < attribute.itemSize; axis++) {
        if (!Number.isFinite(attribute.getComponent(index, axis))) fail(`${object.name}.${name}[${index},${axis}] is not finite`, 'validate', url);
      }
      if (attribute.count !== position.count) fail(`${object.name}.${name} vertex count differs from POSITION`, 'validate', url);
    }
    const indices = geometry.index;
    if (indices) for (let index = 0; index < indices.count; index++) {
      const vertex = indices.getX(index);
      if (!Number.isInteger(vertex) || vertex < 0 || vertex >= position.count) fail(`Mesh ${object.name} has an out of range index`, 'validate', url);
    }
    const count = indices ? indices.count : position.count;
    if (count % 3) fail(`Mesh ${object.name} has incomplete triangles`, 'validate', url);
    meshes.push({ name: object.name || '(unnamed mesh)', vertices: position.count, triangles: count / 3,
      skinned: !!object.isSkinnedMesh, morphTargets: Object.keys(geometry.morphAttributes || {}).length,
      materials: materialList(object).map(material => material.name || material.type) });
    if (object.isSkinnedMesh) {
      const skeleton = object.skeleton, skinIndex = geometry.getAttribute('skinIndex'), skinWeight = geometry.getAttribute('skinWeight');
      if (!skeleton?.bones.length || skeleton.boneInverses.length !== skeleton.bones.length) fail(`Mesh ${object.name} has an incomplete skeleton/bind palette`, 'validate', url);
      if (!skinIndex || !skinWeight || skinIndex.itemSize !== 4 || skinWeight.itemSize !== 4) fail(`Mesh ${object.name} needs four joint indices and weights per vertex`, 'validate', url);
      finiteArray(object.bindMatrix.elements, `${object.name}.bindMatrix`, url);
      for (const [index, bone] of skeleton.bones.entries()) {
        if (!objects.has(bone)) fail(`Mesh ${object.name} joint ${bone.name} is outside the loaded scene`, 'validate', url);
        finiteArray(skeleton.boneInverses[index].elements, `${bone.name}.inverseBind`, url);
        if (Math.abs(skeleton.boneInverses[index].determinant()) < 1e-12) fail(`Joint ${bone.name} has a singular inverse bind matrix`, 'validate', url);
        joints.add(bone);
      }
      for (let vertex = 0; vertex < position.count; vertex++) {
        let sum = 0;
        for (let axis = 0; axis < 4; axis++) {
          const joint = skinIndex.getComponent(vertex, axis), weight = skinWeight.getComponent(vertex, axis);
          if (!Number.isInteger(joint) || joint < 0 || joint >= skeleton.bones.length) fail(`Mesh ${object.name} vertex ${vertex} references joint ${joint}`, 'validate', url);
          if (weight < 0 || weight > 1 + 1e-5) fail(`Mesh ${object.name} vertex ${vertex} has invalid skin weight`, 'validate', url);
          sum += weight;
        }
        if (Math.abs(sum - 1) > 1e-3) fail(`Mesh ${object.name} vertex ${vertex} weights sum to ${sum}`, 'validate', url);
      }
      skeleton.update();
      skinnedMeshes.push(object);
    }
    for (const material of materialList(object)) materials.add(material);
  });
  if (!meshes.length) fail('The selected scene has no renderable mesh', 'validate', url);
  for (const material of materials) {
    for (const slot of TEXTURE_SLOTS) {
      const texture = material[slot];
      if (!texture) continue;
      const image = texture.source?.data || texture.image, dimensions = imageDimensions(image);
      if (!dimensions.width || !dimensions.height || image?.complete === false) fail(`Material ${material.name || material.type} ${slot} has no decoded pixels`, 'textures', url, 'GLTF_TEXTURE');
      const entry = textures.get(texture) || { name: texture.name || '(embedded texture)', ...dimensions, slots: [], colorSpace: texture.colorSpace, channel: texture.channel };
      entry.slots.push(`${material.name || material.type}.${slot}`);
      textures.set(texture, entry);
    }
  }
  // GLTFLoader deliberately tolerates failed texture loads. Reject those omissions.
  const sourceTextureSlots = [['pbrMetallicRoughness', 'baseColorTexture', 'map'], ['pbrMetallicRoughness', 'metallicRoughnessTexture', 'metalnessMap'],
    [null, 'normalTexture', 'normalMap'], [null, 'occlusionTexture', 'aoMap'], [null, 'emissiveTexture', 'emissiveMap']];
  for (const material of materials) {
    const sourceIndex = gltf.parser?.associations?.get(material)?.materials;
    const source = document.materials?.[sourceIndex];
    if (!source) continue;
    for (const [section, sourceSlot, slot] of sourceTextureSlots) {
      if ((section ? source[section] : source)?.[sourceSlot] && !material[slot]) fail(`Material ${source.name || sourceIndex} lost required ${sourceSlot}`, 'textures', url, 'GLTF_TEXTURE');
    }
  }
  const clips = (gltf.animations || []).map(clip => {
    if (!Number.isFinite(clip.duration) || clip.duration < 0 || !clip.tracks.length) fail(`Animation ${clip.name} has no valid duration/tracks`, 'animations', url);
    const targets = new Set(), paths = new Set();
    for (const track of clip.tracks) {
      finiteArray(track.times, `${clip.name}.${track.name}.times`, url);
      finiteArray(track.values, `${clip.name}.${track.name}.values`, url);
      if (!track.times.length || track.times[0] < 0) fail(`Animation ${clip.name} has invalid key times`, 'animations', url);
      for (let index = 1; index < track.times.length; index++) if (track.times[index] <= track.times[index - 1]) fail(`Animation ${clip.name} key times must increase`, 'animations', url);
      const parsed = THREE.PropertyBinding.parseTrackName(track.name);
      const target = THREE.PropertyBinding.findNode(scene, parsed.nodeName);
      if (!target) fail(`Animation ${clip.name} target ${parsed.nodeName} is unbound`, 'animations', url);
      const cubic = track.createInterpolant?.isInterpolantFactoryMethodGLTFCubicSpline === true;
      const width = parsed.propertyName === 'quaternion' ? 4 : ['position', 'scale'].includes(parsed.propertyName) ? 3 : parsed.propertyName === 'morphTargetInfluences' ? target.morphTargetInfluences?.length : 0;
      const expectedSize = width * (cubic ? 3 : 1);
      if (!width || !Number.isInteger(track.getValueSize()) || track.getValueSize() !== expectedSize || track.values.length !== track.times.length * expectedSize) fail(`Animation ${clip.name} track ${track.name} has invalid value cardinality; expected ${expectedSize} values per key`, 'animations', url);
      if (!cubic && ![THREE.InterpolateDiscrete, THREE.InterpolateLinear].includes(track.getInterpolation())) fail(`Animation ${clip.name} track ${track.name} uses unsupported interpolation`, 'animations', url);
      const binding = new THREE.PropertyBinding(scene, track.name);
      binding.bind();
      if (!binding.node || !binding.targetObject || binding.getValue === binding._getValue_unavailable) fail(`Animation ${clip.name} track ${track.name} cannot bind`, 'animations', url);
      binding.unbind();
      targets.add(target.name || target.uuid); paths.add(parsed.propertyName);
    }
    return { name: clip.name, duration: clip.duration, tracks: clip.tracks.length, targets: [...targets], paths: [...paths] };
  });
  if (!clips.length) warnings.push('No animation clips are present; the bind pose is available.');
  const extensions = document.extensionsUsed || [];
  if (extensions.some(name => !REQUIRED_EXTENSIONS.has(name))) warnings.push(`Optional extensions: ${extensions.filter(name => !REQUIRED_EXTENSIONS.has(name)).join(', ')}; inspect their standard parser support.`);
  return {
    format: 'glTF 2.0', generator: document.asset?.generator || '', source: url,
    nodes: objects.size, meshCount: meshes.length, skinnedMeshCount: skinnedMeshes.length,
    jointCount: joints.size, jointNames: [...joints].map(joint => joint.name),
    vertices: meshes.reduce((sum, mesh) => sum + mesh.vertices, 0), triangles: meshes.reduce((sum, mesh) => sum + mesh.triangles, 0),
    meshes, materials: [...materials].map(material => ({ name: material.name || material.type, type: material.type,
      maps: TEXTURE_SLOTS.filter(slot => !!material[slot]), alphaMode: material.transparent ? 'BLEND' : material.alphaTest > 0 ? 'MASK' : 'OPAQUE',
      doubleSided: material.side === THREE.DoubleSide, metalness: material.metalness, roughness: material.roughness })),
    materialCount: materials.size, textures: [...textures.values()], textureCount: textures.size,
    clips, clipCount: clips.length, resourcePaths: [...resourcePaths], extensions, warnings,
    capabilities: { standardParser: `Three.js r${THREE.REVISION}`, externalResources: true, decodedTextures: true,
      arbitrarySkeletons: true, maxSkinInfluences: 4, morphTargets: true, scaleAnimation: true, pbrMaterials: true }
  };
}

function abortError(url, reason) {
  return new StandardAssetError(reason?.message || 'Asset load cancelled', { stage: 'cancel', url, code: 'GLTF_ABORTED', cause: reason });
}

/** Each call owns its parser, requests and resources; callers may replace assets safely. */
export function createStandardAssetLoader({ THREE, GLTFLoader, fetchImpl = globalThis.fetch } = {}) {
  if (!THREE?.LoadingManager || !GLTFLoader) throw new TypeError('createStandardAssetLoader needs the pinned THREE and GLTFLoader modules');
  return {
    async load({ url, signal, onProgress, timeoutMs = 12000 }) {
      const absoluteURL = new URL(url, globalThis.location?.href || 'http://localhost/').href;
      const base = new URL('.', absoluteURL).href, controller = new AbortController(), resources = new Map(), objectURLs = new Set();
      const failures = [], manager = new THREE.LoadingManager(), startedAt = performance.now();
      let parsed, settled = false, timer, rejectCancellation;
      const progress = (stage, details = {}) => onProgress?.({ stage, url: absoluteURL, elapsedMs: performance.now() - startedAt, ...details });
      const cancelled = new Promise((_, reject) => { rejectCancellation = reject; });
      const abort = () => { controller.abort(signal?.reason); rejectCancellation(abortError(absoluteURL, signal?.reason)); };
      const cleanupURLs = () => { for (const objectURL of objectURLs) URL.revokeObjectURL(objectURL); objectURLs.clear(); };
      if (signal?.aborted) throw abortError(absoluteURL, signal.reason);
      signal?.addEventListener('abort', abort, { once: true });
      timer = setTimeout(() => {
        const error = new StandardAssetError(`Asset loading exceeded ${timeoutMs} ms`, { stage: 'timeout', url: absoluteURL, code: 'GLTF_TIMEOUT' });
        controller.abort(error); rejectCancellation(error);
      }, timeoutMs);
      manager.setURLModifier(request => {
        if (/^(data:|blob:)/.test(request)) return request;
        const resolved = new URL(request, base).href;
        return resources.get(resolved)?.objectURL || request;
      });
      manager.onError = request => {
        const original = [...resources.entries()].find(([, resource]) => resource.objectURL === request)?.[0] || (/^blob:/.test(request) ? `${absoluteURL}#embedded-image` : request);
        failures.push(original);
      };
      async function fetchResource(resourceURL, stage) {
        progress(stage, { resource: resourceURL });
        let response;
        try { response = await fetchImpl(resourceURL, { signal: controller.signal }); }
        catch (cause) {
          if (controller.signal.aborted) throw abortError(resourceURL, controller.signal.reason);
          throw new StandardAssetError(cause.message || 'Network request failed', { stage, url: resourceURL, cause });
        }
        if (!response.ok) fail(`HTTP ${response.status} ${response.statusText || ''}`.trim(), stage, resourceURL, 'GLTF_HTTP');
        const bytes = await response.arrayBuffer();
        progress(stage, { resource: resourceURL, loaded: bytes.byteLength, total: Number(response.headers.get('content-length')) || bytes.byteLength });
        return { bytes, type: response.headers.get('content-type') };
      }
      const work = (async () => {
        const root = await fetchResource(absoluteURL, 'fetch');
        const document = readGLTFDocument(root.bytes, absoluteURL);
        const dependencies = new Map();
        for (const [kind, entries] of [['buffer', document.buffers || []], ['image', document.images || []]]) {
          for (const entry of entries) if (entry.uri && !entry.uri.startsWith('data:')) dependencies.set(new URL(entry.uri, base).href, { kind, mimeType: entry.mimeType });
        }
        // allSettled keeps ownership of every completed request even on a sibling failure.
        const fetched = await Promise.allSettled([...dependencies].map(async ([resourceURL, descriptor]) => {
          const resource = await fetchResource(resourceURL, descriptor.kind);
          if (controller.signal.aborted) throw abortError(resourceURL, controller.signal.reason);
          const objectURL = URL.createObjectURL(new Blob([resource.bytes], { type: descriptor.mimeType || resource.type || 'application/octet-stream' }));
          objectURLs.add(objectURL); resources.set(resourceURL, { ...resource, objectURL });
        }));
        const failed = fetched.find(result => result.status === 'rejected');
        if (failed) throw failed.reason;
        if (controller.signal.aborted) throw abortError(absoluteURL, controller.signal.reason);
        validateSourceData(document, root.bytes, resources, base, absoluteURL);
        progress('parse');
        try { parsed = await new GLTFLoader(manager).parseAsync(root.bytes, base); }
        catch (cause) { throw new StandardAssetError(`Official GLTFLoader: ${cause.message || cause}${failures.length ? `; failed resource: ${failures.join(', ')}` : ''}`, { stage: 'parse', url: failures[0] || absoluteURL, cause }); }
        if (controller.signal.aborted || settled) { disposeStandardAsset(parsed); throw abortError(absoluteURL, controller.signal.reason); }
        if (failures.length) fail(`Resource decoding failed: ${failures.join(', ')}`, 'textures', failures[0], 'GLTF_TEXTURE');
        progress('validate');
        const metadata = inspectStandardAsset(parsed, { THREE, url: absoluteURL, document, resourcePaths: [absoluteURL, ...dependencies.keys()] });
        const result = { ...parsed, gltf: parsed, document, metadata, url: absoluteURL, resources: [...dependencies.keys()],
          dispose() { disposeStandardAsset(parsed); } };
        progress('ready', { metadata });
        return result;
      })();
      // Late parser completion after cancellation is cleaned up inside work.
      try { const result = await Promise.race([work, cancelled]); settled = true; return result; }
      catch (error) { settled = true; controller.abort(error); if (parsed) disposeStandardAsset(parsed); throw error; }
      finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); cleanupURLs(); }
    }
  };
}

/** Convenience entry point; browser resolves these imports through the local import map. */
export async function loadStandardAsset(options) {
  const [THREE, { GLTFLoader }] = await Promise.all([import('three'), import('three/addons/loaders/GLTFLoader.js')]);
  return createStandardAssetLoader({ THREE, GLTFLoader }).load(options);
}
