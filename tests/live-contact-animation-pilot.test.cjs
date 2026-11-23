'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Rig=require('../humanoid-rig.js');
global.TribunHumanoidRig=Rig;
const Pilot=require('../match-contact-pilot.js'),BallVisual=require('../ball-visual.js');
const Renderer=require('../player-renderer.js'),Skinning=require('../player-skinning.js');
const Assets=require('../assets/player/player-model-data.js');
const near=(a,b,eps=1e-5)=>assert(Math.abs(a-b)<=eps,a+' vs '+b);
function fixture(){
 const p={id:0,team:0,role:'ATT',active:true,x:4,z:0,face:0,
  vx:4,vz:0,speed:4,action:'run',actionClock:0,actionElapsed:0,actionDuration:0,
  kickFoot:1,kickMoving:true,contactTime:.38,energy:1};
 const m={players:[p],time:0,releaseSerial:0,flight:null,
  ball:{x:4.88,z:.18,y:.11,vx:0,vy:0,vz:0}};
 return {p,m};
}
test('real contact pilot reads physics and never mutates the ball, player or score',()=>{
 const {p,m}=fixture(),ctl=Pilot.create({playerId:0});
 const initial=structuredClone(m);
 let step=ctl.observe(m,1/60);assert.equal(step.clip,'run');assert.deepEqual(m,initial);
 m.time=.3;p.x=5.2;p.speed=2;p.face=.28;p.action='shoot';
 p.actionClock=.2;p.actionElapsed=.18;p.actionDuration=.58;
 step=ctl.observe(m,1/60);
 assert.equal(step.clip,'shoot');assert(step.brake>0);assert(step.turn>0);
 assert.equal(step.visual.kickMoving,false);
 assert.equal(step.visual.actionElapsed,.18);
 m.time=.5;p.x=5.6;p.actionElapsed=.38;p.actionClock=0;
 m.releaseSerial=1;m.flight={id:1,kind:'shot',from:p,age:0};
 const exact=Rig.kickContact(p);m.ball={x:exact[0],y:exact[1],z:exact[2],vx:26,vy:5,vz:0,spin:.4};
 const unchanged=structuredClone(m);step=ctl.observe(m,1/60);
 assert.deepEqual(m,unchanged,'presentation must not write back to Match');
 assert.equal(step.release,true);
 near(step.visual.actionElapsed,step.visual.contactTime);
 assert(step.visual.actionClock>0);
 const pose=Rig.getPose(step.visual);
 near(pose.legs[0].ankle[1],.13,.002);
 near(Math.hypot(...pose.legs[1].ankle.map((v,i)=>v-Rig.kickAnkle(step.visual)[i])),0,.002);
 assert.equal(ctl.state().contactCount,1);
 m.time=.62;ctl.observe(m,1/60);
 assert.equal(ctl.state().contactCount,1,'one real release must not retrigger');
 m.time=.9;p.action='run';ctl.observe(m,1/60);
 assert.equal(ctl.state().visual.action,'run');
});
test('ball seam yaw follows actual physical side spin and pauses without drifting',()=>{
 const b={x:2,y:1,z:3,vx:18,vy:2,vz:1,spin:.58};
 const untouched=structuredClone(b),positive=BallVisual.create(),negative=BallVisual.create();
 const zero=positive.orientation();near(Math.hypot(...zero[0]),1,1e-7);
 for(let n=0;n<24;n++){
  positive.sample(b,1/60);
  negative.sample({...b,spin:-.58},1/60);
 }
 assert.deepEqual(b,untouched);
 const plus=positive.orientation(),minus=negative.orientation();
 assert.notDeepEqual(plus,minus,'opposite side spin must turn visible seams differently');
 assert.notDeepEqual(plus,zero,'airborne spin must animate the football texture');
 const frozen=positive.orientation();positive.sample(b,0);
 assert.deepEqual(positive.orientation(),frozen,'paused match must not advance presentation');
 positive.reset();assert.deepEqual(positive.orientation(),zero);
});
test('only selected pilot actor gets visual state and reset clears inherited event',()=>{
 const {p,m}=fixture(),other={...p,id:1,x:10};
 const ctl=Pilot.create({playerId:0});m.players=[p,other];
 assert.equal(ctl.observe(m,1/60).player,p);
 assert.equal(ctl.state().playerId,0);
 m.releaseSerial=5;m.flight={id:5,kind:'pass',from:other};
 ctl.observe(m,1/60);assert.equal(ctl.state().contactCount,0);
 ctl.reset();assert.equal(ctl.state().contactCount,0);
});

