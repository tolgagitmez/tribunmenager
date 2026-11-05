'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match,BallPhysics,distance}=require('../football-sim');
function fixture({side=1,vx=0,vz=0,face=0,energy=1,duel=0}={}){
 const m=new Match({seed:21});m.restart=null;m.owner=null;m.kick=null;m.time=10;m.players.forEach(p=>p.active=false);
 const q=m.players[1],from=m.players[3];Object.assign(q,{active:true,x:10*side,z:2*side,vx:vx*side,vz:vz*side,speed:Math.hypot(vx,vz),face:face+(side<0?Math.PI:0),energy,stamina:92,duelRecovery:duel,touchClock:0,receiveClock:0,action:'idle',actionClock:0,holdClock:0,feintReaction:0});
 Object.assign(from,{active:true,x:-5*side,z:8*side,vx:0,vz:0,speed:0});m.ball={x:0,y:.11,z:0,vx:17*side,vy:0,vz:0};m.flight={id:7,kind:'pass',from,target:q,age:0,point:{x:18*side,z:0},offsidePlayers:[]};m.lastTouch=from;m.lastTeam=0;
 return {m,q,from};
}
function replay(q,m,point){
 const c=Object.assign(Object.create(Match.prototype),structuredClone(m)),player=c.players[q.id],ball={...m.ball},dt=1/60,target={x:point.x,z:point.z,state:'receive-run',pace:1.13};
 let elapsed=0;while(elapsed<point.t-1e-9){const step=Math.min(dt,point.t-elapsed);c.ball=BallPhysics.predict(ball,elapsed);elapsed+=step;c.time+=step;
  for(const key of ['duelRecovery','feintReaction','receiveClock','holdClock'])player[key]=Math.max(0,(player[key]||0)-step);
  if(player.actionClock>0){player.actionClock=Math.max(0,player.actionClock-step);player.actionElapsed+=step;if(!player.actionClock)player.action='idle';}
  c.move(player,target,step);
 }
 return distance(player,point);
}
for(const side of [1,-1])test(`incoming pass uses acceleration/turning instead of the old optimistic reach (${side})`,()=>{
 const still=fixture({side}),away=fixture({side,vz:4.5,face:Math.PI/2}),toward=fixture({side,vz:-4.5,face:-Math.PI/2});
 const a=still.m.interceptPoint(still.q),b=away.m.interceptPoint(away.q),c=toward.m.interceptPoint(toward.q);
 // Stage3 gave all three exactly t=.5 despite different actual momentum.
 assert(a.t>.5);assert(b.t>.5);assert(c.reachable);assert(c.t>a.t-0.11);
 assert(b.gap>a.gap);assert(a.gap>c.gap);
 for(const [f,p]of [[still,a],[away,b],[toward,c]])assert(Math.abs(replay(f.q,f.m,p)-p.gap)<1e-8);
});
test('recovery and touch clocks can prevent a candidate from being declared reachable',()=>{
 const {m,q}=fixture({vz:-4.5,face:-Math.PI/2});q.touchClock=3;const p=m.interceptPoint(q);assert.equal(p.reachable,false);
 const recovering=fixture({duel:1});assert.equal(recovering.m.interceptPoint(recovering.q).reachable,false);
});
test('fatigue changes the actual projected approach without touching real attributes',()=>{
 const fresh=fixture({vz:-4.5,face:-Math.PI/2}),tired=fixture({vz:-4.5,face:-Math.PI/2,energy:.25});tired.q.stamina=45;
 for(const f of [fresh,tired]){Object.assign(f.q,{x:12,z:6,vx:0,vz:0,speed:0,face:-Math.PI/2});f.m.ball.vx=6;}
 const before={energy:tired.q.energy,stamina:tired.q.stamina},a=fresh.m.interceptPoint(fresh.q),b=tired.m.interceptPoint(tired.q);
 assert(a.t!==b.t||Math.abs(a.gap-b.gap)>.01);assert.deepEqual({energy:tired.q.energy,stamina:tired.q.stamina},before);
});
test('a failed planning margin returns a near tested approach rather than the horizon endpoint',()=>{
 const {m,q}=fixture({vz:4.5,face:Math.PI/2}),p=m.interceptPoint(q);
 assert.equal(p.reachable,false);assert(p.t<1);assert(p.x<15);assert(p.gap>.7);
});
test('prediction does not invent an interception beyond the touchline or goal line',()=>{
 for(const axis of ['x','z']){
  const {m,q}=fixture();m.ball={x:axis==='x'?51.9:0,y:.11,z:axis==='z'?33.9:0,vx:axis==='x'?17:0,vy:0,vz:axis==='z'?17:0};
  const p=m.interceptPoint(q);assert.equal(p.reachable,false);assert.equal(p.t,0);assert(Math.abs(p.x)<=52.5);assert(Math.abs(p.z)<=34.3);
 }
});
test('no live player, ball, command, clock, seed or observation is changed by the query',()=>{
 const {m,q}=fixture({vz:-4.5,face:-Math.PI/2}),before=structuredClone(m),rival=m.players[14];
 const hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('rival future command');}});m.targets.set(rival,hidden);m.plan=()=>{throw Error('future plan');};m.random=()=>{throw Error('RNG');};
 m.interceptPoint(q);m.targets.delete(rival);delete m.plan;delete m.random;assert.deepEqual(structuredClone(m),before);
});
test('defender, goalkeeper, other target, dead-ball and aerial/through paths retain the old scope',()=>{
 for(const mode of ['defender','keeper','inactive','untargeted','restart','cross','through','long-pass','shot','high','rising']){
  const {m,q}=fixture();if(mode==='defender')m.flight.from=m.players[14];if(mode==='keeper')q.role='GK';if(mode==='inactive')q.active=false;if(mode==='untargeted')m.flight.target=m.players[0];if(mode==='restart')m.restart={kind:'throw'};
  if(['cross','through','long-pass','shot'].includes(mode))m.flight.kind=mode;if(mode==='high')m.ball.y=1.5;if(mode==='rising')m.ball.vy=.5;
  assert.equal(m.interceptPoint(q).reachable,undefined,mode);
 }
});
test('old forecast horizons stay bounded while interception projection can reach 2.4 seconds',()=>{
 const {m,q}=fixture(),target={x:12,z:0,state:'receive-run',pace:1.13};
 assert.deepEqual(m.projectPlayer(q,8,target,99),m.projectPlayer(q,2.4,target,2.4));
 assert.deepEqual(m.receiverAt(q,3,target),m.projectPlayer(q,1.6,target,1.6));
 assert.deepEqual(m.passReceiverAt({p:m.players[3],target:q},3),m.receiverAt(q,.45,m.targets.get(q)));
});
test('a full planner reuses one selected receiver query for support, movement and reception',()=>{
 const {m,q}=fixture();let calls=0;const intercept=m.receiverInterceptPoint;
 m.receiverInterceptPoint=function(p){calls++;return intercept.call(this,p);};m.plan();assert.equal(calls,1);assert.equal(m.targets.get(q).state,'receive-run');
});
test('interception planning leaves released ball flight entirely governed by BallPhysics',()=>{
 const {m,q}=fixture(),future=BallPhysics.predict(m.ball,.25);m.interceptPoint(q);q.x+=10;m.interceptPoint(q);m.integrateBall(.25);
 for(const k of Object.keys(future))assert.equal(m.ball[k],future[k]);
});
