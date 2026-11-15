'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Renderer=require('../player-renderer.js');
const assets=require('../assets/player/player-model-data.js');
function unpack(b64,Typed){const raw=Buffer.from(b64,'base64');return new Typed(raw.buffer,raw.byteOffset,raw.byteLength/Typed.BYTES_PER_ELEMENT);}
test('licensed MakeHuman base stays unmodified while two distant GPU LODs reduce indexed triangles',()=>{
 assert.equal(assets.lods.length,1,'licenced asset must remain the original single-LOD source');
 const base=assets.lods[0],v=unpack(base.vertices,Float32Array),ix=unpack(base.indices,Uint16Array);
 assert.equal(v.length%20,0);assert.equal(ix.length%3,0);assert(ix.length>70000);
 const middle=Renderer.simplifyLOD(v,ix,.075),far=Renderer.simplifyLOD(v,ix,.155);
 assert(middle.indices.length<ix.length*.92,'middle LOD must reduce draw calls / triangles meaningfully');
 assert(far.indices.length<middle.indices.length*.92,'far LOD must be materially smaller');
 assert(far.vertices.length<middle.vertices.length);
 for(const lod of [middle,far]){
  assert(lod.vertexCount>500,'do not collapse footballer silhouette');
  assert(lod.indexCount%3===0);
  assert(lod.indexCount>2000,'do not replace human body with an unrecognisable shell');
  for(const j of lod.indices)assert(j<lod.vertexCount,'in-bounds index');
  let maxHeight=0,minHeight=Infinity,boots=0;
  const w=lod.vertices;
  for(let i=0;i<w.length;i+=20){
   const x=w[i],y=w[i+1],z=w[i+2];
   assert(Number.isFinite(x)&&Number.isFinite(y)&&Number.isFinite(z));
   maxHeight=Math.max(maxHeight,y);minHeight=Math.min(minHeight,y);
   if(Math.round(w[i+16])===4)boots++;
   let weight=0;
   for(let k=0;k<4;k++){
    assert(Number.isInteger(w[i+8+k])&&w[i+8+k]>=0&&w[i+8+k]<19);
    weight+=w[i+12+k];
   }
   assert(Math.abs(weight-1)<.0001,'normalized skin joint weights must survive clustering');
  }
  assert(maxHeight>1.7&&maxHeight<2.1&&minHeight>=-.01);
  assert(boots>12,'boots should remain visible');
 }
});
