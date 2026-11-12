'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Match}=require('../football-sim');
const Diagnostics=require('../attack-diagnostics');
const dt=1/60;
function fixture({team=0,x=0,moving=false}={}){
 const m=new Match({seed:21});m.restart=null;m.kick=null;m.goalPause=null;m.time=10;m.planClock=100;m.phase='carry';
 for(const p of m.players)p.active=false;
 const side=team===0?1:-1,p=m.players[team*11+3];
 Object.assign(p,{active:true,x:x*side,z:0,vx:moving?5*side:0,vz:0,speed:moving?5:0,face:side>0?0:Math.PI,skill:82,passing:82,shooting:82,dribbling:82,agility:82,pace:82,vision:82,composure:82,weakFoot:70,preferredFoot:1,kickFoot:1,stamina:92,energy:1,action:'idle',actionClock:0,actionElapsed:0,receiveClock:0,touchClock:moving?0:100,tackleClock:100,duelRecovery:0,decision:100,carryTime:0,carryTarget:{x:(x+15)*side,z:0}});
 m.owner=p;m.lastTouch=p;m.lastTeam=team;m.ball={x:(x+.8)*side,y:.11,z:.18*side,vx:moving?5*side:0,vy:0,vz:0};
 m.targets=new Map([[p,{x:moving?(x+15)*side:p.x,z:0,pace:moving?.98:0,state:'dribble'}]]);
 return {m,p,side};
}
const snapshot=m=>structuredClone(m);
const summary=o=>o.summary();
const shotCount=(o,team=0)=>summary(o).teams[team].shots;

test('observing real matches preserves the complete engine state and RNG during and after attachment',()=>{
 const cfg={seed:42,tactics:{playstyle:'possession',passing:'short'}},plain=new Match(cfg),observed=new Match(cfg),keys=Object.getOwnPropertyNames(observed).sort(),o=Diagnostics.attach(observed);
 for(let i=0;i<12*60;i++){plain.step(dt);o.step(dt);}
 assert.deepEqual(snapshot(observed),snapshot(plain));assert.equal(observed.seed,plain.seed);
 o.detach();assert.deepEqual(Object.getOwnPropertyNames(observed).sort(),Object.getOwnPropertyNames(plain).sort());assert(keys.every(k=>Object.hasOwn(observed,k)));
 assert.deepEqual(snapshot(observed),snapshot(plain));
 const again=Diagnostics.attach(observed);plain.step(dt);again.step(dt);again.detach();assert.deepEqual(snapshot(observed),snapshot(plain));
});

test('attachment preserves pre-existing own method descriptors and rejects double attachment',()=>{
 const {m}=fixture(),own=function(p){return {kind:'carry',point:{x:p.x+2,z:p.z},hold:true};};
 Object.defineProperty(m,'choose',{value:own,enumerable:true,writable:true,configurable:true});const before=Object.getOwnPropertyDescriptor(m,'choose');
 const o=Diagnostics.attach(m);assert.throws(()=>Diagnostics.attach(m));assert.equal(Object.getOwnPropertyDescriptor(m,'choose').enumerable,true);
 o.detach();o.detach();assert.deepEqual(Object.getOwnPropertyDescriptor(m,'choose'),before);
 assert.equal(Object.hasOwn(m,'acquire'),false);assert.equal(Object.hasOwn(m,'release'),false);
});

test('quiet-frame observation and reports cannot run extra AI, planning, trajectory or random queries',()=>{
 const {m}=fixture(),queries=['choose','preparedChoice','passOptions','shotWindow','plan','rivals','goalThreat','ballCrossing','passPreparation','receiverInterceptPoint'];
 for(const name of queries)m[name]=()=>{throw Error('observer invoked '+name);};m.random=()=>{throw Error('observer drew randomness');};
 const before=m.seed,o=Diagnostics.attach(m);assert.doesNotThrow(()=>{o.step(dt);o.sample();o.report();o.summary();});assert.equal(m.seed,before);o.detach();
});

test('isolated preparation forecasts are not recorded as live decisions or releases',()=>{
 const {m,p}=fixture(),q=m.players[5];Object.assign(q,{active:true,x:8,z:6,vx:0,vz:0,speed:0,face:0,duelRecovery:0,touchClock:0,action:'idle',actionClock:0,receiveClock:0});
 p.touchClock=0;const o=Diagnostics.attach(m),before=structuredClone(summary(o));
 m.passPreparation(p,{q,point:{x:q.x,z:q.z}});m.controlPreparation(p,{kind:'carry',point:{x:5,z:0}},null,.35);
 assert.deepEqual(summary(o),before);o.detach();
});

