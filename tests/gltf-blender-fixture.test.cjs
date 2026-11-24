'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),zlib=require('node:zlib');
const Rig=require('../humanoid-rig'),Renderer=require('../player-renderer'),Scenarios=require('../animation-scenarios');
const Assets=require('../assets/player/player-model-data');
const Baker=require('../tools/bake-licensed-clips.cjs');
const ROOT=path.resolve(__dirname,'..'),DIR=path.join(ROOT,'assets/interchange');
const manifest=JSON.parse(fs.readFileSync(path.join(DIR,'manifest.json')));
const sha256=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const read=relative=>fs.readFileSync(path.join(ROOT,relative));
function portablePath(relative){assert.equal(typeof relative,'string');assert(!path.isAbsolute(relative)&&!relative.includes('\\')&&!/^[a-z][a-z\d+.-]*:/i.test(relative),relative+' is a portable relative path');assert.equal(path.posix.normalize(relative),relative);assert(!relative.split('/').includes('..'),relative+' stays in its package');}
function gltf(file){const bytes=fs.readFileSync(file);if(file.endsWith('.glb'))return Baker.parseGLB(bytes);const json=JSON.parse(bytes);return {json,bin:fs.readFileSync(path.resolve(path.dirname(file),json.buffers[0].uri))};}
const outputs=['footballer.blender.glb','footballer.blender.gltf'].map(file=>({file,...gltf(path.join(DIR,file))}));
const source=gltf(path.join(ROOT,'assets/player/footballer.glb'));
const widths={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16};
const component={5121:[1,'readUInt8',255],5123:[2,'readUInt16LE',65535],5125:[4,'readUInt32LE',4294967295],5126:[4,'readFloatLE',1]};
function accessor(model,id){const a=model.json.accessors[id],view=model.json.bufferViews[a.bufferView],width=widths[a.type],[bytes,method,maximum]=component[a.componentType];assert(width&&bytes);const result=[];for(let i=0;i<a.count;i++){const row=[];for(let c=0;c<width;c++){let value=model.bin[method]((view.byteOffset||0)+(a.byteOffset||0)+i*(view.byteStride||bytes*width)+c*bytes);if(a.normalized)value/=maximum;row.push(value);}result.push(row);}return result;}
const near=(a,b,tolerance,message)=>assert(Math.abs(a-b)<=tolerance,`${message}: ${a} versus ${b} (tolerance ${tolerance})`);
// Independent row-major matrix implementation: never call the baker's matrix
// multiplication, inverse or decomposition in round-trip pose verification.
const identity=()=>[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];
const rowMatrix=flat=>Array.from({length:4},(_,r)=>Array.from({length:4},(_,c)=>flat[c*4+r]));
const multiply=(a,b)=>a.map(row=>b[0].map((_,column)=>row.reduce((sum,value,k)=>sum+value*b[k][column],0)));
function trs(node){const t=node.translation||[0,0,0],s=node.scale||[1,1,1],q=node.rotation||[0,0,0,1],n=Math.hypot(...q),[x,y,z,w]=q.map(v=>v/n);return [[(1-2*(y*y+z*z))*s[0],2*(x*y-z*w)*s[1],2*(x*z+y*w)*s[2],t[0]],[2*(x*y+z*w)*s[0],(1-2*(x*x+z*z))*s[1],2*(y*z-x*w)*s[2],t[1]],[2*(x*z-y*w)*s[0],2*(y*z+x*w)*s[1],(1-2*(x*x+y*y))*s[2],t[2]],[0,0,0,1]];}
function animatedWorld(model,animation,key){const nodes=structuredClone(model.json.nodes),parents=[];nodes.forEach((node,i)=>(node.children||[]).forEach(child=>parents[child]=i));for(const channel of animation.channels){const sampler=animation.samplers[channel.sampler];nodes[channel.target.node][channel.target.path]=accessor(model,sampler.output)[key];}const cache=[];function world(i){return cache[i]||(cache[i]=multiply(parents[i]===undefined?identity():world(parents[i]),nodes[i].matrix?rowMatrix(nodes[i].matrix):trs(nodes[i])));}return nodes.map((_,i)=>world(i));}
function expectedSamples(clip){const scenario=Scenarios.create(clip.name==='idle'?'walk':clip.name),samples=[];for(let tick=0;tick<=Math.round(clip.duration*60);tick++){const p=scenario.p;if(clip.name==='idle')Object.assign(p,{x:0,z:0,face:0,speed:0,action:'idle',actionClock:0});else Scenarios.sample(scenario,tick/60,Rig);const pose=Rig.update(p,1/60);if(tick%2===0){const palette=Renderer.palette(p,Assets,pose);samples.push(Assets.bones.map((bone,j)=>({skin:rowMatrix(palette.subarray(j*16,j*16+16)),world:multiply(rowMatrix(palette.subarray(j*16,j*16+16)),rowMatrix(bone.matrix))})));}}return samples;}
const referenceClips=manifest.clips.map(clip=>({clip,samples:expectedSamples(clip)}));

