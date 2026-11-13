'use strict';
/* Passive attack analysis. No decision, forecast or random query is made. */
(function(root){
const attached=new WeakMap(),stages=['gain','pressureEscape','lineBreak','finalThird','box','shot'];
const passKinds=new Set(['pass','through','cross','cutback','long-pass']);
const supportStates=new Set(['support','build-support','return-support','between-lines','wide-support','inside-support']);
const boxStates=new Set(['box-run','cutback-support','channel-run','penetration']);
const defaultSide=t=>t===0?1:-1,finite=Number.isFinite,team=t=>t===0||t===1;
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z),point=p=>p&&finite(p.x)&&finite(p.z)?{x:p.x,z:p.z}:null;
const clone=value=>JSON.parse(JSON.stringify(value));
const add=(o,k,n=1)=>{o[k]=(o[k]||0)+n;};
const emptyStages=()=>Object.fromEntries(stages.map(s=>[s,0]));
const ratio=(a,b)=>b>0?a/b:null;
const segment=(p,a,b)=>{const x=b.x-a.x,z=b.z-a.z,n=x*x+z*z,u=n?Math.max(0,Math.min(1,((p.x-a.x)*x+(p.z-a.z)*z)/n)):0;return {u,d:Math.hypot(p.x-a.x-x*u,p.z-a.z-z*u)};};
const definitions={
 version:1,stages,
 attack:'An episode starts on an actual successful acquire, actual restart release or an already active possession at attachment. A physical shot release ends the episode; a same-team rebound control starts another episode. New opponent control or a dead ball also ends it. Window/match end is right-censored, not failure.',
 control:'Acquire is a contact/intention, recorded separately from settled control. Confirmation requires at least 0.15 continuous sampled seconds with ball centre gap<=1.45m and height<=0.65m (or hands), or an actual release. Aerial contact is confirmed physical contact, not a settled ground reception.',
 zones:'Team-relative physical ball position, never a commanded destination. Final third begins at 52/3m; box begins at 35.5m and |z|<=20.16m. A sampled zone needs 0.15 continuous controlled seconds; actual release/header contact qualifies immediately. An episode starting inside a zone is labelled at-start and excluded from that zone progression denominator.',
 pressureEscape:'Eligible only when a live opposing outfielder is within 4m at episode start. After confirmed control, keep the ball controlled with nearest rival>=5m for 0.5 continuous sampled seconds. No initial pressure is not-required, not a successful escape. This geometric pressure proxy is not the player perception model.',
 lineBreak:'Operational proxy, not certified formation recognition: freeze at least two outfield rival IDs ahead of the physical origin (>=1m) within a 12m lateral band. At a later confirmed control/release, advance>=2m and be>=1m beyond both their frozen and current positions. The reference is refreshed from an actual pass release, not its planned destination.',
 clocks:'Classify each observer.step interval from the state before the real step, using actual match time delta. Open-play windup, loose ball and goalkeeper holding are in play; placed restart windup, goal pause and halftime are dead. Restart, goal-pause and halftime bins partition dead-ball seconds. Territory uses the current period attack direction; halftime censors the old episode before the ends change. A boundary has at most one supplied step of classification uncertainty. Manual sample gaps over 0.05s are unobserved, not invented in-play time. Controlled, flight and loose bins partition in-play seconds.',
 evidence:'Hold decisions/time, low-speed control, support commands/readiness by centre gap<=3m and box runner commands/arrivals are observed facts. They do not prove unnecessary waiting, a safe available pass, the best decision, or a causal tactical defect. No additional choose/passOptions/shotWindow/forecast query is made.',
 coverage:'Natural counters measure actual processed windows and method/event outcomes. Descending cross windows and candidate reach are geometric samples; keeper processing opportunities are distinct keeperRead keys actually created by the engine. They are not all possible chances or quality ratings. Controlled scenario reports must remain separate.',
 truncation:'Team aggregates retain every observed episode. maxEpisodes bounds detailed closed-episode and shot traces; dropped detail counts are explicit. Reading a report never ends an active episode.'
};
function attach(match,options={}){
 if(!match||typeof match.step!=='function')throw new TypeError('A Match instance is required');
 if(attached.has(match))throw new Error('Attack diagnostics already attached to this match');
 const side=t=>typeof match.direction==='function'?match.direction(t):defaultSide(t);
 const inBox=(p,t)=>p.x*side(t)>=35.5&&Math.abs(p.z)<=20.16;
 const maxEpisodes=Math.max(1,Math.floor(finite(options.maxEpisodes)?options.maxEpisodes:2000));
 const originals=new Map(),errors=[],records=[],shotRecords=[],passRecords=new Map(),seenFlights=new WeakMap();
 let detached=false,active=null,serial=0,foreignSerial=0,dropped=0,droppedShots=0,lastBoundary=null,lastShot=null,pendingShot=null,pendingKick=null,keeperDepth=0;
 const clock={start:Number(match.time)||0,end:Number(match.time)||0,observedSeconds:0,inPlaySeconds:0,deadBallSeconds:0,restartSeconds:0,goalPauseSeconds:0,halftimeSeconds:0,controlledSeconds:[0,0],flightSeconds:[0,0],looseSeconds:0,unobservedSeconds:0};
 const evidence=()=>({holdDecisions:0,holdSeconds:0,stationaryControlSeconds:0,heldStationarySeconds:0,supportMissingSeconds:0,supportUnreadySeconds:0,readySupportSeconds:0,passPreparationAborts:0,preparationReplans:0,boxRunnerCommands:0,boxRunnerArrivals:0,boxRunnerCommandSeconds:0,boxRunnerReadySeconds:0,duelDislodgements:0,controlDislodgements:0});
 const passTotals=()=>({attempted:0,completed:0,intercepted:0,looseOrDeflected:0,out:0,offside:0,interrupted:0,unknown:0,returnedToSender:0,goalsWithoutShot:0,headerContacts:0,defensiveHeaders:0});
 const teams=[0,1].map(t=>({team:t,attacks:0,origins:{},contactGains:0,confirmedGains:0,unsettledGains:0,stageCounts:emptyStages(),stageEligibility:emptyStages(),eligibleReached:emptyStages(),startedBeyond:emptyStages(),notRequired:emptyStages(),endedByStage:{},endReasons:{},pending:0,censored:0,ended:0,passes:passTotals(),shots:0,evidence:evidence()}));
 const coverage={crosses:{releases:0,descendingWindows:0,reachableWindows:0,contacts:0,headedShots:0,headedPasses:0,defensiveClearances:0},cutbacks:{releases:0,completed:0,intercepted:0},offsides:{flaggedPlayersAtRelease:0,flaggedFlightsAtRelease:0,contactChecks:0,flaggedContactChecks:0,incidents:0},keepers:{processingOpportunities:0,preparations:0,catches:0,parries:0,screenedReads:0},shots:{physical:0,prepared:0,goalEvents:0,goals:0,nonShotGoalEvents:0,unattributedGoalEvents:0,blocked:0,out:0,opponentControl:0,reboundControl:0}};
 const windows=new Set(),reachableWindows=new Set(),keeperReads=new Set(),keeperPreparations=new Set(),keeperScreens=new Set();
 const time=()=>finite(match.time)?match.time:clock.end;
 const alive=p=>p&&p.active!==false&&!p.referee&&team(p.team);
 const rivals=t=>(match.players||[]).filter(p=>alive(p)&&p.team!==t&&p.role!=='GK');
 const pressure=(t,p)=>Math.min(99,...rivals(t).map(q=>distance(q,p)));
 const flightKey=f=>{if(!f)return null;if(f.id!==undefined)return String(f.id);if(!seenFlights.has(f))seenFlights.set(f,'unidentified-'+(++foreignSerial));return seenFlights.get(f);};
 const safe=fn=>{try{return fn();}catch(error){if(errors.length<20)errors.push({time:time(),message:String(error?.message||error)});return undefined;}};
 const bump=(key,n=1,episode=active)=>{if(!episode)return;add(episode.evidence,key,n);add(teams[episode.team].evidence,key,n);};
 function screen(t,origin){return {origin:{...origin},rivals:rivals(t).filter(q=>q.x*side(t)>=origin.x*side(t)+1&&Math.abs(q.z-origin.z)<=12).map(q=>({id:q.id,x:q.x,z:q.z}))};}
 function stage(ep,name,p,method,atStart=false){
  if(ep.stages[name])return;
  ep.stages[name]={time:time(),x:p.x,z:p.z,playerId:match.owner?.team===ep.team?match.owner.id:ep.lastPlayerId??null,method,entryMode:atStart?'at-start':'progression'};
  add(teams[ep.team].stageCounts,name);if(ep.eligibility[name])add(teams[ep.team].eligibleReached,name);
  if(stages.indexOf(name)>stages.indexOf(ep.lastStage))ep.lastStage=name;
 }
 function zones(ep,p,method,immediate=false,dt=0){
  for(const [name,inside]of [['finalThird',p.x*side(ep.team)>=52/3],['box',inBox(p,ep.team)]]){
   ep.zoneDwell[name]=inside?ep.zoneDwell[name]+dt:0;
   if(inside&&(immediate||ep.settledSeconds>=.15-1e-8&&ep.zoneDwell[name]>=.15-1e-8))stage(ep,name,p,method,ep.startedBeyond[name]);
  }
 }
 function confirm(ep,p,method){
  if(!ep.confirmedControl){ep.confirmedControl=true;ep.confirmedAt=time();if(ep.origin==='gain'){teams[ep.team].confirmedGains++;stage(ep,'gain',p,method);}}
 }
 function lineBreak(ep,p,method){
  if(ep.stages.lineBreak||!ep.eligibility.lineBreak)return;
  const reference=ep.controlReference||ep.initialScreen;if(!reference||p.x*side(ep.team)<reference.origin.x*side(ep.team)+2)return;
  const current=new Map(rivals(ep.team).map(q=>[q.id,q])),crossed=reference.rivals.filter(q=>current.has(q.id)&&p.x*side(ep.team)>=Math.max(q.x*side(ep.team),current.get(q.id).x*side(ep.team))+1);
  if(crossed.length>=2){stage(ep,'lineBreak',p,method);ep.stages.lineBreak.rivalIds=crossed.map(q=>q.id);ep.stages.lineBreak.origin={...reference.origin};}
 }
 function view(ep){
  return clone({id:ep.id,team:ep.team,origin:ep.origin,leftCensored:ep.origin==='left-censored',start:ep.start,end:ep.end??null,status:ep.status,endReason:ep.endReason??null,lastStage:ep.lastStage,lastStageMode:ep.stages[ep.lastStage]?.entryMode??'start-location',startPosition:ep.startPosition,endPosition:ep.endPosition??null,confirmedControl:ep.confirmedControl,confirmedAt:ep.confirmedAt??null,contactGain:ep.origin==='gain',pressureRequired:ep.pressureRequired,initialPressure:ep.initialPressure,stages:ep.stages,eligibility:ep.eligibility,startedBeyond:ep.startedBeyond,notRequired:ep.notRequired,passes:{...ep.passes,pending:[...passRecords.values()].filter(q=>q.episodeId===ep.id&&!q.outcome).length},evidence:ep.evidence,observations:ep.observations,truncatedObservations:ep.truncatedObservations||0,linkedShotId:ep.linkedShotId??null});
 }
 function begin(t,origin,p,playerId,extra={}){
  if(!team(t)||!point(p))return null;
  const initialPressure=pressure(t,p),initialScreen=screen(t,p),startedBeyond={finalThird:p.x*side(t)>=52/3,box:inBox(p,t)};
  const eligibility={gain:origin==='gain',pressureEscape:initialPressure<4,lineBreak:initialScreen.rivals.length>=2&&!startedBeyond.box,finalThird:!startedBeyond.finalThird,box:!startedBeyond.box,shot:true};
  active={id:++serial,team:t,origin,start:time(),status:'pending',startPosition:{...p},lastStage:startedBeyond.box?'box':startedBeyond.finalThird?'finalThird':'start',lastPlayerId:playerId??null,confirmedControl:false,settledSeconds:0,pressureRequired:eligibility.pressureEscape,initialPressure,pressureSafeSeconds:0,zoneDwell:{finalThird:0,box:0},stages:{},eligibility,startedBeyond,notRequired:{pressureEscape:!eligibility.pressureEscape,lineBreak:!eligibility.lineBreak},initialScreen,controlReference:initialScreen,passes:passTotals(),evidence:evidence(),observations:[],boxCommandPlayers:new Set(),boxArrivedPlayers:new Set(),holdUntil:0,lossCue:null,lossCueAt:null,...extra};
  const aggregate=teams[t];aggregate.attacks++;add(aggregate.origins,origin);if(origin==='gain')aggregate.contactGains++;
  for(const s of stages){if(eligibility[s])add(aggregate.stageEligibility,s);if(startedBeyond[s])add(aggregate.startedBeyond,s);if(active.notRequired[s])add(aggregate.notRequired,s);}
  return active;
 }
 function end(reason,status='ended',extra={}){
  if(!active)return;
  const ep=active,aggregate=teams[ep.team];ep.end=time();ep.endPosition=point(match.ball);ep.status=status;ep.endReason=reason;Object.assign(ep,extra);
  if(status==='censored')aggregate.censored++;else{aggregate.ended++;add(aggregate.endReasons,reason);aggregate.endedByStage[ep.lastStage]??={};add(aggregate.endedByStage[ep.lastStage],reason);}
  if(ep.origin==='gain'&&!ep.confirmedControl)aggregate.unsettledGains++;
  records.push(view(ep));if(records.length>maxEpisodes){records.shift();dropped++;}active=null;
 }
 function ensure(t,origin,p,actor,extra){if(active&&active.team!==t)end('opponent-control');return active||begin(t,origin,p,actor,extra);}
 function noteInto(ep,type,data={}){if(ep){if(ep.observations.length>=100){ep.observations.shift();ep.truncatedObservations=(ep.truncatedObservations||0)+1;}ep.observations.push({time:time(),type,...data});}}
 function note(type,data={}){noteInto(active,type,data);}
 function resolveShot(outcome,details={}){
  if(!pendingShot)return;pendingShot.status='resolved';pendingShot.outcome=outcome;pendingShot.resolvedAt=time();Object.assign(pendingShot,details);pendingShot=null;
 }
 function shot(t,method,p,actor,flightId){
  const ep=ensure(t,method==='header'?'aerial-touch':'left-censored',p,actor);if(!ep)return;
  ep.lastPlayerId=actor;confirm(ep,p,'physical-'+method);zones(ep,p,'physical-'+method,true);lineBreak(ep,p,'physical-'+method);stage(ep,'shot',p,'physical-'+method);
  teams[t].shots++;coverage.shots.physical++;
  const record={id:flightId??'shot-'+coverage.shots.physical,team:t,episodeId:ep.id,time:time(),x:p.x,z:p.z,playerId:actor,method,status:'pending',outcome:null};
  shotRecords.push(record);if(shotRecords.length>maxEpisodes){shotRecords.shift();droppedShots++;}pendingShot=record;lastShot={team:t,time:time(),id:record.id};end('shot');
 }
 function pass(t,kind,p,actor,f){
  const ep=ensure(t,'left-censored',p,actor);if(!ep)return;
  ep.lastPlayerId=actor;confirm(ep,p,'physical-release');zones(ep,p,'physical-release',true);lineBreak(ep,p,'physical-release');
  ep.passes.attempted++;teams[t].passes.attempted++;const id=flightKey(f);
  if(id!==null)passRecords.set(id,{id,team:t,kind,fromId:actor,targetId:f?.target?.id??null,episodeId:ep.id,episode:ep,reference:screen(t,p),outcome:null});
  if(kind==='cross')coverage.crosses.releases++;if(kind==='cutback')coverage.cutbacks.releases++;
  const flags=f?.offsidePlayers?.length||0;coverage.offsides.flaggedPlayersAtRelease+=flags;if(flags)coverage.offsides.flaggedFlightsAtRelease++;
 }
 function passOutcome(record,outcome){
  if(!record||record.outcome)return;record.outcome=outcome;
  const keys={'completed':'completed','intercepted':'intercepted','loose-or-deflected':'looseOrDeflected','out':'out','offside':'offside','interrupted':'interrupted','unknown':'unknown','returned-to-sender':'returnedToSender','goal-without-shot':'goalsWithoutShot','attacking-header':'headerContacts','defensive-header':'defensiveHeaders'};
  const key=keys[outcome]||'unknown';teams[record.team].passes[key]++;
  record.episode.passes[key]++;
  if(record.kind==='cutback'&&['completed','intercepted'].includes(outcome))coverage.cutbacks[outcome]++;
  noteInto(record.episode,'pass-outcome',{flightId:record.id,kind:record.kind,targetId:record.targetId,outcome});
  passRecords.delete(record.id);
  if(record.episode.status!=='pending'){const i=records.findIndex(ep=>ep.id===record.episodeId);if(i>=0)records[i]=view(record.episode);}
 }
 function supportFacts(ep){
  const support=[],box=[];
  for(const [p,target]of match.targets||[]){if(!alive(p)||p.team!==ep.team||p===match.owner||p.role==='GK')continue;
   if(supportStates.has(target.state))support.push({id:p.id,ready:distance(p,target)<=3});
   if(boxStates.has(target.state))box.push({id:p.id,inside:inBox(p,ep.team),state:target.state});
  }
  return {support,box};
 }
 function controlValid(owner=match.owner,b=match.ball){return alive(owner)&&!!b&&(owner.holdingBall===true||b.y<=.65&&distance(owner,b)<=1.45);}
 function frame(){
  const owner=match.owner,halftime=match.lifecycle==='halftime',controlled=!halftime&&controlValid(owner),dead=halftime||!!match.restart||!!match.kick?.restartContext||!!match.goalPause;
  let allocation='loose',allocationTeam=null;if(controlled){allocation='controlled';allocationTeam=owner.team;}else if(team(match.flight?.from?.team)){allocation='flight';allocationTeam=match.flight.from.team;}
  return {time:time(),dead,halftime,restart:!!match.restart||!!match.kick?.restartContext,goalPause:!!match.goalPause,allocation,allocationTeam,ownerId:owner?.id??null,ownerTeam:owner?.team??null,controlled,speed:owner?.speed??Math.hypot(owner?.vx||0,owner?.vz||0),ball:point(match.ball),ownerGap:owner&&match.ball?distance(owner,match.ball):null,episodeId:active?.id??null,episode:active,hold:!!active&&time()<active.holdUntil,support:active&&controlled?supportFacts(active):null,aborted:match.telemetry?.abortedKicks||0,looseBalls:match.telemetry?.looseBalls||0};
 }
 let previous=frame();
 function sampleWith(before,explicit=false){
  const now=time(),dt=now-clock.end;if(dt< -1e-8){errors.push({time:now,message:'Match time moved backwards; detach and attach a new observer after reset'});clock.end=now;previous=frame();return;}
  clock.end=now;if(dt>0){clock.observedSeconds+=dt;
   if(!explicit&&dt>.05+1e-8){clock.unobservedSeconds+=dt;if(active){active.settledSeconds=0;active.pressureSafeSeconds=0;active.zoneDwell.finalThird=active.zoneDwell.box=0;}}
   else if(before.dead){clock.deadBallSeconds+=dt;if(before.halftime)clock.halftimeSeconds+=dt;else if(before.goalPause)clock.goalPauseSeconds+=dt;else clock.restartSeconds+=dt;}
   else{
    clock.inPlaySeconds+=dt;if(before.allocation==='controlled')clock.controlledSeconds[before.allocationTeam]+=dt;else if(before.allocation==='flight')clock.flightSeconds[before.allocationTeam]+=dt;else clock.looseSeconds+=dt;
    if(before.episode&&before.controlled){
     const ep=before.episode;
     if(before.hold)bump('holdSeconds',dt,ep);if(before.speed<.6){bump('stationaryControlSeconds',dt,ep);if(before.hold)bump('heldStationarySeconds',dt,ep);}
     const facts=before.support;if(facts){bump(facts.support.length===0?'supportMissingSeconds':facts.support.some(q=>q.ready)?'readySupportSeconds':'supportUnreadySeconds',dt,ep);
      if(facts.box.length)bump('boxRunnerCommandSeconds',dt,ep);if(facts.box.some(q=>q.inside))bump('boxRunnerReadySeconds',dt,ep);
     }
     if(ep.status!=='pending'){const i=records.findIndex(q=>q.id===ep.id);if(i>=0)records[i]=view(ep);}
    }
   }
  }
  if(active){
   const p=match.owner,b=match.ball,controlled=controlValid(p,b)&&p.team===active.team;
   if(controlled){
    const controlledDt=before.episodeId===active.id&&before.controlled&&dt>0&&(explicit||dt<=.05+1e-8)?dt:0;
    active.lastPlayerId=p.id;active.settledSeconds+=controlledDt;
    if(active.settledSeconds>=.15-1e-8)confirm(active,b,'settled-control');
    zones(active,b,'settled-control',false,controlledDt);
    if(active.settledSeconds>=.15-1e-8){lineBreak(active,b,'settled-control');
     active.pressureSafeSeconds=active.pressureRequired&&pressure(active.team,b)>=5?active.pressureSafeSeconds+controlledDt:0;
     if(active.pressureSafeSeconds>=.5-1e-8)stage(active,'pressureEscape',b,'stable-controlled-space');
    }
    const facts=supportFacts(active);for(const q of facts.box){if(!active.boxCommandPlayers.has(q.id)){active.boxCommandPlayers.add(q.id);bump('boxRunnerCommands');}if(q.inside&&!active.boxArrivedPlayers.has(q.id)){active.boxArrivedPlayers.add(q.id);bump('boxRunnerArrivals');}}
   }else{active.settledSeconds=0;active.pressureSafeSeconds=0;active.zoneDwell.finalThird=active.zoneDwell.box=0;}
   if(before.ownerTeam===active.team&&before.ownerId!==null&&!match.owner&&!match.kick&&!match.flight&&!match.restart&&match.lastTouch?.team===active.team&&distance(match.lastTouch,b)>3.2){active.lossCue='control-lost';active.lossCueAt=time();bump('controlDislodgements');note('control-recovery-needed',{gap:distance(match.lastTouch,b)});}
  }
  if(pendingKick&&match.kick!==pendingKick.ref){
   if((match.telemetry?.abortedKicks||0)>before.aborted){if(passKinds.has(pendingKick.kind))bump('passPreparationAborts');note('preparation-aborted',{kind:pendingKick.kind,playerId:pendingKick.playerId});if(active){active.lossCue='preparation-abort';active.lossCueAt=time();}}
   pendingKick=null;
  }
  for(const record of passRecords.values())if(!record.outcome&&flightKey(match.flight)!==record.id&&match.owner===null&&!match.kick&&!match.restart)passOutcome(record,(match.telemetry?.looseBalls||0)>before.looseBalls?'loose-or-deflected':'unknown');
  if(match.done&&active)end('match-end','censored');previous=frame();
 }
 function beforeCall(name,args){
  const f=match.flight;
  if(name==='acquire')return {owner:match.owner,lastTeam:match.lastTeam,flight:f,flightId:flightKey(f),fromTeam:f?.from?.team,kind:f?.kind,ball:{...match.ball},role:args[0]?.role};
  if(name==='release')return {kick:match.kick,serial:match.releaseSerial,ball:{...match.ball}};
  if(name==='startKick')return {kick:match.kick};
  if(name==='aerial')return {flight:f,flightId:flightKey(f),resolved:f?.aerialResolved,ball:{...match.ball},shots:[...(match.shots||[0,0])],headedPasses:match.telemetry?.headedPasses||0};
  if(name==='doTackle')return {owner:match.owner,duels:match.telemetry?.duels||0};
  if(name==='keeper'){keeperDepth++;return {reads:new Map((match.players||[]).filter(p=>p.role==='GK').map(p=>[p.id,{ref:p.keeperRead,key:p.keeperRead?.key}]))};}
  if(name==='setRestart')return {flightId:flightKey(f),boundaryType:lastBoundary?.time===time()?lastBoundary.type:null};
  if(name==='offsideTouch'){coverage.offsides.contactChecks++;if(f?.offsidePlayers?.includes(args[0]?.id)&&f.from?.team===args[0]?.team)coverage.offsides.flaggedContactChecks++;}
  return null;
 }
 function afterCall(name,args,result,before){
  if(name==='acquire'&&result===true&&match.owner===args[0]){
   const p=args[0],record=passRecords.get(before.flightId);
   if(record)passOutcome(record,p.team===record.team?(p.id===record.fromId?'returned-to-sender':'completed'):'intercepted');
   if(active&&active.team!==p.team){const cue=time()-(active.lossCueAt??-Infinity)<=1.5?active.lossCue:null;const reason=before.fromTeam===active.team&&passKinds.has(before.kind)?'pass-interception':cue==='duel-displacement'?'duel-loss':cue==='control-lost'?'control-recovery-loss':cue==='preparation-abort'?'preparation-loss':p.role==='GK'?'keeper-possession':'opponent-control';end(reason);}
   const rebound=lastShot?.team===p.team&&time()-lastShot.time<5;
   if(pendingShot&&!(p.role==='GK'&&keeperDepth>0)){coverage.shots[p.team===pendingShot.team?'reboundControl':'opponentControl']++;resolveShot(p.team===pendingShot.team?'rebound-control':'opponent-control',{playerId:p.id});}
   const ep=ensure(p.team,before.lastTeam!==p.team?'gain':rebound?'rebound':'left-censored',before.ball,p.id,rebound?{linkedShotId:lastShot.id}:{});
   if(record?.team===p.team)ep.controlReference=record.reference;
   ep.lastPlayerId=p.id;ep.settledSeconds=0;ep.pressureSafeSeconds=0;ep.zoneDwell.finalThird=ep.zoneDwell.box=0;ep.lossCue=null;ep.lossCueAt=null;note('actual-acquire',{playerId:p.id,fromFlightId:before.flightId,receiveMode:p.receiveMode??null});
  }
  if(name==='release'&&before.kick&&match.kick!==before.kick&&match.releaseSerial>before.serial){
   const k=before.kick,p=k.p,ep=ensure(p.team,k.restartContext?'restart':'left-censored',before.ball,p.id);
   if(ep){ep.lastPlayerId=p.id;ep.lossCue=null;ep.lossCueAt=null;confirm(ep,before.ball,'physical-release');zones(ep,before.ball,'physical-release',true);lineBreak(ep,before.ball,'physical-release');}
   if(k.kind==='shot')shot(p.team,'foot',before.ball,p.id,flightKey(match.flight));else if(passKinds.has(k.kind))pass(p.team,k.kind,before.ball,p.id,match.flight);
   if(pendingKick?.ref===k)pendingKick=null;
  }
  if(name==='startKick'&&result===true&&match.kick&&match.kick!==before.kick){
   if(pendingKick&&pendingKick.ref!==match.kick)bump('preparationReplans');
   const k=match.kick;pendingKick={ref:k,kind:k.kind,playerId:k.p.id,time:time()};if(k.kind==='shot')coverage.shots.prepared++;
   if(!k.restartContext){const ep=ensure(k.p.team,'left-censored',match.ball,k.p.id),facts=supportFacts(ep);note('preparation-started',{kind:k.kind,playerId:k.p.id,targetId:k.target?.id??null,targetPosition:point(k.target),stage:ep.lastStage,supportCommands:facts.support.length,readySupportCommands:facts.support.filter(q=>q.ready).length,boxRunners:facts.box});}
  }
  if(name==='startCarry'&&active?.team===args[0]?.team){if(args[1]?.hold){bump('holdDecisions');active.holdUntil=Math.max(active.holdUntil,args[0].settleUntil||time());}const facts=supportFacts(active);note('carry-decision',{hold:!!args[1]?.hold,shield:!!args[1]?.shield,playerId:args[0].id,stage:active.lastStage,supportCommands:facts.support.length,readySupportCommands:facts.support.filter(q=>q.ready).length,boxRunners:facts.box});}
  if(name==='setRestart'){
   if(!match.restart&&match.done)return;
   const kind=match.restart?.kind??args[0],t=match.restart?.team??args[1],same=active?.team===t,sameRequest=kind===args[0]&&t===args[1]&&(!match.restart?.spot||distance(match.restart.spot,args[2])<1e-8),boundary=sameRequest?before.boundaryType:null;
   const reason=boundary==='offside'?'offside':['free-kick','penalty'].includes(kind)?(same?'foul-won':'foul-conceded'):kind==='throw'?(same?'out-retained':'out-loss'):kind==='corner'?(same?'corner-won':'corner-conceded'):kind==='goal-kick'?(same?'goal-kick-retained':'goal-kick-conceded'):'restart';
   const record=passRecords.get(before.flightId);if(record)passOutcome(record,reason==='offside'?'offside':['free-kick','penalty'].includes(kind)?'interrupted':'out');
   end(reason);if(pendingShot){coverage.shots.out++;resolveShot('out',{restartKind:kind,restartTeam:t});}pendingKick=null;lastBoundary=null;
  }
  if(name==='aerial'&&before.flight?.kind==='cross'){
   const b=before.ball,key=before.flightId,window=b.vy<=0&&b.y>=1.6&&b.y<=2.15&&!before.resolved;
   if(window&&!windows.has(key)){windows.add(key);coverage.crosses.descendingWindows++;}
   if(window&&!reachableWindows.has(key)&&(match.players||[]).some(p=>alive(p)&&p.role!=='GK'&&!(p.duelRecovery>0)&&segment(p,args[0],b).d<.43)){reachableWindows.add(key);coverage.crosses.reachableWindows++;}
   if(!before.resolved&&before.flight.aerialResolved){
    coverage.crosses.contacts++;const p=match.lastTouch,record=passRecords.get(key);if(active&&record?.episodeId===active.id)active.controlReference=record.reference;if(record)passOutcome(record,p?.team===record.team?'attacking-header':'defensive-header');
    if(p?.team!==before.flight.from?.team)coverage.crosses.defensiveClearances++;
    if((match.telemetry?.headedPasses||0)>before.headedPasses){coverage.crosses.headedPasses++;pass(p.team,'pass',b,p.id,match.flight);}
    for(const t of [0,1])if(match.shots[t]>before.shots[t]){coverage.crosses.headedShots++;shot(t,'header',b,p?.id,flightKey(match.flight));}
   }
  }
  if(name==='doTackle'&&before.owner&&match.owner!==before.owner&&(match.telemetry?.duels||0)>before.duels&&!match.restart&&active?.team===before.owner.team){active.lossCue='duel-displacement';active.lossCueAt=time();bump('duelDislodgements');note('duel-dislodged',{playerId:args[0]?.id});}
  if(name==='keeper'){
   keeperDepth=Math.max(0,keeperDepth-1);
   for(const p of match.players||[]){if(!alive(p)||p.role!=='GK'||!p.keeperRead)continue;const key=p.id+':'+p.keeperRead.key;
    const old=before.reads.get(p.id);if(!keeperReads.has(key)&&(old?.ref!==p.keeperRead||old?.key!==p.keeperRead.key)){keeperReads.add(key);coverage.keepers.processingOpportunities++;}
    if(!keeperReads.has(key))continue;
    if(p.keeperRead.screened&&!keeperScreens.has(key)){keeperScreens.add(key);coverage.keepers.screenedReads++;}
    if(['dive','catch-ready'].includes(p.action)&&!keeperPreparations.has(key)){keeperPreparations.add(key);coverage.keepers.preparations++;}
   }
  }
  if(name==='emit'){
   const type=args[0],p=args[3];lastBoundary={type,time:time()};
   if(type==='offside')coverage.offsides.incidents++;
   if(type==='goal'){const scoring=args[4]??p?.team??0;coverage.shots.goalEvents++;if(pendingShot&&pendingShot.team===scoring)coverage.shots.goals++;else if(pendingShot)coverage.shots.unattributedGoalEvents++;else coverage.shots.nonShotGoalEvents++;resolveShot('goal',{scoringTeam:scoring});const record=passRecords.get(flightKey(match.flight));if(record)passOutcome(record,'goal-without-shot');if(active)end(scoring===active.team?'goal':'opponent-goal');}
   if(type==='block'){coverage.shots.blocked++;resolveShot('blocked',{playerId:p?.id??null});note('shot-blocked');}
   if(type==='save'){const caught=!!p?.holdingBall;coverage.keepers[caught?'catches':'parries']++;resolveShot(caught?'keeper-catch':'keeper-parry',{playerId:p?.id??null});}
   if(type==='half'&&match.lifecycle==='halftime'&&active)end('halftime','censored');
   if(type==='end'&&active)end('match-end','censored');
  }
 }
 const methods=['acquire','release','startKick','startCarry','setRestart','aerial','keeper','doTackle','offsideTouch','emit'];
 // Validate first so a rejected attachment cannot leave a partially wrapped match.
 for(const name of methods){const descriptor=Object.getOwnPropertyDescriptor(match,name);
  if(descriptor&&(!Object.prototype.hasOwnProperty.call(descriptor,'value')||descriptor.configurable===false))throw new Error('Cannot observe non-configurable/accessor method: '+name);
  const original=match[name];if(typeof original!=='function')continue;
  if(!descriptor&&!Object.isExtensible(match))throw new Error('Cannot observe a non-extensible match');
  originals.set(name,{descriptor,original});
 }
 for(const [name,{descriptor,original}]of originals){
  const wrapper=function(...args){if(this!==match)return original.apply(this,args);const before=safe(()=>beforeCall(name,args));let result;
   try{result=original.apply(this,args);}catch(error){if(name==='keeper')keeperDepth=Math.max(0,keeperDepth-1);throw error;}
   safe(()=>afterCall(name,args,result,before));return result;
  };
  Object.defineProperty(match,name,descriptor?{...descriptor,value:wrapper}:{value:wrapper,configurable:true,writable:true,enumerable:false});
 }
 if(!previous.dead&&team(match.owner?.team))begin(match.owner.team,'left-censored',match.ball,match.owner.id);
 else if(!previous.dead&&team(match.flight?.from?.team)&&match.flight.kind!=='shot')begin(match.flight.from.team,'left-censored',match.ball,match.flight.from.id);
 previous=frame();
 function report(options={}){
  const endTime=clock.end,teamReports=clone(teams);for(const t of [0,1]){const a=teamReports[t];a.pending=active?.team===t?1:0;a.passes.pending=[...passRecords.values()].filter(p=>p.team===t&&!p.outcome).length;a.rates={shotsPer10InPlay:clock.inPlaySeconds>0?a.shots*600/clock.inPlaySeconds:null,shotsPerAttack:ratio(a.shots,a.attacks),passesPerAttack:ratio(a.passes.attempted,a.attacks),stageConversions:Object.fromEntries(stages.map(s=>[s,ratio(a.eligibleReached[s],a.stageEligibility[s])]))};}
  const recent=Math.max(0,Math.floor(finite(options.recent)?options.recent:10));
  const selected=options.includeEpisodes===false?(recent?records.slice(-recent):[]):records;
  const all=selected.map(ep=>clone(ep));if(active)all.push(view(active));
  return {version:1,definitions:clone(definitions),window:{start:clock.start,end:endTime,detached},clock:clone(clock),teams:teamReports,coverage:clone(coverage),episodes:options.includeEpisodes===false?[]:all,recentEpisodes:recent?all.slice(-recent):[],shots:options.includeEpisodes===false?[]:clone(shotRecords),truncatedEpisodes:dropped,truncatedShots:droppedShots,errors:clone(errors),valid:errors.length===0};
 }
 const observer={
  step(dt=1/60){if(detached)throw new Error('Attack diagnostics is detached');const before=frame();const result=match.step(dt);safe(()=>sampleWith(before,true));return result;},
  sample(){if(detached)throw new Error('Attack diagnostics is detached');safe(()=>sampleWith(previous,false));},
  report,summary(){return report({includeEpisodes:false,recent:10});},
  detach(){if(detached)return;for(const [name,{descriptor}]of originals){if(descriptor)Object.defineProperty(match,name,descriptor);else delete match[name];}detached=true;attached.delete(match);}
 };
 attached.set(match,observer);return observer;
}
const api={attach,definitions};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.TribunAttackDiagnostics=api;
})(typeof window!=='undefined'?window:globalThis);
