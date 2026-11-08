'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto'),Module=require('node:module');
const {Match,BallPhysics,distance}=require('../football-sim');
const source=zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'../docs/validation/baselines/stage5-football-sim.js.gz')));
assert.equal(crypto.createHash('sha256').update(source).digest('hex'),'7038778922feb9f8f24389003b5ddf92fb8c0790280af84ae9818a04198acf60');
const oldModule=new Module(path.join(__dirname,'../reception-facing-stage5.js'),module);oldModule.filename=path.join(__dirname,'../reception-facing-stage5.js');oldModule.paths=module.paths;oldModule._compile(source.toString(),oldModule.filename);
const OldMatch=oldModule.exports.Match,dt=1/60,angle=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
function fixture({side=1,start=-5.5,speed=9,face=0,mode='protect'}={}){
 const m=new Match({seed:21});m.restart=null;m.kick=null;m.owner=null;m.time=10;m.players.forEach(p=>p.active=false);
 const q=m.players[1],from=m.players[3];
 Object.assign(q,{active:true,x:0,z:0,vx:0,vz:0,speed:0,face:face+(side<0?Math.PI:0),skill:82,passing:82,vision:82,dribbling:82,agility:82,energy:1,stamina:92,touchClock:0,receiveClock:0,duelRecovery:0,holdClock:0,feintReaction:0,action:'idle',actionClock:0});
 Object.assign(from,{active:true,x:-12*side,z:8*side,vx:0,vz:0,speed:0});
 m.ball={x:start*side,y:BallPhysics.radius,z:0,vx:speed*side,vy:0,vz:0};
 m.flight={id:7,kind:'pass',from,target:q,age:0,point:{x:0,z:0},offsidePlayers:[]};m.lastTouch=from;m.lastTeam=q.team;
 q.reception={flightId:7,fromId:from.id,refreshAt:10.2,at:10,mode,point:{x:4*side,z:3*side},face:side<0?Math.PI:0,next:mode==='one-touch'?{kind:'pass',qId:from.id,point:{x:from.x,z:from.z}}:null};
 return {m,q,from,target:{x:q.x,z:q.z,state:'receive-run',pace:1.13}};
}
function clone(m,Engine=Match){return Object.assign(Object.create(Engine.prototype),structuredClone(m));}
function receive(f){
 const {m,q,target}=f,initialBall={...m.ball},initialTime=m.time;let largestTurn=0,steps=0;
 while(!m.owner&&steps<60){
  const previous=q.face;m.time+=dt;m.move(q,target,dt);largestTurn=Math.max(largestTurn,Math.abs(angle(q.face,previous)));m.ballStep(dt);steps++;
 }
 assert.equal(m.owner,q,'the existing physical interception must actually acquire the pass');
 const untouched=BallPhysics.predict(initialBall,m.time-initialTime);
 assert(Math.abs(m.ball.x-untouched.x)<1e-10&&Math.abs(m.ball.z-untouched.z)<1e-10,'acquisition must not relocate the ball');
 assert(largestTurn<=4.5*dt+1e-12,'preparation must obey the existing angular speed');
 return {steps,largestTurn};
}
for(const side of [1,-1])test(`preparation keeps the incoming ground ball in front without overwriting the outlet (${side})`,()=>{
 const {m,q}=fixture({side}),outlet=q.reception.face,incoming=Math.atan2(m.ball.z-q.z,m.ball.x-q.x),body=m.receptionFacing(q);
 assert(Math.abs(angle(body,incoming))<=Math.PI/3+1e-12);assert(Math.abs(angle(body,outlet))>2);
 assert.equal(q.reception.face,outlet);assert.equal(m.owner,null);assert.equal(m.telemetry.directedTouches,0);
});
for(const side of [1,-1])test(`enough real preparation time changes a rear swept reception into an open-foot control (${side})`,()=>{
 const current=fixture({side}),old=clone(current.m,OldMatch),prior={m:old,q:old.players[current.q.id],target:current.target};
 const a=receive(current),b=receive(prior);
 assert.equal(a.steps,b.steps);assert.equal(prior.q.receiveMode,'cushion');assert.notEqual(current.q.receiveMode,'cushion');
 assert.equal(old.telemetry.directedTouches,0);assert.equal(current.m.telemetry.directedTouches,1);
 assert.deepEqual({x:current.q.x,z:current.q.z},{x:0,z:0});assert.equal(current.m.completed[0],1);assert.equal(old.completed[0],1);
});
for(const side of [1,-1])test(`late preparation cannot bypass the first-control foot gate (${side})`,()=>{
 const f=fixture({side,start:-1.7,mode:'one-touch'});receive(f);
 assert.equal(f.q.receiveMode,'cushion');assert.equal(f.q.nextAction,null);assert.equal(f.q.oneTouchUntil,0);
 assert.equal(f.m.telemetry.directedTouches,0);assert.equal(f.m.telemetry.firstControlDeferrals,1);assert(f.q.receiveClock>.045);
});
test('a physically prepared quick continuation remains an intention requiring a later kick',()=>{
 const f=fixture({mode:'one-touch'});receive(f);
 assert.equal(f.q.receiveMode,'one-touch');assert.equal(f.q.nextAction.qId,f.from.id);assert.equal(f.q.receiveClock,.045);
 assert.equal(f.m.kick,null);assert.equal(f.m.passes[0],0);assert.equal(f.m.telemetry.directedTouches,0);
});
test('the prepared continuation releases only after normal windup and actual foot contact',()=>{
 const {m,q,...rest}=fixture({mode:'one-touch'});receive({m,q,...rest});
 const acquisition=m.time,release=m.release;let observed=null,startedAt=null;
 m.release=function(...args){
  const k=this.kick,foot=this.contactPoint(k.p,k.kind),heading=Math.atan2(k.point.z-k.p.z,k.point.x-k.p.x);
  observed={time:this.time,clock:k.clock,duration:k.duration,gap:Math.hypot(foot[0]-this.ball.x,foot[2]-this.ball.z),turn:Math.abs(angle(heading,k.p.face)),kind:k.kind,oneTouch:k.oneTouch};
  return release.apply(this,args);
 };
 for(let i=0;i<120&&!observed;i++){m.step(dt);if(m.kick&&startedAt===null)startedAt=m.time;}
 assert(observed,'the ordinary owner decision and preparation must produce an actual release');
 assert(startedAt>=acquisition+.045-1e-8);assert(observed.time>startedAt);assert(observed.clock+1e-9>=observed.duration);
 assert(observed.gap<.11);assert(observed.turn<.07);assert.equal(observed.kind,'pass');assert.equal(observed.oneTouch,true);assert.equal(m.passes[0],1);
});
test('an outlet already open toward a nearby arriving ball preserves the stage5 movement exactly',()=>{
 const {m,q,target}=fixture();m.ball.x=1.5;m.ball.vx=-9;q.reception.face=.3;
 const old=clone(m,OldMatch);assert.equal(m.receptionFacing(q),.3);
 for(let i=0;i<8;i++){m.move(q,target,dt);old.move(old.players[q.id],target,dt);}
 assert.deepEqual(structuredClone(m),structuredClone(old));
});
test('a ground cutback receives the same incoming-facing preparation',()=>{
 const {m,q}=fixture();m.flight.kind='cutback';const incoming=Math.atan2(m.ball.z-q.z,m.ball.x-q.x);
 assert(Math.abs(angle(m.receptionFacing(q),incoming))<=Math.PI/3+1e-12);
});
test('a ground through pass prepares the receiver with the same physical turning limit',()=>{
 for(const side of [1,-1]){
  const f=fixture({side});f.m.flight.kind='through';const outlet=f.q.reception.face,incoming=Math.atan2(f.m.ball.z-f.q.z,f.m.ball.x-f.q.x);
  assert(Math.abs(angle(f.m.receptionFacing(f.q),incoming))<=Math.PI/3+1e-12);assert.equal(f.q.reception.face,outlet);
  const old=clone(f.m,OldMatch),prior={m:old,q:old.players[f.q.id],target:f.target};
  assert.equal(receive(f).steps,receive(prior).steps);assert(Math.abs(angle(f.q.face,prior.q.face))>1);assert.equal(f.m.completed[0],1);
 }
});
test('a distant receiver keeps travelling until the arriving ball needs preparation',()=>{
 const {m,q,target}=fixture({start:-15});q.reception.face=Math.PI/2;target.x=8;q.vx=3;q.speed=3;
 const control=clone(m),actor=control.players[q.id];actor.reception=null;
 assert.equal(m.receptionFacing(q,0),0);m.move(q,target,dt);control.move(actor,target,dt);
 for(const key of ['x','z','vx','vz','face','energy','stamina'])assert.equal(q[key],actor[key],key);
 assert.equal(q.reception.face,Math.PI/2);
});
test('a rapidly closing ground ball prompts preparation before entering the near-ball radius',()=>{
 const slow=fixture({start:-8,speed:3}),fast=fixture({start:-8,speed:24}),travel=.25;
 assert.equal(slow.m.receptionFacing(slow.q,travel),travel);
 const incoming=Math.atan2(fast.m.ball.z-fast.q.z,fast.m.ball.x-fast.q.x),body=fast.m.receptionFacing(fast.q,travel);
 assert(Math.abs(angle(body,incoming))<=Math.PI/3+1e-12);assert(Math.abs(angle(body,travel))>1);
 assert.equal(fast.q.reception.face,0);assert.equal(fast.q.face,0);
});
test('expired and future-dated preparation cannot turn the body toward the arriving ball',()=>{
 for(const at of [0,.551]){
  const {m,q}=fixture({start:-1.7});m.time=.55;q.reception.at=at;q.reception.face=.2;
  const before=structuredClone(m);assert.equal(m.receptionFacing(q,-.4),.2);assert.deepEqual(structuredClone(m),before);
 }
 const {m,q}=fixture({start:-1.7});q.reception.at=m.time-.54;q.reception.face=.2;
 assert(Math.abs(angle(m.receptionFacing(q),q.reception.face))>1);
});
test('aerial, goalkeeper, stale, foreign and dead-ball paths retain stage5 movement',()=>{
 for(const variant of ['cross','long-pass','shot','high','rising','keeper','inactive','untargeted','foreign','wrong-flight','stale','restart','kick-restart','no-flight','unprepared']){
  const {m,q,from,target}=fixture();
  if(['cross','long-pass','shot'].includes(variant))m.flight.kind=variant;
  if(variant==='high')m.ball.y=.8;if(variant==='rising')m.ball.vy=.5;if(variant==='keeper')q.role='GK';if(variant==='inactive')q.active=false;
  if(variant==='untargeted')m.flight.target=from;if(variant==='foreign')m.flight.from=m.players[14];if(variant==='wrong-flight')q.reception.flightId=8;
  if(variant==='stale')q.reception.at=9;if(variant==='restart')m.restart={kind:'throw',team:0,spot:{x:0,z:0}};
  if(variant==='kick-restart')m.kick={p:from,restartContext:{kind:'throw',team:0,spot:{x:0,z:0}}};if(variant==='no-flight')m.flight=null;if(variant==='unprepared')q.reception=null;
  const old=clone(m,OldMatch);m.move(q,target,dt);old.move(old.players[q.id],target,dt);
  assert.deepEqual(structuredClone(m),structuredClone(old),variant);
 }
});
test('the facing query reads neither hidden opponent commands nor RNG and changes no match state',()=>{
 const {m,q}=fixture(),before=structuredClone(m),rival=m.players[14],hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden rival command');}});
 m.targets.set(rival,hidden);m.random=()=>{throw Error('RNG');};m.plan=()=>{throw Error('future tactical plan');};
 m.receptionFacing(q);m.targets.delete(rival);delete m.random;delete m.plan;assert.deepEqual(structuredClone(m),before);
});
test('the projected receiving run matches ordinary movement, including preparation expiry',()=>{
 for(const seconds of [.3,.7]){
  const {m,q,target}=fixture();target.x=-2;target.z=2;q.vx=-1;q.vz=.5;q.speed=Math.hypot(q.vx,q.vz);
  const before=structuredClone(m),result=m.projectPlayer(q,seconds,target,2.4),replay=clone(m),actor=replay.players[q.id],initialBall={...m.ball};
  let elapsed=0;while(elapsed<seconds-1e-9){const step=Math.min(dt,seconds-elapsed);replay.ball=BallPhysics.predict(initialBall,elapsed);elapsed+=step;replay.time=m.time+elapsed;
   for(const key of ['duelRecovery','feintReaction','receiveClock','holdClock'])actor[key]=Math.max(0,(actor[key]||0)-step);
   if(actor.actionClock>0){actor.actionClock=Math.max(0,actor.actionClock-step);actor.actionElapsed+=step;if(!actor.actionClock)actor.action='idle';}
   replay.move(actor,target,step);
  }
  for(const key of ['x','z','vx','vz','face','energy','stamina'])assert(Math.abs(result.player[key]-actor[key])<1e-10,`${seconds}/${key}`);
  assert.deepEqual(structuredClone(m),before);
 }
});
test('projecting the preparation remains isolated from rival commands, future plans and RNG',()=>{
 const {m,q,target}=fixture(),before=structuredClone(m),rival=m.players[14],hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden rival command');}});
 m.targets.set(rival,hidden);m.random=()=>{throw Error('RNG');};m.plan=()=>{throw Error('future tactical plan');};
 m.projectPlayer(q,.4,target);m.targets.delete(rival);delete m.random;delete m.plan;assert.deepEqual(structuredClone(m),before);
});
test('preparation leaves the released ball under independent BallPhysics',()=>{
 const {m,q,target}=fixture(),expected=BallPhysics.predict(m.ball,.25),start={x:q.x,z:q.z};
 m.receptionFacing(q);m.projectPlayer(q,.4,target);m.integrateBall(.25);assert.deepEqual(m.ball,expected);assert.equal(distance(q,start),0);assert.equal(m.owner,null);
});
test('a defender on the actual incoming path still intercepts before the prepared receiver',()=>{
 const {m,q}=fixture({start:-1.7,mode:'one-touch'}),d=m.players[14];Object.assign(d,{active:true,x:-1.8,z:.05,vx:0,vz:0,speed:0,face:0,touchClock:0,duelRecovery:0});
 m.ballStep(dt);assert.equal(m.owner,d);assert.notEqual(m.owner,q);assert.equal(m.completed[0],0);assert.equal(m.telemetry.directedTouches,0);
});