test('both support boots hold the licensed outsole in world space and step when they run out of reach',()=>{
 const raw=Buffer.from(Assets.lods[0].vertices,'base64');
 const vertices=new Float32Array(raw.buffer,raw.byteOffset,raw.length/4);
 const sampleDt=1/60;
 for(const kickFoot of [0,1]){
  const {p,m}=fixture(),ctl=Pilot.create({playerId:p.id});
  const joint=Assets.bones.findIndex(bone=>bone.name===(kickFoot===0?'foot.R':'foot.L'));
  assert(joint>=0);
  const outsole=[];
  for(let i=0;i<vertices.length;i+=20){
   if(vertices[i+16]===4&&vertices[i+1]<.03&&vertices[i+8]===joint)outsole.push(i);
  }
  assert(outsole.length>=100,'outsole sampling includes the licensed visible mesh');
  function sample(frame,x,speed){
   m.time=frame*sampleDt;
   Object.assign(p,{x,z:0,speed,vx:speed,vz:0,kickFoot,action:'pass',actionClock:.9,
    actionDuration:1.6,actionElapsed:.30+Math.min(m.time,.18)});
   const unchanged=structuredClone(m),step=ctl.observe(m,sampleDt);
   assert.deepEqual(m,unchanged);
   const pose=Rig.getPose(step.visual),leg=pose.legs[1-kickFoot];
   near(Math.hypot(...leg.knee.map((v,i)=>v-leg.hip[i])),Rig.ANATOMY.thigh);
   near(Math.hypot(...leg.ankle.map((v,i)=>v-leg.knee[i])),Rig.ANATOMY.shin);
   const palette=Skinning.fromMatrices(Renderer.palette(step.visual,Assets,pose));
   const points=outsole.map(i=>Skinning.deform(palette,vertices.subarray(i+8,i+12),
    vertices.subarray(i+12,i+16),vertices.subarray(i,i+3)));
   return {leg,points};
  }
  const start=sample(0,0,3);
  assert(start.leg.stance);
  for(let frame=1;frame<=9;frame++){
   const {leg,points}=sample(frame,3*frame*sampleDt,3);
   assert(leg.stance,'initial 150 ms is one unbroken plant');
   for(let i=0;i<points.length;i++){
    const [x,y,z]=points[i],reference=start.points[i];
    assert(Math.hypot(x-reference[0],z-reference[2])<.03,'the planted sole must stay on the same turf');
    near(y,reference[1]);
   }
  }
  let lifted=false,replanted=false;
  const initialSole=Math.min(...start.points.map(point=>point[1]));
  for(let frame=10;frame<40&&!replanted;frame++){
   const {leg,points}=sample(frame,3*Math.min(frame,15)*sampleDt,frame<15?3:0);
   if(!leg.stance&&Math.min(...points.map(point=>point[1]))>initialSole+.02)lifted=true;
   if(lifted&&leg.stance){
    assert(Math.abs(leg.ankle[0]-start.leg.ankle[0])>.1,'support must move to a new spot');
    assert.equal(ctl.state().support.phase,'planted');
    replanted=true;
   }
  }
  assert(lifted&&replanted,'unreachable support must visibly lift and replant');
 }
});

