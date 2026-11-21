/* Explicit bridge from a standard parsed scene to the existing 19-joint DQ draw. */
export const CUSTOM_BONE_NAMES = Object.freeze(['pelvis', 'spine', 'chest', 'neck', 'head',
  'clavicle.L', 'upper_arm.L', 'forearm.L', 'hand.L', 'thigh.L', 'shin.L', 'foot.L',
  'clavicle.R', 'upper_arm.R', 'forearm.R', 'hand.R', 'thigh.R', 'shin.R', 'foot.R']);
export const CUSTOM_MATERIAL_NAMES = Object.freeze(['skin', 'shirt', 'shorts', 'socks', 'boots',
  'hair', 'eye-white', 'iris', 'pupil', 'brows']);
const PARENTS = [-1, 0, 1, 2, 3, 2, 5, 6, 7, 0, 9, 10, 2, 12, 13, 14, 0, 16, 17];
const UNIT_TOLERANCE = 0.0001;
const SOURCE_MAPS = ['normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap',
  'alphaMap', 'bumpMap', 'displacementMap', 'clearcoatMap', 'clearcoatNormalMap',
  'clearcoatRoughnessMap', 'transmissionMap', 'thicknessMap', 'specularIntensityMap',
  'specularColorMap', 'sheenColorMap', 'sheenRoughnessMap', 'iridescenceMap',
  'iridescenceThicknessMap', 'anisotropyMap'];

function rigid(matrix, tolerance = UNIT_TOLERANCE) {
  const m = matrix.elements || matrix;
  if (!m || m.length !== 16 || !Array.from(m).every(Number.isFinite)) return false;
  for (let col = 0; col < 3; col++) if (Math.abs(Math.hypot(m[col * 4], m[col * 4 + 1], m[col * 4 + 2]) - 1) > tolerance) return false;
  for (let a = 0; a < 3; a++) for (let b = a + 1; b < 3; b++) {
    if (Math.abs(m[a * 4] * m[b * 4] + m[a * 4 + 1] * m[b * 4 + 1] + m[a * 4 + 2] * m[b * 4 + 2]) > tolerance) return false;
  }
  const determinant = m[0] * (m[5] * m[10] - m[9] * m[6]) - m[4] * (m[1] * m[10] - m[9] * m[2]) + m[8] * (m[1] * m[6] - m[5] * m[2]);
  return Math.abs(determinant - 1) <= tolerance * 3 && Math.abs(m[3]) < tolerance && Math.abs(m[7]) < tolerance && Math.abs(m[11]) < tolerance && Math.abs(m[15] - 1) < tolerance;
}

function base64(array) {
  const bytes = new Uint8Array(array.buffer, array.byteOffset, array.byteLength);
  if (typeof Buffer !== 'undefined') return Buffer.from(bytes).toString('base64');
  let binary = '';
  for (let start = 0; start < bytes.length; start += 16384) binary += String.fromCharCode(...bytes.subarray(start, start + 16384));
  return btoa(binary);
}

function whiteImage() {
  if (typeof OffscreenCanvas !== 'undefined') {
    const canvas = new OffscreenCanvas(1, 1), context = canvas.getContext('2d');
    context.fillStyle = '#fff'; context.fillRect(0, 0, 1, 1); return canvas;
  }
  if (typeof document !== 'undefined') {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d'); context.fillStyle = '#fff'; context.fillRect(0, 0, 1, 1); return canvas;
  }
  return { width: 1, height: 1, data: new Uint8Array([255, 255, 255, 255]) };
}

/**
 * Geometry is converted once and shared by every actor. getPalette(scene) reads
 * the imported/animated clone's actual bone world matrices, never procedural Rig.
 * Unsupported features are a custom-backend result, not a standard-load failure.
 */