test('official Khronos validator reports zero errors and warnings for canonical input and both Blender exports',async()=>{
 const validator=require('gltf-validator'),report=JSON.parse(read('assets/interchange/khronos-validation.json'));
 assert.equal(report.version,validator.version());
 const inputs=[{file:'canonical animated intermediate GLB',bytes:Baker.bakeLicensedGLB().glb},{file:'assets/player/footballer.glb',bytes:read('assets/player/footballer.glb')},...outputs.map(model=>({file:'assets/interchange/'+model.file,bytes:read('assets/interchange/'+model.file)}))];
 for(const input of inputs){const result=await validator.validateBytes(new Uint8Array(input.bytes),{uri:path.basename(input.file),maxIssues:1000,externalResourceFunction:uri=>Promise.resolve(new Uint8Array(read(path.join(path.dirname(input.file),decodeURIComponent(uri)))))});assert.equal(result.issues.numErrors,0,JSON.stringify(result.issues));assert.equal(result.issues.numWarnings,0,JSON.stringify(result.issues));const recorded=report.reports.find(r=>r.path===input.file);assert.equal(recorded.sha256,sha256(input.bytes));assert.deepEqual(recorded.issues,result.issues);}
});

test('Blender package pins the licensed originals, tools, editable project and both export formats',()=>{
 assert.equal(manifest.license,'CC0-1.0');assert.equal(manifest.blenderVersion,'4.3.2');
 assert.equal(manifest.toolProvenance.name,'Blender');assert.equal(manifest.toolProvenance.version,manifest.blenderVersion);assert.equal(manifest.toolProvenance.license,'GPL-3.0-or-later');assert.match(manifest.toolProvenance.scope,/no Blender program code is copied/);
 assert.equal(manifest.unit,'metre');assert.equal(manifest.upAxis,'+Y');assert.equal(manifest.forwardAxis,'+X');assert.equal(manifest.fps,30);assert.equal(manifest.simulationHz,60);
 assert.equal(require('../tools/rig-provenance.cjs').verifyRigReference(manifest.rigReferenceSHA256),manifest.rigReferenceSHA256);
 assert.equal(sha256(read(manifest.sourceModel)),manifest.sourceModelSHA256);
 assert.equal(new Set(manifest.files.map(entry=>entry.path)).size,manifest.files.length,'packaged files are unique');
 assert(!manifest.files.some(entry=>entry.path==='assets/interchange/manifest.json'),'manifest excludes its own changing hash');
 for(const entry of manifest.files){portablePath(entry.path);assert(entry.path.startsWith('assets/interchange/'));const bytes=read(entry.path);assert.equal(bytes.length,entry.bytes,entry.path);assert.equal(sha256(bytes),entry.sha256,entry.path);}
 // These are the source bytes used when the Blender 4.3.2 exports were
 // authored. Keep the historical hashes immutable. Later runtime-only
 // renderer changes and builder documentation edits cannot retroactively
 // rewrite the Blender session that produced the shipped GLB.
 //
 // For explicitly reviewed forward-compatible revisions, pin the CURRENT
 // Git blob too, and (below) compare the *whole* canonical animated GLB
 // byte-for-byte with the Blender package's original input SHA256. Any
 // changed baked pose, bind, clips, or geometry fails that check.
 const reviewedCompatibleSources={
  // Draw-only culling, transient upload buffers and animation detail; the
  // unchanged canonical GLB byte comparison below must still pass.
  'player-renderer.js':'f22c829e4bdf05c121aed54b7660e1f28798a041',
  // Runtime-only recovery cue; original canonical baked GLB must still match.
  'humanoid-rig.js':'2901e6c2e68633bf35810104abc0114666073dcc',
  'tools/bake-licensed-clips.cjs':'64117f50a446c1904bdc6ab48790ae11bbaed971',
  'tools/build-player-assets.py':'98c52e9bf30cd05f5ff51a398b261d10f990dd82'
 };
 const blobSHA1=bytes=>crypto.createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex');
 const rebuild=JSON.parse(read('assets/interchange/rebuild.json'));
 for(const entry of rebuild.sources){
  portablePath(entry.path);const bytes=read(entry.path);
  if(bytes.length===entry.bytes&&sha256(bytes)===entry.sha256)continue;
  const reviewed=reviewedCompatibleSources[entry.path];
  assert(reviewed,entry.path+' differs from the historical Blender build without a reviewed compatible revision');
  assert.equal(blobSHA1(bytes),reviewed,entry.path+' current revision is unreviewed');
 }
 assert(fs.statSync(path.join(DIR,'editable.blend')).size<10*1024*1024);
 const provenance=JSON.parse(read(manifest.sourceProvenance));assert.equal(provenance.files.length,5);assert.deepEqual(manifest.originalPinnedSourceFiles,provenance);
 const originals={'makehuman/data/3dobjs/base.obj':'assets/player/source/makehuman-base.obj.gz','makehuman/data/rigs/default.mhskel':'assets/player/source/makehuman-default.mhskel.gz','makehuman/data/rigs/default_weights.mhw':'assets/player/source/makehuman-default_weights.mhw.gz','LICENSE.md':'assets/player/SOURCE-LICENSE.md','LICENSE.ASSETS.md':'assets/player/LICENSE-CC0.txt'};
 for(const entry of provenance.files){const file=originals[entry.repositoryPath],data=file.endsWith('.gz')?zlib.gunzipSync(read(file)):read(file);assert.equal(data.length,entry.bytes);assert.equal(sha256(data),entry.sha256);assert(entry.sourceURL.includes(manifest.sourceCommit));}
 const baked=Baker.bakeLicensedGLB();assert.equal(sha256(baked.glb),rebuild.canonicalInput.sha256);assert.equal(baked.glb.length,rebuild.canonicalInput.bytes);
 for(const animation of baked.json.animations)for(const channel of animation.channels)assert.equal(baked.json.nodes[channel.target.node].matrix,undefined,'animated nodes use TRS');
});

