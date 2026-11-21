'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),zlib=require('node:zlib');
const root=path.resolve(__dirname,'..'),assetRoot=path.join(root,'assets/player');
const assets=require('../assets/player/player-model-data.js'),Status=require('../player-asset-status'),Rig=require('../humanoid-rig'),Skinning=require('../player-skinning');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const manifest=JSON.parse(fs.readFileSync(path.join(assetRoot,'manifest.json')));
function bytes(name){return fs.readFileSync(path.join(assetRoot,name));}
function floatRows(){const b=Buffer.from(assets.lods[0].vertices,'base64');return new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);}
function glb(){
 const b=bytes('footballer.glb');assert.equal(b.toString('ascii',0,4),'glTF');assert.equal(b.readUInt32LE(4),2);assert.equal(b.readUInt32LE(8),b.length);
 const length=b.readUInt32LE(12);assert.equal(b.toString('ascii',16,20),'JSON');const json=JSON.parse(b.toString('utf8',20,20+length));
 const offset=20+length;assert.equal(b.toString('ascii',offset+4,offset+8),'BIN\0');const bin=b.subarray(offset+8,offset+8+b.readUInt32LE(offset));
 assert.equal(offset+8+bin.length,b.length);return {json,bin};
}
const G=glb(),components={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16};
function accessor(index){
 const a=G.json.accessors[index],view=G.json.bufferViews[a.bufferView],count=components[a.type],width={5123:2,5125:4,5126:4}[a.componentType],read={5123:'readUInt16LE',5125:'readUInt32LE',5126:'readFloatLE'}[a.componentType];
 assert(width&&read);const start=(view.byteOffset||0)+(a.byteOffset||0),stride=view.byteStride||count*width;assert(start+(a.count-1)*stride+count*width<=(view.byteOffset||0)+view.byteLength);
 return Array.from({length:a.count},(_,i)=>Array.from({length:count},(_,k)=>G.bin[read](start+i*stride+k*width)));
}
function matmul(a,b){const c=Array(16).fill(0);for(let col=0;col<4;col++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)c[col*4+row]+=a[k*4+row]*b[col*4+k];return c;}
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const licensedArtifacts=['CREDITS.md','LICENSE-CC0.txt','SOURCE-LICENSE.md','footballer.glb','player-model-data.js','skeleton.json','source/makehuman-base.obj.gz','source/makehuman-default.mhskel.gz','source/makehuman-default_weights.mhw.gz','source/provenance.json','textures/fabric-detail.png','textures/skin-detail.png'];
const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
function selectedRows(predicate){const d=floatRows(),rows=[];for(let at=0;at<d.length;at+=20){const row=Array.from(d.subarray(at,at+20));if(predicate(row))rows.push(row);}return rows;}
function extent(rows,axis){const values=rows.map(r=>r[axis]);return Math.max(...values)-Math.min(...values);}
function covarianceVolume(points){
 const mean=[0,0,0],c=Array(9).fill(0);for(const p of points)for(let k=0;k<3;k++)mean[k]+=p[k]/points.length;
 for(const p of points)for(let i=0;i<3;i++)for(let j=0;j<3;j++)c[i*3+j]+=(p[i]-mean[i])*(p[j]-mean[j])/points.length;
 const determinant=c[0]*(c[4]*c[8]-c[5]*c[7])-c[1]*(c[3]*c[8]-c[5]*c[6])+c[2]*(c[3]*c[7]-c[4]*c[6]);return Math.sqrt(Math.max(0,determinant));
}

