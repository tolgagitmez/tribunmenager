'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Rig=require('../humanoid-rig.js');
global.TribunHumanoidRig=Rig;
const Pilot=require('../match-contact-pilot.js'),BallVisual=require('../ball-visual.js');
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