test('in-play time includes open windup and keeper possession but excludes restart and goal pause',()=>{
 for(const variant of ['open','windup','keeper','restart','goal-pause']){
  const {m,p}=fixture();
  if(variant==='windup'){p.touchClock=0;assert(m.startKick(p,'pass',null,{x:5,z:0}));}
  if(variant==='keeper'){p.role='GK';p.holdingBall=true;p.holdClock=.75;}
  if(variant==='restart'){m.setRestart('throw',0,{x:0,z:33.5},p);m.restart.clock=10;}
  if(variant==='goal-pause'){m.owner=null;m.phase='goal';m.goalPause={clock:1,team:1};}
  const o=Diagnostics.attach(m);o.step(dt);const clock=summary(o).clock;
  assert(Math.abs(clock.observedSeconds-dt)<1e-10,variant);
  const live=['open','windup','keeper'].includes(variant);assert(Math.abs(clock.inPlaySeconds-(live?dt:0))<1e-10,variant);assert(Math.abs(clock.deadBallSeconds-(live?0:dt))<1e-10,variant);o.detach();
 }
});

test('exposure uses the actual clamped final interval, and repeated samples add no time',()=>{
 const {m}=fixture();m.duration=m.time+dt/2;const o=Diagnostics.attach(m);o.step(dt);const before=structuredClone(summary(o));
 assert(Math.abs(before.clock.observedSeconds-dt/2)<1e-10);assert(Math.abs(before.clock.inPlaySeconds-dt/2)<1e-10);
 o.sample();o.sample();assert.deepEqual(summary(o),before);o.detach();
});

test('planned carrying and passing targets never grant territorial stages before actual control reaches them',()=>{
 const {m,p}=fixture();p.carryTarget={x:45,z:0};const q=m.players[5];Object.assign(q,{active:true,x:45,z:0,vx:0,vz:0,speed:0,face:0,touchClock:100,duelRecovery:0});
 const o=Diagnostics.attach(m);for(let i=0;i<20;i++)o.step(dt);
 m.owner=null;m.flight={id:91,from:p,target:q,kind:'pass',age:0,point:{x:45,z:0},offsidePlayers:[]};
 for(let i=0;i<20;i++)o.step(dt);const team=summary(o).teams[0];
 assert.equal(team.stageCounts.finalThird,0);assert.equal(team.stageCounts.box,0);assert.equal(team.stageCounts.shot,0);o.detach();
});

test('a shot preparation event is not a released shot, and repeated sampling cannot count a release twice',()=>{
 const {m,p}=fixture();p.touchClock=0;const o=Diagnostics.attach(m);
 assert(m.startKick(p,'shot',null,{x:52,z:0}));assert(m.events.some(e=>e.type==='shot'));o.sample();assert.equal(shotCount(o),0);assert.equal(summary(o).teams[0].stageCounts.shot,0);
 m.release();o.sample();assert.equal(shotCount(o),1);assert.equal(summary(o).teams[0].stageCounts.shot,1);
 o.sample();assert.equal(shotCount(o),1);o.detach();
});

test('a released pass and its same-timestamp reception both survive before the next sampled frame',()=>{
 const {m,p}=fixture(),q=m.players[5];Object.assign(q,{active:true,x:3,z:0,vx:0,vz:0,speed:0,face:0,duelRecovery:0,touchClock:0,receiveClock:0,action:'idle',actionClock:0});p.touchClock=0;
 const o=Diagnostics.attach(m);assert(m.startKick(p,'pass',q,{x:q.x,z:q.z}));m.release();assert.equal(m.passes[0],1);
 m.ball.x=q.x+.2;m.ball.z=q.z;assert(m.acquire(q));assert.equal(m.completed[0],1);o.sample();
 const passes=summary(o).teams[0].passes;assert.equal(passes.attempted,1);assert.equal(passes.completed,1);assert.equal(passes.intercepted,0);o.detach();
});

test('territory at attachment is left-censored rather than an invented pressure escape or broken line',()=>{
 for(const team of [0,1]){
  const {m}=fixture({team,x:38}),o=Diagnostics.attach(m);for(let i=0;i<20;i++)o.step(dt);
  const record=summary(o).teams[team];assert.equal(record.stageCounts.pressureEscape,0);assert.equal(record.stageCounts.lineBreak,0);
  const episodes=o.report().episodes;assert(episodes.some(e=>e.team===team&&(e.leftCensored===true||e.origin==='left-censored')));o.detach();
 }
});

