'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Brain=require('../player-brain.js'),Intent=require('../team-intent.js'),{Match}=require('../football-sim.js');
const actor=(extra={})=>({id:2,team:0,active:true,role:'ATT',position:'ST',x:14,z:-3,vx:0,vz:0,face:0,pace:94,vision:94,composure:92,acceleration:93,agility:89,energy:1,...extra});
const owner=actor({id:1,role:'MID',position:'AM',x:4,z:0,passing:94,vision:95});
const marker={id:11,role:'DEF',x:17,z:0,face:Math.PI,vx:0,vz:0,confidence:1,age:0};
const back={id:12,role:'DEF',x:24,z:20,face:Math.PI,vx:0,vz:0,confidence:1,age:0};
const options={forward:1,line:24,opponents:[marker,back]};
test('an intelligent fast runner selects a lateral forward blind-side lane on observed defenders',()=>{
 const p=actor(),before=structuredClone(p),r=Brain.offBallOption(p,owner,options);
 assert(r,'qualified runner must offer a real channel');
 assert.equal(r.kind,'blind-side');
 assert(r.point.x>p.x+1.2&&r.point.x<=24-Brain.runMargin(p,1));
 assert(Math.abs(r.point.z-p.z)>=3);
 assert.equal(r.markerId,marker.id);assert.deepEqual(p,before);
 const faced={...marker,face:0};
 const diagonal=Brain.offBallOption(p,owner,{...options,opponents:[faced,back]});
 assert(diagonal);assert.equal(diagonal.kind,'diagonal');
});
test('runs require current personal observation, tactical role, speed, skill and onside runway',()=>{
 const variants=[actor({vision:55,composure:55,acceleration:55}),actor({pace:60}),
 actor({role:'DEF'}),actor({role:'MID',position:'DM'}),actor({energy:.2}),actor({x:23.8})];
 for(const p of variants)assert.equal(Brain.offBallOption(p,owner,options),null);
 assert.equal(Brain.offBallOption(actor(),owner,{...options,opponents:[]}),null);
 assert.equal(Brain.offBallOption(actor(),owner,{...options,opponents:[{...marker,age:1,confidence:.2}]}),null);
});
test('braking margin is directional, increases with real forward velocity, and mirrors at halftime',()=>{
 assert(Brain.runMargin(actor({vx:5}),1)>Brain.runMargin(actor({vx:0}),1)+1.5);
 assert.equal(Brain.runMargin(actor({vx:-5}),1),Brain.runMargin(actor(),1));
 const a=Brain.offBallOption(actor(),owner,options);
 const mirror=p=>({...p,x:-p.x,vx:-(p.vx||0),face:Math.PI-p.face});
 const b=Brain.offBallOption(mirror(actor()),mirror(owner),{forward:-1,line:24,opponents:[mirror(marker),mirror(back)]});
 assert(b);assert.equal(b.kind,a.kind);assert(Math.abs(b.point.x+a.point.x)<1e-8);assert.equal(b.point.z,a.point.z);
});
test('decoy is never credited for a defender that stayed put or an unobserved movement',()=>{
 const carrier={id:1,x:0,z:0},runner={id:2,point:{x:18,z:0}};
 const p=actor({id:3,x:7,z:1.5}),blocker={id:12,role:'DEF',x:8,z:1.5,age:0,confidence:1};
 const decoy=Brain.decoyOption(p,carrier,runner,{forward:1,line:23,opponents:[blocker]});
 assert(decoy,'a nearby actual blocker can be invited away from the lane');
 assert(decoy.point.z>p.z+3);
 assert.equal(Brain.decoyOpened(decoy,blocker,runner.point,carrier,p),false);
 const moved={...blocker,z:6},after={...p,z:7};
 assert.equal(Brain.decoyOpened(decoy,moved,runner.point,carrier,after),true);
 assert.equal(Brain.decoyOpened(decoy,{...moved,confidence:.1},runner.point,carrier,after),false);
 assert.equal(Brain.decoyOpened(decoy,moved,runner.point,carrier,p),false);
 assert.equal(Brain.runPassBias(owner,{kind:'decoy-opening',risk:.1,arrivalRisk:.2,space:5})>0,true);
 assert.equal(Brain.runPassBias(owner,{kind:'decoy-opening',risk:.9,arrivalRisk:.2,space:5}),0);
});
function fixture(){
 const m=new Match({seed:77,individualAI:true});
 for(const p of m.players)p.active=false;
 const carrier=m.players[5],runner=m.players[8],d=m.players[17],d2=m.players[18],gk=m.players[11];
 const set=(p,properties)=>Object.assign(p,{active:true,vx:0,vz:0,speed:0,face:0,energy:1,receiveClock:0,duelRecovery:0,touchClock:0,task:null,runIntent:null,supportIntent:null},properties);
 set(carrier,{role:'MID',position:'AM',x:4,z:0,vision:96,passing:95,composure:90,homeX:0,homeZ:0});
 set(runner,{role:'ATT',position:'ST',x:14,z:-3,vision:95,composure:92,acceleration:93,agility:90,pace:95,homeX:12,homeZ:-3});
 set(d,{role:'DEF',x:17,z:0,face:Math.PI,homeZ:0});
 set(d2,{role:'DEF',x:24,z:20,face:Math.PI,homeZ:20});
 set(gk,{role:'GK',x:49,z:0,face:Math.PI});
 m.restart=null;m.kick=null;m.flight=null;m.time=10;m.owner=carrier;m.lastTeam=0;
 m.ball={x:4.88,z:.18,y:.11,vx:0,vz:0,vy:0};
 m.targets=new Map();m.updateTeamPhases();
 return {m,carrier,runner,d,d2};
}
test('real team planner commits and publishes a run rather than bypassing task arbitration',()=>{
 const {m,carrier,runner}=fixture();
 const plan=m.coordinatedAttack(0,carrier,24);
 assert.equal(plan.runner.id,runner.id);
 assert(['blind-side','diagonal'].includes(plan.runner.kind),'qualified run must actually be selected by team planner');
 m.plan();
 const result=m.targets.get(runner);
 assert.equal(result.state,'penetration');
 assert.equal(runner.task.partnerId,carrier.id);
 assert.equal(m.attackPlans[0].runner.accepted,true);
 assert.deepEqual(m.plannedRun(runner),{x:result.x,z:result.z});
 assert(m.offBallRead(carrier,runner));
 assert(result.x<=24-Brain.runMargin(runner,1)+1e-8);
});
test('pass options can read only an accepted current run and never mark a closed lane as safe',()=>{
 const {m,carrier,runner}=fixture();
 m.plan();
 assert(m.offBallRead(carrier,runner),'fixture must have accepted advanced run');
 m.t[0].passing='mixed';
 m.receiverPoint=()=>({x:runner.x,z:runner.z});
 m.receptionSafety=()=>({risk:.1,pressure:9});
 m.laneRisk=()=>.1;
 const safe=m.passOptions(carrier);
 assert(safe.some(o=>o.q===runner&&o.kind==='pass'&&o.offBallKind),'safe committed movement is read by real passer');
 m.laneRisk=()=>.95;
 assert(!m.passOptions(carrier).some(o=>o.offBallKind),'a closed lane cannot earn skill credit');
 runner.task.partnerId=999;
 assert.equal(m.offBallRead(carrier,runner),null);
});
test('special receiver stages behind line before physical through release, then pursues flight normally',()=>{
 const {m,carrier,runner}=fixture();m.plan();
 assert(m.offBallRead(carrier,runner));
 assert(m.startKick(carrier,'through',runner,{x:28,z:-8}));
 assert.equal(m.kick.timedRun,true);
 m.plan();
 assert.equal(m.targets.get(runner).state,'receive-run');
 assert(m.targets.get(runner).x<=24-Brain.runMargin(runner,1)+1e-8);
 // Model an already released pass; actual legal contact remains under
 // release()/captureOffside(), not under the off-ball planner.
 m.kick=null;m.owner=null;m.flight={id:1,from:carrier,target:runner,kind:'through',point:{x:28,z:-8},age:.05,offsidePlayers:[]};
 m.ball={x:7,z:-1,y:.11,vx:16,vz:-5,vy:0};
 m.plan();
 assert.equal(m.targets.get(runner).state,'receive-run');
 assert(m.targets.get(runner).x>24,'after release the intended target may run beyond the old offside line');
});
test('decoy tasks are bounded attack runs, never independently advertised as a planned receiving run',()=>{
 const {m,carrier,runner}=fixture();
 const result=Intent.resolve(runner,{x:18,z:-9,state:'decoy-run',pace:1.04,priority:30,partnerId:carrier.id},m.taskContext(runner));
 assert.equal(result.purpose,'run');assert.equal(m.plannedRun(runner),null);
});
test('disabled advanced runs preserve the generated fixture and consume no extra random draws',()=>{
 const a=new Match({seed:51}),b=new Match({seed:51,individualAI:false});
 for(let i=0;i<360;i++){a.step(1/60);b.step(1/60);}
 assert.equal(a.seed,b.seed);assert.deepEqual(a.ball,b.ball);assert.deepEqual(a.events,b.events);assert.deepEqual(a.score,b.score);
});
