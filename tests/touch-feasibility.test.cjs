'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto'),Module=require('node:module');
const {Match,BallPhysics,distance}=require('../football-sim');
const source=zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'../docs/validation/baselines/stage8-integration-base.js.gz')));
assert.equal(crypto.createHash('sha256').update(source).digest('hex'),'16d6d78ac01b5490bbb8a178b4134a2f8c41224ad7091fb1e0b6b37aafa07360');
const baseline=new Module(path.join(__dirname,'../touch-feasibility-baseline.js'),module);
baseline.filename=path.join(__dirname,'../touch-feasibility-baseline.js');baseline.paths=module.paths;baseline._compile(source.toString(),baseline.filename);
const OldMatch=baseline.exports.Match,dt=1/60;
function fixture({side=1,speed=4,yaw=0,shield=false,lateral=.18,ballSpeed=3}={}){
 const m=new Match({seed:21});m.restart=null;m.kick=null;m.time=10;m.planClock=100;m.players.forEach(q=>q.active=false);
 const p=m.players[3],target={x:6*Math.cos(yaw)*side,z:6*Math.sin(yaw)*side};
 Object.assign(p,{active:true,x:0,z:0,vx:speed*side,vz:0,speed,face:side>0?0:Math.PI,skill:82,dribbling:82,agility:82,pace:82,stamina:95,energy:1,touchClock:0,receiveClock:0,duelRecovery:0,action:'idle',actionClock:0,decision:100,carryTarget:target,shieldUntil:shield?11:0,shieldFace:side>0?0:Math.PI,preferredFoot:1,kickFoot:1});
 m.owner=p;m.lastTouch=p;m.lastTeam=p.team;m.ball={x:.8*side,y:.11,z:lateral*side,vx:ballSpeed*side,vy:0,vz:0};
 m.targets=new Map([[p,{...target,state:shield?'shield':'dribble',pace:shield?.56:.98}]]);
 return {m,p};
}
function clone(m,Engine=Match){return Object.assign(Object.create(Engine.prototype),structuredClone(m));}
function pose(p){return {x:p.x,z:p.z,vx:p.vx,vz:p.vz,face:p.face};}
function firstLiveTouch(m,p){
 let captured;const query=m.touchPlan;
 m.touchPlan=function(actor,candidate,options){
  const before={...this.ball},result=query.call(this,actor,candidate,options);
  if(actor===p&&result.ready&&!captured)captured={result,options,before,full:this.touchRecovery(actor,candidate,options)};
  return result;
 };
 m.step(dt);delete m.touchPlan;assert(captured,'the ordinary owner step must apply a touch');
 assert.deepEqual(m.ball,BallPhysics.predict({...captured.before,...captured.result.velocity},dt),'the emitted impulse precedes this same frame\'s free ball step');
 return captured;
}
function assertNextLiveContact(m,p,forecast){
 // Observe the next live foot attempt before its impulse and ball integration.
 // Keep the natural clocks and the real owner movement/planner; suppress only
 // that future impulse, which the single-contact forecast must not invent.
 let actual,frame=0;p.decision=100;
 m.dribbleTouch=function(actor){assert.equal(actor,p);actual={frame,player:pose(p),ball:{...this.ball},contact:this.touchContact(p),touchClock:p.touchClock,receiveClock:p.receiveClock};return false;};
 const frames=Math.round(forecast.time*60);
 for(frame=1;frame<=frames;frame++)m.step(dt);
 delete m.dribbleTouch;
 assert(actual,'a real next foot attempt must occur at the predicted frame');assert.equal(actual.frame,frames);
 assert.equal(actual.touchClock,0);assert.equal(actual.receiveClock,0);assert.equal(actual.contact.ready,true);
 assert.deepEqual(actual.player,forecast.player);assert.deepEqual(actual.ball,forecast.ball);
 return actual;
}
function reception(side=1,speed=6,yaw=Math.PI){
 const {m,p}=fixture({side,speed,yaw,ballSpeed:-10}),from=m.players[4];
 Object.assign(from,{active:true,x:-8*side,z:8*side,vx:0,vz:0,speed:0});m.owner=null;
 m.flight={id:7,kind:'pass',from,target:p,age:0,point:{...p.carryTarget},offsidePlayers:[]};
 p.reception={flightId:7,fromId:from.id,at:10,mode:'open',point:{...p.carryTarget},face:yaw+(side<0?Math.PI:0)};
 return {m,p,from};
}
for(const side of [1,-1]){
 test(`a fast reversing dribble is limited to a recoverable next foot contact (${side})`,()=>{
  const {m,p}=fixture({side,yaw:Math.PI}),old=clone(m,OldMatch);old.step(dt);assert(old.ball.vx*side<0);
  const touch=firstLiveTouch(m,p);assert.equal(touch.full.ready,false);assert.equal(touch.result.limited,true);
  assert.equal(m.telemetry.limitedTouches,1);assert(m.ball.vx*side>0);assert.equal(m.owner,p);
  assert.equal(touch.result.recovery.ready,true);assertNextLiveContact(m,p,touch.result.recovery);
 });
 test(`an unrecoverable sprint reversal defers the impulse while the ball rolls freely (${side})`,()=>{
  const {m,p}=fixture({side,speed:6,yaw:Math.PI}),old=clone(m,OldMatch),before={...m.ball};
  old.dribbleTouch(old.players[p.id]);assert(old.ball.vx*side<0);
  assert.equal(m.dribbleTouch(p),false);assert.deepEqual(m.ball,before);assert.equal(m.telemetry.touchDeferrals,1);
  assert.equal(m.telemetry.dribbleTouches,0);assert(p.touchClock>0&&p.touchClock<=.05);
  const expected=BallPhysics.predict(before,dt);m.step(dt);assert.deepEqual(m.ball,expected);assert(p.x*side>0);assert.equal(m.owner,p);
 });
 test(`an ordinary straight stride retains the exact existing touch and physical step (${side})`,()=>{
  const {m,p}=fixture({side}),old=clone(m,OldMatch);assert.equal(m.dribbleTouch(p),true);assert.equal(old.dribbleTouch(old.players[p.id]),true);
  assert.deepEqual(structuredClone(m),structuredClone(old));m.step(dt);old.step(dt);assert.deepEqual(structuredClone(m),structuredClone(old));
  assert.equal(m.telemetry.strideTouches,1);assert.equal(m.telemetry.limitedTouches,undefined);
 });
 test(`next-contact prediction matches actual fixed steps across current owner command refreshes (${side})`,()=>{
  for(const refresh of [100,.03,0])for(const situation of [{speed:4,yaw:Math.PI/2,lateral:.18},{speed:6,yaw:.6,lateral:.8}]){
   const {m,p}=fixture({side,...situation});m.planClock=refresh;
   const touch=firstLiveTouch(m,p),forecast=touch.result.recovery;
   assert.equal(forecast.ready,true);assert(forecast.time>=touch.options.interval&&forecast.time<=touch.options.interval+dt);
   assert.equal(forecast.ballTime,forecast.time);assertNextLiveContact(m,p,forecast);assert.equal(m.kick,null);
  }
 });
 test(`shielding cannot reverse the ball against a sprinting body (${side})`,()=>{
  const {m,p}=fixture({side,speed:6,yaw:Math.PI,shield:true}),old=clone(m,OldMatch);
  old.step(dt);assert(old.ball.vx*side<0);
  const touch=firstLiveTouch(m,p);assert.equal(p.touchMode,'shield');assert.equal(m.telemetry.limitedTouches,1);assert(m.ball.vx*side>=0);
  assertNextLiveContact(m,p,touch.result.recovery);assert(p.x*side>0);
 });
 test(`a prepared reception cannot turn a sprinting player's available front contact into a reverse exit (${side})`,()=>{
  const {m,p}=reception(side),old=clone(m,OldMatch),unprepared=clone(m,OldMatch);unprepared.players[p.id].reception=null;
  const before={x:p.x,z:p.z},physicalArrival=BallPhysics.predict(m.ball,dt);m.ballStep(dt);old.ballStep(dt);unprepared.ballStep(dt);
  assert.equal(m.owner,p);assert.equal(p.receiveMode,'cushion');assert.equal(m.telemetry.touchDeferrals,1);assert.equal(m.telemetry.directedTouches,0);
  assert(old.ball.vx*side<0);assert.equal(old.telemetry.directedTouches,1);assert.deepEqual(m.ball,unprepared.ball);
  assert.deepEqual({x:p.x,z:p.z},before);assert.equal(m.ball.x,physicalArrival.x);assert.equal(m.ball.z,physicalArrival.z);
  assert(p.receiveClock>0);assert.equal(p.reception,null);assert.equal(m.kick,null);
 });
 test(`open-play pass setup waits for real recovery of a ball behind the body and releases at the actual foot (${side})`,()=>{
  const {m,p}=fixture({side,speed:0,ballSpeed:0});m.ball.x=-.7*side;
  const old=clone(m,OldMatch),point={x:6*side,z:0};assert(m.startKick(p,'pass',null,point));old.startKick(old.players[p.id],'pass',null,point);
  const untouched=BallPhysics.predict(m.ball,dt),position={x:p.x,z:p.z};m.step(dt);old.step(dt);
  assert.deepEqual(m.ball,untouched);assert.notDeepEqual(old.ball,untouched);assert.equal(m.kick.setupImpulse,false);assert(m.telemetry.setupTouchDeferrals>0);
  assert(distance(p,position)<.01);assert(Math.abs(p.face-(side>0?0:Math.PI))<=7*dt+1e-12);
  let released=null;const release=m.release;
  m.release=function(){const foot=this.contactPoint(p,'pass'),before={...this.ball};released={gap:Math.hypot(foot[0]-before.x,foot[2]-before.z),time:this.time-10};const result=release.call(this);assert.equal(this.ball.x,before.x);assert.equal(this.ball.z,before.z);return result;};
  for(let i=0;i<90&&m.kick&&!released;i++)m.step(dt);
  assert(released);assert(released.gap<.11);assert(released.time>.18);assert.equal(m.owner,null);assert.equal(m.kick,null);assert.equal(m.flight.kind,'pass');
  assert(distance(p,position)>0);assert(m.telemetry.setupTouchDeferrals>0);
 });
}
test('a physically available prepared forward reception retains the exact baseline control',()=>{
 const {m,p}=reception(1,0,0),old=clone(m,OldMatch);m.ballStep(dt);old.ballStep(dt);
 assert.equal(m.telemetry.directedTouches,1);assert.equal(p.receiveMode,'open');assert.deepEqual(structuredClone(m),structuredClone(old));
});
test('the selected side uses its actual left or right foot in both playing directions',()=>{
 for(const side of [1,-1])for(const foot of [0,1]){
  const {m,p}=fixture({side,speed:2,yaw:Math.PI/2,lateral:foot?.3:-.3});p.preferredFoot=foot;
  assert.equal(m.touchContact(p).foot,foot);assert.equal(m.dribbleTouch(p),true);assert.equal(p.dribbleFoot,foot);
  const predicted=BallPhysics.predict(m.ball,dt);m.step(dt);assert.deepEqual(m.ball,predicted);
 }
});
test('a weaker available foot preserves more incoming momentum on the same turn',()=>{
 const low=fixture({speed:2,yaw:Math.PI/2,lateral:-.3}),high=fixture({speed:2,yaw:Math.PI/2,lateral:-.3});
 low.p.weakFoot=40;high.p.weakFoot=80;assert.equal(low.m.dribbleTouch(low.p),true);assert.equal(high.m.dribbleTouch(high.p),true);
 assert.equal(low.p.dribbleFoot,0);assert.equal(high.p.dribbleFoot,0);assert(low.m.ball.vx>high.m.ball.vx);assert(low.m.ball.vz<high.m.ball.vz);
 for(const {m,p} of [low,high]){const expected=BallPhysics.predict(m.ball,dt);m.step(dt);assert.deepEqual(m.ball,expected);assert.equal(m.owner,p);}
});
test('a pass cannot use a forced foot across a ball reachable only by the other foot',()=>{
 const {m,p}=fixture({speed:0,lateral:.9,ballSpeed:0});m.ball.x=.5;assert(m.startKick(p,'pass',null,{x:6,z:0}));p.kickFoot=0;
 assert.equal(m.touchContact(p,m.ball,0).ready,false);assert.equal(m.touchContact(p,m.ball,1).ready,true);
 const before=structuredClone(m),result=m.touchPlan(p,{vx:0,vy:0,vz:0},{mode:'setup',interval:.2,target:{x:6,z:0}});
 assert.equal(result.ready,false);assert.equal(result.reason,'foot');assert.deepEqual(structuredClone(m),before);
});
test('ordinary reachable interventions and loss of possession still operate after control is deferred',()=>{
 const f=reception(),{m,p}=f;m.ballStep(dt);assert.equal(p.receiveMode,'cushion');const d=m.players[14];
 Object.assign(d,{active:true,x:.8,z:.7,vx:0,vz:0,speed:0,face:Math.atan2(-.7,-.8),touchClock:0,duelRecovery:0,tackleClock:0});
 assert.equal(m.tackleAccess(d,p).attempt,true);const duels=m.telemetry.duels;m.doTackle(d,p);assert.equal(m.telemetry.duels,duels+1);
 const other=reception(),opponent=other.m.players[14];Object.assign(opponent,{active:true,x:.7,z:.05,vx:0,vz:0,speed:0,face:Math.PI,touchClock:0,duelRecovery:0});
 other.m.ballStep(dt);assert.equal(other.m.owner,opponent);assert.equal(other.m.telemetry.directedTouches,0);
 const carry=fixture();carry.m.ball.x=4;const expected=BallPhysics.predict(carry.m.ball,dt);carry.m.step(dt);
 assert.equal(carry.m.owner,null);assert.deepEqual(carry.m.ball,expected);assert(carry.m.telemetry.looseBalls>0);
});
test('the shared prediction consumes no RNG, future plans, hidden rival orders or live state',()=>{
 const {m,p}=fixture({yaw:Math.PI/2}),rival=m.players[14],teammate=m.players[4];
 Object.assign(rival,{active:true,x:5,z:4,vx:-2,vz:0});Object.assign(teammate,{active:true,x:3,z:3,vx:.4,vz:.2});
 const before=structuredClone(m),hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden rival order');}});m.targets.set(rival,hidden);
 m.random=()=>{throw Error('RNG');};m.plan=()=>{throw Error('future tactical choice');};m.choose=()=>{throw Error('future ball choice');};
 const candidate={vx:1.58,vy:.08,vz:3.43},first=m.touchPlan(p,candidate,{interval:.3416,target:p.carryTarget}),second=m.touchPlan(p,candidate,{interval:.3416,target:p.carryTarget});
 assert.equal(first.ready,true);assert.deepEqual(first,second);assert.equal(m.touchContact(p).ready,true);
 m.targets.delete(rival);delete m.random;delete m.plan;delete m.choose;assert.deepEqual(structuredClone(m),before);
});
test('invalid or inactive requests are refused and every next-contact forecast has a bounded horizon',()=>{
 const {m,p}=fixture(),candidate={vx:3,vy:0,vz:0},before=structuredClone(m);
 for(const interval of [undefined,NaN,Infinity,-.1,0,.650001,2])assert.equal(m.touchRecovery(p,candidate,{interval}).ready,false);
 const longest=m.touchRecovery(p,candidate,{interval:.65,target:p.carryTarget});assert(longest.time<=.65+1e-12);
 for(const key of ['vx','vy','vz'])assert.equal(m.touchPlan(p,{...candidate,[key]:NaN},{interval:.3}).ready,false);
 for(const key of ['x','z','vx','vz','face']){const value=p[key];p[key]=NaN;assert.equal(m.touchRecovery(p,candidate,{interval:.3}).ready,false);p[key]=value;}
 p.active=false;assert.equal(m.touchPlan(p,candidate,{interval:.3}).ready,false);assert.equal(m.touchRecovery(p,candidate,{interval:.3}).ready,false);p.active=true;
 m.ball.y=.5;assert.equal(m.touchPlan(p,candidate,{interval:.3}).ready,false);m.ball.y=.11;
 assert.deepEqual(structuredClone(m),before);
});
test('a queried touch leaves later released flight entirely under the shared ball integrator',()=>{
 const {m,p}=fixture();m.touchPlan(p,{vx:4,vy:.1,vz:1},{interval:.3,target:p.carryTarget});m.owner=null;m.flight=null;
 const expected=BallPhysics.predict(m.ball,.2),position=pose(p);m.integrateBall(.2);assert.deepEqual(m.ball,expected);assert.deepEqual(pose(p),position);
});
test('carry and shield retain the dribble cadence, and reception recovery also blocks a real pass setup',()=>{
 for(const clock of ['touchClock','receiveClock']){
  const {m,p}=fixture({speed:0,ballSpeed:0});p[clock]=.2;
  const before={...m.ball};
  for(const mode of ['carry','shield'])assert.equal(m.touchPlan(p,{vx:3,vy:.1,vz:0},{mode,interval:.3,target:p.carryTarget}).ready,false);
  if(clock==='receiveClock'){
   const setup=clone(m),actor=setup.players[p.id];assert(setup.startKick(actor,'pass',null,{...actor.carryTarget}));
   assert.equal(setup.touchPlan(actor,{vx:3,vy:0,vz:0},{mode:'setup',interval:.2,target:actor.carryTarget}).reason,'foot-clock');
   setup.step(dt);assert.equal(setup.kick.setupImpulse,false);assert.deepEqual(setup.ball,before);assert(actor.receiveClock>0);
  }
  assert.equal(m.dribbleTouch(p),false);assert.deepEqual(m.ball,before);assert.equal(p[clock],.2);
  for(let i=0;i<11;i++)m.step(dt);
  assert.equal(m.telemetry.dribbleTouches,0);assert.deepEqual(m.ball,before);assert(p[clock]>0);
  m.step(dt);m.step(dt);assert.equal(m.telemetry.dribbleTouches,1);assert(m.ball.vx>0);
  if(clock==='receiveClock')assert.equal(p.receiveClock,0);
 }
});
test('a recovering player cannot produce a contact impulse before the ordinary duel clock expires',()=>{
 const {m,p}=fixture({speed:0,ballSpeed:0});p.duelRecovery=.2;const before={...m.ball};
 assert.equal(m.touchContact(p).ready,false);assert.equal(m.touchPlan(p,{vx:3,vy:.1,vz:0},{interval:.3,target:p.carryTarget}).ready,false);
 assert.equal(m.dribbleTouch(p),false);assert.deepEqual(m.ball,before);
 for(let i=0;i<11;i++)m.step(dt);
 assert(p.duelRecovery>0);assert.equal(m.telemetry.dribbleTouches,0);assert.deepEqual(m.ball,before);
 for(let i=0;i<7&&!m.telemetry.dribbleTouches;i++)m.step(dt);
 assert.equal(p.duelRecovery,0);assert.equal(m.telemetry.dribbleTouches,1);assert(m.ball.vx>0);
});
test('a candidate that leaves the carrying envelope is a real loose ball, not a promised later contact',()=>{
 const {m,p}=fixture(),candidate={vx:20,vy:0,vz:0};
 const forecast=m.touchRecovery(p,candidate,{interval:.65,target:p.carryTarget});assert.equal(forecast.ready,false);assert.equal(forecast.lost,true);assert(forecast.maxGap>3.2);
 Object.assign(m.ball,candidate);p.touchClock=1;p.decision=100;
 let expected={...m.ball};
 for(let i=0;i<39;i++){BallPhysics.step(expected,dt);m.step(dt);assert.deepEqual(m.ball,expected);}
 assert.equal(m.owner,null);assert(m.telemetry.looseBalls>0);assert.equal(m.telemetry.dribbleTouches,0);
});
for(const side of [1,-1])test(`a first control forecasts the committed receiving action and its post-integration contact phase (${side})`,()=>{
 let ordinary;
 for(const staleClock of [0,.15,.3,.6]){
  const {m,p}=reception(side);Object.assign(p,{action:staleClock?'pass':'idle',actionClock:staleClock,actionElapsed:0,kickMoving:false});
  // Acquisition is the actual ground-contact callback after this frame's ball
  // integration. Its next contact must not include another current-frame roll.
  let captured;const query=m.touchPlan;
  m.touchPlan=function(actor,candidate,options){const result=query.call(this,actor,candidate,options);captured={result,options};return result;};
  assert.equal(m.acquire(p),true);delete m.touchPlan;
  assert(captured);assert.equal(captured.options.mode,'receive');assert.equal(captured.result.ready,true);assert.equal(captured.result.limited,true);
  const forecast=captured.result.recovery;assert.equal(forecast.ballTime,forecast.time-dt);assert.equal(p.action,'receive');assert.equal(m.owner,p);
  const actual=assertNextLiveContact(m,p,forecast);assert(actual.player.x*side>.5);
  if(ordinary)assert.deepEqual(forecast,ordinary,'an obsolete pass animation must not freeze the receiving forecast');else ordinary=forecast;
 }
});
for(const side of [1,-1])test(`a live setup impulse predicts the prepared strike after its ball integration (${side})`,()=>{
 for(const situation of [{speed:0,yaw:.8,ballX:.8},{speed:2,yaw:0,ballX:-.7},{speed:6,yaw:Math.PI,ballX:.8}]){
  const {m,p}=fixture({side,speed:situation.speed,yaw:situation.yaw,ballSpeed:0});m.ball.x=situation.ballX*side;
  assert(m.startKick(p,'pass',null,{...p.carryTarget}));let captured;const query=m.touchPlan;
  // A projection owns one setup impulse. Suppress subsequent setup/release
  // impulses while keeping the ordinary kick movement, turn and free roll.
  m.touchPlan=function(actor,candidate,options){if(captured)return {ready:false};const result=query.call(this,actor,candidate,options);if(result.ready)captured={result,options};return result;};
  m.release=()=>false;
  for(let i=0;i<60&&!captured&&m.kick;i++)m.step(dt);
  assert(captured);assert.equal(captured.options.mode,'setup');const forecast=captured.result.recovery;
  assert.equal(forecast.ballTime,forecast.time+dt);
  for(let i=0;i<Math.round(forecast.time*60);i++)m.step(dt);
  assert(m.kick);assert.deepEqual(pose(p),forecast.player);assert.deepEqual(m.ball,forecast.ball);assert.equal(m.touchContact(p,m.ball,p.kickFoot).ready,true);
  delete m.touchPlan;delete m.release;
 }
});
test('fractional and almost-expired contact clocks select the same available live frame',()=>{
 for(const interval of [Number.EPSILON,dt-1e-12,dt,dt+1e-12,.2,.3416,.44000000000000006]){
  const {m,p}=fixture({speed:0,ballSpeed:0});
  // Place an isolated query at the same pre-ball phase as a carry impulse.
  const candidate={vx:.3,vy:0,vz:0},forecast=m.touchRecovery(p,candidate,{interval,target:p.carryTarget});
  assert.equal(forecast.ready,true);assert(forecast.time>=dt);assert(forecast.time<=interval+dt);
  Object.assign(m.ball,candidate);p.touchClock=interval;m.integrateBall(dt);
  assertNextLiveContact(m,p,forecast);
 }
 for(const clock of ['touchClock','receiveClock']){
  const {m,p}=fixture({speed:0,ballSpeed:0});p[clock]=Number.EPSILON;const before={...m.ball};
  assert.equal(m.touchPlan(p,{vx:1,vy:0,vz:0},{interval:.2,target:p.carryTarget}).ready,false);
  assert.equal(m.dribbleTouch(p),false);assert.deepEqual(m.ball,before);
 }
});
for(const side of [1,-1])test(`a pass setup uses the selected boot recovery independently of the carrying cadence (${side})`,()=>{
 for(const state of [{dribbleFoot:1,footTouch:.14,busy:true},{dribbleFoot:0,footTouch:.14,busy:false},{dribbleFoot:1,footTouch:0,busy:false}]){
  const {m,p}=fixture({side,speed:0,ballSpeed:0});m.ball.vx=0;Object.assign(p,{touchClock:.4,dribbleFoot:state.dribbleFoot,footTouch:state.footTouch});
  assert(m.startKick(p,'pass',null,{...p.carryTarget}));assert.equal(p.kickFoot,1);
  const contact=m.touchContact(p,m.ball,p.kickFoot);assert.equal(contact.footClock,state.busy?.14:0);
  const options={mode:'setup',interval:dt,target:p.carryTarget},before={...m.ball};
  assert.equal(m.touchRecovery(p,{vx:0,vy:0,vz:0},options).ready,!state.busy);
  const direct=m.touchPlan(p,{vx:.5*side,vy:0,vz:0},{...options,interval:.18});
  assert.equal(direct.ready,!state.busy);if(state.busy)assert.equal(direct.reason,'foot-clock');assert.deepEqual(m.ball,before);
  m.step(dt);assert.equal(m.kick.setupImpulse,!state.busy);assert(p.touchClock>0);
  if(state.busy){
   for(let i=0;i<7;i++){assert(p.footTouch>0);assert.deepEqual(m.ball,before);m.step(dt);assert.equal(m.kick.setupImpulse,false);}
   for(let i=0;i<4&&!m.kick.setupImpulse;i++)m.step(dt);
   assert.equal(p.footTouch,0);assert.equal(m.kick.setupImpulse,true);assert(p.touchClock>0);
  }else{
   assert(m.ball.vx*side>0);if(state.footTouch)assert(p.footTouch>0,'the opposite boot remains in its carrying follow-through');
  }
  assert.equal(m.owner,p);assert.equal(m.touchContact(p,m.ball,p.kickFoot).footClock,0);
 }
});
test('a physically deferred first-control exit clears its stale quick-return hint',()=>{
 for(const side of [1,-1]){
  const {m,p,from}=reception(side),hint={kind:'pass',qId:from.id,point:{x:from.x,z:from.z},until:11};
  p.nextAction={...hint};p.oneTouchUntil=11;p.reception.next={...hint};m.ballStep(dt);
  assert.equal(m.owner,p);assert.equal(p.receiveMode,'cushion');assert.equal(m.telemetry.firstControlChecks,1);assert.equal(m.telemetry.touchDeferrals,1);
  assert.equal(m.telemetry.cushionedReceives,undefined,'the current front foot is available; next-contact recovery causes this deferral');
  assert.equal(p.nextAction,null);assert.equal(p.oneTouchUntil,0);assert.equal(m.preparedChoice(p),null);assert.equal(m.kick,null);
 }
});
test('the actual quick-pass strike waits for its selected boot, while a free opposite boot keeps the quick release',()=>{
 for(const side of [1,-1])for(const dribbleFoot of [0,1]){
  const {m,p}=fixture({side,speed:0,ballSpeed:0});Object.assign(m.ball,{x:.88*side,z:.18*side,vx:0});
  Object.assign(p,{dribbleFoot,footTouch:.14,touchClock:.4,oneTouchUntil:11});assert(m.startKick(p,'pass',null,{...p.carryTarget}));
  assert.equal(p.kickFoot,1);assert.equal(m.kick.oneTouch,true);let actual;const release=m.release;
  m.release=function(){
   const before={...this.ball},foot=this.contactPoint(p,'pass');actual={time:this.time-10,selectedClock:this.touchContact(p,this.ball,p.kickFoot).footClock,cadence:p.touchClock,otherClock:p.footTouch};
   assert.equal(actual.selectedClock,0,'the final outgoing impulse also needs an available selected boot');assert(Math.hypot(foot[0]-before.x,foot[2]-before.z)<.11);
   const result=release.call(this);assert.equal(this.ball.x,before.x);assert.equal(this.ball.z,before.z);return result;
  };
  for(let i=0;i<24&&!actual;i++)m.step(dt);
  assert(actual);assert(actual.cadence>0);assert.equal(m.flight.kind,'pass');
  if(dribbleFoot===1){assert(actual.time>=.14);assert.equal(actual.otherClock,0);}else{assert(actual.time<.14);assert(actual.otherClock>0);}
 }
});
test('an airborne ball aligned with the boot in plan view cannot trigger an early ground-pass release',()=>{
 for(const side of [1,-1]){
  const {m,p}=fixture({side,speed:0,ballSpeed:0});Object.assign(m.ball,{x:.88*side,z:.18*side,vx:0,y:.8,vy:1});
  assert(m.startKick(p,'pass',null,{...p.carryTarget}));let actual;const release=m.release;
  m.release=function(){actual={height:this.ball.y,time:this.time-10};assert(actual.height<.45);return release.call(this);};
  for(let i=0;i<12;i++){
   const expected=BallPhysics.predict(m.ball,dt);m.step(dt);assert.equal(actual,undefined);assert(m.kick);assert.deepEqual(m.ball,expected);
  }
  assert(m.ball.y>.45);assert.equal(m.kick.setupImpulse,false);
  for(let i=0;i<48&&!actual;i++)m.step(dt);
  assert(actual);assert(actual.time>.2);assert.equal(m.flight.kind,'pass');assert.equal(m.owner,null);
 }
});
