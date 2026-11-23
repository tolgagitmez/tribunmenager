'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {Match}=require('../football-sim.js'),Club=require('../club-data.js');
const Rig=require('../humanoid-rig.js');
const gap=(a,b)=>Math.hypot(...a.map((n,i)=>n-b[i]));
function game(){
 const roster=Club.createRoster();
 const m=new Match({seed:31,players:roster,starters:Club.starters,
  awayPlayers:roster,awayStarters:Club.starters},Rig);
 m.restart=null;m.kick=null;m.goalPause=null;m.time=10;
 const p=m.players[0],d=m.players[11],q=m.players[1];
 for(const actor of m.players)if(actor!==p&&actor!==d&&actor!==q)actor.active=false;
 Object.assign(p,{x:0,z:0,face:0,vx:0,vz:0,speed:0,receiveClock:0,touchClock:0,duelRecovery:0,
  role:'ATT',position:'ST',dribbling:98,energy:1,personality:.8});
 Object.assign(d,{x:2,z:0,face:Math.PI,vx:-2,vz:0,speed:2,tackleClock:0,duelRecovery:0,
  tackling:35,composure:60,energy:1,personality:0});
 Object.assign(q,{x:8,z:0,active:true,team:0,role:'ATT'});
 m.ball={x:.88,y:.11,z:.18,vx:0,vy:0,vz:0};
 m.owner=p;m.lastTeam=0;
 return {m,p,d,q};
}
test('an actual perceived fake can make a defender take a bounded wrong-foot step',()=>{
 const {m,p,d}=game();
 m.applyFeint(p,{kind:'feint',defender:d,sign:1,point:{x:2,z:2}});
 assert.equal(m.telemetry.feints,1);
 assert.equal(m.telemetry.feintWrongSteps,1);
 assert(d.feintResponseClock>.11);
 const original={x:d.x,z:d.z},snapshot=structuredClone(m.ball);
 m.move(d,{x:0,z:0,state:'press',pace:1.05},1/60);
 assert(d.z>original.z,'the misread must produce real lateral motion, not just rig animation');
 assert(Math.hypot(d.x-original.x,d.z-original.z)<.15,'no defender teleportation');
 assert.deepEqual(m.ball,snapshot,'defender movement cannot rewrite ball physics');
 const pose=Rig.update(d,1/60);
 assert(pose.defenderMisread>0,'physical response is visible in same humanoid rig');
 assert(pose.legs.some(l=>!l.stance),'short wrong foot cue');
 for(const leg of pose.legs){
  assert(Math.abs(gap(leg.hip,leg.knee)-Rig.ANATOMY.thigh)<1e-5);
  assert(Math.abs(gap(leg.knee,leg.ankle)-Rig.ANATOMY.shin)<1e-5);
 }
});
test('a defender outside the visual cone or with superior composure does not invent a wrong step',()=>{
 for(const mode of ['blind','skilled','receding']){
  const {m,p,d}=game();
  if(mode==='blind')d.face=0;
  if(mode==='skilled'){d.tackling=99;d.composure=99;}
  if(mode==='receding')d.vx=2;
  m.applyFeint(p,{kind:'feint',defender:d,sign:1,point:{x:2,z:2}});
  assert.equal(d.feintResponseClock??0,0,mode);
  assert.equal(m.telemetry.feintWrongSteps,0,mode);
 }
});
test('a strong shielded target forward resists a marginal tackle more often than a weak one under identical roll',()=>{
 function contest(strength,balance){
  const {m,p,d}=game();p.strength=strength;p.balance=balance;p.dribbling=85;
  d.strength=76;d.balance=76;d.tackling=90;
  Object.assign(d,{x:.45,z:.1,vx:0,vz:0,face:Math.PI});
  m.ball={x:-.24,z:-.08,y:.11,vx:0,vy:0,vz:0};
  p.shieldUntil=m.time+.3;
  m.tackleAccess=()=>({attempt:true});
  m.random=()=>.4;m.t[d.team].aggression=50;
  m.doTackle(d,p);
  return {m,p,d};
 }
 const strong=contest(97,96),weak=contest(42,40);
 assert.equal(strong.m.owner,strong.p,'balanced striker shields at marginal fixed roll');
 assert.equal(weak.m.owner,null,'weaker back-to-goal player loses the same reachable duel');
 assert.equal(strong.m.telemetry.duels,1);assert.equal(weak.m.telemetry.duels,1);
});
test('a real hold-up decision can release a physically evaluated safe outlet',()=>{
 const {m,p,q}=game();
 Object.assign(p,{role:'ATT',position:'ST',x:0,z:0,face:Math.PI,carryTime:.5,
  holdUpStartedAt:9.65,shieldUntil:10.5});
 const option={kind:'pass',q,point:{x:8,z:0},risk:.1,arrivalRisk:.1,space:8,
  distance:8,score:13};
 m.rivals=()=>[{id:11,x:1.7,z:0,vx:0,vz:0,face:Math.PI}];
 m.shotWindow=()=>({quality:0,distance:50,open:0,execution:0,pressure:0,point:{x:52,z:0}});
 m.clearFinish=()=>false;m.crossingOption=()=>null;
 m.carryOption=()=>({kind:'carry',point:{x:3,z:2},clearance:.7,score:3});
 m.passOptions=()=>[option];let safetyCalls=0;
 m.passPreparation=()=>{safetyCalls++;return {feasible:true};};
 const selected=m.choose(p);
 assert.equal(selected.kind,'pass');
 assert.equal(selected.holdUpOutlet,true);
 assert.equal(safetyCalls,1,'must validate actual windup before choosing escape pass');
 m.startChosenDelivery(p,selected);
 assert.equal(m.kick.holdUpOutlet,true);
});
test('an inaccessible hold-up pass remains a shield/turn rather than a magical release',()=>{
 const {m,p,q}=game();
 Object.assign(p,{role:'ATT',position:'ST',x:0,z:0,face:Math.PI,carryTime:.5,
  holdUpStartedAt:9.65,shieldUntil:10.5});
 const option={kind:'pass',q,point:{x:8,z:0},risk:.1,arrivalRisk:.1,space:8,distance:8,score:13};
 m.rivals=()=>[{id:11,x:1.7,z:0,vx:0,vz:0,face:Math.PI}];
 m.shotWindow=()=>({quality:0,distance:50,open:0,execution:0,pressure:0,point:{x:52,z:0}});
 m.clearFinish=()=>false;m.crossingOption=()=>null;
 m.carryOption=()=>({kind:'carry',point:{x:3,z:2},clearance:2,score:4});
 m.passOptions=()=>[option];
 m.passPreparation=()=>({feasible:false});
 assert.notEqual(m.choose(p).holdUpOutlet,true,'no illegal pass from the hold-up branch');
});
test('verified one-touch wall pass marks the physical kick and its opposite-arm counterbalance',()=>{
 const {m,p,q}=game();
 p.face=0;p.oneTouchUntil=m.time+.5;
 q.runIntent={kind:'give-go',partnerId:p.id,epoch:m.attackEpoch[0],origin:{x:0,z:0},
  point:{x:13,z:0},until:m.time+2};
 assert(m.startKick(p,'pass',q,{x:8,z:0}));
 assert.equal(m.kick.wallPass,true);
 assert.equal(p.wallPassFoot,p.kickFoot);
 assert(p.wallPassClock>=m.kick.duration);
 const before=structuredClone(m.ball);
 p.actionElapsed=p.contactTime;p.actionClock=.16;
 const pose=Rig.update(p,1/60);
 assert.equal(pose.wallPassWeight,1);
 assert(gap(pose.legs[p.kickFoot].ankle,Rig.kickAnkle(p))<.003,
  'one-touch shoe shares the authoritative kick ankle');
 assert.deepEqual(m.ball,before,'wall pass animation has no separate impulse');
});
test('an ordinary one-touch pass is not mislabeled as a coordinated wall return',()=>{
 const {m,p,q}=game();p.oneTouchUntil=m.time+.5;
 assert(m.startKick(p,'pass',q,{x:8,z:0}));
 assert.equal(m.kick.wallPass,false);
 assert.equal(p.wallPassClock??0,0);
});
test('live snapshots carry only grounded wall-pass and feint clocks; rendering does not alter them',()=>{
 const worker=fs.readFileSync(path.join(__dirname,'../live-match-worker.cjs'),'utf8');
 for(const field of ['feintResponseClock','feintResponseSign','wallPassClock','wallPassFoot'])
  assert(worker.includes("'"+field+"'"));
 const source=fs.readFileSync(path.join(__dirname,'../live-match-view.js'),'utf8'),context={
  window:{TribunHumanoidRig:{update(){}}},Map,Math,Object,Number};
 vm.runInNewContext(source,context);
 const view=new context.window.TribunLiveMatchView(),state={
  time:10,events:[],eventSerial:0,ownerId:0,direction:[1,-1],tactics:[{},{}],
  ball:{x:0,z:0,y:.11},players:[{id:0,active:true,x:0,z:0,face:0,
   feintResponseClock:.18,wallPassClock:.32}]
 };
 view.ingest(state,1000);view.sample(1080,1/60);
 assert(Math.abs(view.players[0].feintResponseClock-.1)<1e-5);
 assert(Math.abs(view.players[0].wallPassClock-.24)<1e-5);
 assert.equal(state.players[0].feintResponseClock,.18);
 assert.equal(state.players[0].wallPassClock,.32);
});
