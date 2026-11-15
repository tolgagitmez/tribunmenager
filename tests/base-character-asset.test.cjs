'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Rig=require('../humanoid-rig-procedural');
const Renderer=require('../player-renderer-procedural');
const Assets=require('../assets/player/procedural-player-model-data.js');
const nearly=(a,b,tol=1e-5)=>assert(Math.abs(a-b)<tol,Math.abs(a-b)+' exceeds '+tol);
function view(b64,Type){
 const buffer=Buffer.from(b64,'base64');
 assert.equal(buffer.byteLength%Type.BYTES_PER_ELEMENT,0);
 return new Type(buffer.buffer,buffer.byteOffset,buffer.byteLength/Type.BYTES_PER_ELEMENT);
}
test('single procedural base footballer has a complete, stable nineteen-bone binding',()=>{
 assert.equal(Assets.units,'metres');
 assert.equal(Assets.bones.length,19);
 assert.equal(Assets.boneCount,19);
 assert.equal(Assets.restBends.length,4);
 assert(Assets.restBends.every(v=>Number.isFinite(v)&&v>.1&&v<2.7));
 assert.equal(new Set(Assets.bones.map(b=>b.name)).size,19);
 for(const b of Assets.bones){
  assert.equal(b.head.length,3);
  assert.equal(b.tail.length,3);
  assert.equal(b.inverseBind.length,16);
  assert.equal(b.matrix.length,16);
  b.head.forEach((x,i)=>nearly(b.inverseBind[12+i],-x));
  nearly(b.matrix[0],1);
  nearly(b.matrix[5],1);
  nearly(b.matrix[10],1);
 }
});
test('all three WebGL LODs have finite vertices, valid indices, normalized skin weights',()=>{
 assert.equal(Assets.lods.length,3);
 let prior=Infinity;
 for(const [lodId,lod] of Assets.lods.entries()){
  const vertices=view(lod.vertices,Float32Array);
  const indices=view(lod.indices,Uint16Array);
  assert.equal(lod.indexType,'H');
  assert.equal(vertices.length,lod.vertexCount*20,'vertex layout is 20 floats');
  assert.equal(indices.length,lod.indexCount);
  assert.equal(indices.length%3,0);
  assert(lod.vertexCount<prior);
  prior=lod.vertexCount;
  const usedBones=new Set(),materials=new Set();
  for(let i=0;i<vertices.length;i+=20){
   for(let j=0;j<20;j++)assert(Number.isFinite(vertices[i+j]),'finite vertex at '+lodId+'/'+i+'/'+j);
   let weights=0;
   for(let j=0;j<4;j++){
    const bone=vertices[i+8+j],weight=vertices[i+12+j];
    assert(Number.isInteger(bone)&&bone>=0&&bone<Assets.bones.length,'bone index');
    assert(weight>=0&&weight<=1,'nonnegative weights');
    weights+=weight;
    if(weight>0)usedBones.add(bone);
   }
   nearly(weights,1,2e-6);
   assert(vertices[i+1]>=-.02&&vertices[i+1]<=2.1,'human-sized asset');
   materials.add(vertices[i+16]);
  }
  for(const i of indices)assert(i<lod.vertexCount,'triangle points to an existing vertex');
  assert(usedBones.size>=16,'most bones influence actual geometry');
  assert(materials.has(0)&&materials.has(1)&&materials.has(2)&&materials.has(4),'skin, jersey, shorts, boots');
 }
});
test('bind pose maps the generated mesh to itself; no hidden bind scale',()=>{
 const p={x:0,z:0,face:0,speed:0,action:'idle',actionClock:0};
 const pose=Rig.update(p,1/60),palette=Renderer.palette(p,Assets,pose);
 for(let i=0;i<Assets.bones.length;i++){
  const m=palette.subarray(i*16,(i+1)*16);
  for(let j=0;j<16;j++)nearly(m[j],j%5===0?1:0,1e-5);
 }
});
test('a moving player deforms using unit-length basis axes',()=>{
 const p={x:0,z:0,face:0,speed:2,action:'run',actionClock:0};
 for(let t=0;t<24;t++){p.x+=1/30;Rig.update(p,1/60);}
 const palette=Renderer.palette(p,Assets,Rig.getPose(p));
 for(let i=0;i<Assets.bones.length;i++){
  const offset=i*16;
  for(let c=0;c<3;c++)nearly(Math.hypot(palette[offset+c*4],palette[offset+c*4+1],palette[offset+c*4+2]),1,1e-5);
 }
});
