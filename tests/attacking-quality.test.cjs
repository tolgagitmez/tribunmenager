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

test('a curled strike uses live spin, opposite bend in mirrored halves, and no ball teleport',()=>{
 const {BallPhysics}=require('../football-sim');
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  link.active=mid.active=back.active=false;
  Object.assign(owner,{x:34*side,z:11,face:Math.atan2(-11,18*side),shooting:94,composure:94});
  const point={x:52*side,z:0};
  m.ball.x=owner.x+.6*side;m.ball.z=owner.z-.4;
  const profile=m.openPlayShotProfile(owner,point);
  assert.equal(profile.style,'curled');assert.equal(Math.sign(profile.spin),-side);
  const before=[m.ball.x,m.ball.y,m.ball.z];
  assert(m.startOpenPlayShot(owner,point));m.release();
  assert.equal(m.flight.shotStyle,'curled');assert.equal(m.telemetry.curledShotReleases,1);
  assert.deepEqual([m.ball.x,m.ball.y,m.ball.z],before);
  assert.equal(Math.sign(m.ball.spin),-side);
  const curved=BallPhysics.atX(m.ball,52*side,3),straight=BallPhysics.atX({...m.ball,spin:0},52*side,3);
  assert(curved&&straight);assert(Math.abs(curved.z-straight.z)>.1);
 }
});
test('chip option needs an advanced keeper and a trajectory that clears him',()=>{
 const {m,owner,link,mid,back,keeper}=fixture();
 link.active=mid.active=back.active=false;
 Object.assign(owner,{z:0,face:0,shooting:94,composure:94});
 const point={x:52,z:0};
 let qualified=null;
 for(const x of [27,29,31,33,35,37])for(const g of [40,41,42,43,44]){
  owner.x=x;keeper.x=g;
  const profile=m.openPlayShotProfile(owner,point);
  if(profile.style==='chip')qualified={x,g,profile};
 }
 assert(qualified,'at least one physically reachable lob should exist');
 owner.x=qualified.x;keeper.x=qualified.g;
 assert.equal(m.openPlayShotProfile(owner,point).style,'chip');
 keeper.x=50;assert.notEqual(m.openPlayShotProfile(owner,point).style,'chip');
});
test('first-time finish requires actual foot contact and completes the incoming pass before a real shot',()=>{
 const {m,owner,link,mid,back}=fixture();
 mid.active=back.active=false;
 Object.assign(owner,{x:44,z:0,face:0,shooting:94,composure:94,touchClock:0,footTouch:0,receiveClock:0,action:'idle'});
 m.owner=null;m.lastTouch=link;
 m.flight={id:17,kind:'pass',from:link,target:owner,age:.5,offsidePlayers:[]};
 m.ball={x:43.8,y:.11,z:0,vx:9,vy:0,vz:0};
 assert.equal(m.firstTimeFinish(owner),false);assert.equal(m.shots[0],0);
 const foot=m.contactPoint({...owner,kickFoot:1},'shot');
 Object.assign(m.ball,{x:foot[0],z:foot[2]});
 const before=[m.ball.x,m.ball.y,m.ball.z];
 m.fieldBallContact({x:m.ball.x-.03,y:m.ball.y,z:m.ball.z});
 assert.equal(m.completed[0],1);assert.equal(m.shots[0],1);
 assert.equal(m.telemetry.firstTimeShotReleases,1);assert.equal(m.flight.kind,'shot');
 assert.deepEqual([m.ball.x,m.ball.y,m.ball.z],before);
});

test('carry style distinguishes skilled sharp cuts and straight bursts from tired or blocked routes',()=>{
 const p={role:'ATT',x:0,z:0,face:0,speed:1,energy:1,dribbling:94,agility:92,acceleration:95,pace:94};
 const cut={x:3,z:4},straight={x:5,z:0},input={forward:1,pressure:3.6,clearance:3.5};
 assert.equal(Brain.dribbleStyle(p,cut,input),'cut');
 assert.equal(Brain.dribbleStyle(p,straight,input),'burst');
 assert.equal(Brain.dribbleStyle({...p,agility:60},cut,input),null);
 assert.equal(Brain.dribbleStyle({...p,energy:.2},straight,input),null);
 assert.equal(Brain.dribbleStyle(p,straight,{...input,clearance:1}),null);
 assert.equal(Brain.dribbleStyle({...p,face:Math.PI},{x:-5,z:0},{...input,forward:-1}),'burst');
});
test('accepted carry requests a skill touch, but a rejected recovery does not award it',()=>{
 const {m,owner,link,mid,back}=fixture();
 link.active=mid.active=back.active=false;
 Object.assign(owner,{x:0,z:0,face:0,speed:1,dribbling:94,agility:92,acceleration:95,pace:94,touchClock:0});
 m.ball={x:.6,y:.11,z:.18,vx:0,vy:0,vz:0};
 m.startCarry(owner,{kind:'carry',point:{x:5,z:0},clearance:4,commit:.65});
 assert.equal(owner.carryIntent.style,'burst');
 const before=structuredClone(m.ball);
 m.touchPlan=()=>({ready:false});
 assert.equal(m.dribbleTouch(owner),false);
 assert.equal(m.telemetry.accelerationBurstTouches??0,0);
 assert.deepEqual(m.ball,before);
 m.touchPlan=()=>({ready:true,velocity:{vx:3,vy:.16,vz:0}});
 assert.equal(m.dribbleTouch(owner),true);
 assert.equal(m.telemetry.accelerationBurstTouches,1);
 assert.equal(owner.touchMode,'burst');
 assert.equal(owner.footTouch,.14);
 assert.deepEqual([m.ball.x,m.ball.y,m.ball.z],[before.x,before.y,before.z]);
});
test('real touch cues change animation without moving actors or stretching leg bones',()=>{
 const Rig=require('../humanoid-rig');
 const base={x:0,z:0,face:0,speed:0,action:'idle',actionClock:0,kickFoot:1,dribbleFoot:1,footTouch:.14,touchPosition:{x:.5,z:.18}};
 const plain=Rig.update({...base,touchMode:'close'},1/60);
 for(const mode of ['cut','burst']){
  const p={...base,touchMode:mode},before=structuredClone(p),pose=Rig.update(p,1/60);
  assert.equal(pose[mode+'Weight'],1);
  assert.notDeepEqual(pose.torsoUpper,plain.torsoUpper);
  assert.deepEqual(p,before);
  for(const l of pose.legs){
   const gap=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
   assert(Math.abs(gap(l.hip,l.knee)-Rig.ANATOMY.thigh)<1e-5);
   assert(Math.abs(gap(l.knee,l.ankle)-Rig.ANATOMY.shin)<1e-5);
  }
  p.footTouch=0;assert.equal(Rig.update(p,1/60)[mode+'Weight'],0);
 }
});

