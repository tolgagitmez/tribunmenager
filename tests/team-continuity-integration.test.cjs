'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match,BallPhysics,distance}=require('../football-sim');
const Perception=require('../player-perception'),Intent=require('../team-intent');
const dt=1/60;
function fixture({observe=true}={}){
 const m=new Match({seed:21,tactics:{playstyle:'possession',passing:'short',fullbacks:'overlap'}});m.restart=null;m.time=10;m.planClock=100;m.phase='carry';
 for(const a of m.players)a.active=false;
 const p=m.players[3],q=m.players[5],d=m.players[14],keeper=m.players[21];
 for(const a of[p,q,d,keeper])Object.assign(a,{active:true,x:0,z:0,vx:0,vz:0,speed:0,face:0,action:'idle',actionClock:0,actionElapsed:0,duelRecovery:0,touchClock:0,tackleClock:0,receiveClock:0,decision:100,energy:1,stamina:92});
 Object.assign(q,{x:8,z:8});Object.assign(d,{x:-8,z:0});Object.assign(keeper,{x:49,z:0,face:Math.PI});
 Object.assign(p,{carryTime:.6,carryTarget:{x:5,z:0}});m.owner=p;m.lastTouch=p;m.lastTeam=0;m.ball={x:.88,y:.11,z:.18,vx:0,vy:0,vz:0};m.updateTeamPhases();
 if(observe){Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;}
 return{m,p,q,d,keeper};
}
function clone(m){return Object.assign(Object.create(Match.prototype),structuredClone(m));}
function choice(c){return {...c,...(c.q?{q:c.q.id}:{})};}
function state(m){return structuredClone({seed:m.seed,time:m.time,ball:m.ball,players:m.players,targets:[...m.targets].map(([p,t])=>[p.id,t]),telemetry:m.telemetry,teamPhases:m.teamPhases,attackPlans:m.attackPlans,flankPlans:m.flankPlans,boxPlans:m.boxPlans,supportPlans:m.supportPlans,pressAssignments:m.pressAssignments,kick:m.kick});}

