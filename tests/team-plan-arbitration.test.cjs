'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim');
const Perception=require('../player-perception'),Intent=require('../team-intent');
const dt=1/60;
function activate(p,extra={}){return Object.assign(p,{active:true,x:0,z:0,vx:0,vz:0,speed:0,face:0,action:'idle',actionClock:0,actionElapsed:0,receiveClock:0,touchClock:100,tackleClock:100,duelRecovery:0,decision:100,energy:1,stamina:92},extra);}
function fixture(team=0){
 const m=new Match({seed:21,tactics:{passing:'short',playstyle:'possession',fullbacks:'overlap'}});m.restart=null;m.time=10;m.phase='carry';m.players.forEach(p=>p.active=false);
 const owner=activate(m.players[team?11:5],{x:5,z:0,face:team?Math.PI:0});m.owner=owner;m.lastTouch=owner;m.lastTeam=team;m.ball={x:5.8,y:.11,z:0,vx:0,vy:0,vz:0};
 activate(m.players[team?10:21],{x:team?-49:49,z:0,face:team?0:Math.PI});
 activate(m.players[team?7:17],{x:team?-46:46,z:28,face:team?0:Math.PI});m.updateTeamPhases();
 return {m,owner};
}
function point(p){return {x:p.x,z:p.z};}
function commit(m,p,state,destination,partnerId=m.owner.id,focusId=null){return Intent.resolve(p,{...destination,state,pace:state==='build-support'?.98:1.07,priority:30,partnerId,focusId},m.taskContext(p));}
function commands(m,team){return [...m.targets].filter(([p])=>p.team===team).map(([p,t])=>[p.id,t]);}

