'use strict';
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {Match}=require('../football-sim');
function fixture(team=0){
 const m=new Match({seed:21}),p=m.players[team*11+4],q=m.players[team*11+5],side=m.direction(team);
 m.restart=null;m.goalPause=null;m.kick=null;m.pendingManagerKick=null;m.owner=p;
 Object.assign(p,{active:true,role:'MID',x:0,z:0,face:team===0?0:Math.PI,carryTime:.28,duelMemory:null,escapeUntil:0});
 Object.assign(q,{active:true,role:'MID',x:9*side,z:2,duelRecovery:0});
 m.ball={x:.8*side,y:.11,z:0,vx:0,vy:0,vz:0};
 m.transitionUntil[team]=0;m.supportPlans[team]=null;m.lastTeam=team;
 m.rivals=()=>[{x:5*side,z:0,vx:0,vz:0,face:0,duelRecovery:0}];
 m.shotWindow=()=>({distance:52,quality:0,open:0,execution:0,pressure:0,point:{x:52*side,z:0}});
 m.clearFinish=()=>false;m.crossingOption=()=>null;
 m.carryOption=()=>({kind:'carry',point:{x:6*side,z:4},clearance:1.6,score:6});
 m.threat=()=>0;
 const option=(x=9,risk=.12,score=9)=>({kind:'pass',q,point:{x:side*x,z:2},risk,arrivalRisk:.12,space:7,distance:Math.hypot(x,2),score});
 const first=option();
 m.passOptions=()=>[first];
 m.passPreparation=()=>({feasible:true});
 return {m,p,q,option,first};
}
for(const team of [0,1]){
 test('feasible forward pass is not postponed by the support waiting hold, team '+team,()=>{
  const {m,p,first}=fixture(team),seed=m.seed;
  const choice=m.choose(p);
  assert.equal(choice.kind,'pass');
  assert.equal(choice.q,first.q);
  assert.equal(choice.safeForwardBeforeHold,true);
  assert.equal(m.telemetry.safeForwardBeforeHold,1);
  assert.equal(m.seed,seed);
 });
 test('physically unready or dangerous outlet retains the old conservative hold, team '+team,()=>{
  for(const reason of ['not-feasible','blocked-lane','backward']){
   const {m,p,first}=fixture(team);
   if(reason==='not-feasible')m.passPreparation=()=>({feasible:false});
   if(reason==='blocked-lane')first.risk=.8;
   if(reason==='backward')first.point.x=-9*m.direction(team);
   const choice=m.choose(p);
   assert.equal(choice.kind,'carry',reason);
   assert.equal(choice.hold,true,reason);
   assert.equal(m.telemetry.safeForwardBeforeHold??0,0,reason);
  }
 });
 test('a lower ranked playable forward outlet can beat an infeasible top option, team '+team,()=>{
  const {m,p,first,option}=fixture(team),second=option(10,.20,4);
  m.passOptions=()=>[first,second];
  m.passPreparation=(_actor,candidate)=>({feasible:candidate===second});
  const choice=m.choose(p);
  assert.equal(choice.kind,'pass');assert.equal(choice.point.x,second.point.x);
  assert.equal(m.telemetry.safeForwardBeforeHold,1);
 });
}