export function createCustomRuntimeAdapter(asset, { THREE } = {}) {
  if (!THREE?.Matrix4) throw new TypeError('createCustomRuntimeAdapter needs the pinned THREE module');
  const scene = asset.scene, parser = asset.parser || asset.gltf?.parser, document = asset.document || parser?.json || {};
  const reasons = [], warnings = [], meshes = [], allMaterials = new Set(), sourceBones = new Map(), sourceNameForBone = new Map();
  const reject = message => { if (!reasons.includes(message)) reasons.push(message); };
  const sourceName = object => document.nodes?.[parser?.associations?.get(object)?.nodes]?.name || object.userData?.name || object.name;
  scene.updateMatrixWorld(true);
  scene.traverse(object => {
    if (object.isBone) {
      const name = sourceName(object);
      if (sourceBones.has(name) && sourceBones.get(name) !== object) reject(`Duplicate bone name ${name} is outside the custom skeleton subset.`);
      sourceBones.set(name, object); sourceNameForBone.set(object, name);
    }
    if (!object.isMesh) {
      if (object.isLine || object.isPoints || object.isSprite) reject(`${object.type} ${object.name} is not supported by the custom triangle renderer.`);
      return;
    }
    meshes.push(object);
    if (!object.isSkinnedMesh) reject(`Static mesh ${object.name} is not supported by the custom skinned draw.`);
    if (object.isInstancedMesh) reject(`Instanced mesh ${object.name} is outside the custom subset.`);
    if (!object.geometry.getAttribute('normal')) reject(`Mesh ${object.name} needs exported vertex normals for the custom renderer.`);
    if (Object.keys(object.geometry.morphAttributes || {}).some(name => object.geometry.morphAttributes[name].length)) reject(`Morph targets on ${object.name} require the Three.js backend.`);
    if (object.bindMatrix && !rigid(object.bindMatrix)) reject(`Mesh ${object.name} has a scaled or reflected bind matrix; the custom DQ renderer needs rigid transforms.`);
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) allMaterials.add(material);
  });
  if (sourceBones.size !== CUSTOM_BONE_NAMES.length || CUSTOM_BONE_NAMES.some(name => !sourceBones.has(name))) reject(`Custom renderer requires the named 19-joint humanoid; this scene has ${sourceBones.size} bones.`);
  const paletteSources = [], inverseBinds = [], cloneNames = [];
  for (const [index, name] of CUSTOM_BONE_NAMES.entries()) {
    const bone = sourceBones.get(name);
    if (!bone) continue;
    let parent = bone.parent;
    while (parent && !parent.isBone) parent = parent.parent;
    const expectedParent = PARENTS[index] < 0 ? undefined : CUSTOM_BONE_NAMES[PARENTS[index]];
    if (sourceNameForBone.get(parent) !== expectedParent) reject(`Bone ${name} has a different parent from the custom humanoid hierarchy.`);
    let inverse;
    for (const mesh of meshes) if (mesh.isSkinnedMesh) {
      const at = mesh.skeleton.bones.indexOf(bone);
      if (at < 0) { reject(`Mesh ${mesh.name} does not bind the complete custom skeleton.`); continue; }
      const candidate = mesh.skeleton.boneInverses[at];
      if (!inverse) inverse = candidate.clone();
      else if (candidate.elements.some((value, at) => Math.abs(value - inverse.elements[at]) > UNIT_TOLERANCE)) reject(`Meshes use different inverse binds for ${name}.`);
    }
    if (inverse) {
      if (!rigid(inverse)) reject(`Bone ${name} has a scaled/reflected inverse bind; the custom DQ renderer needs rigid transforms.`);
      const skin = new THREE.Matrix4().multiplyMatrices(bone.matrixWorld, inverse);
      if (!rigid(skin)) reject(`Bone ${name} produces a scaled/reflected skin matrix.`);
      inverseBinds[index] = inverse; paletteSources[index] = bone; cloneNames[index] = bone.name;
    }
  }
  for (const clip of asset.animations || []) for (const track of clip.tracks) {
    const property = THREE.PropertyBinding.parseTrackName(track.name).propertyName;
    if (property === 'scale') {
      if (Array.from(track.values).some(value => Math.abs(value - 1) > 0.00002)) reject(`Scale animation ${clip.name}/${track.name} requires the Three.js backend.`);
      else if (!warnings.includes('Blender unit-scale bake tracks are within 0.00002 of identity; the custom DQ path approximates these as rigid.')) warnings.push('Blender unit-scale bake tracks are within 0.00002 of identity; the custom DQ path approximates these as rigid.');
    } else if (!['position', 'quaternion'].includes(property)) reject(`Animated property ${clip.name}/${property} requires the Three.js backend.`);
    const parsed = THREE.PropertyBinding.parseTrackName(track.name), target = THREE.PropertyBinding.findNode(scene, parsed.nodeName);
    // Mesh/parent animation can change bind behaviour and is deliberately outside this bridge.
    if (target && !target.isBone) reject(`Animation target ${target.name} is not a deform joint; use the Three.js backend.`);
  }
  const materialSlots = new Map(), baseColors = new Float32Array(30).fill(1), roughness = new Float32Array(10).fill(0.72), mapImages = { skin: null, fabric: null };
  const textureSettings = {}, textureSignatures = {}, semanticMaterials = new Map();
  const mipFilters = [THREE.NearestMipmapNearestFilter, THREE.NearestMipmapLinearFilter, THREE.LinearMipmapNearestFilter, THREE.LinearMipmapLinearFilter];
  for (const material of allMaterials) {
    const source = document.materials?.[parser?.associations?.get(material)?.materials];
    const name = source?.name || material.name, slot = CUSTOM_MATERIAL_NAMES.indexOf(name);
    if (slot < 0) { reject(`Material ${name || '(unnamed)'} is not one of the ten custom semantic material slots.`); continue; }
    if (semanticMaterials.has(slot) && semanticMaterials.get(slot) !== material) reject(`Distinct materials share the custom semantic slot ${name}; material names need to be unique for this backend.`);
    semanticMaterials.set(slot, material);
    materialSlots.set(material, slot);
    if (material.type !== 'MeshStandardMaterial') reject(`Material ${name} uses ${material.type}; use the Three.js backend for this material model.`);
    if (material.transparent || material.alphaTest > 0 || material.opacity < 0.99999) reject(`Material ${name} uses alpha blending/masking; use the Three.js backend.`);
    if (material.side !== THREE.FrontSide) reject(`Material ${name} is double-sided; use the Three.js backend.`);
    if (material.metalness > 0.00001) reject(`Material ${name} has metallic response; use the Three.js backend.`);
    if (material.emissive && material.emissive.getHex() !== 0 && material.emissiveIntensity > 0) reject(`Material ${name} is emissive; use the Three.js backend.`);
    for (const map of SOURCE_MAPS) if (material[map]) reject(`Material ${name} uses ${map}; the custom backend supports only base color maps.`);
    baseColors.set(material.color.toArray(), slot * 3); roughness[slot] = material.roughness;
    if (material.map) {
      const texture = material.map, family = slot === 0 ? 'skin' : 'fabric', image = texture.source?.data || texture.image;
      if (texture.channel !== 0 || texture.offset.x || texture.offset.y || texture.repeat.x !== 1 || texture.repeat.y !== 1 || texture.rotation) reject(`Material ${name} needs transformed or alternate-channel UVs; use the Three.js backend.`);
      if (mapImages[family] && mapImages[family] !== image) reject(`Custom ${family} slots use different base color images; use the Three.js backend.`);
      mapImages[family] = image;
      if (texture.flipY) reject(`Material ${name} has a nonstandard vertical image orientation.`);
      if (texture.colorSpace !== THREE.SRGBColorSpace) reject(`Material ${name} base color map is not sRGB; use the Three.js backend.`);
      if (texture.mapping !== THREE.UVMapping || texture.anisotropy !== 1 || texture.premultiplyAlpha) reject(`Material ${name} needs unsupported texture mapping, anisotropy or premultiplied alpha.`);
      const settings = { wrapS: texture.wrapS, wrapT: texture.wrapT, minFilter: texture.minFilter, magFilter: texture.magFilter };
      const signature = JSON.stringify({ ...settings, colorSpace: texture.colorSpace,
        channel: texture.channel, offset: texture.offset.toArray(), repeat: texture.repeat.toArray(), rotation: texture.rotation, center: texture.center.toArray() });
      if (textureSignatures[family] && textureSignatures[family] !== signature) reject(`Custom ${family} slots use different sampler/color-space/UV settings; use the Three.js backend.`);
      textureSignatures[family] = signature; textureSettings[family] = settings;
      const width = image?.naturalWidth || image?.width || 0, height = image?.naturalHeight || image?.height || 0;
      const powerOfTwo = value => value > 0 && (value & (value - 1)) === 0;
      if ((!powerOfTwo(width) || !powerOfTwo(height)) && (settings.wrapS !== THREE.ClampToEdgeWrapping || settings.wrapT !== THREE.ClampToEdgeWrapping || mipFilters.includes(settings.minFilter))) reject(`Material ${name} needs repeat/mipmap sampling on a non-power-of-two image; the custom WebGL1 backend cannot represent this sampler.`);
    }
  }
  // One sampler is shared by each family; mixed textured/untextured slots would
  // otherwise accidentally receive another material's map.
  for (const [material, slot] of materialSlots) if (!material.map && mapImages[slot === 0 ? 'skin' : 'fabric']) reject(`Material ${material.name} is untextured inside a shared textured custom material family.`);
  const capabilities = { skeleton: 'named 19-joint humanoid', skinning: 'rigid dual quaternion', materialModel: 'opaque base color + roughness',
    morphTargets: false, scaleAnimation: false, normalMaps: false, metallicRoughnessMaps: false, alpha: false };
  const common = { supported: reasons.length === 0, reasons, warnings, capabilities };
  if (reasons.length) return common;

  const vertices = [], indices = [], point = new THREE.Vector3(), normal = new THREE.Vector3(), normalMatrix = new THREE.Matrix3();
  for (const mesh of meshes) {
    const geometry = mesh.geometry, position = geometry.getAttribute('position'), normals = geometry.getAttribute('normal'), uv = geometry.getAttribute('uv'), color = geometry.getAttribute('color');
    const joints = geometry.getAttribute('skinIndex'), weights = geometry.getAttribute('skinWeight'), meshMaterials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const index = geometry.index, count = index?.count || position.count;
    const groups = geometry.groups.length ? geometry.groups : [{ start: 0, count, materialIndex: 0 }], lookup = new Map();
    normalMatrix.getNormalMatrix(mesh.bindMatrix);
    const jointRemap = mesh.skeleton.bones.map(bone => CUSTOM_BONE_NAMES.indexOf(sourceNameForBone.get(bone)));
    for (const group of groups) {
      const material = meshMaterials[group.materialIndex || 0], materialSlot = materialSlots.get(material);
      for (let item = group.start; item < Math.min(count, group.start + group.count); item++) {
        const vertex = index ? index.getX(item) : item, key = `${materialSlot}:${vertex}`;
        let output = lookup.get(key);
        if (output === undefined) {
          output = vertices.length / 20; lookup.set(key, output);
          point.fromBufferAttribute(position, vertex).applyMatrix4(mesh.bindMatrix);
          normal.fromBufferAttribute(normals, vertex).applyMatrix3(normalMatrix).normalize();
          vertices.push(point.x, point.y, point.z, normal.x, normal.y, normal.z, uv?.getX(vertex) || 0, uv?.getY(vertex) || 0);
          for (let axis = 0; axis < 4; axis++) vertices.push(jointRemap[joints.getComponent(vertex, axis)]);
          for (let axis = 0; axis < 4; axis++) vertices.push(weights.getComponent(vertex, axis));
          vertices.push(materialSlot);
          for (let axis = 0; axis < 3; axis++) vertices.push(material.vertexColors && color ? color.getComponent(vertex, axis) : 1);
        }
        indices.push(output);
      }
    }
  }
  const vertexArray = new Float32Array(vertices), IndexType = vertices.length / 20 > 65535 ? Uint32Array : Uint16Array, indexArray = new IndexType(indices);
  const bones = CUSTOM_BONE_NAMES.map((name, index) => {
    const matrix = inverseBinds[index].clone().invert(), head = new THREE.Vector3().setFromMatrixPosition(matrix);
    const child = PARENTS.indexOf(index), tail = child >= 0 ? new THREE.Vector3().setFromMatrixPosition(inverseBinds[child].clone().invert()) : head.clone().add(new THREE.Vector3(0, 0.1, 0).transformDirection(matrix).multiplyScalar(0.1));
    if (head.distanceTo(tail) < 1e-6) tail.y += 0.1;
    return { name, parent: PARENTS[index], head: head.toArray(), tail: tail.toArray(), matrix: matrix.toArray(), inverseBind: inverseBinds[index].toArray() };
  });
  const assets = { metadata: { id: 'standard-gltf-custom-adapter', source: asset.url || asset.metadata?.source || 'standard glTF scene',
    license: document.asset?.copyright || 'See source asset credits', version: '1' }, bones,
    textures: { skin: '(decoded glTF skin image)', fabric: '(decoded glTF fabric image)' },
    lods: [{ vertices: base64(vertexArray), indices: base64(indexArray), vertexCount: vertexArray.length / 20,
      indexCount: indexArray.length, indexType: IndexType === Uint16Array ? 'H' : 'I' }] };
  const fallback = (!mapImages.skin || !mapImages.fabric) ? whiteImage() : null;
  const textureImages = { skin: mapImages.skin || fallback, fabric: mapImages.fabric || fallback };
  for (const family of ['skin', 'fabric']) textureSettings[family] ||= { wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter };
  const sceneBoneCache = new WeakMap();
  function bonesForScene(targetScene) {
    if (targetScene === scene) return paletteSources;
    if (sceneBoneCache.has(targetScene)) return sceneBoneCache.get(targetScene);
    const byName = new Map();
    targetScene.traverse(object => { if (object.isBone) byName.set(object.name, object); });
    const cloned = cloneNames.map(name => byName.get(name));
    if (cloned.some(bone => !bone)) throw new Error('Custom palette scene does not contain the validated imported skeleton.');
    sceneBoneCache.set(targetScene, cloned); return cloned;
  }
  function getPalette(targetScene = scene) {
    targetScene.updateWorldMatrix(true, true);
    const actorBones = bonesForScene(targetScene), palette = new Float32Array(19 * 16), matrix = new THREE.Matrix4();
    for (let index = 0; index < actorBones.length; index++) {
      matrix.multiplyMatrices(actorBones[index].matrixWorld, inverseBinds[index]);
      if (!rigid(matrix)) throw new Error(`Custom palette ${CUSTOM_BONE_NAMES[index]} contains scale, shear or a reflection; select the Three.js backend.`);
      palette.set(matrix.elements, index * 16);
    }
    return palette;
  }
  return { ...common, assets, textureImages, textureSettings, textureFlipY: false, appearance: { baseColors, roughness },
    standardMaterials: { baseColors, roughness }, getPalette, paletteForScene: getPalette,
    geometry: { vertices: vertexArray, indices: indexArray }, boneNames: [...CUSTOM_BONE_NAMES] };
}