test('live decision queries cannot inspect an unobserved rival position or velocity',()=>{
 const {m,p,q,d}=fixture();assert.deepEqual(m.rivals(p),[]);
 const before={lane:m.laneRisk(p,q),choice:choice(m.choose(p)),preparation:m.passPreparation(p,{q,point:{x:q.x,z:q.z}})};
 for(const key of['x','z','vx','vz'])Object.defineProperty(d,key,{get(){throw Error('unobserved live '+key+' read');}});
 assert.equal(m.laneRisk(p,q),before.lane);assert.deepEqual(choice(m.choose(p)),before.choice);assert.deepEqual(m.passPreparation(p,{q,point:{x:q.x,z:q.z}}),before.preparation);
});
test('a hidden rival change cannot affect a lane, choice or preparation before another observation',()=>{
 const {m,p,q,d}=fixture(),before={lane:m.laneRisk(p,q),choice:choice(m.choose(p)),preparation:m.passPreparation(p,{q,point:{x:q.x,z:q.z}})};
 Object.assign(d,{x:3,z:3,vx:-6,vz:-6,speed:Math.sqrt(72)});
 assert.equal(m.laneRisk(p,q),before.lane);assert.deepEqual(choice(m.choose(p)),before.choice);assert.deepEqual(m.passPreparation(p,{q,point:{x:q.x,z:q.z}}),before.preparation);
 Perception.update(m.players,m.time,0,{scanAllowed:false});assert.equal(m.rivals(p)[0].id,d.id);assert(m.laneRisk(p,q)>before.lane,'the lane reacts once the player actually sees the defender');
});
test('a remembered rival contributes the observed estimate until the body turns to see him',()=>{
 const {m,p,q,d}=fixture({observe:false});Object.assign(d,{x:6,z:6,vx:0,vz:0});Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;
 p.face=Math.PI;m.time+=.2;const estimate=m.rivals(p)[0],risk=m.laneRisk(p,q),prepared=m.passPreparation(p,{q,point:{x:q.x,z:q.z}});
 Object.assign(d,{x:20,z:-10,vx:-7,vz:2});Perception.update(m.players,m.time,dt,{scanAllowed:false});
 assert.deepEqual(m.rivals(p)[0],estimate);assert.equal(m.laneRisk(p,q),risk);assert.deepEqual(m.passPreparation(p,{q,point:{x:q.x,z:q.z}}),prepared);assert.equal(estimate.x,6);assert(estimate.age>.19&&estimate.confidence<1);
 p.face=0;Perception.update(m.players,m.time,0,{scanAllowed:false});assert.equal(m.rivals(p)[0].x,20);assert(m.laneRisk(p,q)<risk);
});
test('pass review does not react to an unseen defender moving into the physical lane',()=>{
 const {m,p,q,d}=fixture();p.face=Math.PI;assert(m.startKick(p,'pass',q,{x:q.x,z:q.z}));assert(m.kick.passRead);m.kick.clock=.05;
 const other=clone(m),otherD=other.players[d.id];Object.assign(otherD,{x:2,z:2,vx:-7,vz:-7});
 const first=m.reviewPass(m.kick),second=other.reviewPass(other.kick);assert.equal(first,false);assert.equal(second,first);assert.deepEqual(other.kick.passRead,m.kick.passRead);assert.deepEqual(other.telemetry,m.telemetry);
});
test('an unseen blind presser does not trigger the post-reception hold correction from live coordinates',()=>{
 const {m,p,d}=fixture();Object.assign(p,{vx:3,speed:3,receiveMode:'protect',carryIntent:{until:11,point:{x:5,z:0}},receiveClock:0});m.lastGain={player:p.id,team:0,time:9.5,x:0,z:0};
 Object.assign(d,{x:-2,z:.2,vx:4,vz:0,speed:4});Perception.clear(p,m.time);Perception.update(m.players,m.time,0,{scanAllowed:false});assert.deepEqual(m.rivals(p),[]);
 const requested={kind:'carry',point:{x:-2,z:0},hold:true};assert.equal(m.postReceiveHold(p,requested),requested);
 Object.assign(d,{x:-1,z:-1,vx:6,vz:1});assert.equal(m.postReceiveHold(p,requested),requested);
});
test('physical preparation forecasts preserve RNG, task history, observations and the live frame',()=>{
 const {m,p,q}=fixture();m.startCarry(p,{kind:'carry',point:{x:5,z:0},commit:.5});
 Intent.resolve(q,{x:q.x-1,z:q.z,state:'support',partnerId:p.id,priority:30},m.taskContext(q));
 assert(m.startKick(p,'pass',q,{x:q.x,z:q.z}));const before=state(m),random=m.random;m.random=()=>{throw Error('speculation consumed live randomness');};
 try{m.passPreparation(p,{q,point:{x:q.x,z:q.z}});m.controlPreparation(p,{kind:'carry',point:{x:5,z:0}},null,.35);m.passReleaseRisk(m.kick);m.touchRecovery(p,{vx:3,vz:0,vy:0},{mode:'setup',interval:.2,target:{x:q.x,z:q.z}});}finally{m.random=random;}
 assert.deepEqual(state(m),before);
});
test('a real gain starts win/loss phases and a same-team pass preserves the transition and other duties',()=>{
 const {m,p,q,d}=fixture();assert.deepEqual(m.teamPhases.map(x=>x.phase),['possession','defence']);
 Intent.resolve(q,{x:12,z:8,state:'channel-run',partnerId:p.id},m.taskContext(q));const oldEpoch=m.attackEpoch[1];
 m.owner=null;m.ball={x:d.x+.3,y:.11,z:d.z,vx:0,vy:0,vz:0};assert(m.acquire(d));
 assert.deepEqual(m.teamPhases.map(x=>x.phase),['loss','win']);assert.equal(m.attackEpoch[1],oldEpoch+1);assert.equal(q.task,null);assert(q.taskHistory.some(e=>e.reason==='loss'));
 const receiver=m.players[12];Object.assign(receiver,{active:true,x:-1,z:5,vx:0,vz:0,speed:0,face:Math.PI,duelRecovery:0,touchClock:0});
 const transition=m.transitionUntil[1],loss=m.lossUntil[0],phaseEpoch=m.teamPhases[1].epoch,attackEpoch=m.attackEpoch[1],memory=structuredClone(d.perception);
 Intent.resolve(d,{x:-9,z:7,state:'return-support',partnerId:receiver.id},m.taskContext(d));const duty=structuredClone(d.task);
 m.time+=.3;m.owner=null;m.flight={id:42,from:d,target:receiver,kind:'pass',age:.3,point:{x:receiver.x,z:receiver.z}};m.ball={x:receiver.x+.3,y:.11,z:receiver.z,vx:1,vy:0,vz:0};assert(m.acquire(receiver));
 assert.equal(m.transitionUntil[1],transition);assert.equal(m.lossUntil[0],loss);assert.equal(m.attackEpoch[1],attackEpoch);assert.equal(m.teamPhases[1].epoch,phaseEpoch);assert.deepEqual(d.task,duty);assert.deepEqual(d.perception,memory);
 m.time=Math.max(transition,loss)+.01;m.updateTeamPhases();assert.deepEqual(m.teamPhases.map(x=>x.phase),['defence','possession']);
});
test('an explicit give-and-go run survives box allocation and a new team plan',()=>{
 const {m,p,q}=fixture();Object.assign(p,{x:35,z:20});Object.assign(q,{role:'ATT',homeX:28,homeZ:0,x:31,z:5});m.ball.x=35.8;m.ball.z=20;
 q.runIntent={kind:'give-go',partnerId:p.id,epoch:m.attackEpoch[0],origin:{x:29,z:5},point:{x:40,z:9},until:m.time+3};
 m.plan();assert.equal(m.targets.get(q).state,'channel-run');assert(distance(m.targets.get(q),q.runIntent.point)<.01);assert(!m.boxPlans[0]?.points.has(q.id));
 m.time+=.16;m.plan();assert.equal(m.targets.get(q).state,'channel-run');assert.equal(q.task.partnerId,p.id);
});
test('an arrived support remains available for the opportunity window and still expires',()=>{
 const {m,p,q}=fixture();Object.assign(p,{x:35,z:20});Object.assign(q,{role:'ATT',homeX:28,homeZ:0,x:31,z:5});m.ball.x=35.8;m.ball.z=20;
 // Reach the support after its initial minimum commitment has already ended.
 // The opening must then survive on its own .45s opportunity window.
 m.time=9;Object.assign(q,{x:28,z:2});Intent.resolve(q,{x:31,z:5,state:'support',partnerId:p.id,priority:30},m.taskContext(q));m.time=10;Object.assign(q,{x:31,z:5});
 m.plan();assert.equal(m.targets.get(q).state,'support');assert.equal(q.task.arrivedAt,m.time);
 const arrival=m.time,expiry=q.task.expiresAt;m.time=arrival+.05;m.plan();m.time=arrival+.40;m.plan();assert.equal(m.targets.get(q).state,'support');assert.equal(q.task.partnerId,p.id);
 m.time=expiry+.01;m.plan();assert.notEqual(m.targets.get(q).state,'support');assert(q.taskHistory.some(e=>['expiry','arrived'].includes(e.reason)));
});
test('the intended receiver is reserved during windup and stops waiting after a physical abort',()=>{
 const {m,p,q}=fixture();assert(m.startKick(p,'pass',q,{x:12,z:10}));m.plan();assert.equal(m.targets.get(q).state,'receive-run');assert.equal(q.task.purpose,'receive');
 m.time+=.16;m.plan();assert.equal(m.targets.get(q).state,'receive-run');
 m.ball.x=p.x+5;m.ball.z=p.z;m.kickStep(dt);assert.equal(m.kick,null);assert.equal(m.owner,null);assert.equal(m.telemetry.abortedKicks,1);
 m.time+=.16;m.plan();assert.notEqual(m.targets.get(q).state,'receive-run');assert.notEqual(q.task.purpose,'receive');
});
test('a restart clears task reservations and observations before the next live frame',()=>{
 const {m,p,q,d}=fixture();Object.assign(d,{x:5,z:2});Perception.update(m.players,m.time,0,{scanAllowed:false});m.startCarry(p,{kind:'carry',point:{x:6,z:0}});assert(p.task);assert(m.rivals(p).length);
 q.runIntent={point:{x:12,z:5},until:12};m.transitionUntil=[12,12];m.lossUntil=[12,12];m.buildPlans=[{id:q.id},null];m.boxPlans=[{points:new Map([[q.id,{x:12,z:5}]])},null];m.setRestart('throw',1,{x:1,z:34});assert.equal(m._perceptionActive,false);
 for(const a of m.players.filter(a=>a.active&&!a.referee)){assert.equal(a.task??null,null);assert.deepEqual(Perception.rivals(a,m.time),[]);assert.equal(a.runIntent,null);}
 assert.deepEqual(m.transitionUntil,[0,0]);assert.deepEqual(m.lossUntil,[0,0]);assert.deepEqual(m.teamPhases,[null,null]);assert.deepEqual(m.buildPlans,[null,null]);assert.deepEqual(m.boxPlans,[null,null]);assert(p.taskHistory.some(e=>e.reason==='restart'));
});
test('substitution discards the outgoing player task and observation identity',()=>{
 const {m,p,q,d}=fixture();Object.assign(d,{x:5,z:3});Perception.update(m.players,m.time,0,{scanAllowed:false});Intent.resolve(q,{x:10,z:8,state:'support',partnerId:p.id},m.taskContext(q));
 m.cfg.players=[{id:999,name:'Fresh midfielder',rating:83,fitness:95,passing:84,owned:true,pos:'MID'}];assert(q.task);assert(Perception.rivals(q,m.time).length);
 m.goalPause={clock:2,team:0};const result=m.substitute(q.index,999);assert.equal(result.ok,true);assert.equal(q.rosterId,999);assert.equal(q.task,null);assert.deepEqual(Perception.rivals(q,m.time),[]);assert(q.taskHistory.some(e=>e.reason==='substitution'));
});
test('a quiet real step activates perception without extra random draws or physical integration',()=>{
 const {m,p,d}=fixture({observe:false});Object.assign(d,{x:25,z:-15});p.touchClock=100;p.decision=100;m.planClock=0;m.ball.vx=1;const before={seed:m.seed,time:m.time,p:{x:p.x,z:p.z},ball:{...m.ball}},expected=BallPhysics.predict(m.ball,dt),random=m.random;
 m.random=()=>{throw Error('quiet frame added an RNG draw');};try{m.step(dt);}finally{m.random=random;}
 assert.equal(m._perceptionActive,true);assert.equal(m.seed,before.seed);assert.equal(m.time,before.time+dt);assert(distance(p,before.p)<.15);assert.deepEqual(m.ball,expected);assert(p.perception.lastUpdate===m.time);
});
test('an unobserved rival can still intervene through exact live physical contact',()=>{
 const {m,p,d}=fixture();assert.deepEqual(m.rivals(p),[]);
 Object.assign(d,{x:-.4,z:-1.1,vx:0,vz:0,speed:0,face:Math.atan2(1.1,.4),tackleClock:0,duelRecovery:0});m.ball={x:-.1,y:.11,z:-.5,vx:0,vy:0,vz:0};p.touchClock=1;
 assert.deepEqual(m.rivals(p),[],'a decision query cannot refresh the contact observation');assert.equal(m.tackleAccess(d,p).attempt,true);const duels=m.telemetry.duels;m.doTackle(d,p);assert.equal(m.telemetry.duels,duels+1);
});
test('a marker cannot inherit a teammate observation as personal sight of a blind runner',()=>{
 const {m,p,q,d}=fixture({observe:false}),observer=m.players[15],presser=m.players[16];
 Object.assign(q,{role:'ATT',x:15,z:0,homeX:28,homeZ:0});Object.assign(d,{role:'DEF',homeX:28,homeZ:0,x:20,z:0,face:0});
 for(const a of[observer,presser])Object.assign(a,{active:true,role:'MID',vx:0,vz:0,speed:0,duelRecovery:0,touchClock:0,tackleClock:1,receiveClock:0,face:Math.PI});
 Object.assign(observer,{x:25,z:5,homeX:2,homeZ:5});Object.assign(presser,{x:3.3,z:0,homeX:2,homeZ:0});
 Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;
 assert(m.teamRivals(1).some(a=>a.id===q.id),'the team has observed the runner');assert(!m.rivals(d).some(a=>a.id===q.id),'this defender has not');
 m.plan();assert(!['mark','track-run'].includes(m.targets.get(d).state));assert.notEqual(m.defensiveUnits[1].assignments.get(d)?.id,q.id);
 d.face=Math.PI;m.time+=.16;Perception.update(m.players,m.time,0,{scanAllowed:false});m.plan();assert.equal(m.defensiveUnits[1].assignments.get(d)?.id,q.id);assert(['mark','track-run'].includes(m.targets.get(d).state));
});
