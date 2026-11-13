#!/usr/bin/env node
'use strict';
// Controlled coverage of uncommon live contact paths. These selected fixtures
// are not a natural match sample and their outcome frequencies are not quality rates.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {Match,BallPhysics,segment}=require('../football-sim'),Rig=require('../humanoid-rig');
const root=path.resolve(__dirname,'..'),dt=1/60,hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const centredStrikeRandom=()=>.5;
const scenarios=[
 {id:'cross-header-right',kind:'header',side:1,expected:'headed-shot'},
 {id:'cross-header-left',kind:'header',side:-1,expected:'headed-shot'},
 {id:'cross-headed-pass',kind:'headed-pass',side:1,expected:'headed-pass'},
 {id:'cross-defensive-clearance',kind:'aerial-clearance',side:1,expected:'aerial-clearance'},
 {id:'cross-without-aerial-recipient',kind:'aerial-miss',side:1,expected:'no-aerial-contact'},
 {id:'cutback-received-right',kind:'cutback',side:1,expected:'teammate-reception'},
 {id:'cutback-received-left',kind:'cutback',side:-1,expected:'teammate-reception'},
 {id:'cutback-intercepted',kind:'cutback-intercept',side:1,expected:'opponent-reception'},
 {id:'fast-cutback-loose-control',kind:'cutback-loose',side:1,expected:'loose-control'},
 {id:'shot-blocked-by-body',kind:'shot-block',side:1,expected:'body-block'},
 {id:'offside-at-real-contact',kind:'offside',side:1,expected:'offside-restart'},
 {id:'onside-at-real-contact',kind:'onside',side:1,expected:'teammate-reception'},
 {id:'keeper-central-catch-right',kind:'keeper-catch',side:1,expected:'held-catch'},
 {id:'keeper-central-catch-left',kind:'keeper-catch',side:-1,expected:'held-catch'},
 {id:'keeper-fast-one-hand-parry',kind:'keeper-parry',side:1,expected:'parry'},
 {id:'keeper-fast-two-hands-catch',kind:'keeper-fast-catch',side:1,expected:'held-catch'},
 {id:'keeper-skill60-matched-flight',kind:'keeper-skill-low',side:1,expected:'parry',matchedPair:'keeper-skill-profile'},
 {id:'keeper-skill94-matched-flight',kind:'keeper-skill-high',side:1,expected:'held-catch',matchedPair:'keeper-skill-profile'},
 {id:'keeper-own-backpass-no-hands',kind:'keeper-backpass',side:1,expected:'foot-control'},
 {id:'keeper-short-reaction-window',kind:'keeper-late',side:1,expected:'goal-before-contact'},
 {id:'keeper-screened-view',kind:'keeper-screened',side:1,expected:'goal-before-contact'}
];
function activate(p,x,z,extra={}){
 return Object.assign(p,{active:true,x,z,vx:0,vz:0,speed:0,face:p.team?Math.PI:0,skill:100,passing:100,shooting:100,heading:100,dribbling:100,pace:82,agility:82,vision:100,composure:100,touchClock:0,tackleClock:100,receiveClock:0,duelRecovery:0,decision:100,action:'idle',actionClock:0,actionElapsed:0,stamina:92,energy:1},extra);
}
function base(rig=false){
 const m=new Match({seed:21},rig?Rig:null);m.restart=null;m.kick=null;m.goalPause=null;m.time=10;m.planClock=1e6;m.targets=new Map();m.events=[];m.queue=[];m.owner=null;m.flight=null;
 for(const p of m.players)p.active=false;
 return m;
}
const player=p=>({id:p.id,team:p.team,role:p.role,x:p.x,z:p.z,vx:p.vx,vz:p.vz,face:p.face,skill:p.skill,handling:p.handling,reactions:p.reactions,passing:p.passing,shooting:p.shooting,heading:p.heading,touchClock:p.touchClock,tackleClock:p.tackleClock,receiveClock:p.receiveClock,duelRecovery:p.duelRecovery,action:p.action,actionClock:p.actionClock});
function frame(m){return {time:m.time,seed:m.seed,ball:{...m.ball},ownerId:m.owner?.id??null,flight:m.flight?{id:m.flight.id,kind:m.flight.kind,fromId:m.flight.from.id,targetId:m.flight.target?.id??null,age:m.flight.age,offsidePlayers:[...(m.flight.offsidePlayers||[])]}:null,restart:m.restart?{kind:m.restart.kind,team:m.restart.team}:null,activePlayers:m.players.filter(p=>p.active&&!p.referee).map(player)};}
function fingerprint(m){
 const seen=new Map();
 function encode(value){
  if(value===null)return ['null'];if(value===undefined)return ['undefined'];
  if(typeof value==='number')return ['number',Number.isNaN(value)?'NaN':value===Infinity?'Infinity':value===-Infinity?'-Infinity':Object.is(value,-0)?'-0':value];
  if(typeof value!=='object')return [typeof value,String(value)];
  if(seen.has(value))return ['ref',seen.get(value)];const id=seen.size;seen.set(value,id);
  if(value instanceof Map)return ['map',id,[...value].map(([k,v])=>[encode(k),encode(v)])];
  if(value instanceof Set)return ['set',id,[...value].map(encode)];
  return [Array.isArray(value)?'array':'object',id,Object.keys(value).sort().map(k=>[k,encode(value[k])])];
 }
 // The optional immutable motion module has functions and a WeakMap. Its file
 // hash is recorded separately; every ordinary own Match field is retained.
 return hash(JSON.stringify(encode({...m,motion:null})));
}
function fixture(s){
 const side=s.side,team=side>0?0:1,other=1-team,index=team*11,rig=['keeper-fast-catch','keeper-skill-low','keeper-skill-high'].includes(s.kind),m=base(rig);
 const p=activate(m.players[index],29*side,-18*side),q=activate(m.players[index+1],43*side,0);
 let target=q,point={x:q.x,z:q.z},kind='cross',power;
 if(s.kind==='headed-pass'){Object.assign(p,{x:-14*side,z:-12*side});Object.assign(q,{x:0,z:0});point={x:q.x,z:q.z};}
 if(s.kind==='aerial-clearance'){q.active=false;target=activate(m.players[other*11+3],43*side,0,{role:'DEF'});}
 if(s.kind==='aerial-miss'){q.active=false;target=null;}
 if(s.kind.startsWith('cutback')){
  Object.assign(p,{x:45*side,z:20*side});Object.assign(q,{x:35*side,z:0});point={x:q.x,z:q.z};kind='cutback';
  if(s.kind==='cutback-intercept')activate(m.players[other*11+3],40*side,10*side);
  if(s.kind==='cutback-loose')power=30;
 }
 if(s.kind==='shot-block'){
  // This contact-path fixture uses a centred strike; general match scatter
  // remains exercised by natural samples and the separate profile comparisons.
  m.random=centredStrikeRandom;
  Object.assign(p,{x:36*side,z:0});q.active=false;activate(m.players[other*11+3],43*side,0,{role:'DEF'});kind='shot';point={x:52*side,z:0};target=null;
 }
 if(['offside','onside'].includes(s.kind)){
  Object.assign(p,{x:35*side,z:0});Object.assign(q,{x:(s.kind==='offside'?45:39)*side,z:4*side});
  activate(m.players[other*11+3],40*side,15*side,{role:'DEF'});activate(m.players[other*11+10],49*side,0,{role:'GK'});kind='pass';point={x:q.x,z:q.z};
 }
 if(s.kind.startsWith('keeper')){
  q.active=false;const g=activate(m.players[other*11+10],49*side,0,{role:'GK',skill:s.kind==='keeper-skill-low'?60:s.kind==='keeper-skill-high'?94:82,face:side>0?Math.PI:0});
  // Since stage11 handling/reactions are independent of overall quality.
  g.handling=g.reactions=g.skill;
  Object.assign(p,{x:35*side,z:8*side});
  if(s.kind==='keeper-backpass'){p.active=false;target=activate(m.players[other*11+3],35*side,8*side);}
  else target=p;
  const profile=s.kind==='keeper-skill-low'||s.kind==='keeper-skill-high',fast=profile||['keeper-parry','keeper-fast-catch','keeper-late','keeper-screened'].includes(s.kind),speed=profile?30:fast?25:10,x=profile?38:s.kind==='keeper-late'?47:fast?40:45;
  m.ball={x:x*side,y:1,z:0,vx:speed*side,vy:BallPhysics.verticalLaunch(49-x,speed,1,1,7,0),vz:0};m.lastTouch=target;m.lastTeam=target.team;
  m.flight={id:1,from:target,target:null,kind:s.kind==='keeper-backpass'?'pass':'shot',age:0};m.releaseSerial=1;
  if(s.kind==='keeper-screened')activate(m.players[index+7],47*side,.3*side,{touchClock:100});
  return {m,p:target,q:null,g,team,kind:m.flight.kind,point:null,power:null,launchMode:'specified-incoming-flight',motion:rig?'real-rig-two-hands':'fallback-single-hand'};
 }
 p.face=Math.atan2(point.z-p.z,point.x-p.x);m.owner=p;m.lastTouch=p;m.lastTeam=team;
 const cp=m.contactPoint(p);m.ball={x:cp[0],y:cp[1],z:cp[2],vx:0,vy:0,vz:0};
 return {m,p,q:target,g:null,team,kind,point,power,launchMode:'actual-windup-release',motion:'fallback-single-hand'};
}
function runScenario(s){
 if(typeof s==='string'){const found=scenarios.find(x=>x.id===s);assert(found,'unknown fixture');s=found;}
 const f=fixture(s),{m,p,q,g,team}=f,start=frame(m),beforeSeed=m.seed,beforeSerial=m.releaseSerial;
 let windupFrames=0,flightFrames=0,maxPlayerStep=0,launch;
 const aerial=new Set(),contacts=new Set(),aerialWindows=new Set(),keeperActions=new Set(),trace=[];
 if(f.launchMode==='actual-windup-release'){
  assert(m.startKick(p,f.kind,q,f.point,f.power),'real preparation must begin');
  for(;windupFrames<150&&m.kick;windupFrames++)m.step(dt);
  assert(!m.kick&&m.flight&&m.releaseSerial>beforeSerial,'a real foot strike must release this fixture');
 }
 launch=frame(m);const actualRelease=m.releaseSerial>beforeSerial&&f.launchMode==='actual-windup-release';
 const releasedTargetOffside=!!q&&m.flight?.offsidePlayers?.includes(q.id);
 const initialGoal=BallPhysics.atX(m.ball,(g?.team===0?-52:52),1.6),geometricThreat=!!g&&Math.sign(m.ball.vx)===s.side&&!!initialGoal&&Math.abs(initialGoal.z)<4.7&&initialGoal.y<2.9;
 const shouldStop=()=>m.owner||m.restart||m.goalPause||m.events.some(e=>['header','clearance','block','save'].includes(e.type))||(m.telemetry.looseBalls||0)>0;
 for(;flightFrames<300&&!shouldStop();flightFrames++){
  const before=frame(m),next=BallPhysics.predict(m.ball,dt),flight=m.flight;
  if(flight?.kind==='cross'&&next.vy<=0&&next.y>=1.60&&next.y<=2.15){
   aerialWindows.add(flight.id);
   for(const a of m.players)if(a.active&&!a.referee&&a.role!=='GK'&&!(a.duelRecovery>0)&&segment(a,m.ball,next).d<.43)aerial.add(`${flight.id}:${a.id}`);
  }
  if(flight&&next.y<1.05)for(const a of m.players)if(a.active&&!a.referee&&a.role!=='GK'&&a.touchClock<=0&&!(a.duelRecovery>0)&&segment(a,m.ball,next).d<(a===flight.target?1.10:a.team===flight.from.team?.92:.72))contacts.add(`${flight.id}:${a.id}`);
  if(g){
   // Normal Match.step executes the real visibility, reaction, hand motion,
   // swept hand contact and custody rules. No prepared action is injected.
   m.step(dt);keeperActions.add(g.action);
  }else{
   // Flight-only trials hold bodies at their initial locations. Clocks and
   // actions age at 60 Hz; ordinary BallPhysics/aerial/contact methods decide.
   m.time+=dt;
   for(const a of m.players){
    for(const key of ['touchClock','tackleClock','receiveClock','duelRecovery','footTouch'])a[key]=Math.max(0,(a[key]||0)-dt);
    if(a.actionClock>0){a.actionClock=Math.max(0,a.actionClock-dt);a.actionElapsed+=dt;if(a.actionClock===0)a.action='idle';}
   }
   m.ballStep(dt);
  }
  for(const a of m.players.filter(a=>a.active&&!a.referee)){const previous=before.activePlayers.find(x=>x.id===a.id);if(previous)maxPlayerStep=Math.max(maxPlayerStep,Math.hypot(a.x-previous.x,a.z-previous.z));}
  if(shouldStop()||trace.length===0)trace.push({frame:flightFrames+1,...frame(m)});
 }
 const events=m.events.map(e=>({type:e.type,title:e.title,time:e.time,team:e.team,playerId:e.playerId}));
 let outcome=m.telemetry.headers?'headed-shot':m.telemetry.headedPasses?'headed-pass':events.some(e=>e.type==='clearance')?'aerial-clearance':events.some(e=>e.type==='offside')?'offside-restart':events.some(e=>e.type==='block')?'body-block':g&&g.holdingBall?'held-catch':events.some(e=>e.type==='save')?'parry':g&&m.owner===g?'foot-control':m.goalPause?'goal-before-contact':m.owner?(m.owner.team===team?'teammate-reception':'opponent-reception'):(m.telemetry.looseBalls||0)>0?'loose-control':'no-aerial-contact';
 assert.equal(outcome,s.expected,`${s.id}: fixture outcome drifted`);assert(maxPlayerStep<=.15,'real keeper frame moved a body too far');
 const result={id:s.id,kind:s.kind,side:s.side,seed:21,matchedPair:s.matchedPair??null,launchMode:f.launchMode,motion:f.motion,bodyMode:g?'normal-match-steps':'fixed-bodies-during-free-flight',clockStep:dt,frames:{windup:windupFrames,flight:flightFrames},start,launch,end:frame(m),outcome,events,trace,opportunities:{actualFootReleases:actualRelease?1:0,crossReleases:actualRelease&&f.kind==='cross'?1:0,descendingCrossWindows:aerialWindows.size,eligibleAerialContacts:aerial.size,cutbackReleases:actualRelease&&f.kind==='cutback'?1:0,fieldContactApproaches:contacts.size,flaggedOffsideFlights:releasedTargetOffside?1:0,keeperGeometricThreatFlights:geometricThreat?1:0,keeperOpponentShotFlights:g&&f.kind==='shot'?1:0,keeperOwnBackpassFlights:g&&f.kind==='pass'?1:0},counts:{headers:m.telemetry.headers||0,headedPasses:m.telemetry.headedPasses||0,cutbacks:m.telemetry.cutbacks||0,offsides:m.telemetry.offsides||0,keeperCatches:m.telemetry.keeperCatches||0,fastCatches:m.telemetry.fastCatches||0,screenedReads:m.telemetry.screenedReads||0,looseBalls:m.telemetry.looseBalls||0,completedPasses:m.completed.reduce((a,b)=>a+b,0),shotEvents:events.filter(e=>e.type==='shot').length,saveEvents:events.filter(e=>e.type==='save').length,goalEvents:events.filter(e=>e.type==='goal').length},keeperActions:[...keeperActions],rng:{before:beforeSeed,after:m.seed},fullStateSHA256:fingerprint(m),maxPlayerStep};
 return {result,match:m};
}
function buildCoverageReport(){
 const rows=[],outcomes={},opportunities={};
 for(const s of scenarios){
  const first=runScenario(s),second=runScenario(s);
  assert.deepEqual(first.match,second.match,`${s.id}: complete Match replay differs`);assert.deepEqual(first.result,second.result,`${s.id}: result replay differs`);
  rows.push({...first.result,deterministicReplay:true});outcomes[first.result.outcome]=(outcomes[first.result.outcome]||0)+1;
  for(const [name,count]of Object.entries(first.result.opportunities))opportunities[name]=(opportunities[name]||0)+count;
 }
 const files=['football-sim.js','match-rules.js','referee-laws.js','pitch-laws.js','player-model.js','player-model-profiles.json','humanoid-rig.js',path.relative(root,__filename),'tests/attacking-coverage.test.cjs'];
 return {sources:Object.fromEntries(files.map(file=>[file,hash(fs.readFileSync(path.join(root,file)))])),sample:'controlled-coverage',naturalSample:false,method:'Specified deterministic starting geometry. All cases use the ordinary seeded RNG except shot-blocked-by-body, which fixes the random draw to 0.5 for a centred contact-path strike. Keeper handling/reactions are explicitly set alongside their selected overall values since stage11. Field delivery cases execute the real kick windup/release, then fixed-body BallPhysics/ballStep at 60Hz; keeper cases begin with a specified incoming flight and execute ordinary Match.step visibility/reaction/hands/custody. The centred-strike RNG override is the only method override; no player relocation during flight or direct event/counter writes occurs. Two complete own Match states, including RNG, are deeply compared per fixture; immutable motion module is separately source-hashed.',definitions:{opportunity:'Counts are explicit fixture inputs or geometric contact windows, not representative natural frequencies. Distinct cross/body pairs in the real descending 1.60–2.15m contact window are counted once, separately from released crosses and actual headers. Ground contact approaches are geometry plus existing clocks; they do not imply feasible possession.',keeper:'Geometric threat uses the real initial ball trajectory to the goal plane. Opponent-shot and own-backpass fixtures are separate. Save events distinguish custody from parry; specified incoming flights are not counted as executed shots. The fast-catch trial uses the real rig two-hand model; other keeper trials use the existing fallback single hand.',limits:'Selected positive and negative fixtures establish path coverage only. Counts and denominators must not be converted to natural conversion/save rates or evidence that aerial/keeper quality is balanced. Fixed-body free-flight tests do not verify tactical runs, whole matches, fatigue or animation quality.'},fixtureCount:rows.length,opportunities,outcomes,runs:rows,verified:true};
}
if(require.main===module){const report=buildCoverageReport();fs.mkdirSync(path.join(root,'docs/validation'),{recursive:true});fs.writeFileSync(path.resolve(root,process.argv[2]||'docs/validation/match-laws-coverage.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify({verified:true,fixtures:report.fixtureCount,opportunities:report.opportunities,outcomes:report.outcomes})+'\n');}
module.exports={scenarios,runScenario,buildCoverageReport};
