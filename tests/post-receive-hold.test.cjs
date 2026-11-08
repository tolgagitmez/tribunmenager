'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto'),Module=require('node:module');
const {Match,BallPhysics,distance}=require('../football-sim');
const source=zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'../docs/validation/baselines/stage6-football-sim.js.gz')));
assert.equal(crypto.createHash('sha256').update(source).digest('hex'),'108d47253d775de6638460d5fa90dd6bbe2ab2e1e066b581e17591350c4917b6');
const oldModule=new Module(path.join(__dirname,'../post-receive-hold-stage6.js'),module);oldModule.filename=path.join(__dirname,'../post-receive-hold-stage6.js');oldModule.paths=module.paths;oldModule._compile(source.toString(),oldModule.filename);
const OldMatch=oldModule.exports.Match,dt=1/60;
function fixture(side=1){
 const m=new Match({seed:21});m.restart=null;m.kick=null;m.time=10;m.planClock=100;m.players.forEach(q=>q.active=false);
 const p=m.players[3],d=m.players[14],target={x:5*side,z:0};
 Object.assign(p,{active:true,x:0,z:0,vx:3*side,vz:0,speed:3,face:side>0?0:Math.PI,touchClock:0,receiveClock:0,duelRecovery:0,action:'idle',actionClock:0,receiveMode:'protect',carryTime:.5,decision:0,carryTarget:target,carryIntent:{until:11,point:{...target}},energy:1,stamina:92});
 Object.assign(d,{active:true,x:-2*side,z:.2*side,vx:4*side,vz:0,speed:4,face:side>0?0:Math.PI,tackleClock:0,duelRecovery:0,touchClock:0,action:'idle',actionClock:0});
 m.owner=p;m.lastTouch=p;m.lastTeam=p.team;m.ball={x:.8*side,y:.11,z:.1*side,vx:2*side,vy:0,vz:0};m.lastGain={player:p.id,team:p.team,time:9.5,x:0,z:0};
 m.targets=new Map([[p,{...target,state:'dribble',pace:.98}],[d,{x:20*side,z:.2*side,state:'press',pace:.94}]]);
 return {m,p,d,choice:{kind:'carry',point:{x:-2*side,z:0},hold:true}};
}
function clone(m,Engine=Match){return Object.assign(Object.create(Engine.prototype),structuredClone(m));}
for(const side of [1,-1])test(`an exposed reversing hold retains a physically available carrying run (${side})`,()=>{
 const {m,p,choice}=fixture(side),requested=m.controlPreparation(p,choice,null,.75),result=m.postReceiveHold(p,choice);
 const continuation=m.controlPreparation(p,result,null,.75);
 assert(requested.interventionTime>0&&requested.interventionTime<.75);
 assert.equal(continuation.interventionTime,null);assert(continuation.firstTouchTime>0);
 assert.notEqual(result,choice);assert.equal(result.kind,'carry');assert.equal(result.holdContinuation,true);assert.equal(result.hold,undefined);assert.deepEqual(result.point,p.carryTarget);
});
test('a safe nearby hold keeps the original choice and its timing intention',()=>{
 const {m,p,d,choice}=fixture();Object.assign(d,{x:0,z:4,vx:0,vz:0,speed:0,face:-Math.PI/2});
 assert.equal(m.controlPreparation(p,choice,null,.75).interventionTime,null);
 assert.equal(m.postReceiveHold(p,choice),choice);assert.equal(choice.hold,true);
});
test('a continuation also exposed to a reachable intervention is not blindly retained',()=>{
 const {m,p,d,choice}=fixture();Object.assign(d,{x:.95,z:.3,vx:-1,vz:0,speed:1,face:Math.PI});
 const requested=m.controlPreparation(p,choice,null,.75),retained=m.controlPreparation(p,{kind:'carry',point:p.carryTarget},null,.75);
 assert.notEqual(requested.interventionTime,null);assert.notEqual(retained.interventionTime,null);
 assert.equal(m.postReceiveHold(p,choice),choice);
});
test('a carrying run without an observed first touch is not treated as a proven recovery',()=>{
 const {m,p,d,choice}=fixture();p.touchClock=1;m.ball.vx=-2;Object.assign(d,{x:-1,z:-1.5,vx:0,vz:2,speed:2,face:Math.PI/2});
 assert.notEqual(m.controlPreparation(p,choice,null,.75).interventionTime,null);
 const forecast=m.controlPreparation(p,{kind:'carry',point:p.carryTarget},null,.75);
 assert.equal(forecast.interventionTime,null);assert.equal(forecast.firstTouchTime,null);assert.equal(m.postReceiveHold(p,choice),choice);
});
test('expired, missing and inapplicable reception/intent paths do not run a forecast',()=>{
 for(const variant of ['not-owner','inactive','goalkeeper','restart','kick','other-gain','future-gain','old-gain','settle','cushion','one-touch','receiving','expired-intent','missing-intent','near-target','invalid-target','high-ball','far-ball']){
  const {m,p,choice}=fixture();
  if(variant==='not-owner')m.owner=null;if(variant==='inactive')p.active=false;if(variant==='goalkeeper')p.role='GK';
  if(variant==='restart')m.restart={kind:'throw'};if(variant==='kick')m.kick={p};if(variant==='other-gain')m.lastGain.player=14;
  if(variant==='future-gain')m.lastGain.time=11;if(variant==='old-gain')m.lastGain.time=8;
  if(['settle','cushion','one-touch'].includes(variant))p.receiveMode=variant;if(variant==='receiving')p.receiveClock=.1;
  if(variant==='expired-intent')p.carryIntent.until=9;if(variant==='missing-intent')p.carryIntent=null;
  if(variant==='near-target')p.carryTarget={x:.3,z:0};if(variant==='invalid-target')p.carryTarget={x:NaN,z:0};
  if(variant==='high-ball')m.ball.y=.6;if(variant==='far-ball')m.ball.x=2;
  m.controlPreparation=()=>{throw Error('out-of-scope forecast: '+variant);};assert.equal(m.postReceiveHold(p,choice),choice,variant);
 }
});
test('passes, shots, feints and ordinary carries preserve the selected decision',()=>{
 const {m,p}=fixture();m.controlPreparation=()=>{throw Error('not a reversing hold');};
 for(const kind of ['pass','shot','feint','carry']){
  const choice={kind,point:{x:-2,z:0},...(kind==='carry'?{}:{hold:true})};assert.equal(m.postReceiveHold(p,choice),choice);
 }
});
test('a slow player or a hold already aligned with momentum retains the original decision',()=>{
 for(const variant of ['slow','aligned']){
  const {m,p,choice}=fixture();if(variant==='slow'){p.vx=.4;p.speed=.4;}else choice.point={x:2,z:0};
  m.controlPreparation=()=>{throw Error('no abrupt reversal');};assert.equal(m.postReceiveHold(p,choice),choice);
 }
});
test('a distant departing opponent does not trigger an unnecessary forecast',()=>{
 const {m,p,d,choice}=fixture();Object.assign(d,{x:9,z:0,vx:6,vz:0,speed:6});
 m.controlPreparation=()=>{throw Error('no approaching pressure');};assert.equal(m.postReceiveHold(p,choice),choice);
});
test('the real comparison cannot consume RNG, read rival commands, plan ahead or mutate match state',()=>{
 const {m,p,d,choice}=fixture(),before=structuredClone(m),hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden opponent command');}});
 m.targets.set(d,hidden);m.random=()=>{throw Error('RNG');};m.plan=()=>{throw Error('future tactical plan');};
 const result=m.postReceiveHold(p,choice);assert.equal(result.holdContinuation,true);
 m.targets.set(d,before.targets.get(before.players[d.id]));delete m.random;delete m.plan;assert.deepEqual(structuredClone(m),before);
});
test('the retained point is a value copy and cannot mutate the current carrying intention',()=>{
 const {m,p,choice}=fixture(),point={...p.carryTarget},result=m.postReceiveHold(p,choice);
 assert.notEqual(result.point,p.carryTarget);result.point.x+=10;assert.deepEqual(p.carryTarget,point);assert.deepEqual(p.carryIntent.point,point);
});
for(const side of [1,-1])test(`the ordinary owner step applies the retained intention through unchanged movement and ball physics (${side})`,()=>{
 const {m,p,choice}=fixture(side);const Perception=require('../player-perception'),face=p.face;p.face+=Math.PI;Perception.update(m.players,m.time,0,{scanAllowed:false});p.face=face;
 const expected=clone(m,OldMatch),old=clone(m,OldMatch),before={x:p.x,z:p.z},retained=m.postReceiveHold(p,choice);
 assert.equal(retained.holdContinuation,true);
 m.choose=()=>choice;expected.choose=()=>retained;old.choose=()=>choice;
 m.step(dt);expected.step(dt);old.step(dt);
 assert.equal(m.telemetry.holdContinuations,1);assert(p.carryTarget.x*side>0);assert.equal(p.settleUntil,0);
 assert(distance(p,before)<.15);assert.equal(m.owner,p);assert.equal(m.kick,null);
 assert(m.ball.vx*side>0);assert(old.ball.vx*side<0,'the unreviewed hold redirects the same physical ball backwards');
 delete m.telemetry.holdContinuations;for(const v of [m,expected,old])delete v.choose;
 const physical=value=>{const state=structuredClone(value);delete state.teamPhases;delete state._perceptionActive;delete state.telemetry.teamPhaseChanges;for(const actor of state.players){delete actor.perception;delete actor.task;delete actor.taskHistory;}return state;};
 assert.deepEqual(physical(m),physical(expected),'the observed-pressure continuation must use the exact stage6 physical path');
});
test('the pure hold review leaves released ball flight entirely under BallPhysics',()=>{
 const {m,p,choice}=fixture(),predicted=BallPhysics.predict(m.ball,.2),position={x:p.x,z:p.z};
 m.postReceiveHold(p,choice);m.integrateBall(.2);assert.deepEqual(m.ball,predicted);assert.equal(distance(p,position),0);
});
