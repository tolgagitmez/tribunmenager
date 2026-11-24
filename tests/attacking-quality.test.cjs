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