test('preferred foot only wins a physically small preparation trade-off when time is available',()=>{
 const {m,owner,link,mid,back}=fixture();
 link.active=mid.active=back.active=false;
 Object.assign(owner,{x:0,z:0,face:0,shooting:95,preferredFoot:1,footPreference:'right',weakFoot:30});
 m.ball={x:.88,y:.11,z:-.11,vx:0,vy:0,vz:0};
 const before=structuredClone(m.ball),seed=m.seed;
 assert.equal(m.selectKickFoot(owner,0,'shot'),1);
 mid.active=true;Object.assign(mid,{x:1.8,z:0});
 assert.equal(m.selectKickFoot(owner,0,'shot'),0);
 mid.active=false;m.ball.z=-.65;
 assert.equal(m.selectKickFoot(owner,0,'shot'),0);
 m.ball.z=before.z;owner.weakFoot=95;
 assert.equal(m.selectKickFoot(owner,0,'shot'),0);
 assert.deepEqual(m.ball,before);assert.equal(m.seed,seed);
});
test('shoulder challenge needs side-by-side contact and attributes change resistance, not possession',()=>{
 const {m,owner,back}=fixture();
 Object.assign(owner,{x:0,z:0,face:0,vx:3,vz:0,strength:95,balance:94});
 Object.assign(back,{x:.15,z:.8,face:0,vx:3,vz:0,strength:65,balance:65});
 m.ball={x:.7,y:.11,z:0,vx:3,vy:0,vz:0};
 const before=structuredClone(m.ball),seed=m.seed;
 const strong=m.shoulderContest(back,owner);assert(strong&&strong.resistance>.05);
 owner.strength=45;owner.balance=45;
 const weak=m.shoulderContest(back,owner);assert(weak&&weak.resistance<0);
 back.face=Math.PI;assert.equal(m.shoulderContest(back,owner),null);
 back.face=0;back.x=-.8;assert.equal(m.shoulderContest(back,owner),null);
 back.x=.15;back.vx=8;assert.equal(m.shoulderContest(back,owner),null);
 assert.deepEqual(m.ball,before);assert.equal(m.owner,owner);assert.equal(m.seed,seed);
});

test('skilled stationary player chooses a step-over, with no separate ball impulse',()=>{
 const {m,owner,link,mid,back}=fixture();
 link.active=mid.active=false;
 Object.assign(owner,{x:0,z:0,face:0,speed:0,dribbling:95,agility:95,balance:92,feintCooldown:0,footTouch:0});
 Object.assign(back,{x:2,z:0,face:Math.PI,vx:-1,vz:0,tackling:45,composure:65});
 m.ball={x:.65,y:.11,z:.18,vx:0,vy:0,vz:0};
 const choice=m.feintOption(owner,back);assert(choice);assert.equal(choice.feintStyle,'step-over');
 const before=structuredClone(m.ball),seed=m.seed;
 m.startCarry(owner,choice);
 assert.equal(owner.feintStyle,'step-over');assert.equal(m.telemetry.stepOverAttempts,1);
 assert.deepEqual(m.ball,before);assert.equal(m.seed,seed);
 owner.feintClock=.175;const Rig=require('../humanoid-rig');
 const step=Rig.update(owner,1/60),plain=Rig.update({...owner,feintStyle:'body'},1/60);
 const foot=owner.feintSign>0?1:0;
 assert.notDeepEqual(step.legs[foot].ankle,plain.legs[foot].ankle);
 assert.deepEqual(m.ball,before);
 owner.balance=60;
 assert.notEqual(m.feintOption(owner,back)?.feintStyle,'step-over');
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../live-match-worker.cjs'),'utf8');
 assert(source.includes("'feintStyle'"));
});

test('stalled completed circulation allows a safe carry but not a blocked route or a good forward pass',()=>{
 const {m,owner,link}=fixture();
 Object.assign(owner,{x:0,z:0,face:0,dribbling:85,carryTime:.5,energy:1,position:'AM'});
 m.recentPasses=[{from:owner.id,to:link.id,time:5,progress:1},{from:link.id,to:owner.id,time:7,progress:-2},{from:owner.id,to:link.id,time:9,progress:1}];
 const carry={kind:'carry',point:{x:5,z:0},clearance:4};
 assert.equal(m.progressiveCarryRead(owner,carry,[],8),true);
 assert.equal(m.progressiveCarryRead(owner,{...carry,clearance:1},[],8),false);
 assert.equal(m.progressiveCarryRead(owner,carry,[],3),false);
 assert.equal(m.progressiveCarryRead(owner,carry,[{point:{x:9,z:0},risk:.1,arrivalRisk:.1,space:5,score:8}],8),false);
 m.recentPasses[0].progress=9;
 assert.equal(m.progressiveCarryRead(owner,carry,[],8),false);
 m.recentPasses[0].progress=0;m.recentPasses[0].time=0;
 assert.equal(m.progressiveCarryRead(owner,carry,[],8),false);
});