test('a retained penetration destination is also the destination advertised to the passer',()=>{
 const {m,owner}=fixture(),runner=activate(m.players[0],{x:9,z:6});
 commit(m,runner,'penetration',{x:19,z:9});
 m.attackPlans[0]={ownerTeam:0,epoch:m.attackEpoch[0],zone:0,until:12,runner:{id:runner.id,point:{x:23,z:9},score:10}};
 m.time+=.16;m.plan();const selected=m.targets.get(runner);assert.equal(selected.state,'penetration');assert.equal(selected.x,19);
 assert.deepEqual(m.attackPlans[0].runner.point,point(selected));assert.deepEqual(m.plannedRun(runner),point(selected));assert.equal(runner.task.partnerId,owner.id);
});
test('box runs advertise the actual retained near-post destination',()=>{
 const {m,owner}=fixture();Object.assign(owner,{x:35,z:20});Object.assign(m.ball,{x:35.8,z:20});
 const near=activate(m.players[0],{x:31,z:4}),far=activate(m.players[1],{x:34,z:-7});
 commit(m,near,'box-run',{x:39,z:3.5});
 m.boxPlans[0]={source:owner.id,flank:1,epoch:m.attackEpoch[0],until:13,points:new Map([[near.id,{x:42,z:3.5,state:'box-run',role:'near-post'}],[far.id,{x:44,z:-7,state:'box-run',role:'far-post'}]])};
 m.time+=.16;m.plan();const selected=m.targets.get(near);assert.equal(selected.state,'box-run');assert.equal(selected.x,39);assert.deepEqual(point(m.boxPlans[0].points.get(near.id)),point(selected));
});
test('build support records the selected connection after target arbitration',()=>{
 const {m,owner}=fixture();Object.assign(owner,{x:-20,z:0});Object.assign(m.ball,{x:-19.2,z:0});
 const helper=activate(m.players[3],{x:-12,z:8});const proposed=m.buildOutSupport(0,owner);assert.equal(proposed.id,helper.id);
 const held={x:proposed.point.x-2.5,z:proposed.point.z};commit(m,helper,'build-support',held);
 m.time+=.16;m.plan();const selected=m.targets.get(helper);assert.equal(selected.state,'build-support');assert.deepEqual(point(selected),held);assert.deepEqual(m.buildPlans[0].point,point(selected));
});
test('a reused flank plan publishes the overlap destination that survived arbitration',()=>{
 const {m,owner}=fixture();Object.assign(owner,{x:15,z:20});Object.assign(m.ball,{x:15.8,z:20});
 const fullback=activate(m.players[9],{x:9,z:25});commit(m,fullback,'overlap',{x:20,z:31});
 m.flankPlans[0]={sourceId:owner.id,fullbackId:fullback.id,epoch:m.attackEpoch[0],origin:{x:owner.x,z:owner.z},point:{x:23,z:31},state:'overlap',until:13};
 m.time+=.16;m.plan();const selected=m.targets.get(fullback);assert.equal(selected.state,'overlap');assert.equal(selected.x,20);assert.deepEqual(m.flankPlans[0].point,point(selected));
});
function defenceFixture(){
 const {m,owner}=fixture(1);Object.assign(owner,{x:10,z:0,face:Math.PI});Object.assign(m.ball,{x:10.8,z:0});
 const presser=activate(m.players[3],{x:9,z:0}),cover=activate(m.players[4],{x:2,z:5}),first=activate(m.players[7],{x:-8,z:4}),second=activate(m.players[8],{x:-10,z:-8}),runner=activate(m.players[12],{x:-5,z:0});
 return {m,owner,presser,cover,first,second,runner};
}
test('a coordinated marking handoff drops the old commitment before the new marker takes it',()=>{
 const {m,first,second,runner}=defenceFixture();m.plan();const old=[...m.defensiveUnits[0].assignments].find(([,q])=>q.id===runner.id)?.[0];assert(old);assert(['mark','track-run'].includes(m.targets.get(old).state));
 const replacement=old===first?second:first;Object.assign(old,{x:-30,z:15});Object.assign(replacement,{x:-6,z:0});m.time+=.16;m.plan();
 const selected=commands(m,0).filter(([,t])=>['mark','track-run'].includes(t.state)&&t.focusId===runner.id);
 assert.equal(selected.length,1);assert.equal(selected[0][0],replacement.id);assert(!['mark','track-run'].includes(m.targets.get(old).state));assert(old.taskHistory.some(e=>e.reason==='team-handoff'));
});
test('an urgent coordinated press handoff produces one presser and releases the old presser',()=>{
 const {m,presser,cover}=defenceFixture();m.plan();assert.equal(m.pressAssignments[0].player.id,presser.id);assert.equal(m.targets.get(presser).state,'press');
 Object.assign(presser,{x:-10,z:15});Object.assign(cover,{x:10,z:0});m.time+=.16;m.plan();
 const selected=commands(m,0).filter(([,t])=>['press','counterpress','intercept'].includes(t.state));assert.equal(selected.length,1);assert.equal(selected[0][0],cover.id);
 assert.equal(m.pressAssignments[0].player.id,cover.id);assert(!['press','counterpress','intercept'].includes(m.targets.get(presser).state));assert(presser.taskHistory.some(e=>e.reason==='team-handoff'));
});
test('the nearest blind marker leaves the assignment for the available marker who observed the runner',()=>{
 const {m,owner}=fixture(1);Object.assign(owner,{x:0,z:0});Object.assign(m.ball,{x:.8,z:0});
 const blind=activate(m.players[7],{x:20,z:0,face:0,homeZ:0}),seeing=activate(m.players[8],{x:23,z:0,face:Math.PI,homeZ:0}),runner=activate(m.players[12],{x:15,z:0});
 Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;
 assert(!m.rivals(blind).some(q=>q.id===runner.id));assert(m.rivals(seeing).some(q=>q.id===runner.id));
 const unit=m.defensiveUnit(0,owner,0,[blind,seeing],m.teamRivals(0),null,null);assert.equal(unit.assignments.get(seeing)?.id,runner.id);assert.equal(unit.assignments.has(blind),false);
});
test('a visible shooter can trigger a block without exposing the private shot aim',()=>{
 const {m,owner}=fixture(1);Object.assign(owner,{x:20,z:0,face:Math.PI});Object.assign(m.ball,{x:19.2,z:0});
 const blocker=activate(m.players[7],{x:15,z:0,face:0});Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;
 m.kick={p:owner,kind:'shot',target:null};Object.defineProperty(m.kick,'point',{get(){throw Error('defender read private opponent shot aim');}});
 assert.doesNotThrow(()=>m.plan());assert.equal(m.targets.get(blocker).state,'block');
});
function flightFixture(destination){
 const {m,owner}=fixture(1);m.owner=null;Object.assign(owner,{x:0,z:0});Object.assign(m.ball,{x:-10,z:0,vx:-15,vz:0});
 const defender=activate(m.players[7],{x:-18,z:5,face:0});m.flight={id:31,from:owner,target:null,kind:'through',age:.2,point:destination};
 return {m,defender};
}
test('defensive flight interception cannot read an untargeted opponents private intended destination',()=>{
 const {m,defender}=flightFixture({x:-25,z:0});Object.defineProperty(m.flight,'point',{get(){throw Error('defender read private opponent pass destination');}});
 assert.doesNotThrow(()=>m.plan());assert.equal(m.targets.get(defender).state,'track-run');
});
test('changing only the private pass destination leaves every defensive command identical',()=>{
 const a=flightFixture({x:-25,z:0}),b=flightFixture({x:30,z:30});a.m.plan();b.m.plan();assert.deepEqual(commands(a.m,0),commands(b.m,0));
});
test('settled carrying follows the selected .34 and .60 pace in the actual frame',()=>{
 const {m,owner}=fixture();Object.assign(owner,{x:0,z:0});Object.assign(m.ball,{x:.88,z:.18});
 m.startCarry(owner,{kind:'carry',point:{x:5,z:0},hold:true,commit:.65});
 for(const [time,pace]of [[10,.34],[10.7,.60]]){
  m.time=time;m.planClock=0;const expected=m.projectPlayer(owner,dt,{x:5,z:0,pace,state:'dribble'}).player;
  m.step(dt);assert.equal(m.targets.get(owner).pace,pace);
  for(const key of['x','z','vx','vz','speed','face'])assert.equal(owner[key],expected[key],`pace ${pace}: ${key}`);
 }
});
test('a shooting windup does not open a head-scan window onto a blind opponent',()=>{
 const {m,owner}=fixture();Object.assign(owner,{x:0,z:0,face:0});const blind=activate(m.players[14],{x:-5,z:0});
 Perception.clear(owner,m.time);Perception.update(m.players,m.time,0,{scanAllowed:false});assert(!Perception.rivals(owner,m.time).some(q=>q.id===blind.id));
 owner.action='shoot';owner.actionClock=.8;owner.perception.nextScanAt=m.time+.01;m.time+=.02;
 Perception.update(m.players,m.time,.02,{scanAllowed:true});assert.equal(owner.perception.headYaw,0);assert(!Perception.rivals(owner,m.time).some(q=>q.id===blind.id));assert.equal(owner.face,0);
});
test('a run producer rejected by the accepted support task is not advertised as a planned run',()=>{
 const {m,owner}=fixture(),helper=activate(m.players[3],{x:2,z:8});
 commit(m,helper,'support',{x:2,z:8});helper.runIntent={kind:'give-go',partnerId:owner.id,origin:{x:0,z:8},point:{x:15,z:8},epoch:m.attackEpoch[0],until:13};
 m.time+=.16;m.plan();assert.equal(m.targets.get(helper).state,'support');assert.equal(m.plannedRun(helper),null);
 assert.equal(helper.runIntent.point.x,15,'the producer wish remains distinct from the accepted task');
});
test('an accepted run advertises its retained task point while a conflicting raw run intent waits',()=>{
 const {m,owner}=fixture(),runner=activate(m.players[0],{x:9,z:6});
 commit(m,runner,'channel-run',{x:19,z:9});runner.runIntent={kind:'give-go',partnerId:owner.id,origin:{x:7,z:6},point:{x:23,z:9},epoch:m.attackEpoch[0],until:13};
 m.time+=.16;m.plan();assert.equal(m.targets.get(runner).state,'channel-run');assert.deepEqual(point(m.targets.get(runner)),{x:19,z:9});
 assert.deepEqual(m.plannedRun(runner),{x:19,z:9});assert.deepEqual(runner.runIntent.point,{x:23,z:9});
});
function pressLaneFixture(ownerZ,observeOwner=false){
 const {m,owner}=fixture();m.players.forEach(p=>p.active=false);activate(owner,{x:0,z:ownerZ});
 const first=activate(m.players[0],{x:10,z:-4}),second=activate(m.players[1],{x:10,z:4});
 const presser=activate(m.players[14],{x:4,z:0,face:0}),cover=activate(m.players[15],{x:3,z:0,face:0});
 m.ball={x:0,y:.11,z:0,vx:0,vy:0,vz:0};Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;
 if(observeOwner){cover.face=Math.PI;Perception.update(m.players,m.time,0,{scanAllowed:false});}
 assert.deepEqual(m.rivals(cover).filter(q=>q.id!==owner.id).map(q=>q.id),[first.id,second.id]);
 assert.equal(m.rivals(cover).some(q=>q.id===owner.id),observeOwner);
 for(const key of['x','z'])Object.defineProperty(owner,key,{get(){throw Error('press unit read an unobserved live owner '+key);}});
 return {m,owner,presser,cover,first,second,query:()=>m.pressUnit(1,owner,presser,cover,{assignments:new Map()},{active:true})};
}
test('a press lane cannot read a hidden owner position or change when only that hidden position changes',()=>{
 const first=pressLaneFixture(-1),second=pressLaneFixture(1);
 assert.deepEqual(first.m.rivals(first.cover),second.m.rivals(second.cover),'the cover has the same actual observations in both worlds');
 const a=first.query(),b=second.query();assert.deepEqual(a,b);assert.equal(a.receiverId,first.first.id);
 // The retained receiver branch must use the same observed origin as initial selection.
 first.m.time+=.16;second.m.time+=.16;assert.deepEqual(first.query(),second.query());
});
test('a newly observed owner origin can change the screened passing lane',()=>{
 const first=pressLaneFixture(-1,true),second=pressLaneFixture(1,true),a=first.query(),b=second.query();
 assert.equal(a.receiverId,first.first.id);assert.equal(b.receiverId,second.second.id);
 assert.notDeepEqual(a.pressPoint,b.pressPoint);assert.notDeepEqual(a.coverPoint,b.coverPoint);
});
function returnPassHandoffFixture(velocity=-8,targetReceiver=false){
 const {m,owner}=fixture(1);m.players.forEach(p=>p.active=false);m.owner=null;
 activate(owner,{role:'MID',x:20,z:20});
 const defender=activate(m.players[7],{role:'DEF',x:-21,z:0,homeZ:0}),helper=activate(m.players[3],{role:'MID',x:-30,z:8,homeZ:8}),receiver=activate(m.players[12],{role:'ATT',x:-20,z:0});
 m.ball={x:-30,y:.11,z:0,vx:velocity,vy:0,vz:0};m.t[0].marking='zone';
 Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;
 m.flight={id:32,from:owner,target:targetReceiver?receiver:owner,kind:'pass',age:.2};
 const query=()=>m.defensiveUnit(0,null,-38,[defender,helper],m.teamRivals(0),null,null);
 return {m,owner,defender,helper,receiver,query};
}
const handoffSummary=unit=>({assignments:[...unit.assignments].map(([p,q])=>[p.id,q.id]),screeners:[...unit.cutbackScreeners].map(p=>p.id),heldMarkers:[...unit.heldMarkers].map(p=>p.id)});
test('a defensive handoff ignores the private pass target identity with the same observed ball path',()=>{
 const first=returnPassHandoffFixture(-8,false),second=returnPassHandoffFixture(-8,true);
 assert.deepEqual(first.m.ball,second.m.ball);assert.deepEqual(first.m.rivals(first.defender),second.m.rivals(second.defender));
 const a=handoffSummary(first.query()),b=handoffSummary(second.query());assert.deepEqual(a,b);assert.deepEqual(a.assignments,[[first.helper.id,first.receiver.id]]);
 for(const {m}of[first,second])Object.defineProperty(m.flight,'target',{get(){throw Error('defensive handoff read the private opponent receiver');}});
 assert.deepEqual(handoffSummary(first.query()),a);assert.deepEqual(handoffSummary(second.query()),b);
});
test('an observed ball travelling toward a marked runner delays the distant return-pass handoff',()=>{
 const away=returnPassHandoffFixture(-8,true),incoming=returnPassHandoffFixture(20,false);
 assert.deepEqual(away.m.rivals(away.defender),incoming.m.rivals(incoming.defender),'only the public ball velocity changes');
 for(const {m}of[away,incoming])Object.defineProperty(m.flight,'target',{get(){throw Error('visible trajectory must supply the handoff cue');}});
 const a=handoffSummary(away.query()),b=handoffSummary(incoming.query());
 assert.deepEqual(a.assignments,[[away.helper.id,away.receiver.id]]);assert.deepEqual(a.screeners,[away.helper.id]);
 assert.deepEqual(b.assignments,[[incoming.defender.id,incoming.receiver.id]]);assert.deepEqual(b.screeners,[]);
});
