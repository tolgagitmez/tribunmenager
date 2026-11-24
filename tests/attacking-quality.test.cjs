'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),Brain=require('../player-brain');
function fixture(mirror=1){
 const m=new Match({seed:113,individualAI:true});
 if(mirror<0)m.period=2;
 for(const p of m.players)p.active=false;
 const set=(i,role,x,z,extra={})=>Object.assign(m.players[i],{active:true,role,x:x*mirror,z,homeX:x*mirror,homeZ:z,vx:0,vz:0,face:mirror>0?0:Math.PI,energy:1,speed:0,task:null,runIntent:null,supportIntent:null,duelRecovery:0,receiveClock:0},extra);
 const owner=set(5,'MID',8,0,{position:'AM',vision:95});
 const link=set(6,'MID',19,0,{position:'AM',vision:95});
 const mid=set(15,'MID',14,-8),back=set(17,'DEF',30,8),keeper=set(21,'GK',49,0);
 m.owner=owner;m.restart=null;m.kick=null;m.flight=null;m.goalPause=null;m.lastTeam=0;m.time=10;
 m.ball={x:owner.x,y:.11,z:owner.z,vx:0,vy:0,vz:0};m.targets=new Map();m.updateTeamPhases();
 return {m,set,owner,link,mid,back,keeper};
}
test('connection uses a reachable observed midfield-defence pocket and mirrors across halves',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid}=fixture(side);
  m.laneRisk=()=>.1;
  const p=m.connectionPoint(owner,link,-12,30);
  assert.equal(p.inPocket,true);
  assert(p.x*side>=16&&p.x*side<=28);
  assert(p.space>2.5&&p.risk<.42);
  mid.active=false;link.connectionIntent=null;
  assert.equal(m.connectionPoint(owner,link,-12,30).inPocket,false);
 }
});
test('central attack allocates separate legal striker and winger lanes without a wide ball',()=>{
 for(const side of [1,-1]){
  const {m,set,owner,link,back}=fixture(side);
  owner.x=28*side;owner.z=2;m.ball.x=owner.x;m.ball.z=owner.z;
  link.active=false;back.x=43*side;back.z=20;
  const st=set(1,'ATT',31,0,{position:'ST'}),wing=set(2,'ATT',30,-13,{position:'LW'});
  const plan=m.boxAttack(0,owner);
  assert(plan.central);
  const a=plan.points.get(st.id),b=plan.points.get(wing.id);
  assert(a&&b);assert.equal(a.role,'near-post');assert.equal(b.role,'far-post');
  assert(Math.hypot(a.x-b.x,a.z-b.z)>=6);
  for(const [p,q] of [[st,a],[wing,b]]){
   assert(q.x*side>=35.5);assert(q.x*side<=43-Brain.runMargin(p,side)+1e-8);
  }
  back.x=29*side;
  assert.equal(m.boxAttack(0,owner).points.size,0);
 }
});
test('shot read chooses the opposite side of a displaced keeper and a clear finish skips speculative forecasts',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back,keeper}=fixture(side);
  owner.x=45*side;owner.z=0;link.active=mid.active=back.active=false;
  keeper.z=1.5;const left=m.shotWindow(owner);assert(left.point.z<0);
  keeper.z=-1.5;const right=m.shotWindow(owner);assert(right.point.z>0);
  assert(m.clearFinish(owner,right));
  m.passOptions=()=>{throw Error('unneeded pass forecast');};
  m.crossingOption=m.carryOption=m.passOptions;
  assert.equal(m.choose(owner).kind,'shot');
 }
});
