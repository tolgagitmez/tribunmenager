'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');
const {Match,BallPhysics,distance}=require('../football-sim');
function fixture({side=1,state='shape',vx=5,vz=0,x=1.5,z=0}={}){
 const m=new Match({seed:21});m.restart=null;m.time=10;m.owner=null;m.kick=null;m.players.forEach(p=>p.active=false);
 const q=m.players[1];Object.assign(q,{active:true,x:0,z:0,vx:vx*side,vz:vz*side,speed:Math.hypot(vx,vz),face:Math.atan2(vz*side,vx*side),action:'run',actionClock:0,receiveClock:0,touchClock:0,duelRecovery:0,feintReaction:0,holdClock:0});
 const target={x:x*side,z:z*side,state,pace:.88};m.targets=new Map([[q,target]]);m.ball={x:20,y:.11,z:20,vx:2,vy:0,vz:-1};
 return {m,q,target};
}
function replay(m,q,target,seconds){
 const copy=Object.assign(Object.create(Match.prototype),structuredClone(m)),p=copy.players.find(p=>p.id===q.id),original={...m.ball};let elapsed=0;
 while(elapsed<seconds-1e-9){const dt=Math.min(1/60,seconds-elapsed);copy.ball=BallPhysics.predict(original,elapsed);elapsed+=dt;copy.time+=dt;
  for(const key of ['duelRecovery','feintReaction','receiveClock','holdClock'])p[key]=Math.max(0,(p[key]||0)-dt);
  if(p.actionClock>0){p.actionClock=Math.max(0,p.actionClock-dt);p.actionElapsed+=dt;if(!p.actionClock)p.action='idle';}
  copy.move(p,target,dt);
 }
 return p;
}
for(const side of [1,-1])for(const state of ['shape','support','between-lines','wide-support','rest-defence'])test(`known ${state} braking follows real 60Hz movement (${side})`,()=>{
 const {m,q,target}=fixture({side,state});const actual=replay(m,q,target,.8),forecast=m.receiverPoint(q,.8);
 assert(distance(forecast,actual)<1e-8);assert(Math.abs(forecast.x-q.vx*.8)>.5,'braking should differ from coasting');
});
for(const side of [1,-1])test(`turn/reverse momentum uses acceleration rather than snapping (${side})`,()=>{
 const {m,q,target}=fixture({side,vx:4,vz:2,x:-.5,z:1});const actual=replay(m,q,target,.7),forecast=m.receiverPoint(q,.7);
 assert(distance(actual,forecast)<1e-8);assert(distance(forecast,target)>.05);
});
test('short near destination cannot delete a fast runner’s momentum',()=>{
 const {m,q,target}=fixture({vx:8,x:.1});const forecast=m.receiverPoint(q,.4),actual=replay(m,q,target,.4);
 assert(distance(forecast,actual)<1e-8);assert(forecast.x>1,'must physically overshoot a very close destination');
});
test('far run keeps the existing coasting estimate',()=>{
 const {m,q}=fixture({x:50,vx:4});assert.deepEqual(m.receiverPoint(q,1.2),{x:4.8,z:0});
});
test('unknown, invalid, dead-ball and inactive commands fall back without phantom movement',()=>{
 for(const state of ['unknown','invalid','missing-pace','negative-pace','restart','wall','goal','inactive']){
  const {m,q,target}=fixture();if(state==='unknown')m.targets.clear();else if(state==='invalid')target.x=NaN;else if(state==='missing-pace')delete target.pace;else if(state==='negative-pace')target.pace=-1;else if(state==='inactive')q.active=false;else target.state=state;
  assert.deepEqual(m.receiverPoint(q,.5),{x:2.5,z:0},state);
 }
});
test('receiver forecast does not mutate real players, target maps, ball, telemetry, clock or RNG',()=>{
 const {m,q}=fixture({vx:4,vz:2,x:-.5,z:1}),before=structuredClone(m);
 m.plan=()=>{throw Error('future planning');};m.random=()=>{throw Error('RNG');};
 const rival=m.players[14],hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden rival order');}});m.targets.set(rival,hidden);
 m.receiverPoint(q,.8);m.receiverAt(q,1.6,m.targets.get(q));m.targets.delete(rival);delete m.plan;delete m.random;
 assert.deepEqual(structuredClone(m),before);
});
test('a projected copy is not repelled by a duplicate of its real counterpart',()=>{
 const {m,q,target}=fixture({vx:4,vz:1,x:1,z:1});
 const actual=m.receiverAt(q,.8,target).player,fromCopy=m.receiverAt({...q},.8,target).player;
 assert.deepEqual(fromCopy,actual);
});
test('shared helper is bounded but original release-read horizon stays .45 seconds',()=>{
 const {m,q,target}=fixture();const p=m.players[3];
 assert.deepEqual(m.passReceiverAt({p,target:q},2).player,m.receiverAt(q,.45,target).player);
 assert.deepEqual(m.receiverAt(q,8,target).player,m.receiverAt(q,1.6,target).player);
 assert.deepEqual(m.receiverPoint(q,NaN),{x:q.x,z:q.z});assert.deepEqual(m.receiverPoint(q,-1),{x:q.x,z:q.z});
});
test('post-release flight ignores later receiver relocation and changed team orders',()=>{
 const {m,q,target}=fixture();m.flight={id:9,from:m.players[3],target:q,kind:'pass'};m.ball={x:0,y:.11,z:0,vx:17,vy:0,vz:2};
 const predicted=BallPhysics.predict(m.ball,.2);q.x+=20;q.z-=15;target.x=-30;target.z=-30;m.receiverPoint(q,.6);m.integrateBall(.2);
 for(const key of Object.keys(predicted))assert.equal(m.ball[key],predicted[key]);
});
function passFixture(side=1,block=false){
 const m=new Match({seed:21});m.restart=null;m.time=10;m.phase='carry';m.planClock=100;m.players.forEach(p=>p.active=false);
 const p=m.players[3],q=m.players[1],gk=m.players[21],cover=m.players[20];
 for(const a of [p,q,gk,cover])Object.assign(a,{active:true,vx:0,vz:0,speed:0,face:side===1?0:Math.PI,action:'idle',actionClock:0,touchClock:0,receiveClock:0,duelRecovery:0,tackleClock:0});
 Object.assign(p,{x:0,z:0});Object.assign(q,{x:18*side,z:-4*side,vx:.6*side,vz:4.5*side,speed:Math.hypot(.6,4.5),face:Math.atan2(4.5*side,.6*side)});Object.assign(gk,{x:49*side,z:0});Object.assign(cover,{x:40*side,z:-25*side});
 m.ball={x:.88*side,y:.11,z:.18*side,vx:0,vy:0,vz:0};m.owner=p;m.lastTeam=0;m.lastTouch=p;
 m.targets=new Map([[p,{x:0,z:0,pace:1,state:'dribble'}],[q,{x:18.5*side,z:0,pace:.88,state:'shape'}]]);
 const d=m.players[14];if(block){Object.assign(d,{active:true,x:8*side,z:0,vx:0,vz:0,speed:0,face:side===1?Math.PI:0,touchClock:0,duelRecovery:0});m.targets.set(d,{x:d.x,z:d.z,pace:0,state:'cover'});}
 const lead=m.passTime('pass',distance(p,q),m.passSpeed('pass',distance(p,q),m.t[0]));m.startKick(p,'pass',q,m.receiverPoint(q,lead));
 return {m,p,q,d};
}
for(const side of [1,-1])test(`real ordinary pass reaches a braking shape receiver with fixed known commands (${side})`,()=>{
 const {m,q}=passFixture(side);let received=false,kind=null;const acquire=m.acquire;
 m.acquire=function(p){const flight=this.flight,out=acquire.call(this,p);if(out&&p===q){received=true;kind=flight?.kind;}return out;};
 for(let i=0;i<120&&!received;i++)m.step();assert(received);assert.equal(kind,'pass');assert.equal(m.owner,q);
});
test('a physically present defender can still intercept the corrected ordinary pass',()=>{
 const {m,q,d}=passFixture(1,true);let intercepted=false;const acquire=m.acquire;
 m.acquire=function(p){const out=acquire.call(this,p);if(out&&p===d)intercepted=true;return out;};
 for(let i=0;i<120&&!intercepted;i++)m.step();assert(intercepted);assert.notEqual(m.owner,q);
});
