'use strict';

const assert=require('node:assert/strict');
const {test}=require('node:test');
const Assets=require('../assets/player/player-model-data.js');
const Renderer=require('../player-renderer.js');
const Rig=require('../humanoid-rig.js');

const distance=(a,b)=>Math.hypot(...a.map((value,index)=>value-b[index]));
const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-8,`${actual} vs ${expected}`);

function reception(foot){
 const side=foot?1:-1;
 const player={x:12,z:-7,face:side*1.1,action:'receive',actionClock:.15,actionDuration:.15,kickFoot:foot};
 const co=Math.cos(player.face),si=Math.sin(player.face);
 const ball={x:player.x+.5*co-side*.86*si,y:.11,z:player.z+.5*si+side*.86*co};
 return {player,ball,pose:Rig.getPose(player)};
}

function assertLimbLengths(pose){
 for(const leg of pose.legs){
  near(distance(leg.hip,leg.knee),Rig.ANATOMY.thigh);
  near(distance(leg.knee,leg.ankle),Rig.ANATOMY.shin);
  near(distance(leg.ankle,leg.toe),Rig.ANATOMY.foot);
  assert.ok(leg.flex>=Rig.LIMITS.hip.flexMin&&leg.flex<=Rig.LIMITS.hip.flexMax);
  assert.ok(leg.abduct>=Rig.LIMITS.hip.abductMin&&leg.abduct<=Rig.LIMITS.hip.abductMax);
  assert.ok(leg.bend>=Rig.LIMITS.knee.min-1e-8&&leg.bend<=Rig.LIMITS.knee.max+1e-8);
 }
}

test('either receiving boot reaches the licensed ball surface while the support boot holds its pose',async()=>{
 const [THREE,{createBootContactMeter},{firstTouchPose}]=await Promise.all([
  import('../vendor/three/build/three.module.min.js'),import('../match-boot-contact.mjs'),import('../match-first-touch.mjs')
 ]);
 const meter=createBootContactMeter({assets:Assets,decode:Renderer.decode,Skinning:Renderer.skinning,THREE});
 for(const foot of [0,1]){
  const {player,ball,pose}=reception(foot);
  const planted=pose.legs[1-foot];
  const anchor={ankle:[planted.ankle[0]+.02,planted.ankle[1],planted.ankle[2]],
   toe:[planted.toe[0]+.02,planted.toe[1],planted.toe[2]]};
  const original=structuredClone({pose,ball,anchor});
  const measure=pose=>meter.measure({palette:Renderer.palette(player,Assets,pose),foot,ball}).gapMetres;
  assert.ok(measure(pose)>.30);
  assert.equal(firstTouchPose(Rig,pose,{foot,ball,weight:0,support:anchor}),pose);
  for(const weight of [.125,.25,.5,.75,1]){
   const shape=firstTouchPose(Rig,pose,{foot,ball,weight,support:anchor});
   assert.notEqual(shape,pose);
   assertLimbLengths(shape);
   near(distance(shape.legs[1-foot].ankle,anchor.ankle),0);
   near(distance(shape.legs[1-foot].toe,anchor.toe),0);
   assert.ok(distance(shape.pelvis,pose.pelvis)<.24);
   if(weight===1){
    const gap=measure(shape);
    assert.ok(gap>=-.005&&gap<.01,`foot ${foot}: ${gap} m`);
   }
  }
  assert.deepEqual({pose,ball,anchor},original);
 }
});

test('the ground pose ignores aerial and non-finite targets and respects reach for remote anchors',async()=>{
 const {firstTouchPose}=await import('../match-first-touch.mjs');
 const {ball,pose}=reception(1);
 assert.equal(firstTouchPose(Rig,pose,{foot:1,ball:{...ball,y:.4},weight:1}),pose);
 assert.equal(firstTouchPose(Rig,pose,{foot:1,ball:{...ball,z:NaN},weight:1}),pose);
 const remote={ankle:[200,.13,200],toe:[200.2,.055,200]};
 const reachable=firstTouchPose(Rig,pose,{foot:1,ball,weight:1,support:remote});
 assertLimbLengths(reachable);
 near(distance(reachable.legs[0].ankle,pose.legs[0].ankle),0);
 const outside=firstTouchPose(Rig,pose,{foot:1,ball:{x:120,y:.11,z:120},weight:1});
 assertLimbLengths(outside);
 assert.ok(distance(outside.pelvis,pose.pelvis)<.24);
});