test('open grass permits forward carrying without a stale pass chain, including a safe turn from back to goal',()=>{
 const {m,owner}=fixture();Object.assign(owner,{x:0,z:0,face:Math.PI,position:'AM',dribbling:76,carryTime:.3,energy:1});
 const carry={kind:'carry',point:{x:5.5,z:0},clearance:7};
 assert.equal(m.openFieldCarryRead(owner,carry,[],12),true);
 assert.equal(m.openFieldCarryRead(owner,carry,[],7),false);
 assert.equal(m.openFieldCarryRead(owner,{...carry,clearance:3},[],12),false);
 assert.equal(m.openFieldCarryRead(owner,carry,[{point:{x:9,z:0},risk:.1,arrivalRisk:.1,space:5,score:8}],12),false);
 owner.face=0;assert.equal(m.openFieldCarryRead(owner,carry,[],7),true);
 owner.position='DM';assert.equal(m.openFieldCarryRead(owner,carry,[],12),false);
});

test('final-third link prefers a verified box pass and rejects closed preparation or recycled possession',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  Object.assign(owner,{x:28*side,z:11,face:side>0?0:Math.PI});
  Object.assign(link,{x:36*side,z:2});
  m.ball.x=owner.x;m.ball.z=owner.z;
  const option={kind:'pass',q:link,point:{x:38*side,z:2},distance:14,risk:.12,arrivalRisk:.2,space:5,score:8};
  const safe={...option,point:{x:26*side,z:12},score:20};
  let checked=0;m.passPreparation=()=>{checked++;return {feasible:true};};
  assert.equal(m.finalThirdLink(owner,[safe,option]).finalThirdLink,true);
  assert.equal(checked,1);
  m.passPreparation=()=>({feasible:false});
  assert.equal(m.finalThirdLink(owner,[option]),null);
  m.passPreparation=()=>{throw Error('unsafe option should not be previewed');};
  assert.equal(m.finalThirdLink(owner,[{...option,risk:.5}]),null);
  assert.equal(m.finalThirdLink(owner,[{...option,arrivalRisk:.8}]),null);
  owner.x=15*side;assert.equal(m.finalThirdLink(owner,[option]),null);
 }
});
test('central carrier at the defensive line retains an onside diagonal cutback outlet',()=>{
 for(const side of [1,-1]){
  const {m,set,owner,link,mid,back}=fixture(side);
  Object.assign(owner,{x:39*side,z:1});m.ball.x=owner.x;m.ball.z=owner.z;
  Object.assign(back,{x:38*side,z:0});
  const edge=set(7,'MID',29,-9,{position:'AM'});
  link.active=false;mid.active=false;
  const plan=m.boxAttack(0,owner),point=plan.points.get(edge.id);
  assert(point&&point.role==='edge');
  assert(point.x*side<=35&&point.x*side<owner.x*side);
  assert(Math.abs(point.z)>3);
 }
});

test('progressive carry pace remains physical and returns to ordinary pace when the path closes',()=>{
 const {m,owner}=fixture();
 Object.assign(owner,{x:0,z:0,face:0,receiveClock:0,carryTarget:{x:5,z:0},carryIntent:{progressive:true,until:m.time+.4}});
 m.ball={x:.65,y:.11,z:.18,vx:0,vz:0,vy:0};
 assert.equal(m.progressiveCarryPace(owner,[],10),.96);
 assert.equal(m.progressiveCarryPace(owner,[{x:3,z:1,vx:0,vz:0}],10),null);
 assert.equal(m.progressiveCarryPace(owner,[],4),null);
 owner.face=Math.PI;assert.equal(m.progressiveCarryPace(owner,[],10),null);
 owner.face=0;m.ball.x=2;assert.equal(m.progressiveCarryPace(owner,[],10),null);
 m.ball.x=.65;owner.carryIntent.until=m.time;assert.equal(m.progressiveCarryPace(owner,[],10),null);
});

test('receiver shoulder scan uses bounded real observations once per flight, not hidden opponent coordinates',()=>{
 const Perception=require('../player-perception');
 const {m,owner,link,mid,back}=fixture();
 Object.assign(link,{x:10,z:0,face:Math.PI,vision:92});
 Object.assign(mid,{x:18,z:0});back.active=false;
 m.owner=null;m.flight={id:42,kind:'pass',target:link,from:owner};
 m.ball={x:3,y:.11,z:0,vx:12,vy:0,vz:0};
 const request=m.receiveScanRequest();assert(request&&request.id===link.id);
 Perception.update(m.players,m.time,1/60,{scanAllowed:false});
 const before=link.face;
 const t=m.time+.12;
 Perception.update(m.players,t,1/60,{receiveScan:request});
 assert.equal(link.perception.lastReceiveScan,42);
 assert(Math.abs(link.perception.headYaw)<=1.55);
 assert.equal(link.face,before);
 assert(Perception.rivals(link,t).some(q=>q.id===mid.id&&q.source==='scan'));
 const first=link.perception.nextScanAt;
 Perception.update(m.players,t+.2,1/60,{receiveScan:request});
 assert.equal(link.perception.nextScanAt,first);assert.equal(link.perception.headYaw,0);
 m.ball.x=9.5;assert.equal(m.receiveScanRequest(),null);
});
test('safe forward first touch is selected for enabled individual AI, but not forced through a closed lane',()=>{
 for(const side of [1,-1]){
  const {m,owner,mid,back,keeper}=fixture(side);
  Object.assign(owner,{x:8*side,z:0,face:side===1?0:Math.PI,dribbling:92,composure:90,position:'AM'});
  mid.active=back.active=keeper.active=false;
  const forward=side===1?0:Math.PI;
  const point=m.controlOption(owner,owner,forward+Math.PI,0);
  assert(point.progressive);assert((point.x-owner.x)*side>=1.9);
  m.cfg.progressiveFirstTouch=false;
  assert(!m.controlOption(owner,owner,forward+Math.PI,0).progressive);
  m.cfg.progressiveFirstTouch=true;
  mid.active=true;mid.x=owner.x+side*2;mid.z=0;
  assert(!m.controlOption(owner,owner,forward+Math.PI,0).progressive);
 }
});

