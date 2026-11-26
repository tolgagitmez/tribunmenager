'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),A=require('./match-atmosphere.js'),R=require('../../player-renderer.js');
test('broadcast framing bounded at corners and fast transitions',()=>{
 for(const x of [-52,0,52])for(const z of [-34,0,34]){
  const q=A.cameraFrame([x,z],{vx:50,vz:-50},.7);
  assert.ok(Math.abs(q.target[0])<=39&&Math.abs(q.target[2])<=15);
  assert.ok(q.eye[1]>=31&&q.eye[2]>=56&&q.fov>=49&&q.fov<=64);
 }
 assert.ok(A.cameraFrame([0,0],{vx:20,vz:0}).fov>A.cameraFrame([0,0],{vx:0,vz:0}).fov);
 assert.ok(A.cameraFrame([NaN,Infinity],{vx:NaN,vz:Infinity},NaN).target.every(Number.isFinite));
});
test('neutral default and shared GPU atmosphere',()=>{
 assert.deepEqual(A.profiles.classic.tone,[1,1,1]);
 for(const p of Object.values(A.profiles))assert.ok(p.tone.every(x=>x>0&&x<=1.2));
 assert.ok(R.fragmentShader.includes('uAtmosphere'));assert.ok(R.batchShaders.fragment.includes('uAtmosphere'));
});