test('final-third and box entries require actual controlled motion and are symmetric in both directions',()=>{
 for(const stage of ['finalThird','box']){
  const counts=[];
  for(const team of [0,1]){
   const {m}=fixture({team,x:stage==='box'?34.4:16.2,moving:true}),o=Diagnostics.attach(m);
   assert.equal(summary(o).teams[team].stageCounts[stage],0);for(let i=0;i<40;i++)o.step(dt);
   counts.push(summary(o).teams[team].stageCounts[stage]);o.detach();
  }
  assert.deepEqual(counts,[1,1],stage);
 }
});

test('a release confirming several stages cannot move the terminal stage backwards from the box to a broken line',()=>{
 const {m,p}=fixture(),q=m.players[5],r=m.players[0];
 for(const [a,x,z]of [[q,40,0],[r,44,4],[m.players[14],10,-4],[m.players[15],12,4]])Object.assign(a,{active:true,x,z,vx:0,vz:0,speed:0,face:0,action:'idle',actionClock:0,touchClock:0,tackleClock:100,duelRecovery:0,receiveClock:0,decision:100});
 p.touchClock=0;const o=Diagnostics.attach(m);assert(m.startKick(p,'pass',q,{x:q.x,z:q.z}));m.release();
 m.ball.x=q.x+.2;m.ball.z=q.z;assert(m.acquire(q));assert(m.startKick(q,'pass',r,{x:r.x,z:r.z}));m.release();o.sample();
 const episode=o.report().episodes.at(-1);assert(episode.stages.lineBreak);assert(episode.stages.finalThird);assert(episode.stages.box);assert.equal(episode.lastStage,'box');o.detach();
});

test('a carried ball breaks the same frozen two-player line in both attacking directions',()=>{
 for(const team of [0,1]){
  const {m,side}=fixture({team,x:15,moving:true}),other=(1-team)*11,ids=[other+3,other+4];
  for(const [i,id]of ids.entries())Object.assign(m.players[id],{active:true,x:18*side,z:i?-8:8,vx:0,vz:0,speed:0,face:side>0?Math.PI:0,duelRecovery:0,touchClock:100,tackleClock:100,action:'idle',actionClock:0});
  const o=Diagnostics.attach(m);for(let i=0;i<100;i++)o.step(dt);
  const record=summary(o).teams[team];assert.equal(record.stageCounts.lineBreak,1);assert.equal(record.eligibleReached.lineBreak,1);
  const entry=o.report().episodes.find(e=>e.team===team&&e.stages.lineBreak)?.stages.lineBreak;
  assert(entry);assert.deepEqual([...entry.rivalIds].sort((a,b)=>a-b),ids);assert(entry.x*side>=19);o.detach();
 }
});

test('an actual gain still settling at the time limit is censored rather than a tactical loss',()=>{
 const {m,p}=fixture();m.owner=null;m.lastTeam=1;m.lastTouch=m.players[14];const o=Diagnostics.attach(m);
 assert(m.acquire(p));assert.equal(summary(o).teams[0].pending,1);assert.equal(summary(o).teams[0].confirmedGains,0);
 m.duration=m.time+dt*4;for(let i=0;i<4;i++)o.step(dt);
 const aggregate=summary(o).teams[0],episode=o.report().episodes.find(e=>e.origin==='gain');
 assert.equal(aggregate.censored,1);assert.equal(aggregate.ended,0);assert.equal(aggregate.pending,0);assert.deepEqual(aggregate.endReasons,{});
 assert.equal(episode.status,'censored');assert.equal(episode.endReason,'match-end');o.detach();
});

test('pressure escape is an eligible controlled event, while unpressured carrying cannot earn it',()=>{
 for(const pressed of [false,true]){
  const {m}=fixture({moving:true});if(pressed)Object.assign(m.players[14],{active:true,x:-.5,z:3,vx:0,vz:0,speed:0,face:0,duelRecovery:0,touchClock:100,tackleClock:100,action:'idle',actionClock:0});
  const o=Diagnostics.attach(m);for(let i=0;i<120;i++)o.step(dt);const aggregate=summary(o).teams[0];
  assert.equal(aggregate.stageEligibility.pressureEscape,pressed?1:0);assert.equal(aggregate.stageCounts.pressureEscape,pressed?1:0);assert.equal(aggregate.notRequired.pressureEscape,pressed?0:1);o.detach();
 }
});