test('early diagonal runs create a reachable onside passing lane before the last defensive line',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  Object.assign(link,{x:17*side,z:2,role:'ATT',position:'ST',pace:83,vision:83,face:side===1?0:Math.PI});
  Object.assign(mid,{x:14*side,z:-8});
  Object.assign(back,{x:33*side,z:10});
  m.laneRisk=()=>.1;
  const option=m.earlyDiagonalRun(link,owner,33);
  assert(option&&option.kind==='diagonal');
  assert((option.point.x-link.x)*side>=3);
  assert(option.point.x*side<=33-Brain.runMargin(link,side));
  assert(Math.abs(option.point.z-link.z)>=3);
  m.laneRisk=()=>.6;assert.equal(m.earlyDiagonalRun(link,owner,33),null);
  m.laneRisk=()=>.1;link.position='DM';assert.equal(m.earlyDiagonalRun(link,owner,33),null);
 }
});

test('accepted diagonal movement earns a feed only for a moving receiver in a safe corridor',()=>{
 const {m,owner,link,back}=fixture();
 Object.assign(link,{x:17,z:2,role:'ATT',position:'ST',vx:4,vz:2,face:Math.atan2(2,4),pace:85});
 back.x=37;
 const Intent=require('../team-intent');
 Intent.resolve(link,{x:24,z:5,state:'penetration',pace:1.07,partnerId:owner.id,priority:30},m.taskContext(link));
 m.attackPlans[0]={ownerId:owner.id,epoch:m.attackEpoch[0],until:m.time+2,runner:{id:link.id,kind:'diagonal',accepted:true,point:{x:24,z:5}}};
 m.receiverPoint=(q)=>q===link?{x:20,z:3.5}:{x:q.x,z:q.z};
 m.laneRisk=()=>.1;m.receptionSafety=()=>({risk:.1,pressure:6});
 let pass=m.passOptions(owner).find(o=>o.q===link&&o.kind==='pass');
 assert(pass?.diagonalFeed);
 const scored=pass.score;
 m.attackPlans[0].runner.accepted=false;
 pass=m.passOptions(owner).find(o=>o.q===link&&o.kind==='pass');
 assert(!pass?.diagonalFeed);assert(pass.score<scored);
 m.attackPlans[0].runner.accepted=true;m.laneRisk=()=>.7;
 assert(!m.passOptions(owner).find(o=>o.q===link&&o.kind==='pass')?.diagonalFeed);
});

test('attacking depth is retained only if an alternative can actually be played',()=>{
 for(const side of [1,-1]){
  const {m,owner,link}=fixture(side);
  Object.assign(owner,{x:26*side,z:8,face:side===1?0:Math.PI,carryTime:.5,receiveClock:0,position:'AM'});
  const retreat={kind:'pass',q:link,point:{x:5*side,z:10},distance:21,risk:.05,arrivalRisk:.1,space:9,score:20};
  const forward={...retreat,point:{x:31*side,z:4},distance:7,space:5,score:5};
  const carry={kind:'carry',point:{x:31*side,z:8},clearance:4};
  assert.equal(m.retainAttackingDepth(owner,[retreat,forward],carry,5),null);
  m.cfg.attackingSupportExperiment=true;
  m.passPreparation=()=>({feasible:true});
  assert.equal(m.retainAttackingDepth(owner,[retreat,forward],carry,5).retainDepth,true);
  m.passPreparation=()=>({feasible:false});m.controlPreparation=()=>({firstTouchTime:.2,interventionTime:null});
  assert.equal(m.retainAttackingDepth(owner,[retreat,forward],carry,5).kind,'carry');
  m.controlPreparation=()=>({firstTouchTime:.2,interventionTime:.3});
  assert.equal(m.retainAttackingDepth(owner,[retreat,forward],carry,5),null);
  assert.equal(m.retainAttackingDepth(owner,[retreat,forward],carry,1.5),null);
  assert.equal(m.retainAttackingDepth(owner,[forward,retreat],carry,5),null);
 }
});

test('advanced carrier receives a nearby diagonal support target without displacing reserved runners',()=>{
 for(const side of [1,-1]){
  const {m,owner,link}=fixture(side);
  Object.assign(owner,{x:25*side,z:0});
  Object.assign(link,{x:13*side,z:5.5,homeZ:5.5});
  m.cfg.attackingSupportExperiment=true;
  const reserved=new Map([[100,{x:29*side,z:0}]]);
  m.supportRead=(p,q,point)=>({space:6,risk:.1,travel:Math.hypot(q.x-point.x,q.z-point.z),eta:.7,window:1.3,urgency:0,earlyRisk:.1,readyAt:0});
  const point=m.supportTargets(owner,[link],reserved,40).get(link.id);
  assert(point);
  assert((point.x-owner.x)*side>=-9);
  assert(Math.hypot(point.x-owner.x,point.z-owner.z)<=14);
  assert(Math.hypot(point.x-29*side,point.z)>=3.2);
  m.supportRead=()=>({space:.5,risk:.9,travel:0,eta:0,window:1,urgency:1,earlyRisk:.9,readyAt:3});
  assert.equal(m.supportTargets(owner,[link],reserved,40).size,0);
 }
});


