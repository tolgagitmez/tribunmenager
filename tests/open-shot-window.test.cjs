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
