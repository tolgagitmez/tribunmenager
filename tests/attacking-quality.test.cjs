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

test('accepted central runs stage onside during through-ball wind-up; stale tasks cannot qualify',()=>{
 const {m,set,owner,link,back}=fixture();
 owner.x=28;owner.z=0;m.ball.x=28;link.active=false;back.x=40;
 const st=set(1,'ATT',34,0,{position:'ST'});
 const Intent=require('../team-intent');
 Intent.resolve(st,{x:37,z:0,pace:1.06,state:'box-run',partnerId:owner.id,priority:30},m.taskContext(st));
 assert(m.acceptedTimedRun(owner,st));
 const seed=m.seed;
 st.task.epoch--;assert.equal(m.acceptedTimedRun(owner,st),false);st.task.epoch++;
 assert.equal(m.seed,seed);
 assert(m.startKick(owner,'through',st,{x:44,z:0}));
 assert.equal(m.kick.timedRun,true);
 m.plan();
 assert.equal(m.targets.get(st).state,'receive-run');
 assert(m.targets.get(st).x<=40-Brain.runMargin(st,1)+1e-8);
});
test('shot intentions depend on distance, balance and pressure; count only actual releases',()=>{
 const {m,owner,link,mid,back}=fixture();
 link.active=mid.active=back.active=false;
 Object.assign(owner,{x:43,z:0,face:0,speed:0,shooting:90,composure:90});
 m.ball.x=43.88;m.ball.z=.18;
 const point={x:52,z:-2};
 const seed=m.seed,placed=m.openPlayShotProfile(owner,point);
 assert.equal(placed.style,'placed');assert.equal(m.seed,seed);
 owner.speed=6;
 const driven=m.openPlayShotProfile(owner,point);
 assert.equal(driven.style,'driven');assert(driven.power>placed.power);
 owner.speed=0;
 assert(m.startOpenPlayShot(owner,point));
 assert.equal(m.kick.shotStyle,'placed');assert.equal(m.kick.heightTarget,.65);
 assert.equal(m.telemetry.placedShotReleases??0,0);
 m.release();
 assert.equal(m.flight.shotStyle,'placed');assert.equal(m.telemetry.placedShotReleases,1);
 assert(Math.abs(Math.hypot(m.ball.vx,m.ball.vz)-placed.power)<1e-8);
});
