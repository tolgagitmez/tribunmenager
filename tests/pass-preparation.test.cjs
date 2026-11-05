'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Match,BallPhysics}=require('../football-sim.js');

function fixture({side=1,defenderX=2,velocity=-5,receiverX=3,receiverZ=12}={}){
 const m=new Match({seed:21});m.restart=null;m.kick=null;m.phase='carry';m.time=10;m.planClock=100;
 m.players.forEach(p=>p.active=false);
 const [p,q,original,d]=[m.players[3],m.players[4],m.players[5],m.players[14]];
 for(const a of [p,q,original,d])Object.assign(a,{active:true,vx:0,vz:0,speed:0,face:side===1?0:Math.PI,action:'idle',actionClock:0,duelRecovery:0,tackleClock:0,touchClock:0,receiveClock:0});
 Object.assign(p,{x:0,z:0,kickFoot:1,preferredFoot:1});
 Object.assign(q,{x:receiverX*side,z:receiverZ*side});Object.assign(original,{x:12*side,z:0});
 Object.assign(d,{x:defenderX*side,z:0,vx:velocity*side,speed:Math.abs(velocity),face:side===1?Math.PI:0});
 m.owner=p;m.lastTouch=p;m.ball={x:.88*side,y:.11,z:.18*side,vx:0,vy:0,vz:0};
 m.targets=new Map([[p,{x:0,z:0,pace:1,state:'dribble'}],[q,{x:q.x,z:q.z,pace:1,state:'support'}],[original,{x:original.x,z:original.z,pace:1,state:'support'}],[d,{x:-30*side,z:0,pace:1,state:'press'}]]);
 return {m,p,q,original,d,option:{kind:'pass',q,point:{x:q.x,z:q.z}}};
}
function armReview(f){
 const {m,p,original}=f;
 m.startKick(p,'pass',original,{x:original.x,z:original.z});
 // A controlled already-sustained change of lane risk, not a whole-match claim.
 m.kick.duration=.6;m.kick.clock=.15;
 m.kick.passRead={base:0,next:0,badSince:9,motionAt:10,motion:new Map()};
 return m.kick;
}
for(const side of [1,-1]){
 test(`open lane rejected when real preparation overlaps an intervention (direction ${side})`,()=>{
  const {m,p,option}=fixture({side});
  assert(m.laneRisk(p,option.point,m.passSpeed('pass',12,m.t[0]))<.35);
  const result=m.passPreparation(p,option);
  assert.equal(result.reason,'intervention');assert.equal(result.feasible,false);
  assert(result.interventionTime<result.contactTime);
  assert(result.contactGap<.11);assert(result.facingError<.07);
 });
 test(`same pass is feasible with a later approaching defender (direction ${side})`,()=>{
  const {m,p,option}=fixture({side,defenderX:2.5});
  const result=m.passPreparation(p,option);
  assert.equal(result.feasible,true);assert.equal(result.interventionTime,null);
  assert(result.contactTime>=result.duration&&result.contactTime<.3);
 });
}
test('forecast leaves every real player, ball, target, clock, seed and observation unchanged',()=>{
 const {m,p,option,d}=fixture();armReview({m,p,original:m.players[5]});
 const before=structuredClone(m);
 // Reading future opponent orders would fail. Current own orders are permitted.
 const hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden opponent command');}});m.targets.set(d,hidden);
 m.plan=()=>{throw Error('future plan');};m.random=()=>{throw Error('real RNG');};
 const result=m.passPreparation(p,option,m.kick.passRead);
 delete m.plan;delete m.random;m.targets.set(d,before.targets.get(before.players[14]));
 assert.deepEqual(structuredClone(m),before);assert.equal(result.reason,'intervention');
});
test('preview uses actual kick setup, turning and contact; safe pass releases without repositioning the ball',()=>{
 const f=fixture({defenderX:12,velocity:0});f.d.active=false;
 const {m,p,q,option}=f;const forecast=m.passPreparation(p,option);assert(forecast.feasible);
 let actual=null;const release=m.release;
 m.release=function(){const foot=this.contactPoint(p,'pass'),before={...this.ball};actual={time:this.time-10,gap:Math.hypot(foot[0]-before.x,foot[2]-before.z)};release.call(this);assert.equal(this.ball.x,before.x);assert.equal(this.ball.z,before.z);};
 m.startKick(p,'pass',q,option.point);
 for(let i=0;i<45&&!actual;i++)m.step();
 assert(actual);assert(Math.abs(actual.time-forecast.contactTime)<1e-8);assert(actual.gap<.11);assert.equal(m.flight.target,q);
 const predicted=BallPhysics.predict(m.ball,.1);q.x-=20;q.z+=10;m.integrateBall(.1);
 assert.deepEqual(Object.fromEntries(Object.keys(predicted).map(key=>[key,m.ball[key]])),predicted);
});
test('an exposed fallback does not replace a less immediately exposed emergency outlet',()=>{
 const f=fixture(),{m,p}=f,k=armReview(f),before={ball:{...m.ball},x:p.x,z:p.z,face:p.face,seed:m.seed};
 assert.equal(m.reviewPass(k),true);assert.equal(m.kick.target,f.q);
 assert.equal(m.lastPassPreparation.emergency,true);assert.equal(m.telemetry.passPreparationRejects,1);
 assert.equal(m.telemetry.passEmergencyOutlets,1);assert.equal(m.lastPassPreparation.candidates[0].feasible,false);
 assert(m.lastPassPreparation.control.interventionTime<m.lastPassPreparation.candidates[0].interventionTime);
 assert.deepEqual({ball:m.ball,x:p.x,z:p.z,face:p.face,seed:m.seed},before);
 assert.equal(p.passReviewUntil,10.9);
});
test('a safe alternative is still redirected, with the same physical preparation',()=>{
 const f=fixture({defenderX:2.5}),{m,q}=f,k=armReview(f);
 assert.equal(m.reviewPass(k),true);assert.equal(m.kick.target,q);assert(m.kick.replanned);
 assert.equal(m.lastPassPreparation.candidates[0].feasible,true);assert.equal(m.telemetry.passRedirects,1);
});
test('reaction time and last .12 seconds commitment remain required',()=>{
 for(const phase of ['reaction','commitment']){
  const f=fixture(),{m}=f,k=armReview(f);
  if(phase==='reaction')k.passRead.badSince=m.time;else k.clock=k.duration-.1;
  assert.equal(m.reviewPass(k),false);assert.equal(m.kick,k);assert.equal(m.lastPassPreparation,null);
 }
});
test('shield intent does not suppress a geometrically reachable physical tackle',()=>{
 const f=fixture(),{m,p,d}=f;f.q.active=false;m.reviewPass(armReview(f));assert(p.shieldUntil>m.time);
 Object.assign(d,{x:.9,z:.7,face:Math.atan2(-.7,-.9),vx:0,vz:0,tackleClock:0,duelRecovery:0});
 assert(m.tackleAccess(d,p).attempt);const before=m.telemetry.duels;
 m.doTackle(d,p);assert.equal(m.telemetry.duels,before+1);
});
test('turn/ball preparation and observed recovery clocks change feasibility',()=>{
 const a=fixture({receiverX:3,receiverZ:12}),b=fixture({receiverX:-3,receiverZ:12});
 const early=a.m.passPreparation(a.p,a.option),screened=b.m.passPreparation(b.p,b.option);
 assert(screened.duration>early.duration);assert.equal(screened.feasible,true);assert.equal(early.feasible,false);
 a.d.tackleClock=.5;assert.equal(a.m.passPreparation(a.p,a.option).feasible,true);
});
test('forecast horizon is bounded and inactive receivers are refused',()=>{
 const {m,p,q,option}=fixture({defenderX:20,velocity:0});m.ball.x=1.5;m.ball.z=-1.5;
 const result=m.passPreparation(p,option);assert(result.horizon===.75);assert(result.contactTime===null||result.contactTime<=.75+1e-8);
 q.active=false;assert.equal(m.passPreparation(p,option).reason,'unavailable');
});
test('reset clears preparation diagnostic and preserves normalized saved tactics',()=>{
 const f=fixture(),{m}=f;m.reviewPass(armReview(f));const tactics={...m.t[0]};m.reset();
 assert.equal(m.lastPassPreparation,null);assert.deepEqual(m.t[0],tactics);
});
test('high tempo cannot turn an impossible preparation into a feasible outlet',()=>{
 for(const tempo of [20,61,95]){
  const {m,p,option}=fixture();m.t[0].tempo=tempo;
  assert.equal(m.passPreparation(p,option).reason,'intervention');
 }
});
test('running kicker and braking receiver forecasts match actual fixed-step contacts',()=>{
 let contacts=0;
 for(const speed of [0,2,4])for(const face of [-.5,0,.5]){
  const {m,p,q,d,option}=fixture({defenderX:20,velocity:0});d.active=false;
  Object.assign(p,{vx:speed,vz:0,speed,face});Object.assign(q,{vx:-2,vz:.5,speed:Math.hypot(2,.5)});
  p.oneTouchUntil=11;const predicted=m.passPreparation(p,option);
  // Reroutes deliberately start a new normal preparation, never a stale one-touch.
  p.oneTouchUntil=0;let contactTime=null;const release=m.release;
  m.release=function(){contactTime=this.time-10;return release.call(this);};
  m.startKick(p,'pass',q,option.point);
  for(let tick=0;tick<45&&m.kick&&contactTime===null;tick++)m.step();
  assert.equal(predicted.contactTime===null,contactTime===null);
  if(contactTime!==null){assert(Math.abs(predicted.contactTime-contactTime)<1e-8);contacts++;}
 }
 assert(contacts>=6,'exercise actual running and stationary contact cases');
});
test('when no outlet exists, control fallback remains vulnerable and forecast does not alter state',()=>{
 const f=fixture(),{m,p,q}=f;q.active=false;const k=armReview(f),before={ball:{...m.ball},seed:m.seed,x:p.x,z:p.z};
 assert.equal(m.reviewPass(k),true);assert.equal(m.kick,null);assert.equal(m.lastPassPreparation.fallback,'shield');
 assert.equal(m.lastPassPreparation.emergency,false);assert.deepEqual({ball:m.ball,seed:m.seed,x:p.x,z:p.z},before);
});
test('control forecast is isolated and shares actual first-frame touch/tackle reach',()=>{
 const {m,p,d}=fixture();const choice=m.shieldOption(p,d),before=structuredClone(m);
 const result=m.controlPreparation(p,choice);assert.deepEqual(structuredClone(m),before);
 assert.equal(result.interventionTime,1/60);assert.equal(result.firstTouchTime,1/60);
 m.startCarry(p,choice);m.action(p,'idle',0);m.planClock=0;const beforeDuels=m.telemetry.duels;m.step();assert.equal(m.telemetry.duels,beforeDuels+1);
});
test('an alternative that turns into a challenge is refused when control has time',()=>{
 const f=fixture(),{m,p,q,d}=f;
 Object.assign(d,{x:-1,z:1.5,vx:5/Math.hypot(1,1.5),vz:-7.5/Math.hypot(1,1.5),face:Math.atan2(-1.5,1)});
 const blocker=m.players[15];Object.assign(blocker,{active:true,x:6,z:0,vx:0,vz:0,speed:0,face:Math.PI,duelRecovery:0,tackleClock:0});
 Object.assign(m.players[21],{active:true,x:49,z:0,vx:0,vz:0,speed:0,role:'GK'});
 const k=armReview(f);assert(m.laneRisk(p,k.point)>.75);
 assert.equal(m.reviewPass(k),true);assert.equal(m.kick,null);
 assert.equal(m.lastPassPreparation.emergency,false);assert.equal(m.lastPassPreparation.selectedTargetId,null);
 assert(m.lastPassPreparation.candidates.some(a=>a.targetId===q.id&&a.reason==='intervention'));
 assert.equal(m.lastPassPreparation.control.interventionTime,null);
});