for(const model of outputs){
 test(`${model.file}: actual Blender export retains skin, 10 materials, source maps, normals, UVs, colors and weights`,()=>{
  const {json}=model;assert.match(json.asset.generator,/Khronos glTF Blender I\/O/);assert.equal(json.asset.version,'2.0');assert.equal(json.skins.length,1);assert.equal(json.skins[0].joints.length,19);assert.equal(json.materials.length,10);assert.equal(json.images.length,2);
  for(const resource of [...json.buffers,...json.images])if(resource.uri){const relative=decodeURIComponent(resource.uri);portablePath(relative);assert(fs.statSync(path.join(DIR,relative)).isFile(),relative+' exists beside the portable glTF');}
  assert.deepEqual(json.skins[0].joints.map(i=>json.nodes[i].name).sort(),Assets.bones.map(b=>b.name).sort());
  let vertices=0,triangles=0,maxWeight=0,maxNormal=0,maxColor=0,maxPosition=0;
  for(const primitive of json.meshes[0].primitives){
   const name=json.materials[primitive.material].name,original=source.json.meshes[0].primitives.find(p=>source.json.materials[p.material].name===name),sourceRows={},rows={};
   for(const attr of ['POSITION','NORMAL','TEXCOORD_0','COLOR_0','JOINTS_0','WEIGHTS_0']){assert.notEqual(primitive.attributes[attr],undefined,attr);sourceRows[attr]=accessor(source,original.attributes[attr]);rows[attr]=accessor(model,primitive.attributes[attr]);}
   const indices=accessor(model,primitive.indices).flat(),sourceIndices=accessor(source,original.indices).flat();assert.equal(indices.length,sourceIndices.length);triangles+=indices.length/3;vertices+=rows.POSITION.length;
   const candidates=new Map();for(const i of new Set(sourceIndices)){const key=sourceRows.POSITION[i].map(v=>Math.round(v*10000)).join(',');if(!candidates.has(key))candidates.set(key,[]);candidates.get(key).push(i);}
   const sourceJointNames=source.json.skins[0].joints.map(i=>source.json.nodes[i].name),jointNames=json.skins[0].joints.map(i=>json.nodes[i].name),matched=[];
   for(let i=0;i<rows.POSITION.length;i++){
    const bucket=rows.POSITION[i].map(v=>Math.round(v*10000)),options=[];
    for(let x=-1;x<=1;x++)for(let y=-1;y<=1;y++)for(let z=-1;z<=1;z++)options.push(...(candidates.get([bucket[0]+x,bucket[1]+y,bucket[2]+z].join(','))||[]));
    const selected=options.find(j=>rows.POSITION[i].every((v,c)=>Math.abs(v-sourceRows.POSITION[j][c])<2e-6)&&rows.TEXCOORD_0[i].every((v,c)=>Math.abs(v-sourceRows.TEXCOORD_0[j][c])<2e-6)&&rows.NORMAL[i].every((v,c)=>Math.abs(v-sourceRows.NORMAL[j][c])<manifest.validationTolerances.normalComponent));assert.notEqual(selected,undefined,`${name} vertex ${i} matches a source position/normal/UV`);matched.push(selected);
    for(const attr of ['POSITION','NORMAL','TEXCOORD_0','COLOR_0'])for(let c=0;c<sourceRows[attr][selected].length;c++){const expected=attr==='COLOR_0'?Math.max(0,Math.min(1,sourceRows[attr][selected][c])):sourceRows[attr][selected][c],error=Math.abs(rows[attr][i][c]-expected);if(attr==='POSITION')maxPosition=Math.max(maxPosition,error);if(attr==='NORMAL')maxNormal=Math.max(maxNormal,error);if(attr==='COLOR_0')maxColor=Math.max(maxColor,error);near(rows[attr][i][c],expected,attr==='COLOR_0'?manifest.validationTolerances.vertexColor:attr==='NORMAL'?manifest.validationTolerances.normalComponent:2e-6,`${name} ${attr}`);}
    const expected=Object.create(null),actual=Object.create(null);for(let c=0;c<4;c++){const old=sourceJointNames[sourceRows.JOINTS_0[selected][c]],next=jointNames[rows.JOINTS_0[i][c]];expected[old]=(expected[old]||0)+sourceRows.WEIGHTS_0[selected][c];actual[next]=(actual[next]||0)+rows.WEIGHTS_0[i][c];}
    for(const bone of Assets.bones){maxWeight=Math.max(maxWeight,Math.abs((actual[bone.name]||0)-(expected[bone.name]||0)));near(actual[bone.name]||0,expected[bone.name]||0,manifest.validationTolerances.weights,`${name} weight ${bone.name}`);}
   }
   for(const index of indices)assert(index>=0&&index<rows.POSITION.length);
   const signature=i=>[...sourceRows.POSITION[i],...sourceRows.TEXCOORD_0[i]].join(',');
   function trianglesOf(list){const result=[];for(let i=0;i<list.length;i+=3){const v=list.slice(i,i+3).map(signature),rotations=[v,v.slice(1).concat(v[0]),v.slice(2).concat(v.slice(0,2))];result.push(rotations.map(row=>row.join('|')).sort()[0]);}return result.sort();}
   assert.deepEqual(trianglesOf(indices.map(i=>matched[i])),trianglesOf(sourceIndices),name+' preserves oriented triangles through reordering');
  }
  assert(vertices>=16558);assert.equal(triangles,28946);
  for(const material of json.materials){const original=source.json.materials.find(m=>m.name===material.name),p=material.pbrMetallicRoughness,o=original.pbrMetallicRoughness;for(let i=0;i<4;i++)near(p.baseColorFactor[i],o.baseColorFactor[i],2e-6,material.name+' base color');near(p.metallicFactor||0,o.metallicFactor,2e-6,material.name+' metallic');near(p.roughnessFactor,o.roughnessFactor,2e-6,material.name+' roughness');const image=json.images[json.textures[p.baseColorTexture.index].source];assert.equal(image.name,material.name==='skin'?'skin-detail':'fabric-detail');}
  for(const image of json.images){const original=source.json.images.find(i=>i.name===image.name),view=source.json.bufferViews[original.bufferView],expected=source.bin.subarray(view.byteOffset||0,(view.byteOffset||0)+view.byteLength);let actual;if(image.uri)actual=fs.readFileSync(path.join(DIR,image.uri));else{const v=json.bufferViews[image.bufferView];actual=model.bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength);}assert.deepEqual(actual,expected,'source PNG remains byte identical');}
  console.log(`${model.file} geometry parity: position=${maxPosition}, normal=${maxNormal}, clampedColor=${maxColor}, weight=${maxWeight}`);
 });
 test(`${model.file}: all four clips match independent canonical world poses and linear CPU skinning at every baked key`,()=>{
  const {json}=model,skin=json.skins[0],ibm=accessor(model,skin.inverseBindMatrices).map(rowMatrix),jointMap=Object.fromEntries(Assets.bones.map((b,i)=>[b.name,i]));
  assert.deepEqual(json.animations.map(a=>a.name).sort(),manifest.clips.map(c=>c.name).sort());
  const primitive=json.meshes[0].primitives[0],positions=accessor(model,primitive.attributes.POSITION),joints=accessor(model,primitive.attributes.JOINTS_0),weights=accessor(model,primitive.attributes.WEIGHTS_0);
  const original=source.json.meshes[0].primitives[0],sourcePositions=accessor(source,original.attributes.POSITION),sourceUV=accessor(source,original.attributes.TEXCOORD_0),sourceJoints=accessor(source,original.attributes.JOINTS_0),sourceWeights=accessor(source,original.attributes.WEIGHTS_0),uv=accessor(model,primitive.attributes.TEXCOORD_0),sourceJointNames=source.json.skins[0].joints.map(i=>source.json.nodes[i].name),originals=[];
  for(let i=0;i<positions.length;i+=127){const match=sourcePositions.findIndex((p,j)=>p.every((v,c)=>Math.abs(v-positions[i][c])<2e-6)&&sourceUV[j].every((v,c)=>Math.abs(v-uv[i][c])<2e-6));assert(match>=0);originals[i]=match;}
  let maxWorld=0,maxSkin=0,maxVertex=0;
  for(const {clip,samples} of referenceClips){const animation=json.animations.find(a=>a.name===clip.name);assert.equal(animation.channels.length,57);assert.equal(new Set(animation.channels.map(c=>c.target.node)).size,19);
   for(const channel of animation.channels){const sampler=animation.samplers[channel.sampler];assert.equal(sampler.interpolation,'LINEAR');assert(['translation','rotation','scale'].includes(channel.target.path));assert.equal(json.nodes[channel.target.node].matrix,undefined);const time=accessor(model,sampler.input).flat();assert.equal(time.length,samples.length);time.forEach((value,key)=>near(value,key/30,2e-6,'fixed 30 fps'));}
   for(let key=0;key<samples.length;key++){const world=animatedWorld(model,animation,key),palettes=skin.joints.map((node,j)=>multiply(world[node],ibm[j]));
    for(let j=0;j<skin.joints.length;j++){const node=skin.joints[j],reference=samples[key][jointMap[json.nodes[node].name]];for(let r=0;r<4;r++)for(let c=0;c<4;c++){maxWorld=Math.max(maxWorld,Math.abs(world[node][r][c]-reference.world[r][c]));maxSkin=Math.max(maxSkin,Math.abs(palettes[j][r][c]-reference.skin[r][c]));}}
    // Compare actual exported geometry/weights with the original licensed bind
    // geometry/weights using independent canonical palettes. This includes the
    // stock Blender exporter's tiny-weight pruning, without assuming DQS.
    for(let vertex=0;vertex<positions.length;vertex+=127){const actual=[0,0,0],expected=[0,0,0],p=[...positions[vertex],1],original=originals[vertex],bind=[...sourcePositions[original],1];for(let k=0;k<4;k++){const j=joints[vertex][k],weight=weights[vertex][k],reference=samples[key][jointMap[sourceJointNames[sourceJoints[original][k]]]].skin;for(let r=0;r<3;r++){actual[r]+=weight*palettes[j][r].reduce((s,v,c)=>s+v*p[c],0);expected[r]+=sourceWeights[original][k]*reference[r].reduce((s,v,c)=>s+v*bind[c],0);}}maxVertex=Math.max(maxVertex,Math.hypot(...actual.map((v,c)=>v-expected[c])));}
   }
  }
  console.log(`${model.file} canonical parity: world=${maxWorld}, skin=${maxSkin}, vertex=${maxVertex}`);
  assert(maxWorld<manifest.validationTolerances.jointWorldMetres,`world matrix max error ${maxWorld}`);assert(maxSkin<manifest.validationTolerances.skinMatrixElement,`skin matrix max error ${maxSkin}`);assert(maxVertex<manifest.validationTolerances.skinnedVertexMetres,`skinned vertex max error ${maxVertex}`);
 });
}

test('reviewed live rig preserves every canonical joint endpoint at 60 Hz',()=>{
 const vm=require('node:vm'),sandbox={module:{exports:{}}};
 vm.runInNewContext(read('assets/interchange/rig-reference.js').toString(),sandbox,{filename:'historical-rig-reference.js'});
 const historical=sandbox.module.exports;
 for(const [name,duration] of [['idle',1],['run',2],['shoot',1.3],['dive-right',1.3]]){
  const live=Scenarios.create(name==='idle'?'walk':name),original=Scenarios.create(name==='idle'?'walk':name);
  for(let tick=0;tick<=Math.round(duration*60);tick++){
   for(const [s,rig] of [[live,Rig],[original,historical]]){
    if(name==='idle')Object.assign(s.p,{x:0,z:0,face:0,speed:0,action:'idle',actionClock:0});
    else Scenarios.sample(s,tick/60,rig);
   }
   const current=Rig.boneFrames(Rig.update(live.p,1/60)),reference=historical.boneFrames(historical.update(original.p,1/60));
   assert.equal(JSON.stringify(current),JSON.stringify(reference),name+' canonical frame '+tick);
  }
 }
});
