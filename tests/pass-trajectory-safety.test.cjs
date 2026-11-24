'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim');
function fixture(team=0){
 const m=new Match({seed:93,individualAI:true});
 for(const p of m.players)p.active=false;
 const p=m.players[team*11+4],q=m.players[team*11+7],side=m.direction(team);
 Object.assign(p,{active:true,role:'MID',position:'AM',x:0,z:0,vx:0,vz:0,face:team?Math.PI:0,vision:95,passing:95,composure:90});
 Object.assign(q,{active:true,role:'ATT',position:'ST',x:16*side,z:0,vx:0,vz:0,pace:90});
 m.owner=p;m.kick=null;m.restart=null;m.flight=null;m.goalPause=null;m.lastTeam=team;
 m.ball={x:0,z:1.2,y:.11,vx:0,vy:0,vz:0};
 m.t[team].passing='mixed';m.observedLine=()=>19;
 m.rivals=()=>[{id:999,active:true,x:19*side,z:25,vx:0,vz:0,pace:80,role:'DEF'}];
 m.receiverPoint=()=>({x:q.x,z:q.z});
 return {m,p,q,side};
}
for(const team of [0,1]){
 test('ground pass corridor follows the offset ball rather than the body, team '+team,()=>{
  const {m,p,side}=fixture(team),rival={x:10*side,z:1.2,vx:0,vz:0,touchClock:0,duelRecovery:0};
  const point={x:20*side,z:1.2},seed=m.seed,ball={...m.ball};
  const corrected=m.laneRisk(p,point,23,'pass',[rival]);
  m.cfg.individualAI=false;const legacy=m.laneRisk(p,point,23,'pass',[rival]);
  assert(corrected>legacy+.1,{corrected,legacy});
  assert.deepEqual(m.ball,ball);assert.equal(m.seed,seed);
 });
 test('through ball evaluates its own destination and arrival rather than borrowing safe feet pass, team '+team,()=>{
  const {m,p,q,side}=fixture(team),reads=[];
  m.laneRisk=(_p,_point,speed,kind)=>{if(kind==='through')assert.equal(speed,21);return .1;};
  m.receptionSafety=(_p,_q,point,seconds)=>{reads.push({point,seconds});return {risk:point.x*side>19?.95:.1,pressure:12};};
  const rejected=m.passOptions(p);
  assert(rejected.some(o=>o.q===q&&o.kind==='pass'));
  assert(!rejected.some(o=>o.kind==='through'));
  assert(reads.some(r=>r.point.x*side>19&&Number.isFinite(r.seconds)));
  m.receptionSafety=(_p,_q,point)=>({risk:point.x*side>19?.32:.1,pressure:12});
  const accepted=m.passOptions(p).find(o=>o.q===q&&o.kind==='through');
  assert(accepted);assert.equal(accepted.arrivalRisk,.32);assert(accepted.risk>.1);
 });
}
