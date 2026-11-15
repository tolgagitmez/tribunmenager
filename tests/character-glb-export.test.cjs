'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Assets=require('../assets/player/player-model-data.js');
const {buildGLB,PARENT}=require('../tools/export-character-glb.cjs');
const EPS=1e-5;
function parse(glb){
 const b=Buffer.from(glb),total=b.readUInt32LE(8),jsonLength=b.readUInt32LE(12);
 assert.equal(b.readUInt32LE(0),0x46546c67,'GLB magic');
 assert.equal(b.readUInt32LE(4),2,'glTF 2.0 version');
 assert.equal(total,b.length);
 assert.equal(b.readUInt32LE(16),0x4e4f534a,'JSON chunk type');
 assert.equal(jsonLength%4,0);
 const doc=JSON.parse(b.subarray(20,20+jsonLength).toString('utf8').trimEnd());
 const binStart=20+jsonLength;
 assert.equal(b.readUInt32LE(binStart+4),0x004e4942,'binary chunk type');
 assert.equal(b.readUInt32LE(binStart),b.length-binStart-8);
 return {doc,bin:b.subarray(binStart+8)};
}
function accessorInfo(doc,index,bin){
 const a=doc.accessors[index],view=doc.bufferViews[a.bufferView];
 const start=view.byteOffset+(a.byteOffset||0);
 assert.equal(view.byteOffset%4,0,'4-byte aligned GLB view');
 assert(start+view.byteLength<=bin.length,'valid binary range');
 return {a,view,start};
}
function near(a,b){assert(Math.abs(a-b)<EPS,a+' != '+b);}
test('GLB contains spec-shaped binary chunks, a bound 19-joint skin and LOD-specific indexed triangles',()=>{
 for(let lod=0;lod<3;lod++){
  const {glb,json,stats}=buildGLB({lod}),{doc,bin}=parse(glb);
  assert.deepEqual(doc,json);
  assert.equal(doc.asset.version,'2.0');
  assert.equal(doc.buffers.length,1);
  assert.equal(doc.buffers[0].byteLength,bin.length);
  assert.equal(doc.buffers[0].uri,undefined);
  assert.equal(doc.scenes[0].nodes.length,2);
  assert.equal(doc.nodes.length,20);
  assert.equal(doc.skins.length,1);
  assert.equal(doc.skins[0].joints.length,19);
  assert.equal(doc.skins[0].skeleton,1);
  const skin=accessorInfo(doc,doc.skins[0].inverseBindMatrices,bin);
  assert.equal(skin.a.count,19);assert.equal(skin.a.type,'MAT4');assert.equal(skin.a.componentType,5126);
  for(let i=0;i<19;i++){
   const bone=Assets.bones[i],node=doc.nodes[i+1],parent=PARENT[bone.name];
   assert.equal(node.name,bone.name);
   const rest=parent?Assets.bones.find(b=>b.name===parent).head:[0,0,0];
   node.translation.forEach((x,j)=>near(x,bone.head[j]-rest[j]));
   for(let j=0;j<3;j++)near(bin.readFloatLE(skin.start+i*64+48+j*4),-bone.head[j]);
   for(let j of [0,5,10,15])near(bin.readFloatLE(skin.start+i*64+j*4),1);
  }
  const primitives=doc.meshes[0].primitives;assert(primitives.length>=8);
  let count=0;
  for(const primitive of primitives){
   assert(primitive.material>=0&&primitive.material<10);
   assert.equal(primitive.mode,4);
   const attrs=primitive.attributes;
   assert.equal(doc.accessors[attrs.POSITION].count,stats.vertices);
   assert.equal(doc.accessors[attrs.POSITION].componentType,5126);
   assert.equal(doc.accessors[attrs.NORMAL].type,'VEC3');
   assert.equal(doc.accessors[attrs.JOINTS_0].componentType,5121);
   assert.equal(doc.accessors[attrs.JOINTS_0].type,'VEC4');
   assert.equal(doc.accessors[attrs.WEIGHTS_0].componentType,5126);
   const index=accessorInfo(doc,primitive.indices,bin);
   assert.equal(index.a.componentType,5123);
   assert.equal(index.a.count%3,0);
   for(let i=0;i<index.a.count;i++)assert(bin.readUInt16LE(index.start+2*i)<stats.vertices);
   count+=index.a.count;
  }
  assert.equal(count,Assets.lods[lod].indexCount);
  assert.equal(stats.triangles,Assets.lods[lod].indexCount/3);
 }
});
test('face winding agrees with declared outward-facing vertex normals in every LOD',()=>{
 for(const data of Assets.lods){
  const vbytes=Buffer.from(data.vertices,'base64'),ibytes=Buffer.from(data.indices,'base64');
  const vertex=new Float32Array(vbytes.buffer,vbytes.byteOffset,data.vertexCount*20);
  const indices=new Uint16Array(ibytes.buffer,ibytes.byteOffset,data.indexCount);
  let inwards=0,measured=0;
  for(let i=0;i<indices.length;i+=3){
   const offsets=[indices[i],indices[i+1],indices[i+2]].map(n=>n*20),[a,b,c]=offsets;
   const edge=(v,w)=>[0,1,2].map(j=>vertex[w+j]-vertex[v+j]);
   const u=edge(a,b),w=edge(a,c);
   const normal=[u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]];
   const expected=[0,1,2].map(j=>vertex[a+3+j]+vertex[b+3+j]+vertex[c+3+j]);
   const dot=normal.reduce((s,n,j)=>s+n*expected[j],0);
   if(Math.abs(dot)>1e-8){measured++;if(dot<0)inwards++;}
  }
  assert(measured>data.indexCount/3*.9,'must have enough non-degenerate faces');
  assert.equal(inwards,0,'all measurable faces must have outward winding');
 }
});
test('exporter rejects unsupported LOD values',()=>{
 for(const lod of [-1,3,Infinity,NaN,1.5])assert.throws(()=>buildGLB({lod}));
});

test('committed LOD0 binary is byte-for-byte reproducible from source',()=>{
 const fs=require('node:fs');
 const path=require('node:path');
 const actual=fs.readFileSync(path.resolve(__dirname,'../assets/player/tribun-base-footballer.glb'));
 const generated=Buffer.from(buildGLB({lod:0}).glb);
 assert.equal(Buffer.compare(actual,generated),0,'committed binary must match mesh generator exactly');
});

test('player studio exposes the committed GLB asset without a network dependency',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const html=fs.readFileSync(path.resolve(__dirname,'../player-studio.html'),'utf8');
 assert(html.includes('href="assets/player/tribun-base-footballer.glb"'));
 assert(fs.statSync(path.resolve(__dirname,'../assets/player/tribun-base-footballer.glb')).size>100000);
});
