'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),Brain=require('../player-brain');
for(const team of [0,1]){
 function fixture(){
  const m=new Match({seed:91,individualAI:true}),side=m.direction(team);
  for(const p of m.players)p.active=false;
  const source=m.players[team*11+3],runner=m.players[team*11+1],edge=m.players[team*11+5],anchor=m.players[team*11+4],rival=m.players[(1-team)*11+7];
  const set=(p,attrs)=>Object.assign(p,{active:true,vx:0,vz:0,energy:1,duelRecovery:0,task:null,runIntent:null,supportIntent:null},attrs);
  set(source,{x:25*side,z:0,role:'MID',position:'CM',face:team?Math.PI:0});
  set(runner,{x:34*side,z:4,role:'ATT',position:'ST',pace:90});
  set(edge,{x:27*side,z:-12,role:'MID',position:'CM',homeZ:-12});
  set(anchor,{x:24*side,z:12,role:'MID',position:'DM'});
  set(rival,{x:20*side,z:20,role:'DEF'});
  m.owner=source;m.restart=null;m.flight=null;m.kick=null;m.time=10;m.lastTeam=team;m.ball={x:25*side,z:0,y:.11,vx:0,vz:0,vy:0};
  m.observedLine=()=>44;m.laneRisk=()=>.1;
  return {m,source,runner,edge,anchor,side};
 }
 test('central scoring support remains reachable, onside and preserves the anchor, team '+team,()=>{
  const {m,source,runner,edge,anchor,side}=fixture(),before={...m.ball},seed=m.seed;
  const plan=m.boxAttack(team,source);
  assert(plan?.central);assert.equal(plan.points.get(runner.id).role,'central-run');assert.equal(plan.points.get(edge.id).role,'central-edge');assert(!plan.points.has(anchor.id));
  for(const [id,q] of plan.points){const p=m.players[id];assert(q.x*side<=44-Brain.runMargin(p,side)+1e-9);assert(Math.hypot(q.x-p.x,q.z-p.z)<=10);}
  assert.deepEqual(m.ball,before);assert.equal(m.seed,seed);
  assert.equal(m.boxAttack(team,source).until,plan.until);
 });
 test('central plan avoids reserved roles, closed lanes and unavailable onside space, team '+team,()=>{
  for(const variant of ['runner-reserved','blocked','offside','disabled','deep']){
   const {m,source,runner,side}=fixture();let pattern=null;
   if(variant==='runner-reserved')pattern={runner:{id:runner.id}};
   if(variant==='blocked')m.laneRisk=()=>.9;
   if(variant==='offside')m.observedLine=()=>30;
   if(variant==='disabled')m.cfg.individualAI=false;
   if(variant==='deep')source.x=5*side;
   assert.equal(m.boxAttack(team,source,pattern),null,variant);
  }
 });
}
