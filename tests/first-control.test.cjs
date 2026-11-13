'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto'),Module=require('node:module');
const {Match,BallPhysics,distance}=require('../football-sim');
const baselineSource=zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'../docs/validation/baselines/stage4-football-sim.js.gz')));
assert.equal(crypto.createHash('sha256').update(baselineSource).digest('hex'),'406526afd60d3d2469e4d320b4a5a801f9680ecdbc6b98de9bf8d20d1c9ab539');
const baselineModule=new Module(path.join(__dirname,'../first-control-stage4.js'),module);baselineModule.filename=path.join(__dirname,'../first-control-stage4.js');baselineModule.paths=module.paths;baselineModule._compile(baselineSource.toString(),baselineModule.filename);
const OldMatch=baselineModule.exports.Match,dt=1/60;
// Isolate control/momentum from roster tuning. 75 is the neutral runtime
// acceleration, turn and endurance profile; fitness=100 makes fatigue use the
// same stamina fraction in the archived and current movement integrators.
const physicalProfile={skill:82,passing:82,shooting:82,tackling:82,dribbling:82,pace:82,heading:82,crossing:82,vision:82,composure:82,agility:75,acceleration:75,endurance:75,strength:75,balance:75,fitness:100,stamina:92,energy:1,preferredFoot:1,footPreference:'right',weakFoot:70,goalkeeping:82,reactions:82,handling:82};
function fixture({side=1,front=false,mode='protect',speed=10,skill=82}={}){
 const m=new Match({seed:21});m.restart=null;m.owner=null;m.kick=null;m.time=10;m.players.forEach(p=>Object.assign(p,physicalProfile,{active:false}));
 const q=m.players[1],from=m.players[3];
 Object.assign(q,{active:true,x:0,z:0,vx:0,vz:0,speed:0,face:side>0?0:Math.PI,skill,dribbling:skill,passing:skill,vision:skill,touchClock:0,receiveClock:0,duelRecovery:0,action:'idle',actionClock:0});
 Object.assign(from,{active:true,x:-10*side,z:8*side,vx:0,vz:0,speed:0});
 m.ball={x:(front?.9:-.9)*side,y:.11,z:0,vx:(front?-speed:speed)*side,vy:0,vz:0};
 m.flight={id:7,kind:'pass',from,target:q,age:0,point:{x:4*side,z:3*side},offsidePlayers:[]};m.lastTouch=from;m.lastTeam=q.team;
 q.reception={flightId:7,fromId:from.id,refreshAt:10.2,at:10,mode,point:{x:4*side,z:3*side},face:Math.atan2(3*side,4*side),next:mode==='one-touch'?{kind:'pass',qId:from.id,point:{x:from.x,z:from.z}}:null};
 return {m,q,from};
}
function clone(m,Engine=Match){return Object.assign(Object.create(Engine.prototype),structuredClone(m));}
function behavior(m,q){return {ball:{...m.ball},owner:m.owner?.id,mode:q.receiveMode,receiveClock:q.receiveClock,decision:q.decision,carryTarget:q.carryTarget,nextAction:q.nextAction,oneTouchUntil:q.oneTouchUntil,directedTouches:m.telemetry.directedTouches};}
for(const side of [1,-1])test(`a real swept reception behind the body cushions without an impossible directed touch (${side})`,()=>{
 const {m,q}=fixture({side}),base=clone(m,OldMatch);base.players[q.id].reception=null;
 const expectedPosition=BallPhysics.predict(m.ball,dt),playerPosition={x:q.x,z:q.z},seed=m.seed;
 m.ballStep(dt);base.ballStep(dt);
 assert.equal(m.owner,q);assert.equal(q.receiveMode,'cushion');assert.equal(m.telemetry.cushionedReceives,1);
 assert.deepEqual(m.ball,base.ball,'the only impulse is the existing glancing cushion');
 assert.equal(m.ball.x,expectedPosition.x);assert.equal(m.ball.z,expectedPosition.z);assert.deepEqual({x:q.x,z:q.z},playerPosition);assert.equal(m.seed,seed);
 assert.equal(m.telemetry.directedTouches,0);assert(q.receiveClock>.045&&q.receiveClock<=.45);assert.equal(q.reception,null);
});
for(const side of [1,-1])test(`a prepared quick pass is deferred when its actual ground contact arrives behind the body (${side})`,()=>{
 const {m,q}=fixture({side,mode:'one-touch'});q.nextAction={kind:'pass',qId:3,until:11};q.oneTouchUntil=11;
 m.ballStep(dt);assert.equal(m.owner,q);assert.equal(q.receiveMode,'cushion');assert.equal(q.nextAction,null);assert.equal(q.oneTouchUntil,0);
 assert.equal(m.telemetry.firstControlDeferrals,1);assert(q.receiveClock>.045);assert(q.decision>=q.receiveClock);assert.equal(m.kick,null);
});
for(const side of [1,-1])test(`an open-foot reception preserves both old directed control and quick continuation (${side})`,()=>{
 for(const mode of ['protect','one-touch']){
  const {m,q}=fixture({side,front:true,mode}),old=clone(m,OldMatch);m.ballStep(dt);old.ballStep(dt);
  assert.equal(m.owner,q);assert.deepEqual(behavior(m,q),behavior(old,old.players[q.id]));assert.equal(m.telemetry.firstControlChecks,1);assert.equal(m.telemetry.cushionedReceives,undefined);
  if(mode==='one-touch'){assert.equal(q.receiveClock,.045);assert.equal(q.nextAction.qId,3);}else assert.equal(m.telemetry.directedTouches,1);
 }
});
test('through balls, cutbacks and a side-of-body swept contact use the same control restriction',()=>{
 for(const kind of ['through','cutback']){
  const {m,q}=fixture();m.flight.kind=kind;m.ballStep(dt);assert.equal(m.owner,q);assert.equal(q.receiveMode,'cushion');assert.equal(m.telemetry.directedTouches,0);
 }
 const {m,q}=fixture({mode:'one-touch'});m.ball={x:0,y:.11,z:1.05,vx:0,vy:0,vz:0};m.ballStep(dt);
 assert.equal(m.owner,q);assert.equal(q.receiveMode,'cushion');assert.equal(q.nextAction,null);assert.equal(m.telemetry.firstControlDeferrals,1);
});
test('an opponent closer to the actual incoming path still intercepts before the prepared receiver',()=>{
 const {m,q}=fixture({mode:'one-touch'}),d=m.players[14];Object.assign(d,{active:true,x:-1.2,z:.05,vx:0,vz:0,speed:0,face:0,touchClock:0,duelRecovery:0});
 m.ballStep(dt);assert.equal(m.owner,d);assert.notEqual(m.owner,q);assert.equal(m.telemetry.cushionedReceives,undefined);assert.equal(m.completed[0],0);
});
test('a receiver recovering the cushion remains exposed to an ordinary reachable tackle',()=>{
 const {m,q}=fixture();m.ballStep(dt);const d=m.players[14];Object.assign(d,{active:true,x:-1.35,z:.2,vx:0,vz:0,speed:0,face:Math.atan2(-.2,1.35),touchClock:0,duelRecovery:0,tackleClock:0});
 assert(q.receiveClock>0);assert.equal(m.tackleAccess(d,q).attempt,true);
 const duels=m.telemetry.duels;m.doTackle(d,q);assert.equal(m.telemetry.duels,duels+1);assert(d.tackleClock>1);assert(['tackle','receive'].includes(d.action));
});
test('the recovery command follows the moving physical ball, then expires with the control clock',()=>{
 const {m,q}=fixture();m.ballStep(dt);q.carryTarget={x:20,z:20};
 m.plan();let command=m.targets.get(q);assert.equal(command.state,'receive');assert.equal(command.x,m.ball.x+m.ball.vx*.12);assert.equal(command.z,m.ball.z+m.ball.vz*.12);
 m.integrateBall(.1);m.plan();command=m.targets.get(q);assert.equal(command.x,m.ball.x+m.ball.vx*.12);
 q.receiveClock=0;m.plan();command=m.targets.get(q);assert.equal(command.state,'dribble');assert.equal(command.x,20);assert.equal(command.z,20);
});
test('a recovery step turns and accelerates normally while the released cushion rolls independently',()=>{
 const {m,q}=fixture();m.ballStep(dt);const expected=BallPhysics.predict(m.ball,dt),before={x:q.x,z:q.z,face:q.face};
 m.targets=new Map([[q,{x:m.ball.x,z:m.ball.z,state:'receive',pace:.48}]]);m.planClock=1;m.step(dt);
 assert.deepEqual(m.ball,expected);assert(distance(q,before)<.01);assert(Math.abs(q.face-before.face)<=4.5*dt+1e-12);assert.notEqual(q.face,before.face);assert.equal(m.kick,null);
});
test('the foot-envelope query cannot consume RNG, run a future plan, read rival commands or mutate match state',()=>{
 const {m,q}=fixture(),before=structuredClone(m),rival=m.players[14],hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden rival command');}});
 m.targets.set(rival,hidden);m.random=()=>{throw Error('RNG');};m.plan=()=>{throw Error('future tactical plan');};
 assert.equal(m.firstControlContact(q).ready,false);m.targets.delete(rival);delete m.random;delete m.plan;assert.deepEqual(structuredClone(m),before);
});
test('aerial, goalkeeper, other recipient, unprepared and stale receptions retain the exact stage4 behavior',()=>{
 for(const variant of ['cross','long-pass','high','rising','keeper','untargeted','unprepared','stale']){
  const {m,q,from}=fixture({mode:'one-touch'});
  if(['cross','long-pass'].includes(variant))m.flight.kind=variant;
  if(variant==='high')m.ball.y=.8;if(variant==='rising')m.ball.vy=.5;if(variant==='keeper')q.role='GK';if(variant==='untargeted')m.flight.target=from;
  if(variant==='unprepared')q.reception=null;if(variant==='stale')q.reception.at=9;
  const old=clone(m,OldMatch);assert.equal(m.acquire(q),true);assert.equal(old.acquire(old.players[q.id]),true);const current=structuredClone(m),baseline=structuredClone(old);delete current.teamPhases;delete baseline.teamPhases;delete current.telemetry.teamPhaseChanges;delete baseline.telemetry.teamPhaseChanges;assert.deepEqual(current,baseline,variant);assert.equal(m.teamPhases[q.team].phase,'possession');
 }
});
test('the retained glancing cushion still responds to player technique and incoming speed',()=>{
 const skilled=fixture({skill:95,speed:18}),novice=fixture({skill:55,speed:18}),slow=fixture({skill:55,speed:8});
 for(const f of [skilled,novice,slow]){f.m.ballStep(dt);assert.equal(f.q.receiveMode,'cushion');}
 assert(Math.hypot(novice.m.ball.vx,novice.m.ball.vz)>Math.hypot(skilled.m.ball.vx,skilled.m.ball.vz));
 assert(Math.hypot(novice.m.ball.vx,novice.m.ball.vz)>Math.hypot(slow.m.ball.vx,slow.m.ball.vz));
});