test('open lane wins over backwards recycling and survives both playing directions',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  owner.x=31*side;owner.z=0;owner.face=side===1?0:Math.PI;owner.carryTime=3;owner.receiveClock=0;owner.shieldUntil=0;
  m.ball.x=owner.x+.5*side;m.ball.z=0;
  const carry={kind:'carry',point:{x:36*side,z:0},clearance:4.5};
  const retreat={kind:'pass',q:link,point:{x:19*side,z:0},risk:.05,arrivalRisk:.1,space:8,score:30};
  assert(m.directProgressRead(owner,carry,[retreat],8));
  assert(!m.directProgressRead(owner,carry,[retreat],2));
  assert(!m.directProgressRead(owner,{...carry,clearance:1},[retreat],8));
  assert(!m.directProgressRead(owner,carry,[{...retreat,point:{x:40*side,z:0}}],8));
  m.shotWindow=()=>({distance:24,quality:.04,open:.2,execution:.8,pressure:.2,point:{x:52*side,z:0}});
  m.passOptions=()=>[retreat];m.carryOption=()=>carry;m.crossingOption=()=>null;
  const selected=m.choose(owner);
  assert.equal(selected.kind,'carry');assert(selected.openFieldCarry);
 }
});

test('safe central shot is not suppressed by a high-value recycling pass',()=>{
 const {m,owner,link}=fixture();
 owner.x=32;owner.z=2;
 m.shotWindow=()=>({distance:20,quality:.12,open:.8,execution:.8,pressure:.2,point:{x:52,z:1}});
 m.t[owner.team].shooting='early';
 m.passOptions=()=>[{kind:'pass',q:link,point:{x:19,z:0},score:50,risk:.05,arrivalRisk:.1}];
 m.carryOption=()=>({kind:'carry',point:{x:37,z:2},clearance:5});m.crossingOption=()=>null;
 assert.equal(m.choose(owner).kind,'shot');
});

test('keeper advances for an uncontested slow ground ball but not into an arriving rival',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back,keeper}=fixture(side);
  owner.active=link.active=mid.active=back.active=false;
  Object.assign(keeper,{x:49*side,z:0,touchClock:0,duelRecovery:0});
  m.owner=null;m.flight=null;m.ball={x:43*side,y:.11,z:0,vx:.5*side,vy:0,vz:0};
  const pickup=m.keeperGroundPickup(keeper);
  assert(pickup&&pickup.x*side<48);
  owner.active=true;owner.x=43*side;owner.z=2;
  assert.equal(m.keeperGroundPickup(keeper),null);
 }
});

test('ordinary free kicks use a shorter preparation without bypassing exclusion distance',()=>{
 const {m,owner,mid}=fixture();
 m.setRestart('free-kick',0,{x:0,z:0},owner);
 assert.equal(m.restart.clock,2);
 mid.x=2;mid.z=0;
 assert.equal(m.restartReady(m.restart),false);
 mid.x=12;mid.z=0;
 // Other opponents in the fixture are already beyond the exclusion radius.
 assert.equal(m.restartReady(m.restart),true);
 m.setRestart('free-kick',0,{x:29,z:0},owner);
 assert.equal(m.restart.clock,4);
});

test('carry forecast rejects an unnecessarily wide gap and accepts a recoverable softer touch',()=>{
 const {m,owner}=fixture();
 m.touchContact=()=>({ready:true,gap:.6,foot:1,technique:80});
 owner.touchClock=owner.receiveClock=0;
 m.touchRecovery=(p,v)=>({ready:true,maxGap:v.vx>3?2.1:1.1});
 m.ball.vx=0;m.ball.vz=0;m.ball.vy=0;
 const plan=m.touchPlan(owner,{vx:6,vz:0,vy:0},{mode:'carry',interval:.25,maxGap:1.3});
 assert(plan.ready&&plan.limited);assert(plan.velocity.vx<=3);
});


test('second-wave midfielder chooses a distinct onside half-space and preserves the anchor',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back,keeper}=fixture(side);
  Object.assign(owner,{x:28*side,z:2});
  Object.assign(link,{x:27*side,z:6,position:'AM',homeX:19*side,energy:1});
  mid.active=false;back.x=44*side;back.z=23;keeper.x=49*side;
  m.ball.x=owner.x;m.ball.z=owner.z;
  const occupied=new Map([[1,{x:39*side,z:0}],[2,{x:40*side,z:-12}]]);
  const point=m.secondWavePoint(owner,link,occupied,44);
  assert(point);assert(point.x*side>=35.5);assert(point.x*side<=44-Brain.runMargin(link,side)+1e-8);
  assert([...occupied.values()].every(q=>Math.hypot(q.x-point.x,q.z-point.z)>=5.5));
  assert.equal(m.secondWavePoint(owner,link,occupied,35),null);
  link.position='DM';assert.equal(m.secondWavePoint(owner,link,occupied,44),null);
 }
});

test('run delivery prefers an accepted box entry over recycling, but rejects stale, offside or blocked options',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  Object.assign(owner,{x:28*side,z:0,receiveClock:0});
  Object.assign(link,{role:'MID',position:'AM',x:32*side,z:7});
  back.x=44*side;back.z=20;mid.active=false;
  m.ball.x=owner.x;m.ball.z=0;
  const Intent=require('../team-intent');
  Intent.resolve(link,{x:38*side,z:8,state:'box-run',pace:1.06,partnerId:owner.id,priority:30},m.taskContext(link));
  const feed={kind:'pass',q:link,point:{x:37*side,z:8},risk:.10,arrivalRisk:.25,space:5,score:8,distance:12};
  const recycle={...feed,point:{x:18*side,z:0},score:30};
  m.passPreparation=()=>({feasible:true});
  assert(m.attackingRunDelivery(owner,[recycle,feed])?.attackingRunDelivery);
  assert.equal(m.attackingRunDelivery(owner,[{...feed,risk:.65}]),null);
  assert.equal(m.attackingRunDelivery(owner,[{...feed,kind:'through',plannedRun:false}]),null);
  assert(m.attackingRunDelivery(owner,[{...feed,kind:'through',plannedRun:true}]));
  m.passPreparation=()=>({feasible:false});assert.equal(m.attackingRunDelivery(owner,[feed]),null);
  m.passPreparation=()=>({feasible:true});
  link.task.epoch--;assert.equal(m.attackingRunDelivery(owner,[feed]),null);
  link.task.epoch++;link.x=46*side;assert.equal(m.attackingRunDelivery(owner,[feed]),null);
 }
});


