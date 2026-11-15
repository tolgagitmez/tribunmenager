'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),zlib=require('node:zlib');
const root=path.resolve(__dirname,'..'),assetRoot=path.join(root,'assets/player');
const assets=require('../assets/player/player-model-data.js'),Status=require('../player-asset-status');
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

test('packaged hashes cover every shipped player file and no hidden program code',()=>{
 assert.equal(manifest.modelId,assets.metadata.id);assert.equal(manifest.files.length,12);
 for(const entry of manifest.files){assert(entry.path.startsWith('assets/player/'));assert(!entry.path.split('/').includes('..'));const b=fs.readFileSync(path.join(root,entry.path));assert.equal(b.length,entry.bytes,entry.path);assert.equal(digest(b),entry.sha256,entry.path);}
 const sourceFiles=fs.readdirSync(path.join(assetRoot,'source'));assert(sourceFiles.every(n=>['provenance.json','makehuman-base.obj.gz','makehuman-default.mhskel.gz','makehuman-default_weights.mhw.gz'].includes(n)));
});
test('retained original anatomy, rig and weights match official commit-pinned provenance',()=>{
 const p=JSON.parse(bytes('source/provenance.json'));assert.equal(p.commit,'a8bc2d54ff0ac92e78ff71431b1023eda42bf482');assert.equal(p.repository,'https://github.com/makehumancommunity/makehuman');assert.equal(p.assetLicense,'CC0-1.0');assert.equal(p.files.length,5);
 for(const record of p.files){const name=path.basename(record.local),b=name==='makehuman-LICENSE.md'?bytes('SOURCE-LICENSE.md'):name==='makehuman-LICENSE.ASSETS.md'?bytes('LICENSE-CC0.txt'):zlib.gunzipSync(bytes('source/'+name+'.gz'));assert.equal(digest(b),record.sha256);assert.equal(b.length,record.bytes);assert.equal(record.sourceURL,'https://raw.githubusercontent.com/makehumancommunity/makehuman/'+p.commit+'/'+record.repositoryPath);}
 const source=zlib.gunzipSync(bytes('source/makehuman-base.obj.gz')).toString();assert.match(source.slice(0,500),/explicitly released as CC0/);assert.match(bytes('SOURCE-LICENSE.md').toString(),/C\. The license for the bundled assets/);assert.match(bytes('LICENSE-CC0.txt').toString(),/CC0 1\.0 Universal/);
 assert.equal(JSON.parse(zlib.gunzipSync(bytes('source/makehuman-default.mhskel.gz'))).license,'CC0');assert.equal(JSON.parse(zlib.gunzipSync(bytes('source/makehuman-default_weights.mhw.gz'))).license,'CC0');
});
test('runtime is a validated anatomical skin with all nineteen bones and sensible human bounds',()=>{
 const r=Status.validate(assets);assert(r.ok,JSON.stringify(r.errors));assert.equal(r.summary.boneCount,19);assert.equal(r.summary.lods[0].skinnedBoneCount,19);assert.equal(r.summary.lods[0].vertexCount,manifest.vertices);assert.equal(r.summary.lods[0].triangleCount,manifest.triangles);
 const b=r.summary.lods[0].bounds;assert(b.min[1]>=-.005&&b.max[1]>1.7&&b.max[1]<2.05);assert(b.max[2]-b.min[2]<1.6);assert(manifest.triangles>20000);assert.equal(assets.metadata.rigReferenceSHA256,digest(fs.readFileSync(path.join(root,'humanoid-rig.js'))));
});
test('hands preserve human proportions and the front pelvis is fully covered by shorts',()=>{
 const d=floatRows();for(const bone of [8,15]){const wrist=assets.bones[bone].head;let count=0,max=0;for(let at=0;at<d.length;at+=20)if(d[at+8]===bone){count++;max=Math.max(max,Math.hypot(d[at]-wrist[0],d[at+1]-wrist[1],d[at+2]-wrist[2]));}assert(count>500);assert(max>.10&&max<.24,'wrist-to-finger extent: '+max);}
 let covered=0;for(let at=0;at<d.length;at+=20){const x=d[at],y=d[at+1],z=d[at+2];if(y>.68&&y<.98&&Math.abs(z)<.13&&x>.03){assert.equal(d[at+16],2);covered++;}}assert(covered>100);
});
test('collar, shorts and socks share continuous level hems with the exposed skin',()=>{
 const d=floatRows();
 for(const [height,cloth] of [[1.56,1],[.625,2],[.43,3]]){
  const seam=[new Set(),new Set()];
  for(let at=0;at<d.length;at+=20)if(Math.abs(d[at+1]-height)<2e-6){const side=d[at+16]===0?0:d[at+16]===cloth?1:-1;if(side>=0)seam[side].add([d[at],d[at+1],d[at+2]].map(v=>v.toFixed(6)).join(','));}
  const joined=[...seam[0]].filter(p=>seam[1].has(p));assert(joined.length>60,'continuous skin/cloth hem at '+height);assert.equal(joined.length,seam[1].size,'no detached cloth edge at '+height);
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