test('packaged hashes cover all twelve licensed payloads without claiming the independent procedural assets',()=>{
 assert.equal(manifest.modelId,assets.metadata.id);assert.equal(manifest.files.length,12);
 assert.deepEqual(manifest.files.map(f=>f.path).sort(),licensedArtifacts.map(p=>'assets/player/'+p).sort());
 for(const entry of manifest.files){assert(entry.path.startsWith('assets/player/'));assert(!entry.path.split('/').includes('..'));const b=fs.readFileSync(path.join(root,entry.path));assert.equal(b.length,entry.bytes,entry.path);assert.equal(digest(b),entry.sha256,entry.path);}
 const sourceFiles=fs.readdirSync(path.join(assetRoot,'source'));assert(sourceFiles.every(n=>['provenance.json','makehuman-base.obj.gz','makehuman-default.mhskel.gz','makehuman-default_weights.mhw.gz'].includes(n)));
});
test('licensed bind joints use the shared canonical nineteen-bone frames and fixed human lengths',()=>{
 const p={x:0,z:0,face:0,speed:0,action:'idle',actionClock:0},pose=Rig.update(p,0),frames=Rig.boneFrames(pose),reference=assets.metadata.anatomicalReference;
 assert.equal(reference.schemaVersion,1);assert.deepEqual(manifest.anatomicalReference,reference);
 for(const bone of assets.bones){const [head,tail]=frames[bone.name];assert(distance(head,bone.head)<1e-7,bone.name+' shared head');assert(distance(tail,bone.tail)<1e-7,bone.name+' shared tail');}
 for(const [name,length] of [['pelvis',.085],['spine',.18],['chest',.205],['neck',.13],['head',.25],['upper_arm.L',.315],['upper_arm.R',.315],['forearm.L',.29],['forearm.R',.29],['hand.L',.17],['hand.R',.17],['thigh.L',.475],['thigh.R',.475],['shin.L',.431],['shin.R',.431]]){
  const bone=assets.bones.find(b=>b.name===name);assert(Math.abs(distance(bone.head,bone.tail)-length)<1e-7,name+' fixed segment length');
 }
 assert(Math.abs(assets.bones[0].head[1]-1.03)<1e-7);assert(Math.abs(distance(assets.bones[6].head,assets.bones[13].head)-.44)<1e-7);assert(Math.abs(distance(assets.bones[9].head,assets.bones[16].head)-.26)<1e-7);
 for(const [field,value] of [['pelvisHeight',assets.bones[0].head[1]],['shoulderJointSpan',distance(assets.bones[6].head,assets.bones[13].head)],['hipJointSpan',distance(assets.bones[9].head,assets.bones[16].head)],['headBoneHeight',distance(assets.bones[4].head,assets.bones[4].tail)],['upperArmLength',distance(assets.bones[6].head,assets.bones[6].tail)],['forearmLength',distance(assets.bones[7].head,assets.bones[7].tail)],['handBoneLength',distance(assets.bones[8].head,assets.bones[8].tail)],['thighLength',distance(assets.bones[9].head,assets.bones[9].tail)],['shinLength',distance(assets.bones[10].head,assets.bones[10].tail)]])assert(Math.abs(reference[field]-value)<1e-7,field+' matches measured bind anatomy');
});
test('retained original anatomy, rig and weights match official commit-pinned provenance',()=>{
 const p=JSON.parse(bytes('source/provenance.json'));assert.equal(p.commit,'a8bc2d54ff0ac92e78ff71431b1023eda42bf482');assert.equal(p.repository,'https://github.com/makehumancommunity/makehuman');assert.equal(p.assetLicense,'CC0-1.0');assert.equal(p.files.length,5);
 for(const record of p.files){const name=path.basename(record.local),b=name==='makehuman-LICENSE.md'?bytes('SOURCE-LICENSE.md'):name==='makehuman-LICENSE.ASSETS.md'?bytes('LICENSE-CC0.txt'):zlib.gunzipSync(bytes('source/'+name+'.gz'));assert.equal(digest(b),record.sha256);assert.equal(b.length,record.bytes);assert.equal(record.sourceURL,'https://raw.githubusercontent.com/makehumancommunity/makehuman/'+p.commit+'/'+record.repositoryPath);}
 const source=zlib.gunzipSync(bytes('source/makehuman-base.obj.gz')).toString();assert.match(source.slice(0,500),/explicitly released as CC0/);assert.match(bytes('SOURCE-LICENSE.md').toString(),/C\. The license for the bundled assets/);assert.match(bytes('LICENSE-CC0.txt').toString(),/CC0 1\.0 Universal/);
 assert.equal(JSON.parse(zlib.gunzipSync(bytes('source/makehuman-default.mhskel.gz'))).license,'CC0');assert.equal(JSON.parse(zlib.gunzipSync(bytes('source/makehuman-default_weights.mhw.gz'))).license,'CC0');
});
test('runtime weight painting is documented as a localized derivative of the retained official weights',()=>{
 const reference=assets.metadata.anatomicalReference,paint=reference.runtimeWeightPainting,stats=assets.statistics.runtimeWeightPainting;
 assert.equal(paint.iterations,6);assert.equal(paint.selfWeight,.5);assert.equal(paint.neighborWeight,.5);assert.deepEqual(paint.radii,{shoulder:.18,elbow:.12,knee:.15});assert.equal(paint.minimumAdjacentBoneWeight,.35);assert.equal(paint.maximumInfluences,4);
 assert.match(paint.adjacency,/original body quad edges/);assert.match(paint.stage,/after bind geometry is fixed/);assert.match(paint.protected,/hand.*0\.13 m.*wrist/);assert.match(paint.originalWeights,/verbatim.*source archive.*runtime weights are an authored derivative/);assert.match(reference.skinWeights,/authored.*derivative/i);
 assert.deepEqual(stats.parameters,paint);assert.deepEqual(manifest.statistics.runtimeWeightPainting,stats);assert(stats.changedSourceVertices>300&&stats.changedSourceVertices<=stats.selectedSourceVertices);assert(stats.protectedHandAndWristVertices>500);assert(stats.maximumWeightSumError<1e-14);
 assert.deepEqual(Object.keys(stats.jointPatchVertices).sort(),['elbow.L','elbow.R','knee.L','knee.R','shoulder.L','shoulder.R']);for(const [joint,count] of Object.entries(stats.jointPatchVertices))assert(count>20,joint+' contains an actual source-surface patch');
 assert(stats.meanPatchEdgeWeightL1After<stats.meanPatchEdgeWeightL1Before,'painting reduces adjacent source weight jumps');
});
test('runtime is a validated anatomical skin with all nineteen bones and sensible human bounds',()=>{
 const r=Status.validate(assets);assert(r.ok,JSON.stringify(r.errors));assert.equal(r.summary.boneCount,19);assert.equal(r.summary.lods[0].skinnedBoneCount,19);assert.equal(r.summary.lods[0].vertexCount,manifest.vertices);assert.equal(r.summary.lods[0].triangleCount,manifest.triangles);
 const b=r.summary.lods[0].bounds;assert(b.min[1]>=-.005&&b.max[1]>1.7&&b.max[1]<2.05);assert(b.max[2]-b.min[2]<1.6);assert(manifest.triangles>20000);assert.equal(assets.metadata.rigReferenceSHA256,digest(fs.readFileSync(path.join(root,'humanoid-rig.js'))));
});
test('actual head, hands, boots and hip belt have adult proportions and the front pelvis is covered by shorts',()=>{
 const d=floatRows();for(const bone of [8,15]){const wrist=assets.bones[bone].head;let count=0,max=0;for(let at=0;at<d.length;at+=20)if(d[at+8]===bone){count++;max=Math.max(max,Math.hypot(d[at]-wrist[0],d[at+1]-wrist[1],d[at+2]-wrist[2]));}assert(count>500);assert(max>.16&&max<.215,'wrist-to-finger extent: '+max);}
 const reference=assets.metadata.anatomicalReference,head=selectedRows(r=>r[1]>1.64&&r[8]===4);assert(head.length>1000);assert(Math.abs(Math.max(...head.map(r=>r[1]))-1.88)<1e-5);assert(Math.abs(Math.max(...head.map(r=>r[1]))-reference.standingHeight)<1e-5);assert(extent(head,2)>.15&&extent(head,2)<.20,'head width: '+extent(head,2));assert(extent(head,0)>.18&&extent(head,0)<.24,'head depth: '+extent(head,0));
 for(const foot of [11,18]){const boot=selectedRows(r=>r[16]===4&&r[8]===foot);assert(boot.length>200);assert(extent(boot,0)>.275&&extent(boot,0)<.305,'boot length: '+extent(boot,0));assert(extent(boot,2)>.105&&extent(boot,2)<.125,'boot width: '+extent(boot,2));assert(Math.abs(extent(boot,0)-reference.bootLength)<1e-6,'documented boot length matches actual mesh');assert(Math.abs(extent(boot,2)-reference.bootWidth)<1e-6,'documented boot width matches actual mesh');}
 const hips=selectedRows(r=>Math.abs(r[1]-1.03)<.025&&[0,1,2,9,16].includes(r[8]));assert(hips.length>30);assert(extent(hips,2)>.34&&extent(hips,2)<.42,'external hip width: '+extent(hips,2));
 let covered=0;for(let at=0;at<d.length;at+=20){const x=d[at],y=d[at+1],z=d[at+2];if(y>.68&&y<.98&&Math.abs(z)<.13&&x>.03){assert.equal(d[at+16],2);covered++;}}assert(covered>100);
});
test('actual elbow, knee and shoulder skin shells retain radius and spatial spread through ninety-degree bends',()=>{
 for(const [label,joint,parent,child,radius] of [['elbow.L',7,[6],[7,8],.085],['elbow.R',14,[13],[14,15],.085],['knee.L',10,[9],[10,11],.12],['knee.R',17,[16],[17,18],.12],['shoulder.L',6,[2,5],[6,7,8],.14],['shoulder.R',13,[2,12],[13,14,15],.14]]){
  const pivot=assets.bones[joint].head,angle=Math.PI/2,c=Math.cos(angle),s=Math.sin(angle);
  const rotated=[c,s,0,0,-s,c,0,0,0,0,1,0,pivot[0]-c*pivot[0]+s*pivot[1],pivot[1]-s*pivot[0]-c*pivot[1],0,1];
  const palette=Skinning.fromMatrices(assets.bones.flatMap((_,i)=>child.includes(i)?rotated:identity));
  const weight=(row,bones)=>row.slice(8,12).reduce((sum,bone,i)=>sum+(bones.includes(bone)?row[12+i]:0),0);
  const shell=selectedRows(row=>distance(row.slice(0,3),pivot)<radius&&weight(row,parent)>.1&&weight(row,child)>.1);
  assert(shell.length>=40,label+' has a continuous mixed-weight joint shell: '+shell.length);
  const rest=shell.map(row=>row.slice(0,3)),posed=shell.map(row=>Skinning.deform(palette,row.slice(8,12),row.slice(12,16),row.slice(0,3)));
  const squaredRadius=points=>points.reduce((sum,p)=>sum+distance(p,pivot)**2,0);
  const radialRatio=Math.sqrt(squaredRadius(posed)/squaredRadius(rest)),volumeRatio=covarianceVolume(posed)/covarianceVolume(rest);
  assert(posed.every(p=>p.every(Number.isFinite)),label+' finite deformed positions');
  assert(radialRatio>.97&&radialRatio<1.03,label+' joint-shell radius retention: '+radialRatio);
  assert(volumeRatio>.75&&volumeRatio<1.5,label+' joint-shell covariance spread retention: '+volumeRatio);
  // Verify this actual shell exercises the pinching case: linear blending of
  // the same two rigid frames loses visible cross-section at this bend.
  const linear=rest.map((p,i)=>{const w=weight(shell[i],child),v=p.map((n,k)=>n-pivot[k]);return [pivot[0]+(1-w)*v[0]-w*v[1],pivot[1]+(1-w)*v[1]+w*v[0],p[2]];});
  assert(Math.sqrt(squaredRadius(linear)/squaredRadius(rest))<.96,label+' fixture has meaningful blended bending weights');
 }
});
test('curved crewneck, shorts and socks share continuous seams with the exposed skin',()=>{
 const d=floatRows();
 const tangents=[-.12,-.09,-.06,-.03,0,.03,.06,.09,.12],curvature=.055/(.08*.08);
 const collarLevel=z=>Math.max(...tangents.map(z0=>1.565+curvature*(2*z0*z-z0*z0)));
 const seams=[['crewneck',1,(x,y,z)=>Math.abs(y-collarLevel(z))<2e-6,40],['shorts',2,(x,y)=>Math.abs(y-.625)<2e-6,60],['socks',3,(x,y)=>Math.abs(y-.43)<2e-6,60]];
 for(const [label,cloth,onSeam,minimum] of seams){
  const seam=[new Set(),new Set()];
  for(let at=0;at<d.length;at+=20)if(onSeam(d[at],d[at+1],d[at+2])){const side=d[at+16]===0?0:d[at+16]===cloth?1:-1;if(side>=0)seam[side].add([d[at],d[at+1],d[at+2]].map(v=>v.toFixed(6)).join(','));}
  const joined=[...seam[0]].filter(p=>seam[1].has(p));assert(joined.length>minimum,'continuous skin/cloth seam at '+label);assert.equal(joined.length,seam[1].size,'no detached cloth edge at '+label);
  if(label==='crewneck'){const heights=joined.map(key=>Number(key.split(',')[1]));assert(Math.max(...heights)-Math.min(...heights)>.025,'crewneck has a curved neckline');}
 }
 let chest=0;for(let at=0;at<d.length;at+=20)if(d[at+16]===1&&d[at+8]<4&&d[at+1]>1.13&&d[at+1]<1.4&&Math.abs(d[at+2])<.15){assert(d[at]<.13,'neutral athletic chest envelope');chest++;}assert(chest>100);
});
test('standard GLB contains exactly the runtime positions, normals, UVs, joints, weights and colors',()=>{
 const d=floatRows(),primitives=G.json.meshes[0].primitives;assert.equal(G.json.asset.version,'2.0');assert.equal(G.json.extras.modelId,assets.metadata.id);assert.equal(G.json.extras.rigReferenceSHA256,assets.metadata.rigReferenceSHA256);assert.equal(G.json.animations,undefined);
 for(const [key,start,width] of [['POSITION',0,3],['NORMAL',3,3],['TEXCOORD_0',6,2],['JOINTS_0',8,4],['WEIGHTS_0',12,4],['COLOR_0',17,3]]){
  const values=accessor(primitives[0].attributes[key]);assert.equal(values.length,d.length/20);for(const p of primitives)assert.equal(p.attributes[key],primitives[0].attributes[key]);
  values.forEach((row,i)=>row.forEach((v,k)=>assert.equal(v,d[i*20+start+k],`${key}/${i}/${k}`)));assert.equal(values[0].length,width);
 }
 const b=Buffer.from(assets.lods[0].indices,'base64'),runtime=assets.lods[0].indexType==='H'?new Uint16Array(b.buffer,b.byteOffset,b.byteLength/2):new Uint32Array(b.buffer,b.byteOffset,b.byteLength/4);
 for(const primitive of primitives){const expected=[];for(let i=0;i<runtime.length;i+=3)if(d[runtime[i]*20+16]===primitive.material){assert.equal(d[runtime[i+1]*20+16],primitive.material);assert.equal(d[runtime[i+2]*20+16],primitive.material);expected.push(runtime[i],runtime[i+1],runtime[i+2]);}assert.deepEqual(accessor(primitive.indices).flat(),expected);}
});
test('GLB joint hierarchy and inverse bind matrices preserve the packaged rest shape',()=>{
 const skin=G.json.skins[0],ibm=accessor(skin.inverseBindMatrices),globals=new Map();assert.equal(skin.joints.length,19);
 function walk(index,parent){const node=G.json.nodes[index],world=matmul(parent,node.matrix||identity);globals.set(index,world);for(const child of node.children||[])walk(child,world);}
 for(const node of G.json.scenes[G.json.scene].nodes)walk(node,identity);
 skin.joints.forEach((node,i)=>{assert.equal(G.json.nodes[node].name,assets.bones[i].name);const product=matmul(globals.get(node),ibm[i]);product.forEach((v,k)=>assert(Math.abs(v-identity[k])<2e-6,assets.bones[i].name+' inverse-bind'));});
});
test('both external PNG textures are embedded byte-for-byte in GLB',()=>{
 assert.equal(G.json.images.length,2);G.json.images.forEach((image,i)=>{assert.equal(image.mimeType,'image/png');const view=G.json.bufferViews[image.bufferView],b=G.bin.subarray(view.byteOffset||0,(view.byteOffset||0)+view.byteLength),name=i===0?'skin':'fabric';assert.deepEqual(b,fs.readFileSync(path.join(root,assets.textures[name])));assert.deepEqual([...b.subarray(0,8)],[137,80,78,71,13,10,26,10]);assert.equal(b.readUInt32BE(16),256);assert.equal(b.readUInt32BE(20),256);});
});
