'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),Diagnostics=require('../attack-diagnostics');
const dt=1/60;
function fixture(t=0,x=0,z=0){
 const m=new Match({seed:21});m.restart=null;m.goalPause=null;m.time=10;m.planClock=100;m.phase='open';m.players.forEach(p=>p.active=false);
 const p=m.players[t?14:3],q=m.players[t?16:5],r=m.players[t?3:14];
 for(const a of[p,q,r])Object.assign(a,{active:true,x:0,z:0,vx:0,vz:0,speed:0,face:t?Math.PI:0,touchClock:100,tackleClock:100,duelRecovery:0,receiveClock:0,decision:100,action:'idle',actionClock:0,energy:1,stamina:92});
 Object.assign(p,{x,z});Object.assign(q,{x:x+(t?-8:8),z:z+8});Object.assign(r,{x:x+(t?-25:25),z:z-15,face:t?0:Math.PI});
 m.owner=null;m.lastTeam=1-t;m.lastTouch=r;m.ball={x:x+(t?-.3:.3),y:.11,z,vx:0,vy:0,vz:0};m.targets=new Map();return {m,p,q,r,t};
}
function gain(f){assert.equal(f.m.acquire(f.p),true);f.p.touchClock=f.p.decision=100;f.m.planClock=100;return f;}
function steps(o,n=12){for(let i=0;i<n;i++)o.step(dt);}
function release(f,kind='pass',target=f.q){
 const {m,p}=f;m.owner=p;m.ball={x:p.x+Math.cos(p.face)*.88-Math.sin(p.face)*.18,y:.11,z:p.z+Math.sin(p.face)*.88+Math.cos(p.face)*.18,vx:0,vy:0,vz:0};
 assert.equal(m.startKick(p,kind,kind==='shot'?null:target,kind==='shot'?{x:f.t?-52:52,z:0}:{x:target.x,z:target.z}),true);m.release();
}
function assertPassPartition(report,t=0){const p=report.teams[t].passes;assert.equal(p.attempted,Object.entries(p).filter(([k])=>k!=='attempted').reduce((n,[,v])=>n+v,0));}