test('timed cutback and through cues survive a missing flight without replaying past contacts',()=>{
 for(const kickKind of ['cutback','through']){
  const {p,m}=fixture(),ctl=Pilot.create({playerId:p.id});
  const cue={id:3,kind:'release',playerId:p.id,flightId:17,kickKind,time:1,
   actor:{...p,contactTime:.41},ball:{...m.ball}};
  m.contacts=[cue];m.time=.97;m.releaseSerial=21;
  assert.equal(ctl.observe(m,1/60).release,false,'a future cue must not reach the pose early');
  m.time=1.08;
  const unchanged=structuredClone(m),step=ctl.observe(m,1/60);
  assert.equal(step.release,true);
  assert.equal(step.releaseCue,cue);
  assert.equal(step.visual.action,'pass');
  near(step.visual.actionElapsed,.49);
  assert.equal(ctl.state().releaseAt,cue.time);
  assert.equal(ctl.state().releaseSerial,cue.flightId);
  assert.deepEqual(m,unchanged);
  m.time=1.10;ctl.observe(m,1/60);
  assert.equal(ctl.state().contactCount,1,'repeated snapshots must not replay the cue');
  m.contacts=[cue,{...cue,id:4,time:1.2}];m.time=1.60;
  assert.equal(ctl.observe(m,1/60).release,false,'late history past the recovery window must not animate');
  assert.equal(ctl.state().contactCount,1);
 }
});

test('a headed shot keeps its header pose in both the timed and direct observers',()=>{
 const {p,m}=fixture();
 Object.assign(p,{action:'header',actionClock:.22,actionElapsed:.27});
 Object.assign(m,{time:1,releaseSerial:1,flight:{id:1,kind:'shot',from:p,age:0}});
 const cue={id:1,kind:'release',playerId:p.id,flightId:1,kickKind:'shot',time:1,
  actor:{...p},ball:{...m.ball}};
 for(const source of [m,{...m,contacts:[cue]}]){
  const step=Pilot.create({playerId:p.id}).observe(source,1/60);
  assert.equal(step.release,false);
  assert.equal(step.visual.action,'header');
 }
});

test('actual Match penalty release is sampled at the same foot-contact tick',()=>{
 const {Match}=require('../football-sim.js'),Club=require('../club-data.js');
 const m=new Match({seed:21,players:Club.createRoster(),starters:Club.starters,
  managerKicks:true,rules:{minPlayers:1,periodSeconds:160}},Rig);
 const p=m.players[1],pilot=Pilot.create({playerId:p.id});
 m.setRestart('penalty',0,{x:30,z:3},p);
 let release=null;
 for(let tick=0;tick<1800&&!m.done;tick++){
  if(m.pendingManagerKick){
   assert.equal(m.pendingManagerKick.playerId,p.id);
   assert(m.resolveManagerKick(m.pendingManagerKick.id,null),'automatic selection');
  }
  m.step(1/60);
  // Exactly the same presentation observer that runs after local/synced
  // match physics, not an authored animation-lab timeline.
  const step=pilot.observe(m,1/60);
  if(m.releaseSerial>0&&m.flight?.from===p){
   release={step,ball:structuredClone(m.ball),point:m.contactPoint(p)};
   break;
  }
 }
 assert(release,'natural prepared penalty must release at the actual Match boot');
 assert.equal(pilot.state().contactCount,1);
 assert.equal(release.step.release,true);
 assert.equal(release.step.clip,'shoot');
 assert.equal(release.step.visual.kickMoving,false);
 const gap=Math.hypot(release.point[0]-release.ball.x,release.point[1]-release.ball.y,release.point[2]-release.ball.z);
 assert(gap<.115,'physical ball leaves at the same location as the visible boot tip: '+gap);
 const pose=Rig.getPose(release.step.visual),support=pose.legs[1-(p.kickFoot===0?0:1)];
 near(support.ankle[1],.13,.003);
 near(Math.hypot(...pose.legs[p.kickFoot===0?0:1].ankle.map((v,i)=>v-Rig.kickAnkle(release.step.visual)[i])),0,.003);
});