test('isolated keeper read chooses the opposite side of a displaced or moving keeper in both halves',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back,keeper}=fixture(side);
  link.active=mid.active=back.active=false;
  Object.assign(owner,{x:40*side,z:0,face:side===1?0:Math.PI,shooting:94,composure:94});
  Object.assign(keeper,{x:49*side,z:1.5,vz:2});
  const seed=m.seed,read=m.finishingRead(owner,{x:52*side,z:0});
  assert(read&&read.point.z<0);assert.equal(read.point.x,52*side);assert.equal(m.seed,seed);
  keeper.z=-1.5;keeper.vz=-2;
  assert(m.finishingRead(owner,{x:52*side,z:0}).point.z>0);
  mid.active=true;mid.x=owner.x+side*1.5;mid.z=0;
  assert.equal(m.finishingRead(owner,{x:52*side,z:0}),null);
 }
});
test('placed-shot dispersion responds to composure and leaves the ordinary shot path unchanged',()=>{
 const {m,owner,link,mid,back}=fixture();
 link.active=mid.active=back.active=false;
 Object.assign(owner,{x:42,z:0,face:0,shooting:90,composure:94,kickFoot:1,preferredFoot:1,footPreference:'right',weakFoot:50});
 const point={x:52,z:0};
 m.random=()=>.8;
 const good=Math.abs(m.aimShot(owner,point,owner,'placed').z);
 owner.composure=65;
 const poor=Math.abs(m.aimShot(owner,point,owner,'placed').z);
 assert(good<poor);
 owner.composure=94;
 assert(good<Math.abs(m.aimShot(owner,point).z));
 owner.kickFoot=0;
 assert(Math.abs(m.aimShot(owner,point,owner,'placed').z)>good);
});
test('first-time shot uses actual contact foot before computing accuracy',()=>{
 const {m,owner}=fixture();
 owner.x=44;owner.z=0;owner.face=0;owner.kickFoot=1;
 let used;
 m.aimShot=(p,point,origin,style)=>{used={foot:p.kickFoot,style};return point;};
 m.selectKickFoot=()=>1;
 assert(m.startKick(owner,'shot',null,{x:52,z:0},25,null,null,{foot:0,style:'first-time'}));
 assert.deepEqual(used,{foot:0,style:'first-time'});
 assert.equal(owner.kickFoot,0);
});


test('rebound tracking selects a legal nearby runner, not an offside player or holding midfielder',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  Object.assign(owner,{role:'ATT',position:'ST',x:39*side,z:2,face:side===1?0:Math.PI,touchClock:0});
  Object.assign(link,{role:'MID',position:'DM',x:42*side,z:1,touchClock:0});
  const shot={kind:'shot',id:42,from:owner};
  m.owner=null;m.flight=null;m.ball={x:43*side,z:1,y:.11,vx:-2*side,vz:0,vy:0};
  m.markRebound(shot,'parry');
  assert.equal(m.reboundRunner(owner.team)?.id,owner.id);
  m.offsidePhase={team:owner.team,playerIds:[owner.id]};
  assert.equal(m.reboundRunner(owner.team),null);
  m.offsidePhase=null;
  m.time+=3;
  assert.equal(m.reboundRunner(owner.team),null);
 }
});

test('rebound finish requires physical contact and records the actual release',()=>{
 const {m,owner,link,mid,back}=fixture();
 mid.active=back.active=false;
 Object.assign(owner,{x:44,z:0,face:0,shooting:94,composure:94,touchClock:0,footTouch:0,receiveClock:0,action:'idle'});
 m.owner=null;m.flight=null;m.lastTouch=link;
 m.markRebound({kind:'shot',id:21,from:link},'block');
 m.ball={x:43.8,y:.11,z:0,vx:3,vy:0,vz:0};
 assert.equal(m.firstTimeFinish(owner),false);
 const foot=m.contactPoint({...owner,kickFoot:1},'shot');
 Object.assign(m.ball,{x:foot[0],z:foot[2]});
 assert(m.firstTimeFinish(owner));
 assert.equal(m.telemetry.reboundFinishReleases,1);
 assert.equal(m.shots[0],1);
 assert.equal(m.rebound,null);
});

test('shot angle carry needs a genuine improvement, an open corridor and no better box pass',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  Object.assign(owner,{x:38*side,z:0,face:side===1?0:Math.PI,dribbling:91,carryTime:.4,receiveClock:0,shieldUntil:0});
  mid.active=back.active=false;
  const blocked={open:.2,quality:.05};
  m.shotWindow=p=>({open:Math.abs(p.z)>=2?.8:.2,quality:Math.abs(p.z)>=2?.15:.05});
  const result=m.shotAngleCarry(owner,blocked,[],8);
  assert(result?.shotAngleCarry);
  assert(Math.abs(result.point.z)>=2);
  assert.equal(m.shotAngleCarry(owner,blocked,[{q:link,point:{x:42*side,z:1},score:10,risk:.1,arrivalRisk:.1,space:6}],8),null);
  assert.equal(m.shotAngleCarry(owner,blocked,[],1),null);
  m.shotWindow=()=>blocked;
  assert.equal(m.shotAngleCarry(owner,blocked,[],8),null);
 }
});


