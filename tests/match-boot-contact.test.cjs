'use strict';

const assert=require('node:assert/strict');
const {test}=require('node:test');
const Assets=require('../assets/player/player-model-data.js');
const Renderer=require('../player-renderer.js');

test('licensed LOD0 measures signed triangle clearance on both deformed boots',async()=>{
 const [THREE,{createBootContactMeter}]=await Promise.all([
  import('../vendor/three/build/three.module.min.js'),import('../match-boot-contact.mjs')
 ]);
 let decodes=0;
 const meter=createBootContactMeter({
  assets:Assets,Skinning:Renderer.skinning,THREE,
  decode(data){decodes++;return Renderer.decode(data);}
 });
 assert.equal(decodes,0,'normal setup does not decode the reference mesh');

 const palette=new Float32Array(Assets.bones.length*16);
 for(let i=0;i<Assets.bones.length;i++)palette.set([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],i*16);
 for(const foot of [0,1]){
  const name=foot===0?'foot.L':'foot.R';
  const joint=Assets.bones.findIndex(bone=>bone.name===name);
  const yaw=foot===0?Math.PI/3:-Math.PI/4,c=Math.cos(yaw),s=Math.sin(yaw);
  const tx=foot===0?8:-9,tz=foot===0?-6:7;
  palette.set([c,0,s,0,0,1,0,0,-s,0,c,0,tx,0,tz,1],joint*16);
  for(const distance of [.19,.08]){
   // The authored cap is a solid polygon in the x=.265 plane. The
   // centre of that cap is not a mesh vertex, so a vertex-only distance
   // gives the wrong result even at identity.
   const x=.265+distance,z=foot===0?-.15:.15;
   const ball={x:tx+c*x-s*z,y:.07,z:tz+s*x+c*z};
   const reading=meter.measure({palette,foot,ball});
   assert.equal(reading.lod,0);
   assert.equal(reading.triangleCount,368);
   assert.ok(Math.abs(reading.gapMetres-(distance-.11))<2e-6,JSON.stringify(reading));
   assert.ok(Math.abs(reading.closestPoint.x-(tx+c*.265-s*z))<2e-6);
   assert.ok(Math.abs(reading.closestPoint.y-.07)<2e-6);
   assert.ok(Math.abs(reading.closestPoint.z-(tz+s*.265+c*z))<2e-6);
  }
 }
 assert.equal(decodes,2,'vertex and index data are shared by both feet and subsequent measurements');
});
