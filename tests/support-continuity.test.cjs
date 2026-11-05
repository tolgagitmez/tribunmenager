'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Match,BallPhysics,distance}=require('../football-sim');
function fixture(side=1){
 const m=new Match({seed:21,tactics:{passing:'short',playstyle:'possession'}});m.restart=null;m.time=10;m.planClock=0;
 for(const p of m.players){p.vx=p.vz=p.speed=0;p.duelRecovery=0;if(p.team===1){p.x=38*side;p.z=(p.index*5-25)*side;}}
 const [from,receiver,anchor,helper]=[m.players[3],m.players[5],m.players[4],m.players[0]];
 for(const [p,x,z] of [[from,-15,0],[receiver,2,8],[anchor,-14,-11],[helper,-7,13]])Object.assign(p,{x:x*side,z:z*side});
 // A synthetic fourth midfielder leaves two legitimate helpers while the
 // deepest midfielder keeps his anchor duty on the receiving side of halfway.
 Object.assign(helper,{role:'MID',homeX:0,homeZ:13*side});
 const pool=[from,receiver,anchor,helper];
 m.owner=from;m.lastTeam=0;m.lastTouch=from;m.ball={x:-14*side,y:.11,z:0,vx:15*side,vy:0,vz:6*side};
 m.supportUnit(0,from,pool,anchor,null,null,null,null,38);
 m.owner=null;m.flight={id:7,from,target:receiver,kind:'pass',age:.3,point:{x:2*side,z:8*side}};
 m.ball={x:-5*side,y:.11,z:5*side,vx:15*side,vy:0,vz:6*side};
 return {m,from,receiver,anchor,helper,pool,side};
}
function allocate(f){return f.m.supportUnit(0,null,f.pool,f.anchor,null,null,null,null,38);}
for(const side of [1,-1])test(`flight supports focus the receiver without granting possession (${side})`,()=>{
 const f=fixture(side),{m,receiver,anchor}=f,before={ball:{...m.ball},seed:m.seed,players:m.players.map(p=>[p.x,p.z,p.vx,p.vz])};
 const points=allocate(f);assert.equal(m.supportPlans[0].ownerId,receiver.id);assert.equal(points.size,2);
 assert(!points.has(receiver.id));assert(!points.has(anchor.id));assert(m.supportPlans[0].arrival.lead<=1.2);
 assert.equal(m.owner,null);assert.equal(m.flight.target,receiver);
 assert.deepEqual({ball:m.ball,seed:m.seed,players:m.players.map(p=>[p.x,p.z,p.vx,p.vz])},before);
});
test('arrival plan is renewed beyond old passer-plan lifetime and can start without an old plan',()=>{
 const f=fixture();f.m.time=11.31;assert(allocate(f).size>0);assert(f.m.supportPlans[0].until>11.31);
 f.m.supportPlans[0]=null;assert(allocate(f).size>0);assert.equal(f.m.supportPlans[0].ownerId,f.receiver.id);
});
test('reservations for an existing runner are preserved',()=>{
 const f=fixture();f.helper.runIntent={point:{x:12,z:20},until:12,epoch:f.m.attackEpoch[0]};
 assert(!allocate(f).has(f.helper.id));assert.deepEqual(f.helper.runIntent.point,{x:12,z:20});
});
test('same recipient keeps helper identities through a real reception handoff',()=>{
 const f=fixture(),before=allocate(f),{m,receiver}=f;
 const ids=[...before.keys()];m.ball={...m.ball,x:receiver.x+.2,z:receiver.z,vx:1,vz:0};
 assert.equal(m.acquire(receiver),true);const after=m.supportUnit(0,receiver,f.pool,f.anchor,null,null,null,null,38);
 assert.deepEqual([...after.keys()],ids);assert.equal(m.supportPlans[0].arrival,null);assert.equal(m.telemetry.arrivalSupportHandoffs,1);
});
test('interception invalidates receiving plans and all stale offers',()=>{
 const f=fixture();allocate(f);const rival=f.m.players[14];assert(f.m.acquire(rival));
 assert.equal(f.m.supportPlans[0],null);assert(f.m.players.every(p=>!p.offerIntent));
});
test('inactive, opposite-team, untargeted and inappropriate flights do not get arrival support',()=>{
 for(const kind of ['inactive','rival','untargeted','shot','expired','high','late']){
  const f=fixture();if(kind==='inactive')f.receiver.active=false;
  if(kind==='rival')f.m.flight.from=f.m.players[14];if(kind==='untargeted')f.m.flight.target=null;
  if(kind==='shot')f.m.flight.kind='shot';if(kind==='expired')f.m.flight.age=2.5;
  if(kind==='high')f.m.ball.y=4;if(kind==='late'){f.m.ball.x=-45;f.m.ball.vx=2;}
  assert.equal(allocate(f).size,0,kind);assert.equal(f.m.supportPlans[0],null,kind);
 }
});
test('new intended recipient replaces old ownership key and invalidates old offers for that owner',()=>{
 const f=fixture();allocate(f);Object.assign(f.helper,{x:1,z:6});f.m.flight.target=f.helper;allocate(f);assert.equal(f.m.supportPlans[0].ownerId,f.helper.id);
 assert(!f.m.supportPlans[0].points.has(f.helper.id));assert(f.pool.every(p=>p.offerIntent?.ownerId!==f.receiver.id));
});
test('reception refresh reads newly issued own-team targets and leaves real ball flight untouched',()=>{
 const f=fixture(),{m,receiver}=f;let calls=0;const prepare=m.prepareReception;
 m.prepareReception=function(p){calls++;assert.equal(p,receiver);assert.equal(this.targets.get(receiver).state,'receive-run');assert.equal(this.supportPlans[0].ownerId,receiver.id);return prepare.call(this,p);};
 const before={...m.ball},seed=m.seed;m.plan();assert.equal(calls,1);assert.deepEqual(m.ball,before);assert.equal(m.seed,seed);
 const expected=BallPhysics.predict(before,1/60);m.integrateBall(1/60);for(const key of Object.keys(expected))assert.equal(m.ball[key],expected[key]);
});
test('planned helper destinations obey offside and field limits',()=>{
 const f=fixture();for(const point of allocate(f).values()){assert(point.x<=37.3);assert(Math.abs(point.z)<=30);assert(Math.abs(point.x)<=48);}
});
test('flight lead increases the shared support readiness budget without changing real player attributes',()=>{
 const f=fixture(),{m,receiver,helper}=f,point={x:receiver.x-7,z:receiver.z+8};
 const normal=m.supportRead(receiver,helper,point),future=m.supportRead({...receiver,supportLead:.6},helper,point);
 assert(Math.abs(future.window-normal.window-.6)<1e-8);assert.equal(receiver.supportLead,undefined);
});
test('full team planning does not immediately reassign arrival helpers into new attacking duties',()=>{
 const f=fixture(),{m,receiver}=f;m.plan();const ids=[...m.supportPlans[0].points.keys()];assert(ids.length>0);
 m.ball={...m.ball,x:receiver.x+.2,z:receiver.z,vx:1,vz:0};assert(m.acquire(receiver));m.plan();
 for(const id of ids){assert(m.supportPlans[0].points.has(id));assert.equal(m.targets.get(m.players[id]).state,'support');}
 const until=m.supportPlans[0].handoffUntil;assert(until>m.time);m.time=until+.01;
 for(const id of ids)assert.equal(m.arrivalHelper(m.players[id],receiver),false);
});
test('restart clears all arrival support state and reservations',()=>{
 const f=fixture();allocate(f);f.m.setRestart('throw',1,{x:0,z:34});assert.equal(f.m.supportPlans[0],null);assert(f.m.players.every(p=>!p.offerIntent));
});
function outletFixture({press=true,blocked=false}={}){
 const m=new Match({seed:21,tactics:{passing:'short',playstyle:'possession'}});m.restart=null;m.time=10;m.phase='carry';m.players.forEach(p=>p.active=false);
 const p=m.players[5],q=m.players[3],d=m.players[14],gk=m.players[21];
 for(const a of [p,q,d,gk])Object.assign(a,{active:true,vx:0,vz:0,speed:0,face:0,action:'idle',actionClock:0,receiveClock:0,touchClock:0,duelRecovery:0,tackleClock:0});
 Object.assign(p,{x:0,z:0,carryTime:.6,face:0});Object.assign(q,{x:blocked?3:5,z:blocked?12:8});
 Object.assign(d,{x:blocked?2:press?7:20,z:0,vx:press?-4:0,face:Math.PI});Object.assign(gk,{x:49,z:0});
 m.owner=p;m.lastTouch=p;m.ball={x:.88,y:.11,z:.18,vx:0,vy:0,vz:0};
 m.supportPlans[0]={ownerId:p.id,epoch:m.attackEpoch[0],points:new Map([[q.id,{x:q.x,z:q.z}]]),handoffUntil:11.2};
 m.targets=new Map([[q,{x:q.x,z:q.z,state:'support',pace:.94}]]);
 return {m,p,q,d};
}
test('approaching pressure can use an already ready support after a feasible physical preparation',()=>{
 const {m,p,q}=outletFixture();const before={ball:{...m.ball},seed:m.seed,x:p.x,z:p.z};
 const choice=m.choose(p);assert.equal(choice.kind,'pass');assert.equal(choice.q,q);assert.equal(choice.supportContinuation,true);
 assert.deepEqual({ball:m.ball,seed:m.seed,x:p.x,z:p.z},before);
});
test('new continuation path does not bypass an intervenable windup or an unready helper',()=>{
 const blocked=outletFixture({blocked:true});blocked.d.vx=-5;assert.equal(blocked.m.passPreparation(blocked.p,{q:blocked.q,point:{x:3,z:12}}).feasible,false);
 assert.notEqual(blocked.m.choose(blocked.p).supportContinuation,true);
 const unready=outletFixture();unready.m.targets.get(unready.q).z+=5;assert.notEqual(unready.m.choose(unready.p).supportContinuation,true);
});
test('no approaching pressure or expired handoff leaves normal tactical patience in charge',()=>{
 const f=outletFixture({press:false});assert.notEqual(f.m.choose(f.p).supportContinuation,true);
 const expired=outletFixture();expired.m.time=12;assert.notEqual(expired.m.choose(expired.p).supportContinuation,true);
});
test('counter instruction does not force a backward support continuation',()=>{
 const {m,p,q}=outletFixture();q.x=-5;m.targets.get(q).x=-5;m.t[0].onWin='counter';m.transitionUntil[0]=12;
 assert.notEqual(m.choose(p).supportContinuation,true);
});
test('a newly crowded support endpoint is not preserved by handoff continuity',()=>{
 const f=fixture(),points=allocate(f),[id,point]=[...points][0];const rival=f.m.players[14];Object.assign(rival,{x:point.x,z:point.z,vx:0,vz:0});
 const replacement=allocate(f).get(id);assert(!replacement||distance(replacement,rival)>=1.3);
});
test('hold instruction keeps fullbacks out of the receiving support allocation',()=>{
 const f=fixture(),fullback=f.m.players[6];Object.assign(fullback,{x:0,z:-5,homeZ:-23,role:'DEF'});f.pool.push(fullback);f.m.t[0].fullbacks='hold';
 assert(!allocate(f).has(fullback.id));
});