test('shared interception trajectory is identical to independent physical forecasts and invalidates on ball change',()=>{
 const {BallPhysics}=require('../football-sim');
 const {m,owner,link,mid,back}=fixture();
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 function reference(p){
  const top=5.35+((p.pace??80)-75)*.035,q=BallPhysics.copy(m.ball);
  let result;
  for(let i=1;i<=24;i++){
   BallPhysics.step(q,.1);const t=i*.1;
   result={x:clamp(q.x,-52.5,52.5),z:clamp(q.z,-34.3,34.3),t};
   if(q.y<1.1&&Math.hypot(p.x-result.x,p.z-result.z)<.7+top*t)return result;
  }
  return result;
 }
 for(const ball of [{x:30,z:4,y:.11,vx:7,vz:1,vy:0},{x:26,z:-4,y:1.4,vx:12,vz:2,vy:4,spin:.24},{x:47,z:29,y:.11,vx:10,vz:5,vy:0}]){
  m.ball={...ball};const before={...m.ball};
  const first=m.interceptPoint(owner),cache=m.ballForecast;
  assert.deepEqual(first,reference(owner));
  for(const p of [link,mid,back,owner])assert.deepEqual(m.interceptPoint(p),reference(p));
  assert.equal(m.ballForecast,cache);assert(cache.samples.length<=24);
  first.x=999;assert.deepEqual(m.interceptPoint(owner),reference(owner));
  assert.deepEqual(m.ball,before);
  m.ball.vx=-m.ball.vx;
  assert.deepEqual(m.interceptPoint(owner),reference(owner));assert.notEqual(m.ballForecast,cache);
  const changed=m.ballForecast;m.time+=1/60;m.interceptPoint(owner);assert.notEqual(m.ballForecast,changed);
 }
});

test('interception forecasts reuse physical integration work instead of recomputing for each actor',()=>{
 const {BallPhysics}=require('../football-sim');
 const {m,owner,link}=fixture();
 m.ball={x:40,z:15,y:2,vx:10,vz:1,vy:4};
 Object.assign(owner,{x:-20,z:0});Object.assign(link,{x:-20,z:0});
 const step=BallPhysics.step;let calls=0;
 BallPhysics.step=function(...args){calls++;return step.apply(this,args);};
 try {
  const first=m.interceptPoint(owner);const initial=calls;
  assert(initial>0);assert.deepEqual(m.interceptPoint(link),first);
  assert.equal(calls,initial);
  m.ball.vz+=1;m.interceptPoint(link);assert(calls>initial);
 }finally{BallPhysics.step=step;}
});


test('pass scoring shares an observed opponent list across lane and reception forecasts',()=>{
 const {m,owner}=fixture();
 const lane=m.laneRisk.bind(m),reception=m.receptionSafety.bind(m),context=m.matchContext.bind(m);
 const lists=[];let contexts=0;
 m.laneRisk=(p,point,power,kind,opponents)=>{if(p===owner&&opponents)lists.push(opponents);return lane(p,point,power,kind,opponents);};
 m.receptionSafety=(p,q,point,seconds,opponents)=>{if(p===owner&&opponents)lists.push(opponents);return reception(p,q,point,seconds,opponents);};
 m.matchContext=team=>{contexts++;return context(team);};
 const options=m.passOptions(owner);
 assert(options.length>0);assert(lists.length>=2);
 assert(lists.every(list=>list===lists[0]));assert.equal(contexts,1);
});
test('a saturated pass lane never forecasts later defenders unnecessarily',()=>{
 const {m,owner}=fixture();
 const point={x:owner.x+15,z:owner.z};
 const first={x:owner.x+7,z:owner.z,vx:0,vz:0};
 const second={x:owner.x+8,z:owner.z,vx:0,vz:0,passFuture(){throw Error('fully blocked lane should not need another forecast');}};
 assert.equal(m.laneRisk(owner,point,17,'pass',[first,second]),1);
});


test('technical touch responds to actual foot, balance, agility and fatigue at equal overall rating',()=>{
 const {m,owner}=fixture();
 Object.assign(owner,{skill:82,dribbling:95,agility:93,balance:91,composure:92,preferredFoot:1,footPreference:'right',weakFoot:50,energy:1});
 const good=m.technicalTouchProfile(owner,1,1.2,2);
 const weak=m.technicalTouchProfile(owner,0,1.2,2);
 const average=m.technicalTouchProfile({...owner,dribbling:72,agility:70,balance:70,composure:70},1,1.2,2);
 const tired=m.technicalTouchProfile({...owner,energy:.35},1,1.2,2);
 for(const other of [weak,average,tired]){
  assert(good.precision>other.precision);assert(good.interval<other.interval);assert(good.retention<other.retention);
 }
 assert.equal(owner.energy,1);
});
test('technical cut is accepted only by the real touch forecast and never bypasses foot reach',()=>{
 for(const side of [1,-1]){
  const {m,owner,mid,back}=fixture(side);
  m.cfg.technicalTouchExperiment=true;mid.active=false;back.active=false;
  Object.assign(owner,{dribbling:95,agility:92,balance:91,composure:90,preferredFoot:1,footPreference:'right',weakFoot:65,energy:1,speed:1,vx:side,vz:0,touchClock:0,receiveClock:0,duelRecovery:0});
  owner.carryTarget={x:owner.x+side*3,z:3*side};m.ball={x:owner.x+.5*side,y:.11,z:0,vx:side,vy:0,vz:0};
  Object.assign(mid,{active:true,x:owner.x-3*side,z:0,vx:0,vz:0});
  m.planClock=0;
  const before={x:owner.x,z:owner.z,seed:m.seed};
  const calls=[],original=m.touchPlan;
  m.touchPlan=function(p,v,opts){const result=original.call(this,p,v,opts);calls.push({opts,result});return result;};
  m.dribbleTouch(owner);
  assert.equal(calls[0].opts.maxGap,1.12);
  if(m.telemetry.technicalCutTouches){
   assert(calls[0].result.ready);assert(calls[0].result.recovery.maxGap<=Math.max(calls[0].opts.maxGap,.5)+.05);
   assert.equal(m.ball.vx,calls[0].result.velocity.vx);assert.equal(m.ball.vz,calls[0].result.velocity.vz);
  }
  assert.deepEqual({x:owner.x,z:owner.z,seed:m.seed},before);
  m.ball.x=owner.x-2*side;const ball={...m.ball};
  assert.equal(m.dribbleTouch(owner),false);assert.deepEqual(m.ball,ball);
 }
});