test('attachment and detachment preserve property shape, original methods and override descriptors',()=>{
 const {m}=fixture(),keys=Reflect.ownKeys(m),original=m.acquire;
 Object.defineProperty(m,'startCarry',{value:m.startCarry,writable:true,configurable:true,enumerable:true});const own=Object.getOwnPropertyDescriptor(m,'startCarry'),plain={...m};delete plain.startCarry;const state=structuredClone(plain),o=Diagnostics.attach(m);
 assert.equal(Object.getOwnPropertyDescriptor(m,'acquire').enumerable,false);assert.equal(Object.getOwnPropertyDescriptor(m,'startCarry').enumerable,true);assert.equal(m.acquire===original,false);
 // Enumerable own function overrides are preserved; their values cannot be structured-cloned.
 const snap={...m};delete snap.startCarry;const expected={...state};delete expected.startCarry;assert.deepEqual(structuredClone(snap),expected);
 o.detach();o.detach();assert.equal(m.acquire,original);assert.deepEqual(Object.getOwnPropertyDescriptor(m,'startCarry'),own);assert.equal(Object.hasOwn(m,'acquire'),false);assert.deepEqual(Reflect.ownKeys(m),[...keys,'startCarry']);
});
test('duplicate and non-configurable attachments fail atomically without touching the engine',()=>{
 const {m}=fixture(),o=Diagnostics.attach(m);assert.throws(()=>Diagnostics.attach(m),/already attached/);o.detach();
 const original=m.acquire;Object.defineProperty(m,'keeper',{value:m.keeper,configurable:false});assert.throws(()=>Diagnostics.attach(m),/non-configurable/);assert.equal(m.acquire,original);assert.equal(Object.hasOwn(m,'acquire'),false);
});
test('an own accessor is rejected without invoking it or installing earlier wrappers',()=>{
 const {m}=fixture();let reads=0;Object.defineProperty(m,'keeper',{get(){reads++;return ()=>{};},configurable:true});assert.throws(()=>Diagnostics.attach(m),/accessor/);assert.equal(reads,0);assert.equal(Object.hasOwn(m,'acquire'),false);
});
test('empty denominators return null and reading reports cannot finish or mutate an attack',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);assert.equal(o.report().teams[0].rates.shotsPerAttack,null);assert.equal(o.report().teams[0].rates.shotsPer10InPlay,null);
 gain(f);const before=structuredClone(f.m),a=o.report(),b=o.report();assert.deepEqual(a,b);assert.deepEqual(structuredClone(f.m),before);assert.equal(a.episodes[0].status,'pending');assert.equal(a.episodes[0].endReason,null);o.detach();
});
test('an actual contact gain is not called settled control until its continuous dwell completes',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);steps(o,8);assert.equal(o.report().teams[0].contactGains,1);assert.equal(o.report().teams[0].confirmedGains,0);steps(o,1);assert.equal(o.report().teams[0].confirmedGains,1);assert.equal(o.report().episodes[0].stages.gain.method,'settled-control');o.detach();
});
test('commanded final-third and box destinations do not create territorial progress',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);f.m.targets.set(f.q,{x:42,z:0,state:'box-run',pace:0});steps(o,12);const r=o.report();assert.equal(r.teams[0].stageCounts.finalThird,0);assert.equal(r.teams[0].stageCounts.box,0);assert(r.teams[0].evidence.boxRunnerCommands>0);o.detach();
});
for(const t of[0,1])test(`a gain already inside the box keeps its furthest location when gain confirmation arrives (${t})`,()=>{
 const f=fixture(t,(t?-1:1)*38,0),o=Diagnostics.attach(f.m);gain(f);steps(o,12);let e=o.report().episodes[0];assert.equal(e.lastStage,'box');assert.equal(e.startedBeyond.box,true);assert.equal(e.eligibility.box,false);assert.equal(e.stages.box.entryMode,'at-start');
 f.m.setRestart('throw',1-t,{x:f.p.x,z:34});e=o.report().episodes[0];assert.equal(e.lastStage,'box');assert.equal(e.endReason,'out-loss');assert.equal(o.report().teams[t].eligibleReached.box,0);o.detach();
});
test('shot preparation is not a shot and only the actual release ends its episode',()=>{
 const f=fixture(0,40,0),o=Diagnostics.attach(f.m);gain(f);assert(f.m.startKick(f.p,'shot',null,{x:52,z:0}));let r=o.report();assert.equal(r.coverage.shots.prepared,1);assert.equal(r.teams[0].shots,0);assert.equal(r.episodes[0].status,'pending');
 f.m.release();r=o.report();assert.equal(r.teams[0].shots,1);assert.equal(r.episodes[0].endReason,'shot');assert.equal(r.episodes[0].lastStage,'shot');assert.equal(r.shots[0].status,'pending');assert.equal(f.m.shots[0],1);o.detach();
});
test('a goal from a non-shot flight is never counted as a shot-conversion success',()=>{
 const f=fixture(0,49,0),o=Diagnostics.attach(f.m);gain(f);release(f);f.m.ball={x:52.01,y:.11,z:0,vx:1,vy:0,vz:0};f.m.ballStep(dt);const r=o.report();assert.equal(f.m.score[0],1);assert.equal(f.m.shots[0],0);assert.equal(r.coverage.shots.goalEvents,1);assert.equal(r.coverage.shots.nonShotGoalEvents,1);assert.equal(r.coverage.shots.goals,0);assert.equal(r.teams[0].passes.goalsWithoutShot,1);assertPassPartition(r);o.detach();
});
test('an actual out-of-play pass is resolved at the restart and cannot later become a deflection',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);release(f);f.m.setRestart('throw',1,{x:8,z:34});let r=o.report();assert.equal(r.teams[0].passes.out,1);assert.equal(r.teams[0].passes.looseOrDeflected,0);assert.equal(r.teams[0].passes.pending,0);assertPassPartition(r);
 steps(o,2);r=o.report();assert.equal(r.teams[0].passes.out,1);assert.equal(r.teams[0].passes.looseOrDeflected,0);assertPassPartition(r);o.detach();
});
test('a pending pass at the measurement boundary remains pending rather than failed',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);release(f);let r=o.report();assert.equal(r.teams[0].passes.pending,1);assert.equal(r.episodes[0].passes.pending,1);assert.equal(r.teams[0].passes.unknown,0);assertPassPartition(r);o.detach();r=o.report();assert.equal(r.teams[0].passes.pending,1);assert.equal(r.episodes[0].status,'pending');
});
test('an old aborted preparation does not override a later observed pass interception after own recovery',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);f.m.startKick(f.p,'pass',f.q,{x:f.q.x,z:f.q.z});f.m.ball.x=f.p.x+5;f.m.kickStep(dt);o.sample();assert.equal(o.report().teams[0].evidence.passPreparationAborts,1);
 f.p.x=f.m.ball.x-.3;assert(f.m.acquire(f.p));f.p.touchClock=100;release(f);Object.assign(f.r,{x:f.m.ball.x-.3,z:f.m.ball.z});assert(f.m.acquire(f.r));const r=o.report(),ended=r.episodes.find(e=>e.team===0);assert.equal(ended.endReason,'pass-interception');assert.equal(ended.evidence.passPreparationAborts,1);assert.equal(ended.passes.intercepted,1);assert(ended.observations.some(e=>e.type==='preparation-aborted'));assertPassPartition(r);o.detach();
});
test('hold evidence counts the applied carry and never queries a fresh decision',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);const original=f.m.choose;f.m.choose=()=>{throw Error('extra choose query');};f.m.startCarry(f.p,{kind:'carry',hold:true,point:{x:2,z:0}});f.m.planClock=100;f.m.targets.clear();steps(o,3);
 const r=o.report();assert.equal(r.teams[0].evidence.holdDecisions,1);assert(r.teams[0].evidence.holdSeconds>0);assert(r.episodes[0].observations.some(e=>e.type==='carry-decision'&&e.hold&&e.supportCommands===0));f.m.choose=original;o.detach();
});
test('clock categories partition actual in-play time, including goalkeeper hands and a clamped last step',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);f.p.role='GK';f.p.holdingBall=true;f.p.holdClock=1;f.m.ball.y=.95;steps(o,2);f.m.duration=f.m.time+dt/2;o.step(dt);const r=o.report(),c=r.clock;assert.equal(f.m.done,true);assert(Math.abs(c.observedSeconds-(2.5/60))<1e-9);assert(Math.abs(c.inPlaySeconds-c.controlledSeconds[0]-c.controlledSeconds[1]-c.flightSeconds[0]-c.flightSeconds[1]-c.looseSeconds)<1e-9);assert(c.controlledSeconds[0]>.04);assert.equal(r.episodes[0].status,'censored');o.detach();
});
test('manual gaps and time rewind are explicit rather than invented tactical exposure',()=>{
 const {m}=fixture(),o=Diagnostics.attach(m);m.time+=1;o.sample();let r=o.report();assert.equal(r.clock.unobservedSeconds,1);assert.equal(r.clock.inPlaySeconds,0);m.time-=2;o.sample();r=o.report();assert.equal(r.valid,false);assert.match(r.errors[0].message,/backwards/);o.detach();
});
test('an unobserved sample gap cannot bridge two partial control dwells into a confirmed gain',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m);gain(f);steps(o,6);assert.equal(o.report().teams[0].confirmedGains,0);f.m.time+=1;o.sample();steps(o,3);assert.equal(o.report().teams[0].confirmedGains,0);steps(o,6);assert.equal(o.report().teams[0].confirmedGains,1);assert.equal(o.report().clock.unobservedSeconds,1);o.detach();
});
test('a new receiver must settle before a completed pass can earn a controlled line break',()=>{
 const f=fixture(),second=f.m.players[15];Object.assign(f.r,{x:5,z:0});Object.assign(second,{...f.r,id:second.id,index:second.index,x:7,z:0});Object.assign(f.q,{x:10,z:0});
 const o=Diagnostics.attach(f.m);gain(f);steps(o,9);release(f);Object.assign(f.m.ball,{x:10.3,z:0,y:.11});assert(f.m.acquire(f.q));f.q.touchClock=f.q.decision=100;f.m.planClock=100;o.sample();
 assert.equal(o.report().teams[0].stageCounts.lineBreak,0);steps(o,9);assert.equal(o.report().teams[0].stageCounts.lineBreak,1);o.detach();
});
test('bounded trace retention keeps aggregate counts and summary only returns recent episodes',()=>{
 const f=fixture(),o=Diagnostics.attach(f.m,{maxEpisodes:12});for(let i=0;i<18;i++){f.m.restart=null;f.m.lastTeam=1;f.m.owner=null;Object.assign(f.m.ball,{x:f.p.x+.3,z:f.p.z,y:.11,vx:0,vy:0,vz:0});assert(f.m.acquire(f.p));f.m.setRestart('throw',1,{x:0,z:34});}
 const full=o.report(),summary=o.summary();assert.equal(full.teams[0].attacks,18);assert.equal(full.episodes.length,12);assert.equal(full.truncatedEpisodes,6);assert.equal(summary.episodes.length,0);assert.equal(summary.recentEpisodes.length,10);assert.deepEqual(summary.teams,full.teams);o.detach();
});
