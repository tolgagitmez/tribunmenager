'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const Rig=require('../humanoid-rig.js');
const {Match}=require('../football-sim.js');
const hypot=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const player=(extra={})=>({
 id:1,team:0,role:'ATT',position:'ST',active:true,
 x:0,z:0,face:0,vx:0,vz:0,speed:0,action:'idle',actionClock:0,
 actionElapsed:0,actionDuration:0,kickFoot:1,dribbleFoot:1,
 feintClock:0,feintSign:1,brainRole:'dribble',footTouch:0,
 ...extra
});
const fixedLegs=pose=>{
 for(const leg of pose.legs){
  assert(Math.abs(hypot(leg.hip,leg.knee)-Rig.ANATOMY.thigh)<1e-5);
  assert(Math.abs(hypot(leg.knee,leg.ankle)-Rig.ANATOMY.shin)<1e-5);
  for(const key of ['hip','knee','ankle','toe'])assert(leg[key].every(Number.isFinite));
 }
 for(const arm of pose.arms){
  assert(Math.abs(hypot(arm.shoulder,arm.elbow)-Rig.ANATOMY.upperArm)<1e-5);
  assert(Math.abs(hypot(arm.elbow,arm.wrist)-Rig.ANATOMY.forearm)<1e-5);
 }
};
test('real feintClock creates shoulder and non-support fake step without a new ball impulse',()=>{
 const baseline=player(),p=player({feintClock:.175,feintSign:1});
 const original=structuredClone(p);
 const plain=Rig.update(baseline,1/60),fake=Rig.update(p,1/60);
 assert.deepEqual(p,original,'rig must never update simulation values');
 assert(fake.feintWeight>.99);
 assert(fake.legs[1].ankle[1]>plain.legs[1].ankle[1]+.025,'fake foot lifts visibly');
 assert.equal(fake.legs[1].stance,false);
 assert(fake.legs[0].stance,'opposite support boot remains planted');
 assert(hypot(fake.arms[0].wrist,plain.arms[0].wrist)>.02,'shoulders counter-rotate visibly');
 assert(Math.abs(fake.legs[0].ankle[1]-.13)<1e-5);
 fixedLegs(fake);
 assert.strictEqual(Rig.update(p,0),fake,'pause must not regenerate a pose');
});
test('shielding presents a guarded shoulder and bent arms while both planted feet stay stable',()=>{
 const a=player({brainRole:'shield'}),b=player({brainRole:'dribble'});
 const original=structuredClone(a);let shield,neutral;
 for(let i=0;i<15;i++){shield=Rig.update(a,1/60);neutral=Rig.update(b,1/60);}
 assert.deepEqual(a,original);
 assert(shield.shieldWeight>.95);
 assert(Math.abs(shield.torsoUpper[0]-neutral.torsoUpper[0])>.004||
  Math.abs(shield.torsoUpper[2]-neutral.torsoUpper[2])>.004);
 assert(hypot(shield.arms[0].wrist,neutral.arms[0].wrist)>.035);
 assert(shield.legs.every(l=>l.stance&&Math.abs(l.ankle[1]-.13)<1e-5));
 fixedLegs(shield);
 a.brainRole='dribble';
 for(let i=0;i<25;i++)shield=Rig.update(a,1/60);
 assert(shield.shieldWeight<.01,'guard relaxes with a bounded crossfade');
});
test('dribble foot follows the actual recorded touch instead of inventing a second ball position',()=>{
 const base=player(),p=player({touchPosition:{x:.48,z:.18},footTouch:.14,touchMode:'close',dribbleFoot:1});
 const original=structuredClone(p),plain=Rig.update(base,1/60),touch=Rig.update(p,1/60);
 const aim=[p.touchPosition.x-.24,.13,p.touchPosition.z];
 assert(hypot(touch.legs[1].ankle,aim)<hypot(plain.legs[1].ankle,aim));
 assert.equal(touch.legs[1].stance,false);
 assert(touch.legs[0].stance);
 fixedLegs(touch);assert.deepEqual(p,original);
});
test('kick contact priority remains authoritative even while feint and shield cues are present',()=>{
 const p=player({action:'shoot',actionClock:.22,actionDuration:.48,actionElapsed:.26,
  contactTime:.26,feintClock:.175,brainRole:'shield',kickFoot:1});
 const pose=Rig.update(p,1/60),boot=Rig.kickAnkle(p);
 assert.equal(pose.feintWeight,0);
 assert(pose.shieldWeight<1e-8);
 assert(hypot(pose.legs[1].ankle,boot)<.003,'visual boot shares the actual release anchor');
 fixedLegs(pose);
});
test('network render extrapolates only visual skill clocks between snapshots',()=>{
 const src=fs.readFileSync(path.join(__dirname,'../live-match-view.js'),'utf8');
 const env={window:{TribunHumanoidRig:{update:()=>{}}},Math,Map,Object,Number};
 vm.runInNewContext(src,env,{filename:'live-match-view.js'});
 const view=new env.window.TribunLiveMatchView();
 const state={
  time:12,duration:90,releaseSerial:0,eventSerial:0,events:[],ownerId:1,
  direction:[1,-1],tactics:[{},{}],ball:{x:0,y:.11,z:0},
  players:[player({feintClock:.30,footTouch:.14,touchPosition:{x:.5,z:.18},brainRole:'shield'})]
 };
 view.ingest(state,1000);view.sample(1080,1/60);
 assert(Math.abs(view.players[0].feintClock-.22)<.001);
 assert(Math.abs(view.players[0].footTouch-.06)<.001);
 assert.equal(state.players[0].feintClock,.30,'server snapshot is immutable to rendering');
 assert.equal(state.players[0].footTouch,.14);
 view.sample(1250,1/60);
 assert.equal(view.players[0].feintClock,.05);
 assert.equal(view.players[0].footTouch,0);
});
test('server snapshot transmits feint, shield and touch cues for the same match actor',()=>{
 const src=fs.readFileSync(path.join(__dirname,'../live-match-worker.cjs'),'utf8');
 for(const field of ['brainRole','touchMode','touchPosition','feintClock','feintSign','shieldFace','footTouch'])
  assert(src.includes("'"+field+"'"),'missing wire field: '+field);
});
test('existing Match physics and deterministic chosen actions are unaffected by rig reads',()=>{
 const m=new Match({seed:19,rules:{periodSeconds:35}}),copy=new Match({seed:19,rules:{periodSeconds:35}});
 for(let n=0;n<240;n++){
  m.step(1/60);copy.step(1/60);
  for(const p of m.players)if(p.active&&!p.referee)Rig.update(p,1/60);
 }
 assert.deepEqual(m.ball,copy.ball);assert.deepEqual(m.events,copy.events);
 assert.deepEqual(m.score,copy.score);assert.deepEqual(m.telemetry,copy.telemetry);
});