test('territorial progress replaces a low-value retreat with a real forward link, preserving shots and safe return combinations',()=>{
 for(const side of [1,-1]){
  const {m,owner,link,mid,back}=fixture(side);
  Object.assign(owner,{x:8*side,z:0,face:side>0?0:Math.PI,receiveClock:0,duelRecovery:0,shieldUntil:0,carryTime:.5});
  Object.assign(link,{x:19*side,z:0});
  m.ball={x:8.6*side,z:0,y:.11,vx:side,vz:0,vy:0};
  m.observedLine=()=>40;
  const option={kind:'pass',q:link,point:{x:19*side,z:0},risk:.15,arrivalRisk:.25,space:5,score:6,distance:11};
  const retreat={kind:'carry',point:{x:6*side,z:0},hold:true};
  const carry={kind:'carry',point:{x:13*side,z:0},clearance:3,score:7};
  let attempts=0;m.passPreparation=()=>{attempts++;return {feasible:true};};
  m.controlPreparation=()=>({firstTouchTime:.12,interventionTime:null});
  const rivals=m.rivals(owner),before={ball:{...m.ball},x:owner.x,z:owner.z,seed:m.seed};
  assert(m.territorialProgression(owner,retreat,[option],carry,rivals,6).territorialPass);
  assert.equal(attempts,1);
  assert.deepEqual({ball:m.ball,x:owner.x,z:owner.z,seed:m.seed},before);
  const shot={kind:'shot',point:{x:52*side,z:0}};assert.equal(m.territorialProgression(owner,shot,[option],carry,rivals,6),shot);
  const combo={...retreat,kind:'pass',movingReturn:true};assert.equal(m.territorialProgression(owner,combo,[option],carry,rivals,6),combo);
  assert.equal(attempts,1);
  assert(m.territorialProgression(owner,retreat,[{...option,risk:.8}],carry,rivals,6).territorialCarry);
  assert.equal(attempts,1);
  m.passPreparation=()=>({feasible:false});m.controlPreparation=()=>({firstTouchTime:.12,interventionTime:.15});
  assert.equal(m.territorialProgression(owner,retreat,[option],carry,rivals,6),retreat);
  m.observedLine=()=>12;m.passPreparation=()=>{assert.fail('offside candidate cannot be previewed');};
  assert.equal(m.territorialProgression(owner,retreat,[option],carry,rivals,6),retreat);
 }
});
test('territorial correction defaults off in engine and can be enabled in an actual local match configuration',()=>{
 const {m,owner,link}=fixture();const before=m.cfg.territorialProgression;
 const chosen={kind:'carry',hold:true,point:{x:owner.x-2,z:0}},forward={kind:'pass',q:link,point:{x:link.x,z:link.z},risk:.1,arrivalRisk:.2,space:5,score:8,distance:11};
 m.clearFinish=()=>false;m.chooseFromOptions=()=>chosen;m.passOptions=()=>[forward];m.passPreparation=()=>({feasible:true});
 assert.equal(before,undefined);assert.equal(m.choose(owner),chosen);
 m.cfg.territorialProgression=true;
 assert(m.choose(owner).territorialPass);
});


test('progressive carry pace uses the supplied actor, ball and deadline without changing the live player',()=>{
 for(const side of [1,-1]){
  const {m,owner}=fixture(side);
  Object.assign(owner,{x:8*side,z:0,face:side>0?0:Math.PI,receiveClock:0,shieldUntil:0,settleUntil:0,escapeUntil:0,carryTarget:{x:14*side,z:0},carryIntent:{progressive:true,until:m.time+1}});
  const ball={x:8.6*side,z:0,y:.11,vx:side,vz:0,vy:0},rivals=[{x:8*side,z:7,vx:0,vz:0}];
  const before=structuredClone(owner);
  assert.equal(m.ownerCarryPace(owner,rivals,7,ball,m.time),.96);
  assert.equal(m.ownerCarryPace(owner,rivals,7,ball,m.time+2),.60);
  assert.equal(m.ownerCarryPace(owner,[{x:11*side,z:1,vx:0,vz:0}],7,ball,m.time),.60);
  assert.equal(m.ownerCarryPace({...owner,receiveClock:.1},rivals,7,ball,m.time),.48);
  assert.equal(m.ownerCarryPace(owner,rivals,7,{...ball,x:21*side},m.time),.98);
  assert.equal(m.ownerCarryPace({...owner,x:12.9*side},rivals,7,{...ball,x:13.4*side},m.time),.60);
  assert.deepEqual(owner,before);
 }
});
test('control preparation uses the copied actor and the same progressive speed rule as live planning',()=>{
 const {m,owner,mid,back,link,keeper}=fixture();
 m.cfg.consistentCarryForecast=true;
 mid.x=8;mid.z=8;back.active=link.active=keeper.active=false;
 Object.assign(owner,{face:0,speed:1,vx:1,vz:0,receiveClock:0,duelRecovery:0,shieldUntil:0,settleUntil:0,escapeUntil:0,touchClock:0,carryTime:.2});
 m.ball={x:8.6,z:0,y:.11,vx:1,vy:0,vz:0};
 const before=structuredClone({owner,ball:m.ball,seed:m.seed});
 const reads=[],pace=m.ownerCarryPace;
 m.ownerCarryPace=function(p,r,pressure,ball,time,target){const result=pace.call(this,p,r,pressure,ball,time,target);reads.push({copied:p!==owner,progressive:!!p.carryIntent?.progressive,result});return result;};
 m.controlPreparation(owner,{kind:'carry',point:{x:14,z:0},clearance:5,openFieldCarry:true,commit:.65},null,.45);
 assert(reads.some(r=>r.copied&&r.progressive&&r.result===.96));
 assert.deepEqual({owner,ball:m.ball,seed:m.seed},before);
});
