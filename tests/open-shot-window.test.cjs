'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim');
for(const team of [0,1]){
 function fixture(){
  const m=new Match({seed:77,individualAI:true}),p=m.players[team*11+7],q=m.players[team*11+8],side=m.direction(team);
  Object.assign(p,{active:true,role:'ATT',position:'ST',x:30.5*side,z:0,face:team?Math.PI:0,speed:0,vx:0,vz:0,shooting:82,energy:1,receiveClock:0});
  m.owner=p;m.restart=null;m.kick=null;m.flight=null;m.ball={x:p.x+.8*side,z:.18,y:.11,vx:0,vz:0,vy:0};
  m.t[team].shooting='normal';m.rivals=()=>[];
  const shot=m.shotWindow(p);
  return {m,p,q,side,shot};
 }
 test('a controlled open medium-range shot does not require a nearby defender, team '+team,()=>{
  const {m,p,shot}=fixture(),seed=m.seed,ball={...m.ball};
  assert(shot.quality>.115);assert(shot.distance>19);assert.equal(m.clearFinish(p,shot),false);
  assert.equal(m.openShotChoice(p,shot,[],12),true);
  assert.deepEqual(m.ball,ball);assert.equal(m.seed,seed);
 });
 test('a better safe central entry pass, blocked shot, poor balance, fatigue and patient tactics beat the open shot, team '+team,()=>{
  const {m,p,q,side,shot}=fixture();
  const pass={q,kind:'pass',point:{x:42*side,z:3},risk:.15,arrivalRisk:.2,space:5};
  assert.equal(m.openShotChoice(p,shot,[pass],12),false);
  assert.equal(m.openShotChoice(p,shot,[{...pass,risk:.9}],12),true);
  for(const changed of [{open:.2},{turn:1.1},{pressure:.7},{execution:.4},{quality:.04}])assert.equal(m.openShotChoice(p,{...shot,...changed},[],12),false);
  p.energy=.2;assert.equal(m.openShotChoice(p,shot,[],12),false);p.energy=1;
  m.t[team].shooting='patient';assert.equal(m.openShotChoice(p,shot,[],12),false);
  m.t[team].shooting='early';assert.equal(m.openShotChoice(p,shot,[],12),true);
  m.cfg.individualAI=false;assert.equal(m.openShotChoice(p,shot,[],12),false);
 });
}

for(const team of [0,1]){
 function stalledFixture(){
  const m=new Match({seed:97,individualAI:true}),p=m.players[team*11+5],q=m.players[team*11+7],back=m.players[team*11+6],side=m.direction(team);
  Object.assign(p,{active:true,role:'MID',position:'CM',x:-8*side,z:0,face:team?Math.PI:0,energy:1,carryTime:.4});
  Object.assign(q,{active:true,role:'ATT',x:2*side,z:0,duelRecovery:0});
  Object.assign(back,{active:true,role:'DEF',x:-12*side,z:4,duelRecovery:0});
  m.owner=p;m.restart=null;m.kick=null;m.flight=null;m.time=10;m.lastTeam=team;
  m.t[team].playstyle='possession';m.recentPasses=[5,7,9].map((time,i)=>({from:back.id,to:p.id,time,team,depth:-8+i*.2,epoch:m.attackEpoch[team],period:m.period,stoppage:m.stoppageSerial}));
  const pass={kind:'pass',q,point:{x:2*side,z:0},risk:.14,arrivalRisk:.24,space:5,distance:10,score:5};
  const recycle={kind:'pass',q:back,point:{x:-12*side,z:4},risk:.08,arrivalRisk:.1,space:8,distance:6,score:10};
  m.passPreparation=()=>({feasible:true});
  return {m,p,q,side,pass,recycle};
 }
 test('stagnant completed pass chain can prioritize a lower-ranked safe forward outlet, team '+team,()=>{
  const {m,p,pass,recycle}=stalledFixture(),seed=m.seed,ball={...m.ball};
  const choice=m.stalledPassOutlet(p,[recycle,pass],7);
  assert.equal(choice?.q,pass.q);assert.equal(choice.stalledOutlet,true);
  assert.deepEqual(m.ball,ball);assert.equal(m.seed,seed);
 });
 test('progressing possession, stale records, dangerous/unready outlets and protective tactics do not trigger progression override, team '+team,()=>{
  for(const variant of ['progress','stale','epoch','stoppage','pressure','risk','arrival','unready','already-forward','protect','disabled']){
   const {m,p,pass,recycle}=stalledFixture();let options=[recycle,pass],pressure=7;
   if(variant==='progress')m.recentPasses[0].depth=-19;
   if(variant==='stale')m.recentPasses[0].time=0;
   if(variant==='epoch')m.recentPasses[0].epoch--;
   if(variant==='stoppage')m.recentPasses[0].stoppage--;
   if(variant==='pressure')pressure=2;
   if(variant==='risk')pass.risk=.7;
   if(variant==='arrival')pass.arrivalRisk=.8;
   if(variant==='unready')m.passPreparation=()=>({feasible:false});
   if(variant==='already-forward')options=[pass,recycle];
   if(variant==='protect')m.matchContext=()=>({protect:true});
   if(variant==='disabled')m.cfg.individualAI=false;
   assert.equal(m.stalledPassOutlet(p,options,pressure),null,variant);
  }
 });
}
