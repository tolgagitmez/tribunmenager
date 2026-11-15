'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Rig=require('../humanoid-rig-procedural');
const Renderer=require('../player-renderer-procedural');

const length=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const close=(a,b,epsilon=1e-6)=>assert(Math.abs(a-b)<epsilon,`expected ${a} ≈ ${b}`);
const player=extra=>({x:0,z:0,speed:0,face:0,action:'idle',actionClock:0,kickFoot:1,...extra});

test('two-bone IK enforces fixed bone lengths for reachable and unreachable goals',()=>{
 for(const goal of [[0,-.65,0],[0,-3,0],[.02,-.01,0],[0,-.5,.5],[0,0,0]]){
  const p=Rig.solveLimb([0,0,0],goal,.47,.47,[1,0,0]);
  close(length([0,0,0],p.joint),.47);
  close(length(p.joint,p.end),.47);
  assert(p.bend>=.07-1e-8&&p.bend<=2.65+1e-8);
 }
});
test('IK hinge can be mirrored without changing segment lengths',()=>{
 for(const side of [-1,1]){
  const a=Rig.solveLimb([0,1,side*.3],[.14,.50,side*.32],.33,.34,[.3,0,side]);
  close(length([0,1,side*.3],a.joint),.33);
  close(length(a.joint,a.end),.34);
 }
});
test('all normal animation scenarios retain constant visual arm and leg lengths',()=>{
 const Scenarios=require('../animation-scenarios');
 for(const mode of ['walk','jog','run','sprint','turn','pass','shoot','dive-left','dive-right']){
  const state=Scenarios.create(mode);
  for(let i=0;i<120;i++){
   Scenarios.sample(state,i/60,Rig);
   const pose=Rig.update(state.p,1/60);
   const legLengths=pose.legs.map(l=>[length(l.hip,l.knee),length(l.knee,l.ankle)]);
   for(const [upper,lower] of legLengths){close(upper,.50,1e-5);close(lower,.50,1e-5);}
   for(const a of pose.arms){
    const expected=mode.startsWith('dive')&&pose.action==='dive'&&pose.weight>.001?.36:.33;
    close(length(a.shoulder,a.elbow),expected,1e-5);
    close(length(a.elbow,a.wrist),mode.startsWith('dive')&&pose.action==='dive'&&pose.weight>.001?.36:.34,1e-5);
   }
  }
 }
});
test('GPU palette rotations never scale a limb',()=>{
 const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
 const bones=['thigh.L','shin.L','upper_arm.R','forearm.R'].map((name,i)=>({
  name,head:[0,0,0],tail:[0,1,0],matrix:identity,inverseBind:identity
 }));
 const p=player(),pose=Rig.update(p,1/60),palette=Renderer.palette(p,{bones},pose);
 for(let i=0;i<bones.length;i++){
  const offset=i*16;
  for(let axis=0;axis<3;axis++){
   const n=Math.hypot(...[0,1,2].map(row=>palette[offset+axis*4+row]));
   close(n,1,1e-5);
  }
 }
});

test('athletic rest proportions maintain a normal pelvis, wrist and foot contact',()=>{
 const p=player(),pose=Rig.update(p,1/60);
 close(pose.pelvis[1],1);
 assert(pose.head[1]>1.70&&pose.head[1]<1.85);
 for(const leg of pose.legs)assert(leg.knee[1]>.45&&leg.knee[1]<.7);
 for(const arm of pose.arms)assert(arm.wrist[1]>.82&&arm.wrist[1]<1.03);
 p.action='shoot';p.actionClock=.25;p.contactTime=.38;p.actionElapsed=.38;p.actionDuration=.65;
 const kick=Rig.update(p,1/60),target=Rig.kickAnkle(p);
 assert(length(kick.legs[1].ankle,target)<1e-6,'kick ankle must remain reachable');
});

test('walk, jog and sprint remain distinct continuous movement patterns',()=>{
 const Scenarios=require('../animation-scenarios');
 const values=[];
 for(const mode of ['walk','jog','sprint']){
  const s=Scenarios.create(mode);
  Scenarios.sample(s,1,Rig);
  values.push(s.p.speed);
  for(let i=1;i<=60;i++){
   const t=i/60;Scenarios.sample(s,t,Rig);const pose=Rig.update(s.p,1/60);
   assert(Number.isFinite(pose.legs[0].knee[0])&&Number.isFinite(pose.legs[1].knee[0]));
  }
 }
 assert(values[0]<values[1]&&values[1]<values[2]);
});
