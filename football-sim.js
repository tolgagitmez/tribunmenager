'use strict';
/* Tribün football simulation. Fixed 60 Hz, metres, Y up.
   Ball ownership is an intention: the ball always has its own velocity and position.
   Original rules/AI implementation, with deliberately simplified aerial/offside rules. */
(function(root){
const Tactics=root.TribunTactics||(typeof require==='function'?require('./tactics.js'):null);
const Perception=root.TribunPerception||(typeof require==='function'?require('./player-perception.js'):null);
const Intent=root.TribunIntent||(typeof require==='function'?require('./team-intent.js'):null);
const MatchRules=root.TribunMatchRules||(typeof require==='function'?require('./match-rules.js'):null);
const RefereeLaws=root.TribunRefereeLaws||(typeof require==='function'?require('./referee-laws.js'):null);
const PitchLaws=root.TribunPitchLaws||(typeof require==='function'?require('./pitch-laws.js'):null);
const PlayerModel=root.TribunPlayerModel||(typeof require==='function'?require('./player-model.js'):null);
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n)),dist=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
const angle=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
const dot=(a,b)=>a.x*b.x+a.z*b.z,dir=t=>t===0?1:-1;
const footSkill=(p,skill,foot)=>p.footPreference==='both'||foot===(p.preferredFoot??foot)?skill:skill*.65+Math.min(skill,p.weakFoot??skill)*.35;
const nearest=(list,point)=>list.slice().sort((a,b)=>dist(a,point)-dist(b,point))[0];
const segment=(p,a,b)=>{const dx=b.x-a.x,dz=b.z-a.z,n=dx*dx+dz*dz||1,u=clamp(((p.x-a.x)*dx+(p.z-a.z)*dz)/n,0,1);return {d:Math.hypot(p.x-a.x-dx*u,p.z-a.z-dz*u),u};};
// One deterministic ball model for free flight AND every arrival prediction.
// Metres/seconds; gameplay coefficients, not a certified ball/grass measurement.
const BallPhysics={radius:.11,gravity:9.81,rolling:1.15,drag:.012,restitution:.44,
 ground(speed,seconds){
  if(speed<=0||seconds<=0)return {distance:0,speed:Math.max(0,speed)};
  const a=this.rolling,k=this.drag,scale=Math.sqrt(a/k),rate=Math.sqrt(a*k),start=Math.atan(speed/scale),end=Math.max(0,start-rate*seconds);
  return {distance:Math.log(Math.cos(end)/Math.cos(start))/k,speed:end>0?scale*Math.tan(end):0};
 },
 groundTime(distance,speed){
  if(distance<=0)return 0;if(speed<=0)return Infinity;
  const start=Math.atan(speed*Math.sqrt(this.drag/this.rolling)),cos=Math.cos(start)*Math.exp(this.drag*distance);
  return cos>1?Infinity:(start-Math.acos(clamp(cos,-1,1)))/Math.sqrt(this.rolling*this.drag);
 },
 launchForGround(distance,seconds){
  if(distance<=0||seconds<=0)return 0;let lo=distance/seconds,hi=Math.max(1,lo*1.4+this.rolling*seconds);
  while(this.ground(hi,seconds).distance<distance&&hi<80)hi*=1.4;
  for(let i=0;i<16;i++){const mid=(lo+hi)/2;if(this.ground(mid,seconds).distance<distance)lo=mid;else hi=mid;}return (lo+hi)/2;
 },
 step(b,seconds){
  let left=seconds,contacts=0;
  while(left>1e-9){
   if(b.y<=this.radius+1e-7&&b.vy<=0){
    b.y=this.radius;b.vy=0;const speed=Math.hypot(b.vx,b.vz),roll=this.ground(speed,left);
    if(speed){b.x+=b.vx/speed*roll.distance;b.z+=b.vz/speed*roll.distance;b.vx*=roll.speed/speed;b.vz*=roll.speed/speed;}if(roll.speed===0)b.vx=b.vz=0;break;
   }
   const dt=Math.min(left,1/120),speed=Math.hypot(b.vx,b.vy,b.vz),ax=-this.drag*speed*b.vx,ay=-this.gravity-this.drag*speed*b.vy,az=-this.drag*speed*b.vz;
   const half={vx:b.vx+ax*dt*.5,vy:b.vy+ay*dt*.5,vz:b.vz+az*dt*.5},drag=this.drag*Math.hypot(half.vx,half.vy,half.vz),acc={x:-drag*half.vx,y:-this.gravity-drag*half.vy,z:-drag*half.vz};
   let time=dt,impact=false;
   if(b.y+b.vy*dt+acc.y*dt*dt*.5<this.radius){
    const disc=Math.max(0,b.vy*b.vy-2*acc.y*(b.y-this.radius));time=clamp((-b.vy-Math.sqrt(disc))/acc.y,0,dt);impact=true;
   }
   b.x+=b.vx*time+acc.x*time*time*.5;b.z+=b.vz*time+acc.z*time*time*.5;b.y+=b.vy*time+acc.y*time*time*.5;
   b.vx+=acc.x*time;b.vy+=acc.y*time;b.vz+=acc.z*time;left-=time;
   if(impact){
    const down=Math.max(0,-b.vy),grip=down>.75?clamp(1-.06-down*.012,.72,.94):1;
    b.y=this.radius;b.vx*=grip;b.vz*=grip;b.vy=down*this.restitution;if(b.vy<.55)b.vy=0;
    if(++contacts>8){b.vy=0;} // settle numerical micro contacts, never add energy
   }
  }
  return b;
 },
 predict(b,seconds){return this.step({x:b.x,y:b.y,z:b.z,vx:b.vx,vy:b.vy,vz:b.vz},Math.max(0,seconds));},
 atX(b,x,limit=3){
  const delta=x-b.x;if(Math.abs(delta)<1e-9)return {...b,t:0};if(delta*b.vx<=0)return null;
  const speed=Math.hypot(b.vx,b.vz);
  if(b.y<=this.radius+1e-7&&b.vy<=0){const t=this.groundTime(Math.abs(delta)*speed/Math.abs(b.vx),speed);return t<=limit?{...this.predict(b,t),x,t}:null;}
  let q={x:b.x,y:b.y,z:b.z,vx:b.vx,vy:b.vy,vz:b.vz},elapsed=0;
  while(elapsed<limit-1e-9){
   const dt=Math.min(1/30,limit-elapsed),prev={...q};this.step(q,dt);
   if((x-prev.x)*(x-q.x)<=0){const part=clamp((x-prev.x)/(q.x-prev.x),0,1),t=elapsed+dt*part;return {...this.predict(prev,dt*part),x,t};}elapsed+=dt;
  }return null;
 },
 airTime(distance,speed){return distance>0&&speed>0?Math.expm1(this.drag*distance)/(this.drag*speed):0;},
 verticalLaunch(distance,power,originHeight,targetHeight,maxVy,minVy=0){
  // Solve only the launch impulse. Nothing redirects the ball after contact.
  let lo=minVy,hi=maxVy;
  for(let i=0;i<11;i++){const vy=(lo+hi)/2,p=this.atX({x:0,y:originHeight,z:0,vx:power,vy,vz:0},distance,7);if(!p||p.y<targetHeight)lo=vy;else hi=vy;}
  return (lo+hi)/2;
 }
};
const formations={
 '4-3-3':[['ATT',23,-22],['ATT',28,0],['ATT',23,22],['MID',-2,-15],['MID',-8,0],['MID',-2,15],['DEF',-24,-23],['DEF',-28,-8],['DEF',-28,8],['DEF',-24,23],['GK',-49,0]],
 '4-2-3-1':[['ATT',27,0],['MID',13,-22],['MID',13,0],['MID',13,22],['MID',-9,-9],['MID',-9,9],['DEF',-25,-23],['DEF',-28,-8],['DEF',-28,8],['DEF',-25,23],['GK',-49,0]],
 '4-4-2':[['ATT',25,-8],['ATT',25,8],['MID',-1,-23],['MID',-5,-8],['MID',-5,8],['MID',-1,23],['DEF',-25,-23],['DEF',-28,-8],['DEF',-28,8],['DEF',-25,23],['GK',-49,0]],
 '3-5-2':[['ATT',25,-8],['ATT',25,8],['MID',-1,-26],['MID',-7,-12],['MID',-1,0],['MID',-7,12],['MID',-1,26],['DEF',-27,-16],['DEF',-29,0],['DEF',-27,16],['GK',-49,0]],
 '5-3-2':[['ATT',25,-8],['ATT',25,8],['MID',-4,-15],['MID',-8,0],['MID',-4,15],['DEF',-23,-27],['DEF',-27,-15],['DEF',-29,0],['DEF',-27,15],['DEF',-23,27],['GK',-49,0]],
 '4-5-1':[['ATT',27,0],['MID',3,-25],['MID',-7,-13],['MID',0,0],['MID',-7,13],['MID',3,25],['DEF',-25,-23],['DEF',-28,-8],['DEF',-28,8],['DEF',-25,23],['GK',-49,0]]
};
const names=['Ethan Blake','Marco Silva','Viktor Pavlov','Rui Monteiro','Mateo Diaz','Jules Bernard','Liam Ward','Tiago Santos','Pablo Torres','Amir Haddad','Nico Ferreira'];
class Match{
 constructor(config={},motion=null){this.cfg=config;this.motion=motion;this.initialSeed=this.hash(JSON.stringify({starters:config.starters,seed:config.seed??5291}));this.reset();}
 hash(s){let n=2166136261;for(const c of s)n=Math.imul(n^c.charCodeAt(0),16777619);return n>>>0;}
 random(){this.seed=(Math.imul(this.seed,1664525)+1013904223)>>>0;return this.seed/4294967296;}
 direction(team){return (team===0?1:-1)*(this.period===2?-1:1);}
 team(t){return this.players.filter(p=>p.active&&p.team===t);}
 field(t){return this.team(t).filter(p=>p.role!=='GK');}
 tactics(t){return this.t[t];}
 // Observation is advanced once by step(), never by a speculative decision.
 // Direct, unstepped fixtures retain their explicitly supplied world state.
 rivals(p,keepers=false){
  const read=this._perceptionActive&&p.role!=='GK'?Perception.rivals(p,this.time):this.team(1-p.team);
  return keepers?read:read.filter(q=>q.role!=='GK');
 }
 teamRivals(team,keepers=false){
  if(!this._perceptionActive)return keepers?this.team(1-team):this.field(1-team);
  const known=new Map();
  for(const p of this.field(team))for(const q of this.rivals(p,keepers))if(!known.has(q.id)||q.seenAt>known.get(q.id).seenAt)known.set(q.id,q);
  return [...known.values()];
 }
 updateTeamPhases(){
  const attacking=this.owner?.team??this.flight?.from.team??this.lastTeam;
  for(let team=0;team<2;team++){
   const phase=team===attacking?(this.transitionUntil[team]>this.time?'win':'possession'):(this.lossUntil[team]>this.time?'loss':'defence'),old=this.teamPhases[team];
   if(!old||old.phase!==phase){
    this.teamPhases[team]={phase,since:this.time,epoch:(old?.epoch||0)+1,attackEpoch:this.attackEpoch[team]};
    this.telemetry.teamPhaseChanges=(this.telemetry.teamPhaseChanges||0)+1;
   }
  }
 }
 taskContext(p,extra={}){
  const phase=this.teamPhases[p.team]||{phase:p.team===this.lastTeam?'possession':'defence',epoch:0};
  return {time:this.time,phase:phase.phase,phaseEpoch:phase.epoch,attackEpoch:this.attackEpoch[p.team],ownerId:this.owner?.id??null,flightTargetId:this.flight?.target?.id??null,kickTargetId:this.kick?.target?.id??null,players:this.players,rivals:this.rivals(p),...extra};
 }
 taskSafe(p,task,context){
  if(task.purpose==='carry'&&context.ownerId!==p.id)return false;
  if(task.purpose==='receive'&&context.flightTargetId!==p.id&&context.kickTargetId!==p.id)return false;
  if(task.purpose==='mark'&&task.focusId!==null&&!context.rivals.some(q=>q.id===task.focusId))return false;
  if(['support','run'].includes(task.purpose)){
   if(task.x*this.direction(p.team)>Math.max(this.observedLine(p),this.ball.x*this.direction(p.team))-.5)return false;
   if(context.rivals.some(q=>dist(q,task)<1.35||dist(q,p)<3.5&&segment(q,p,task).d<.8))return false;
   if(task.partnerId!==null&&task.state!=='overlap'&&task.state!=='wide-support'){
    const connected=[this.owner?.id,this.flight?.from?.id,this.flight?.target?.id,this.kick?.target?.id];
    if(!connected.includes(task.partnerId))return false;
   }
  }
  return true;
 }
 taskReserved(p,allowed=[]){return Intent.reserved(p,this.taskContext(p,{safe:(a,t,c)=>this.taskSafe(a,t,c)}),allowed);}
 reset(){
  this.seed=this.initialSeed;this.time=0;this.score=[0,0];this.shots=[0,0];this.onTarget=[0,0];this.possession=[0,0];this.fouls=[0,0];this.cards=[0,0];this.reds=[0,0];this.passes=[0,0];this.completed=[0,0];this.xg=[0,0];this.events=[];this.queue=[];this.players=[];this.owner=null;this.lastTouch=null;this.flight=null;this.kick=null;this.restart=null;this.goalPause=null;this.phase='open';this.done=false;this.half=false;this.usedBench=new Set();this.subCount=0;this.planClock=0;this.targets=new Map();this.lastTeam=0;this.lastNarratedTurnover=-3;this.chain=0;this.transitionUntil=[0,0];
  this.telemetry={dribbleTouches:0,receives:0,looseBalls:0,shotsAfterPasses:0,restarts:0,turnovers:0,duels:0,throughBalls:0,crosses:0,cutbacks:0,headers:0,feints:0,longPasses:0,switches:0,offsides:0,pressRecoveries:0,clearances:0,giveGoes:0,movingPasses:0,movingShots:0,preparedReceives:0,oneTouchPasses:0,directedTouches:0,keeperCatches:0};this.possessionEpoch=0;this.lastGain=null;
  this.lastPassPreparation=null;this.teamPhases=[null,null];this._perceptionActive=false;
  this.rules=MatchRules.normalize(this.cfg);this.duration=this.rules.periodSeconds*2;
  this.matchClock=MatchRules.createClock(this.rules);this.period=1;this.lifecycle='playing';
  this.substitutionState=MatchRules.createSubstitutionState();this.subWindowsUsed=0;this.substitutionPause=null;
  this.referee={pendingAdvantage:null,pendingDiscipline:[],decisions:[]};this.penaltyAttempt=null;this.offsidePhase=null;this.stoppageSerial=0;
  this.activeWall=null;this.attackPlans=[null,null];this.flankPlans=[null,null];this.boxPlans=[null,null];this.buildPlans=[null,null];this.supportPlans=[null,null];this.pressUnits=[null,null];this.lastSwitch=[null,null];this.pressPolicies=[null,null];this.attackStats=[0,1].map(()=>({switches:0,returnSwitches:0,wideCarries:0,crosses:0,cutbacks:0,completedDeliveries:0,pressStarts:0,pressDrops:0}));this.defensiveUnits=[null,null];this.attackEpoch=[0,0];this.releaseSerial=0;
  Object.assign(this.telemetry,{returnSupports:0,giveGoReturns:0,giveGoCompletions:0,alignedThroughBalls:0,closeControlTouches:0,strideTouches:0,shieldCarries:0,duelOutlets:0,feintResponses:0,beatenDefenders:0,firstTouchRechecks:0,markHandoffs:0,markSamples:0,screenedReads:0,fastCatches:0,decisions:{pass:0,carry:0,feint:0,shot:0,clearance:0}});
  this.t=[Tactics.normalize(this.cfg.tactics),Tactics.normalize({playstyle:'counter',onWin:'counter',tempo:64,...this.cfg.awayTactics})];
  this.lossUntil=[0,0];this.recoveryUntil=[0,0];this.pressAssignments=[null,null];this.recentPasses=[];this.tacticalPhase=['build','defend'];this.tacticalStats=[{passDistance:0,passCount:0,forwardPasses:0,wideReceives:0,pressSamples:0},{passDistance:0,passCount:0,forwardPasses:0,wideReceives:0,pressSamples:0}];
  for(let team=0;team<2;team++){
   const formation=team===0?(this.cfg.formation||'4-3-3'):(this.cfg.awayFormation||'4-2-3-1'),form=formations[formation]||formations['4-3-3'];
   const supplied=team===0?this.cfg.players:this.cfg.awayPlayers,roster=Array.isArray(supplied)&&supplied.length?supplied:PlayerModel.demoTeam(team,formation);
   const configured=team===0?this.cfg.starters:this.cfg.awayStarters,ids=Array.isArray(configured)?configured:roster.slice(0,11).map(p=>p.id),fallback=PlayerModel.demoTeam(team,formation);
   const used=new Set();
   for(let i=0;i<11;i++){
    // A squad record is resolved identically for either side. Slot/ID never
    // manufacture a preferred foot or a technical/physical skill.
    const candidate=roster.find(p=>p.id===ids[i]&&p.owned!==false&&!used.has(p.id)),source=candidate||roster.find(p=>p.owned!==false&&!used.has(p.id))||fallback[i];
    used.add(source.id);
    const f=form[i],slot=PlayerModel.slotFor(formation,i),profile=PlayerModel.forSlot(source,slot),side=this.direction(team);
    const p={...profile,id:team*11+i,index:i,team,role:f[0],position:slot.position,name:source.name||names[i],num:source.number??i+1,rosterId:source.id,portraitId:source.face??i,active:true,yellow:0,x:f[1]*side,z:f[2]*side,homeX:f[1]*side,homeZ:f[2]*side,vx:0,vz:0,speed:0,face:team===0?0:Math.PI,anim:0,action:'idle',actionClock:0,actionElapsed:0,actionDuration:0,kickFoot:profile.preferredFoot,decision:.2+this.random()*.4,touchClock:0,tackleClock:.5+this.random(),receiveClock:0,personality:this.random(),duelRecovery:0,feintCooldown:0,skin:[[.73,.54,.38],[.56,.37,.25],[.34,.23,.18],[.83,.67,.54]][i%4],hair:[[.12,.09,.07],[.22,.17,.11],[.34,.25,.20]][i%3]};
    Object.assign(p,{energy:1,kickMoving:false,reception:null,nextAction:null});
    // A kick-off shape: sides remain in their own half, spread in their roles.
    p.x=side*(p.role==='GK'?-49:clamp(f[1]-.18*Math.max(0,f[1])-22,-42,-2));
    this.players.push(p);
   }
  }
  this.startingRosterIds=this.players.filter(p=>p.team===0).map(p=>p.rosterId);
  this.players.push({id:22,index:0,team:2,role:'REF',referee:true,name:'Hakem',active:true,x:-4,z:-9,vx:0,vz:0,speed:0,face:0,anim:0,action:'idle',actionClock:0,stamina:100,skill:80,skin:[.75,.55,.39]});
  const starter=this.field(0).find(p=>p.role==='MID');starter.x=-.7;starter.z=0;
  this.ball={x:0,y:.11,z:0,vx:0,vy:0,vz:0};
  this.setRestart('kickoff',0,{x:0,z:0},starter,true);
  this.emit('whistle','Başlama düdüğü','İki takım sahaya yayıldı. İlk pasla oyun başlayacak.',null,0);
 }
 clockState(){const c=MatchRules.clockView(this.matchClock);return {...c,elapsed:c.periodElapsed,periodSeconds:this.rules.periodSeconds,addedSeconds:c.announcedAddedSeconds??0,addedAnnounced:c.announcedAddedSeconds!==null,halftimeRemaining:c.breakRemaining,display:MatchRules.formatClock(this.matchClock)};}
 emit(type,title,desc,p=null,team=p?.team??0){const c=this.clockState(),e={type,title,desc,player:p?.name,playerId:p?.id,team,time:this.time,clockDisplay:c.display,period:c.period,minute:Math.floor(c.nominalElapsed/60+1e-7)};this.events.push(e);this.queue.push(e);}
 drain(){const q=this.queue;this.queue=[];return q;}
 action(p,name,duration){p.action=name;p.actionClock=duration;p.actionDuration=duration;p.actionElapsed=0;}
 setRestart(kind,team,spot,taker=null,initial=false){
  const recall=this.refereeRestart?.(kind,team,spot,taker);if(recall)({kind,team,spot,taker}=recall);
  this.settleDiscipline?.();this.offsidePhase=null;
  if(this.done)return;
  if(kind==='penalty')spot={x:this.direction(team)*41,z:0};
  for(const p of this.players)Intent.clear(p,'restart',this.taskContext(p));
  Perception.reset(this.players,this.time);this._perceptionActive=false;
  this.teamPhases=[null,null];this.transitionUntil=[0,0];this.lossUntil=[0,0];
  this.buildPlans=[null,null];this.boxPlans=[null,null];this.defensiveUnits=[null,null];this.pressPolicies=[null,null];
  this.owner=null;this.kick=null;this.flight=null;this.goalPause=null;this.phase='restart';this.planClock=0;
  this.attackPlans=[null,null];this.flankPlans=[null,null];this.activeWall=null;this.recoveryUntil=[0,0];
  this.supportPlans=[null,null];this.pressUnits=[null,null];this.pressAssignments=[null,null];
  for(const p of this.players){p.reception=null;p.nextAction=null;p.holdingBall=false;p.holdClock=0;p.runIntent=null;p.supportIntent=null;p.offerIntent=null;p.connectionIntent=null;p.carryIntent=null;p.keeperRead=null;p.shieldUntil=0;p.duelMemory=null;p.dribbleDuel=null;p.passReviewUntil=0;}
  this.ball={x:spot.x,y:.11,z:spot.z,vx:0,vy:0,vz:0};
  const pool=kind==='goal-kick'?this.team(team).filter(p=>p.role==='GK'):this.field(team);
  const roleKey=kind==='corner'?'corner':kind==='free-kick'?'free':kind==='penalty'?'penalty':null,special=team===0?this.cfg.special:this.cfg.awaySpecial;
  taker=(roleKey&&special?pool.find(p=>p.rosterId===special[roleKey]):null)||taker||nearest(pool,spot)||nearest(this.team(team),spot);
  this.lastTeam=team;
  const preparation={kickoff:18,throw:10,corner:18,'goal-kick':15,'free-kick':14,penalty:8};
  this.restart={id:++this.stoppageSerial,kind,team,spot:{...spot},taker,clock:initial?.6:(preparation[kind]??4.5)};this.telemetry.restarts++;
  if(kind==='penalty')this.penaltyAttempt={state:'pending',team,takerId:taker?.id};
 }
 // Conservative lane interception estimate: defenders must have time to reach a pass.
 laneRisk(p,point,power=17,kind='pass',rivals=null){
  let risk=0;const opponents=rivals||this.rivals(p),origin=p===this.owner&&dist(p,this.ball)<1.6?this.ball:p,length=dist(origin,point),ground=!['cross','long-pass','clearance','throw'].includes(kind),near=[];
  for(const d of opponents){
   let hit=segment(d,p,point);
   if(hit.u>=.05&&hit.u<=.98){const travel=Math.min(6,BallPhysics.groundTime(dist(p,point)*hit.u,power)),future=d.passFuture?d.passFuture(Math.min(.5,travel)):{x:d.x+d.vx*Math.min(.5,travel),z:d.z+d.vz*Math.min(.5,travel)};hit=segment(future,p,point);const reach=.55+Math.max(0,travel-.22)*3.9+clamp(d.uncertainty||0,0,.8);risk=Math.max(risk,clamp((reach-hit.d)/Math.max(.7,reach),0,1));}
   if(ground&&Math.max(d.touchClock||0,d.duelRecovery||0)<.3&&dist(d,origin)<.3*(power+Math.hypot(d.vx,d.vz))+1.1+(d.passFuture?.5:0))near.push(d);
  }
  // The longer-range arrival estimate must not miss a boot already crossing
  // the first metres of a pass. Sweep relative ball/defender motion from the
  // actual ball for its owner, using the same rolling law as the real flight.
  // Hypothetical receivers still read from their own future position.
  if(near.length&&risk<1&&length>.1&&power>0){
   const end=Math.min(.3,BallPhysics.groundTime(length,power)),dx=(point.x-origin.x)/length,dz=(point.z-origin.z)/length;
   for(const d of near){
    const ready=Math.max(.025,d.touchClock||0,d.duelRecovery||0);if(ready>=end)continue;
    const relative=t=>{const travel=BallPhysics.ground(power,t).distance;if(d.passFuture){const future=d.passFuture(t);return {x:origin.x+dx*travel-future.x,z:origin.z+dz*travel-future.z};}return {x:origin.x+dx*travel-d.x-d.vx*t,z:origin.z+dz*travel-d.z-d.vz*t};};
    let at=ready,previous=relative(at);
    while(at<end-1e-9){at=Math.min(end,at+.1);const next=relative(at),gap=segment({x:0,z:0},previous,next).d;risk=Math.max(risk,clamp((1.0-gap)/.4,0,1));previous=next;}
   }
  }
  return risk;
 }
 matchContext(team){
  const progress=this.clockState().nominalElapsed/this.duration,margin=this.score[team]-this.score[1-team];
  const urgency=progress>.70?clamp(-margin,-1,1)*(progress-.70)/.30:0;
  return {urgency,protect:progress>.75&&margin>0};
 }
 observedLine(p){return this.rivals(p,true).map(q=>q.x*this.direction(p.team)).sort((a,b)=>b-a)[1]??49;}
 defenceLine(team){return this.team(1-team).map(q=>q.x*this.direction(team)).sort((a,b)=>b-a)[1]??49;}
 receptionSafety(p,q,point,seconds){
  const top=player=>5.7+((player.pace??player.skill)-75)*.04;
  const control=.12+(100-q.skill)*.003,receiverArrival=dist(q,point)/Math.max(3.5,top(q));
  let risk=0,pressure=18,defenderArrival=10;
  for(const rival of this.rivals(p)){
   const future={x:rival.x+rival.vx*Math.min(seconds,.6)*.5,z:rival.z+rival.vz*Math.min(seconds,.6)*.5};
   const uncertainty=clamp(rival.uncertainty||0,0,1),gap=Math.max(0,dist(future,point)-uncertainty),arrival=.22+Math.max(0,dist(rival,point)-uncertainty)/Math.max(3.5,top(rival));pressure=Math.min(pressure,gap);defenderArrival=Math.min(defenderArrival,arrival);
   const from={x:p.x-point.x,z:p.z-point.z},op={x:rival.x-point.x,z:rival.z-point.z},length=Math.hypot(from.x,from.z)*Math.hypot(op.x,op.z)||1;
   // A defender behind a back-to-goal receiver can be screened by the body;
   // one arriving on the passing side threatens the first touch directly.
   const shield=dot(from,op)/length<-.25&&dist(q,point)<2.5;
   const threat=clamp((Math.max(seconds,receiverArrival)+control+.15-arrival)/.85,0,1)*(shield?.48:1);
   risk=Math.max(risk,threat);
  }
  return {risk,pressure,receiverArrival,defenderArrival};
 }
 giveGoLink(p,q){
  const run=q.runIntent;
  return run?.kind==='give-go'&&run.partnerId===p.id&&run.epoch===this.attackEpoch[p.team]&&run.until>this.time?run:null;
 }
 plannedRun(p){
  // A producer's wish is not a run after task arbitration has rejected it.
  // Teammates pass into the destination the runner actually committed to.
  if(p.task?.epoch===this.attackEpoch[p.team]&&p.task.expiresAt>this.time)return p.task.purpose==='run'?{x:p.task.x,z:p.task.z}:null;
  const run=p.runIntent,pattern=this.attackPlans[p.team];
  if(run?.until>this.time&&(run.epoch===undefined||run.epoch===this.attackEpoch[p.team]))return run.point;
  if(pattern?.epoch===this.attackEpoch[p.team]&&pattern.until>this.time&&pattern.runner?.id===p.id)return pattern.runner.point;
  return null;
 }
 receiverPoint(q,seconds,target=this.targets.get(q)){
  seconds=clamp(Number.isFinite(seconds)?seconds:0,0,1.6);
  const point={x:q.x+q.vx*seconds,z:q.z+q.vz*seconds};
  // Near a known destination the receiver will brake/turn, rather than coast
  // through it. Use the same movement limits; a fast runner may still overshoot.
  // Distant runs and unknown commands retain the existing velocity extension.
  if(q.active&&target&&Number.isFinite(target.x)&&Number.isFinite(target.z)&&Number.isFinite(target.pace)&&target.pace>=0&&!['restart','wall','goal'].includes(target.state)){
   const speed=Math.hypot(q.vx,q.vz),reach=speed*seconds+speed*speed/22+.5;
   if(speed>.2&&dist(q,target)<reach){const predicted=this.receiverAt(q,seconds,target).player;return {x:predicted.x,z:predicted.z};}
  }
  return point;
 }
 passOptions(p){
  const options=[],forward=this.direction(p.team),t=this.t[p.team],tempo=+t.tempo,line=this.observedLine(p),pressure=Math.min(15,...this.rivals(p).map(q=>dist(p,q)));
  for(const q of this.team(p.team)){
   if(q.id===p.id)continue;const d=dist(p,q),limit=t.passing==='short'?28:t.passing==='direct'?62:49;if(d<3.4||d>limit)continue;if(q.x*forward>Math.max(line,this.ball.x*forward)+.12&&q.x*forward>0)continue;
   const long=d>32&&(t.passing==='direct'||Math.abs(q.z-p.z)>32),kind=long?'long-pass':'pass',speed=this.passSpeed(kind,d,t),arrival=this.passTime(kind,d,speed);if(!Number.isFinite(arrival))continue;
   const lead=clamp(arrival,.14,1.6),predicted=this.receiverPoint(q,lead),point={x:clamp(predicted.x,-49,49),z:clamp(predicted.z,-31,31)};
   const reception=this.receptionSafety(p,q,point,this.passTime(kind,dist(p,point),speed)),risk=this.laneRisk(p,point,speed,kind),space=Math.min(15,reception.pressure),advance=(point.x-p.x)*forward;
   const lane=long?risk*.32:risk,preferred=t.passing==='short'?11:t.passing==='direct'?29:17;
   let score=space*.68+advance*(t.playstyle==='counter'||t.playstyle==='direct'?.82:t.passing==='short'?.36:.48)-lane*28-reception.risk*9-Math.abs(d-preferred)*(t.passing==='short'?.52:.23);
   score+=Math.max(0,this.threat(point,p.team)-this.threat(p,p.team))*10;
   const context=this.matchContext(p.team),bodyTurn=Math.abs(angle(Math.atan2(point.z-p.z,point.x-p.x),p.face));
   score+=context.urgency*advance*.18-bodyTurn*(1-(p.composure??p.skill)/120)*1.2;
   if(context.protect)score+=lane<.2?2:-lane*5;
   const combo=this.giveGoLink(p,q),movingReturn=!!combo&&(q.x-combo.origin.x)*forward>1.8;
   const incoming=this.recentPasses.filter(a=>this.time-a.time<5&&a.from===q.id&&a.to===p.id).length;if(incoming&&!movingReturn)score-=incoming*4;
   if(movingReturn)score+=Math.min(3,(q.x-combo.origin.x)*forward*.5);
   const offer=q.offerIntent;
   if(offer?.ownerId===p.id&&offer.epoch===this.attackEpoch[p.team]&&dist(q,offer.point)<2&&risk<.35&&reception.risk<.65)score+=1.5;
   if(q.role==='DEF'&&advance<0&&p.x*forward>20)score-=2;
   if(long)score-=Math.min(8,Math.max(0,7-space)*1.5);
   if(t.onWin==='counter'&&this.transitionUntil[p.team]>this.time)score+=Math.max(0,advance)*.30;
   if(t.playstyle==='wing'&&Math.sign(point.z)!==Math.sign(p.z)&&Math.abs(point.z-p.z)>28){
    // A switch must open space or escape a press, rather than earn a fixed
    // bonus for sending the ball from touchline to touchline indefinitely.
    score+=clamp(space-pressure,-7,7)*.65+Math.max(0,5-pressure)*.75;
    const last=this.lastSwitch[p.team];
    if(last&&this.time-last.time<9&&Math.sign(point.z)===Math.sign(last.fromZ)&&advance<6&&pressure>3)score-=6.5;
   }
   if(t.playstyle==='possession'&&d<19&&risk<.2)score+=3;
   if(p.role==='GK'&&q.role==='DEF'&&t.passing==='short')score+=5;
   if(q.role==='GK')score-=5;if(q.role==='ATT'&&Math.abs(q.z)<12&&p.x*forward>23)score+=3;
   if(t.playstyle==='counter')score+=Math.max(0,advance)*.16;
   if(t.playstyle==='wing'&&Math.abs(q.z)>18&&advance>4)score+=3;
   options.push({kind,q,point,risk:clamp(lane+reception.risk*.18,0,1),score,space,distance:d,arrivalRisk:reception.risk,movingReturn});
   // Pass into a runner's path, beyond the line but only to an initially onside player.
   if((t.passing!=='short'||p.x*forward>16)&&q.role!=='GK'&&q.role!=='DEF'&&q.x*forward<=Math.max(line,p.x*forward)+.05&&(q.x-p.x)*forward>0&&d<34){
    const length=5+clamp((q.pace??80)-70,0,25)*.10,intent=this.plannedRun(q),aligned=!!intent&&(intent.x-q.x)*forward>.75;
    const lateral=aligned?clamp((intent.z-q.z)/Math.max(.75,(intent.x-q.x)*forward)*length,-5.5,5.5):q.vz*.45;
    const run={x:clamp(q.x+forward*length,-48,48),z:clamp(q.z+lateral,-28,28)};
    const reachTime=dist(q,run)/Math.max(3.5,5.35+((q.pace??80)-75)*.035),flight=this.passTime('through',dist(p,run),21);
    const rivals=this.rivals(p),r=this.laneRisk(p,run,20),open=Math.min(16,...rivals.map(o=>dist(o,run)));
    const defenderArrival=Math.min(10,...rivals.map(o=>dist(o,run)/(5.7+((o.pace??80)-75)*.04)+.18));
    if(open>3&&r<.55&&reachTime<flight+.65&&reachTime<defenderArrival+.05&&run.x*forward>line+.8&&line-q.x*forward<9&&p.x*forward>-20)options.push({kind:'through',q,point:run,risk:r,space:open,score:score+(t.passing==='short'?0:2)+(run.x-point.x)*forward*.30+(line<run.x*forward?2:0)-r*7,plannedRun:aligned,movingReturn});
   }
  }
  return options.sort((a,b)=>b.score-a.score);
 }
 prepareReception(p,meeting=null){
  const f=this.flight;
  if(!f||f.target!==p||f.from.team!==p.team||!['pass','through','cutback','long-pass','cross'].includes(f.kind))return;
  if(!f.id)f.id=++this.releaseSerial;
  if(p.reception?.flightId===f.id&&p.reception.refreshAt>this.time)return;
  const intercept=meeting||this.interceptPoint(p),eta=clamp(intercept.t,.08,1.15);
  if(dist(p,this.ball)>24||this.ball.y>3)return;
  const anticipation=clamp(.45+((p.vision??p.skill)-60)*.01,.40,.85),future={...p,x:p.x+p.vx*eta*anticipation,z:p.z+p.vz*eta*anticipation};
  const opponents=this.rivals(p).map(q=>({x:q.x+q.vx*eta*.5,z:q.z+q.vz*eta*.5}));
  const pressure=Math.min(20,...opponents.map(q=>dist(q,future)));
  const options=this.passOptions(future).filter(o=>o.q!==f.from||pressure<2.5||o.movingReturn);
  let outlet=options.find(o=>o.risk<.36&&o.space>2.4&&o.score>1);
  const pendingRun=this.giveGoLink(p,f.from);
  if(pendingRun&&pressure>3.6&&outlet&&!outlet.movingReturn&&(outlet.point.x-future.x)*this.direction(p.team)<-2)outlet=null;
  const incoming=Math.atan2(this.ball.vz,this.ball.vx),outgoing=outlet?Math.atan2(outlet.point.z-future.z,outlet.point.x-future.x):this.direction(p.team)>0?0:Math.PI;
  const redirect=Math.abs(angle(outgoing,incoming));
  const oneTouch=!!outlet&&f.kind!=='cross'&&f.kind!=='long-pass'&&p.passing>=78&&(p.vision??p.skill)>=74&&redirect<2.15&&(pressure<3.6||this.t[p.team].playstyle==='possession'&&p.passing>=83);
  const control=this.controlOption(p,future,outgoing,eta);
  const next=oneTouch?{kind:outlet.kind,qId:outlet.q.id,point:{...outlet.point}}:null;
  p.reception={flightId:f.id,fromId:f.from.id,refreshAt:this.time+clamp(.30-((p.vision??p.skill)-60)*.003,.12,.28),at:this.time,mode:oneTouch?'one-touch':pressure<3?'protect':'open',point:control,face:outgoing,next};
 }
 receptionFacing(p,travel=p.face){
  const r=p.reception,f=this.flight,b=this.ball;
  if(!r||!Number.isFinite(r.face))return travel;
  if(!p.active||p.role==='GK'||this.restart||this.kick?.restartContext||f?.target?.id!==p.id||f.from?.team!==p.team||!['pass','through','cutback'].includes(f.kind)||r.flightId!==f.id||!(this.time-r.at>=0&&this.time-r.at<.55)||b.y>BallPhysics.radius+.01||Math.abs(b.vy)>=1e-6)return r.face;
  // Preserve the remote branch's late opening: a distant receiver runs
  // normally, then prepares an open body while there is still time to turn.
  const dx=b.x-p.x,dz=b.z-p.z,gap=Math.hypot(dx,dz),bearing=Math.atan2(dz,dx),yaw=angle(r.face,bearing);
  const opening=Math.abs(yaw)<=Math.PI/3?r.face:bearing+clamp(yaw,-Math.PI/3,Math.PI/3);
  const closing=gap>1e-8?-(dx*(b.vx-p.vx)+dz*(b.vz-p.vz))/gap:0,eta=closing>.1?Math.max(0,gap-1.1)/closing:Infinity,turn=Math.abs(angle(opening,p.face))/4.5+.15;
  return gap<=2||eta<=turn?opening:travel;
 }
 preparedChoice(p){
  const n=p.nextAction;p.nextAction=null;
  if(!n||n.until<this.time){p.oneTouchUntil=0;return null;}
  const finish=this.shotWindow(p);if(this.clearFinish(p,finish)){p.oneTouchUntil=0;return null;}
  const q=this.players.find(a=>a.id===n.qId&&a.active&&a.team===p.team);
  if(!q){p.oneTouchUntil=0;return null;}
  if(n.kind==='through'){
   const option=this.passOptions(p).find(o=>o.kind==='through'&&o.q===q&&o.risk<.53&&o.space>2.4);
   if(!option){p.oneTouchUntil=0;return null;}return {...option,oneTouch:true};
  }
  const d=dist(p,q),lead=clamp(this.passTime(n.kind,d,this.passSpeed(n.kind,d,this.t[p.team])),.1,1.3),point=this.receiverPoint(q,lead);
  // A preparatory read never bypasses a newly closed lane or the offside line.
  if(this.laneRisk(p,point,this.passSpeed(n.kind,d,this.t[p.team]),n.kind)>.53||this.receptionSafety(p,q,point,this.passTime(n.kind,d,this.passSpeed(n.kind,d,this.t[p.team]))).risk>.82||q.x*this.direction(p.team)>Math.max(this.observedLine(p),this.ball.x*this.direction(p.team))+.1){p.oneTouchUntil=0;return null;}
  return {kind:n.kind,q,point,oneTouch:true};
 }
 controlOption(p,origin,outgoing,eta=0,contact=null){
  const opponents=this.rivals(p).map(q=>({x:q.x+q.vx*Math.min(eta,.6)*.5,z:q.z+q.vz*Math.min(eta,.6)*.5})),pressure=Math.min(20,...opponents.map(q=>dist(q,origin)));let best=null;
  for(const yaw of [0,-.6,.6,-1.2,1.2,Math.PI]){
   const a=outgoing+yaw,length=pressure<2.8?1.4:2.6,point={x:clamp(origin.x+Math.cos(a)*length,-50.5,50.5),z:clamp(origin.z+Math.sin(a)*length,-32.5,32.5)};
   const space=Math.min(12,...opponents.map(q=>dist(q,point))),path=Math.max(0,...opponents.map(q=>{const h=segment(q,contact||origin,point);return h.u>.06?clamp((.85-h.d)/.85,0,1):0;}));
   const turn=Math.abs(angle(a,p.face)),score=space*1.5-Math.abs(yaw)*.7+(point.x-origin.x)*this.direction(p.team)*.2-path*8-turn*(100-(p.agility??p.skill))*.008;
   if(!best||score>best.score)best={...point,score,pathRisk:path};
  }return best;
 }
 touchContact(p,b=this.ball,foot=null){
  const dx=b.x-p.x,dz=b.z-p.z,gap=Math.hypot(dx,dz),forward=dx*Math.cos(p.face)+dz*Math.sin(p.face),lateral=-dx*Math.sin(p.face)+dz*Math.cos(p.face);
  foot=foot===0||foot===1?foot:Math.abs(lateral)>.12?(lateral>0?1:0):(p.preferredFoot??p.kickFoot??0);
  const technique=footSkill(p,p.dribbling??p.skill,foot);
  const footClock=p.dribbleFoot===foot?Math.max(0,p.footTouch||0):0;
  return {ready:p.active!==false&&!(p.duelRecovery>0)&&gap<=1.20&&forward>=-.18&&Math.abs(lateral)<=1.0&&Math.abs(lateral-(foot?1:-1)*.18)<=1.0,gap,forward,lateral,turn:Math.abs(angle(Math.atan2(dz,dx),p.face)),foot,technique,footClock};
 }
 touchRecovery(p,velocity,options={}){
  // Forecast only the current intention until the next available foot contact.
  // There are no future decisions, extra touches, rival orders or RNG draws.
  const interval=options.interval,mode=options.mode||'carry';
  if(!p?.active||![p.x,p.z,p.vx,p.vz,p.face,velocity?.vx,velocity?.vz,velocity?.vy].every(Number.isFinite))return {ready:false,reason:'unavailable',interval};
  if(mode==='setup'&&this.kick?.p?.id!==p.id)return {ready:false,reason:'unavailable',interval};
  if(!Number.isFinite(interval)||interval<=0||interval>.65)return {ready:false,reason:'horizon',interval};
  let ticks=Math.ceil(interval*60-1e-9);
  if(mode!=='setup'){
   let clock=Math.max(interval,p.touchClock||0,p.receiveClock||0,p.duelRecovery||0),clockTicks=0;
   while(clock>0&&clockTicks<=39){clock=Math.max(0,clock-1/60);clockTicks++;}
   ticks=Math.max(ticks,clockTicks);
  }
  if(ticks>39)return {ready:false,reason:'horizon',interval};
  const horizon=ticks/60;
  const actor={...p},ball={...this.ball,...velocity},peers=this.players.filter(q=>q.active&&q.team===p.team&&q.id!==p.id).map(q=>({original:q,player:{...q}}));
  if(mode==='receive'){actor.action='receive';actor.actionClock=p.receiveClock;actor.actionDuration=p.receiveClock;actor.actionElapsed=0;}
  const rivals=this.rivals(p).map(q=>({x:q.x,z:q.z,vx:q.vx,vz:q.vz}));
  const kick=mode==='setup'&&this.kick?.p?.id===p.id?{...this.kick,p:actor,approach:{...this.kick.approach}}:null;
  const context={players:[actor,...peers.map(q=>q.player)],owner:actor,kick,restart:null,flight:null,time:this.time,ball,effort:Match.prototype.effort};
  if(mode!=='setup')actor.touchClock=Math.max(actor.touchClock||0,interval);
  let command=this.targets.get(p),refresh=options.replan?0:Math.max(0,this.planClock||0),elapsed=0,maxGap=dist(actor,ball),lost=false;
  if(!command||!['dribble','receive','shield'].includes(command.state))refresh=0;
  // Carry/setup impulses precede this frame's ball integration; acquire's
  // first control follows it. Observe the next carry contact before the ball
  // step, and a prepared strike after it, exactly like the live step order.
  if(mode!=='receive')BallPhysics.step(ball,1/60);
  while(elapsed<horizon-1e-9){
   const dt=1/60;elapsed+=dt;context.time+=dt;
   for(const q of peers){q.player.x=q.original.x+q.original.vx*elapsed;q.player.z=q.original.z+q.original.vz*elapsed;}
   for(const key of ['duelRecovery','feintReaction','receiveClock','touchClock','footTouch','holdClock'])actor[key]=Math.max(0,(actor[key]||0)-dt);
   if(actor.actionClock>0){actor.actionClock=Math.max(0,actor.actionClock-dt);actor.actionElapsed+=dt;if(!actor.actionClock)actor.action='idle';}
   if(kick){
    Match.prototype.move.call(context,actor,{x:actor.x,z:actor.z,pace:1,state:'kick'},dt);
    const facing=Match.prototype.touchContact.call(context,actor,ball,kick.p.kickFoot).ready?Math.atan2(options.target.z-actor.z,options.target.x-actor.x):Math.atan2(ball.z-actor.z,ball.x-actor.x);
    actor.face+=clamp(angle(facing,actor.face),-7*dt,7*dt);
   }else{
    refresh-=dt;
    if(refresh<=0){
     const target=options.target||p.carryTarget||{x:actor.x+this.direction(p.team)*6,z:actor.z},shield=actor.shieldUntil>context.time;
     const follow=dist(actor,ball)>1.1||actor.receiveMode==='cushion'&&actor.receiveClock>0;
     const pressure=Math.min(20,...rivals.map(q=>Math.hypot(q.x+q.vx*elapsed-actor.x,q.z+q.vz*elapsed-actor.z))),counter=this.transitionUntil[p.team]>context.time&&this.t[p.team].onWin==='counter';
     const pace=actor.receiveClock>0?.48:shield?.56:actor.settleUntil>context.time?.34:counter?1.04:actor.escapeUntil>context.time?.98:pressure>5&&ball.x*this.direction(p.team)<20?.60:.98;
     command={x:follow?ball.x+ball.vx*.12:target.x,z:follow?ball.z+ball.vz*.12:target.z,pace,state:actor.receiveClock>0?'receive':shield?'shield':'dribble'};refresh=.16;
    }
    Match.prototype.move.call(context,actor,command,dt);
   }
   if(!kick&&dist(actor,ball)>3.2)lost=true;
   if(kick||elapsed<horizon-1e-9)BallPhysics.step(ball,dt);
   maxGap=Math.max(maxGap,dist(actor,ball));if(kick&&dist(actor,ball)>2.4)lost=true;
  }
  const contact=Match.prototype.touchContact.call(context,actor,ball,mode==='setup'?p.kickFoot:null),ready=!lost&&contact.ready&&ball.y<.45&&Math.abs(ball.x)<=52&&Math.abs(ball.z)<=34&&Math.max(actor.receiveClock||0,mode==='setup'?contact.footClock:actor.touchClock||0,actor.duelRecovery||0)<=0;
  return {ready,reason:ready?'reachable':'next-contact',interval,time:horizon,ballTime:horizon+(kick?1/60:mode==='receive'?-1/60:0),foot:contact.foot,gap:contact.gap,forward:contact.forward,lateral:contact.lateral,maxGap,lost,player:{x:actor.x,z:actor.z,vx:actor.vx,vz:actor.vz,face:actor.face},ball};
 }
 touchPlan(p,velocity,options={}){
  if(!p?.active||options.mode==='setup'&&this.kick?.p?.id!==p.id)return {ready:false,reason:'unavailable'};
  const contact=this.touchContact(p,this.ball,options.mode==='setup'?p.kickFoot:null);
  if(!contact.ready||this.ball.y>=.45)return {ready:false,reason:'foot',contact};
  if(options.mode!=='receive'&&Math.max(options.mode==='setup'?contact.footClock:p.touchClock||0,p.receiveClock||0)>0)return {ready:false,reason:'foot-clock',contact};
  if(!['vx','vz','vy'].every(k=>Number.isFinite(velocity[k])))return {ready:false,reason:'velocity',contact};
  for(const weight of [1,.75,.5,.25]){
   const candidate=weight===1?{...velocity}:{vx:this.ball.vx+(velocity.vx-this.ball.vx)*weight,vz:this.ball.vz+(velocity.vz-this.ball.vz)*weight,vy:this.ball.vy+(velocity.vy-this.ball.vy)*weight};
   const recovery=this.touchRecovery(p,candidate,options);
   if(recovery.ready)return {ready:true,reason:weight===1?'requested':'limited',limited:weight<1,weight,velocity:candidate,foot:contact.foot,technique:contact.technique,recovery};
  }
  return {ready:false,reason:'next-contact',contact};
 }
 dribbleTouch(p){
  const b=this.ball,dx=b.x-p.x,dz=b.z-p.z,gap=Math.hypot(dx,dz),forward=dx*Math.cos(p.face)+dz*Math.sin(p.face),lateral=-dx*Math.sin(p.face)+dz*Math.cos(p.face);
  // A nearby ball still needs a reachable foot; no reverse impulse from
  // behind the body while the player is looking and running the other way.
  if(gap>1.20||forward<-.18||Math.abs(lateral)>1.0)return false;
  const target=p.carryTarget||{x:p.x+this.direction(p.team)*6,z:p.z},a=Math.atan2(target.z-p.z,target.x-p.x),rivals=this.rivals(p),pressure=Math.min(20,...rivals.map(q=>dist(q,p))),shield=p.shieldUntil>this.time;
  const ahead={x:p.x+Math.cos(a)*3,z:p.z+Math.sin(a)*3},room=Math.min(10,...rivals.map(q=>dist({x:q.x+q.vx*.4,z:q.z+q.vz*.4},ahead)));
  const foot=Math.abs(lateral)>.12?(lateral>0?1:0):(p.preferredFoot??p.kickFoot),technique=footSkill(p,p.dribbling??p.skill,foot);
  const stride=!shield&&pressure>5&&room>3&&p.speed>3.2,close=shield||pressure<2.8,desired=shield?.48:close?.56:stride?1.10+(100-technique)*.002:.82+(100-technique)*.0015;
  const along=dx*Math.cos(a)+dz*Math.sin(a),speed=clamp(p.speed+(desired-along)*3.4,close?.35:.65,stride?7.3:close?Math.max(4.5,p.speed+.65):6.5),turn=Math.abs(angle(a,p.face));
  // Low technique/weak-foot sharp turns retain more of the incoming roll.
  const leak=clamp((100-technique)*.006*turn/Math.PI+Math.max(0,.65-(p.energy??1))*.12,0,.28);
  const interval=close?clamp(.19+(100-technique)*.0012,.19,.27):stride?.32+(100-technique)*.0012:.28+(p.speed<2?.16:0);
  const plan=this.touchPlan(p,{vx:Math.cos(a)*speed*(1-leak)+b.vx*leak,vz:Math.sin(a)*speed*(1-leak)+b.vz*leak,vy:close?.10:.16},{interval,target,mode:shield?'shield':'carry'});
  if(!plan.ready){p.touchClock=Math.max(p.touchClock||0,.05);this.telemetry.touchDeferrals=(this.telemetry.touchDeferrals||0)+1;return false;}
  Object.assign(b,plan.velocity);if(plan.limited)this.telemetry.limitedTouches=(this.telemetry.limitedTouches||0)+1;
  this.lastTouch=p;p.touchClock=interval;
  p.footTouch=.14;p.dribbleFoot=foot;p.touchPosition={x:b.x,z:b.z};p.touchMode=shield?'shield':close?'close':stride?'stride':'control';this.telemetry.dribbleTouches++;
  if(close)this.telemetry.closeControlTouches++;if(stride)this.telemetry.strideTouches++;return true;
 }
 feintOption(p,defender){
  const a=Math.atan2(defender.z-p.z,defender.x-p.x);if(Math.abs(angle(a,p.face))>=1.1)return null;let best=null;
  for(const sign of [-1,1]){
   const heading=a+sign*.95,point={x:clamp(p.x+Math.cos(heading)*5,-49,49),z:clamp(p.z+Math.sin(heading)*5,-31,31)},others=this.rivals(p).filter(q=>q.id!==defender.id);
   const room=Math.min(10,...others.map(q=>{const h=segment({x:q.x+q.vx*.4,z:q.z+q.vz*.4},p,point);return h.u>.08?h.d:10;})),space=Math.min(12,...this.rivals(p).map(q=>dist(q,point)));
   if(space<2||room<1.25)continue;const score=space+room*.35+(sign===(p.personality>.5?1:-1)?.1:0);
   if(!best||score>best.score)best={kind:'feint',point,defender,sign,score};
  }return best;
 }
 applyFeint(p,choice){
  p.feintClock=.35;p.feintSign=-choice.sign;p.feintCooldown=4.6;
  const d=this.players.find(q=>q.id===choice.defender?.id&&q.active);if(!d)return;const gap=dist(p,d),seeing=Math.cos(angle(Math.atan2(p.z-d.z,p.x-d.x),d.face))>.35,closing=((p.x-d.x)*d.vx+(p.z-d.z)*d.vz)/Math.max(.1,gap);
  const susceptibility=(p.dribbling-d.tackling)*.005+Math.max(0,closing)*.015-((d.composure??d.skill)-75)*.002;
  if(seeing&&closing>.3&&gap<3.1&&susceptibility>.055){d.feintReaction=clamp(.06+susceptibility*.5,.06,.14);this.telemetry.feintResponses++;}
  p.dribbleDuel={opponentId:d.id,at:this.time};this.telemetry.feints++;
 }
 canShield(p){return this.time>=(p.shieldReadyAt||0)||p.shieldUntil>this.time&&p.shieldBudgetUntil>this.time;}
 startCarry(p,choice){
  const proposal={...choice.point,state:choice.shield?'shield':'dribble',pace:1,priority:90,urgent:!!choice.shield||choice.kind==='feint'};
  const context=this.taskContext(p,{forceReason:p.task&&p.task.purpose!=='carry'?'ball-control':null,safe:(actor,task,c)=>{
   if(!this.taskSafe(actor,task,c))return false;
   return !c.rivals.some(q=>{const hit=segment(q,actor,task);return hit.u>.05&&hit.u<.95&&hit.d<1.35&&dist(actor,q)<6;});
  }}),selected=Intent.resolve(p,proposal,context);
  if(selected.x!==choice.point.x||selected.z!==choice.point.z)this.telemetry.carryContinuations=(this.telemetry.carryContinuations||0)+1;
  p.carryTarget={x:selected.x,z:selected.z};p.carryIntent={point:{...p.carryTarget},until:Math.min(p.task?.expiresAt??Infinity,this.time+(choice.commit||.4))};p.settleUntil=choice.hold?this.time+.5:0;
  if(choice.shield){
   if(!(p.shieldUntil>this.time)){p.shieldBudgetUntil=this.time+1.1;p.shieldReadyAt=this.time+2;this.telemetry.shieldCarries++;}
   p.shieldUntil=Math.min(p.shieldBudgetUntil,this.time+.4);
   const a=Math.atan2(choice.defender.z-p.z,choice.defender.x-p.x),sign=angle(a+Math.PI/2,p.face)**2<=angle(a-Math.PI/2,p.face)**2?1:-1;p.shieldFace=a+sign*Math.PI/2;
  }else p.shieldUntil=0;
  if(choice.kind==='feint')this.applyFeint(p,choice);this.planClock=0;
 }
 shieldOption(p,defender){
  const a=Math.atan2(p.z-defender.z,p.x-defender.x);let best=null;
  for(const yaw of [0,-.45,.45]){const point={x:clamp(p.x+Math.cos(a+yaw)*1.1,-49,49),z:clamp(p.z+Math.sin(a+yaw)*1.1,-32,32)},room=Math.min(10,...this.rivals(p).map(q=>dist(q,point)));if(!best||room>best.room)best={kind:'carry',point,shield:true,defender,room,commit:.35};}
  return best;
 }
 carryOption(p){
  const opponents=this.rivals(p),side=this.direction(p.team),pace=clamp(p.speed,3.4,5.5);let best=null;
  for(const yaw of [0,-.4,.4,-.85,.85,-1.35,1.35,Math.PI]){
   const a=(side>0?0:Math.PI)+yaw,point={x:clamp(p.x+Math.cos(a)*5.5,-50,50),z:clamp(p.z+Math.sin(a)*5.5,-32,32)};
   if(dist(p,point)<1)continue;
   let clearance=8;
   for(const time of [.25,.55,.95]){
    const progress=Math.min(dist(p,point),pace*time),future={x:p.x+Math.cos(a)*progress,z:p.z+Math.sin(a)*progress};
    for(const rival of opponents){const next={x:rival.x+rival.vx*Math.min(time,.6)*.65,z:rival.z+rival.vz*Math.min(time,.6)*.65};clearance=Math.min(clearance,dist(future,next)-.55-Math.max(0,time-.2)*1.1);}
   }
   const continuity=p.carryIntent?.until>this.time&&dist(point,p.carryIntent.point)<2.5?.9:0;
   const score=Math.min(6,clearance)*1.4+(point.x-p.x)*side*.78-Math.max(0,1.2-clearance)*4-Math.abs(point.z)*.025-Math.abs(angle(a,p.face))*(1.2-(p.agility??80)/110)+continuity;
   if(!best||score>best.score)best={kind:'carry',point,score,clearance,commit:.65};
  }
  return best||{kind:'carry',point:{x:p.x-side*2,z:clamp(p.z+2,-32,32)},score:-20,clearance:0,commit:.4};
 }
 shotWindow(p){
  const goalX=52*this.direction(p.team),x=Math.max(.2,52-p.x*this.direction(p.team)),d=Math.hypot(x,p.z);
  const goalAngle=Math.abs(Math.atan2(3.66-p.z,x)-Math.atan2(-3.66-p.z,x));
  let best=null,open=0;
  for(const z of [-2.65,-1.3,0,1.3,2.65]){
   const point={x:goalX,z},block=this.rivals(p).reduce((r,q)=>{
    const h=segment(q,p,point),travel=d*h.u/31,reach=1.0+clamp((.22+travel-.14)*2.2,0,.9);
    return h.u>.025&&h.u<.96?Math.max(r,clamp((reach-h.d)/reach,0,1)):r;
   },0);
   if(block<.25)open++;
   const keeper=this.rivals(p,true).find(q=>q.role==='GK'),keeperCost=keeper?Math.exp(-Math.abs(z-keeper.z)/1.7)*.15:0;
   const value=(1-block)*.8-keeperCost;if(!best||value>best.value)best={point,block,value};
  }
  const heading=Math.atan2(-p.z,goalX-p.x),turn=Math.abs(angle(heading,p.face??heading));let pressure=0;
  for(const q of this.rivals(p)){
   const dx=q.x-p.x,dz=q.z-p.z,gap=Math.hypot(dx,dz)||.01,front=(dx*Math.cos(heading)+dz*Math.sin(heading))/gap;
   const closing=((q.vx-(p.vx||0))*dx+(q.vz-(p.vz||0))*dz)/gap;
   const effective=gap+Math.min(0,closing)*.18;
   pressure=Math.max(pressure,clamp((3.0-effective)/3,0,1)*(front<-.25?.28:front>.25?1:.75));
  }
  // A geometric lane and a controlled strike are separate questions. A rival
  // arriving from the front disrupts a shot more than one screened behind it.
  const execution=clamp(1-pressure*.48-turn/Math.PI*.24-Math.max(0,(p.speed||0)-4.5)*.045-(p.receiveClock>0?.12:0),.3,1);
  const quality=clamp(goalAngle/Math.PI*1.8*Math.exp(-Math.max(0,d-10)/24)*(1-(best?.block??0)*.65)*execution,.01,.8);
  return {quality,execution,pressure,turn,open:open/5,distance:d,angle:goalAngle,point:best?.point||{x:goalX,z:0}};
 }
 shotQuality(p){return this.shotWindow(p).quality;}
 clearFinish(p,shot=this.shotWindow(p)){
  return p.role!=='GK'&&52-p.x*this.direction(p.team)<23&&Math.abs(p.z)<19&&shot.open>=.60&&(shot.distance<11?shot.quality>.075&&shot.execution>.42:shot.quality>.14&&shot.execution>.66&&(shot.distance<19||shot.quality>.19));
 }
 crossingOption(p){
  const side=this.direction(p.team),t=this.t[p.team];if(p.x*side<25||Math.abs(p.z)<15)return null;
  const candidates=this.field(p.team).filter(q=>q!==p&&q.x*side>24&&Math.abs(q.z)<18),opponents=this.rivals(p);
  let best=null;
  for(const q of candidates){
   const task=this.targets.get(q),back=(p.x-q.x)*side,cutback=back>2&&p.x*side>37;
   const planned=task&&['box-run','cutback-support','receive-run'].includes(task.state)?task:null;
   const ideal=cutback?{x:q.x+q.vx*.3,z:q.z+q.vz*.3}:planned?{x:planned.x,z:planned.z}:{x:side*clamp(q.x*side+3,33,46),z:clamp(q.z,-12,12)};
   let point={...ideal};
   // Solve against the actual delivery speed and a reachable receiver run.
   // The wind-up can improve this margin; it is never assumed to teleport him.
   for(let i=0;i<2;i++){
    const distance=dist(p,point),speed=cutback?18:clamp(distance/1.35,15,25),travel=this.passTime(cutback?'cutback':'cross',distance,speed);
    const reach=Math.max(0,travel-.18)*(5.35+((q.pace??q.skill)-75)*.035),run=dist(q,ideal),fraction=run?Math.min(1,reach/run):1;
    point={x:q.x+(ideal.x-q.x)*fraction,z:q.z+(ideal.z-q.z)*fraction};
   }
   if(!cutback&&point.x*side<(t.crossing==='early'?32:34))continue;
   const distance=dist(p,point);if(distance<4||distance>43)continue;
   const speed=cutback?18:clamp(distance/1.35,15,25),travel=this.passTime(cutback?'cutback':'cross',distance,speed);
   const space=Math.min(12,...opponents.map(o=>dist({x:o.x+o.vx*Math.min(.7,travel)*.5,z:o.z+o.vz*Math.min(.7,travel)*.5},point)));
   const risk=this.laneRisk(p,point,speed,cutback?'cutback':'cross'),quality=this.shotQuality({...q,...point});
   const score=space*.8+(cutback?7:3)+quality*22-risk*(cutback?16:3)+(t.playstyle==='wing'?3:0)+(t.crossing==='low'?(cutback?7:-9):t.crossing==='early'&&!cutback?4:0)-Math.max(0,2-space)*(cutback?3:1.5);
   if(!best||score>best.score)best={kind:cutback?'cutback':'cross',q,point,risk,space,score,arrival:travel};
  }
  return best;
 }
 choose(p){
  const opponents=this.rivals(p),pressure=Math.min(30,...opponents.map(o=>dist(p,o))),goalDist=52-p.x*this.direction(p.team);
  const t=this.t[p.team],shot=this.shotWindow(p),options=this.passOptions(p),best=options[0],cross=this.crossingOption(p),carry=this.carryOption(p);
  // A clear close-range shooting window is taken; a random roll cannot veto it.
  if(this.clearFinish(p,shot))return {kind:'shot',point:shot.point};
  if(p.role!=='GK'&&shot.distance<(t.shooting==='early'?31:t.shooting==='patient'?22:29)&&shot.open>=.4&&shot.execution>.68&&shot.pressure<.65&&shot.quality>(t.shooting==='early'?.09:t.shooting==='patient'?.16:.13)&&(p.shooting>=83||pressure<3)&&(!best||best.score<15))return {kind:'shot',point:shot.point};
  if(cross&&cross.space>1.5&&cross.score>(best?.score??0)-2)return cross;
  if(best?.kind==='through'&&best.score>10&&best.risk<.6)return best;
  const pendingRun=this.field(p.team).find(q=>this.giveGoLink(p,q));
  if(pendingRun&&!best?.movingReturn&&pressure>3.8&&p.carryTime<.9&&(!best||(best.point.x-p.x)*this.direction(p.team)<4))return {kind:'carry',point:{x:clamp(p.x+this.direction(p.team),-49,49),z:p.z},hold:true};
  if(best?.movingReturn&&best.risk<.45&&best.arrivalRisk<.65&&best.space>2.5&&best.score>4)return best;
  const arrivalPlan=this.supportPlans[p.team],counterExit=this.transitionUntil[p.team]>this.time&&t.onWin==='counter';
  const closing=opponents.some(q=>{const gap=dist(q,p);return gap<12&&((p.x-q.x)*(q.vx-p.vx)+(p.z-q.z)*(q.vz-p.vz))/Math.max(.1,gap)>.75;});
  if((pressure<5.5||closing)&&arrivalPlan?.ownerId===p.id&&arrivalPlan.epoch===this.attackEpoch[p.team]&&arrivalPlan.handoffUntil>this.time&&p.carryTime>=.18){
   // A ready lower-ranked connection must not wait merely because the highest
   // ranked attacking option is not ready. Keep clear finishes/runs above.
   const ready=options.filter(o=>o.kind==='pass'&&arrivalPlan.points.has(o.q.id)&&this.targets.get(o.q)?.state==='support'&&dist(o.q,this.targets.get(o.q))<3&&o.score>0&&o.risk<.35&&o.arrivalRisk<.65&&o.space>2.4&&(!counterExit||(o.point.x-p.x)*this.direction(p.team)>-2));
   for(const option of ready.slice(0,2))if(this.passPreparation(p,option).feasible){
    this.telemetry.arrivalSupportChoices=(this.telemetry.arrivalSupportChoices||0)+1;return {...option,supportContinuation:true};
   }
  }
  // A blocked high-value option must not hide a safe lower-ranked exit.
  // Only leave the duel early when the carrying route itself is closing;
  // an open run, a clear finish and an arriving wall pass retain priority.
  const outlet=pressure<4.4&&p.role!=='GK'?options.find(o=>o.kind==='pass'&&o.distance<28&&o.risk<.35&&o.arrivalRisk<.65&&o.space>2.4&&Math.abs(angle(Math.atan2(o.point.z-p.z,o.point.x-p.x),p.face))<2.6):null;
  const repeated=p.duelMemory&&p.duelMemory.count>=2&&this.time-p.duelMemory.at<6&&dist(p,p.duelMemory.origin)<5;
  if(repeated&&best&&best.risk<.55&&(best.arrivalRisk??0)<.82)return {...best,duelOutlet:true};
  if(t.playstyle==='wing'&&p.x*this.direction(p.team)>12&&p.x*this.direction(p.team)<43&&Math.abs(p.z)>17&&pressure>2.8&&carry.clearance>1.3&&(carry.point.x-p.x)*this.direction(p.team)>2&&(!best||(best.point.x-p.x)*this.direction(p.team)<5)){
   this.attackStats[p.team].wideCarries++;return carry;
  }
  if(p.escapeUntil>this.time&&p.escapeTarget&&dist(p,p.escapeTarget)>1.3){
   const blocker=opponents.find(q=>{const h=segment(q,p,p.escapeTarget);return q.duelRecovery<=0&&h.u>.08&&h.u<.95&&h.d<1.4;});
   if(!blocker)return {kind:'carry',point:p.escapeTarget};
   if(best&&best.risk<.55&&(best.arrivalRisk??0)<.82)return {...best,duelOutlet:true};
   if(dist(p,blocker)<2.5&&carry.clearance<1&&this.canShield(p))return this.shieldOption(p,blocker);return carry;
  }
  if(p.role==='GK'){
   if(best&&best.risk<.50&&(pressure>4||best.score>3))return best;
   const outlet=options.filter(o=>o.q.role!=='GK').sort((a,b)=>(b.point.x-p.x)*this.direction(p.team)-(a.point.x-p.x)*this.direction(p.team))[0];
   if(outlet)return {...outlet,kind:dist(p,outlet.point)>27?'long-pass':outlet.kind};
   return {kind:'clearance',point:{x:clamp(p.x+this.direction(p.team)*40,-45,45),z:p.z>=0?24:-24}};
  }
  if(p.x*this.direction(p.team)<-31&&pressure<2.4&&(!best||best.risk>.62)&&!outlet)return {kind:'clearance',point:{x:clamp(p.x+this.direction(p.team)*39,-45,45),z:Math.sign(p.z||1)*29}};
  const counter=this.transitionUntil[p.team]>this.time&&t.onWin==='counter',supports=this.field(p.team).filter(q=>q!==p&&this.targets.get(q)?.state==='support');
  // Circulate at the chosen tempo when the block is closed. A clear shot,
  // through-ball, urgent outlet or counter already took priority above.
  const progress=best?(best.point.x-p.x)*this.direction(p.team):0,gain=best?this.threat(best.point,p.team)-this.threat(p,p.team):0;
  const readTime=clamp(2.1-t.tempo*.016,.65,2.1)+(t.passing==='short'?.25:0),readyOutlet=best&&this.targets.get(best.q)?.state==='support'&&dist(best.q,this.targets.get(best.q))<3;
  if(!counter&&pressure>4.2&&!readyOutlet&&p.carryTime<readTime&&goalDist>23&&(!best||gain<.15&&progress<12)){
   const outlet=best&&best.risk<.35?best:null,a=outlet?Math.atan2(outlet.point.z-p.z,outlet.point.x-p.x):p.face;
   return {kind:'carry',point:{x:clamp(p.x+Math.cos(a)*2,-49,49),z:clamp(p.z+Math.sin(a)*2,-31,31)},hold:true};
  }
  const supportReady=supports.some(q=>dist(q,this.targets.get(q))<3.0),patience=t.playstyle==='possession'?2.3:t.passing==='mixed'?1.65:.9;
  if(!counter&&pressure>5.5&&p.x*this.direction(p.team)<18&&p.carryTime<patience&&supports.length&&!supportReady&&(!best||best.kind!=='through'&&this.threat(best.point,p.team)-this.threat(p,p.team)<.14)){
   return {kind:'carry',point:{x:clamp(p.x+this.direction(p.team)*1.5,-49,49),z:p.z},hold:true};
  }
  if(pressure>1.35&&pressure<3.1&&p.dribbling>=85&&p.feintCooldown<=0&&(!best||best.score<17||best.risk>.5)){
   const feint=this.feintOption(p,nearest(opponents,p));if(feint)return feint;
  }
  if(outlet&&(pressure<3.2&&carry.clearance<1.5||best?.risk>=.5&&carry.clearance<2.0))return {...outlet,pressureOutlet:true};
  const safe=best&&best.risk<.50&&(best.arrivalRisk??0)<.80;
  if(pressure<2.25&&!safe&&this.canShield(p)&&(carry.clearance<1||(carry.point.x-p.x)*this.direction(p.team)<.5))return this.shieldOption(p,nearest(opponents,p));
  if(best&&carry.clearance>2.2&&(best.arrivalRisk>.67||(best.point.x-p.x)*this.direction(p.team)<4&&p.carryTime<2.2)&&(p.escapeUntil||0)<=this.time)return carry;
  if(best&&(pressure<4.4||best.score>16&&(best.point.x-p.x)*this.direction(p.team)>6||p.carryTime>(t.passing==='short'?1.35:2.5)||t.playstyle==='possession'&&best.score>7&&p.carryTime>.45)&&best.risk<(t.passing==='short'?.56:.68)&&(best.arrivalRisk<.82||carry.clearance<.5))return best;
  if(best&&pressure<1.7&&best.risk<.88&&best.arrivalRisk<.85)return best;
  return carry;
 }
 aimShot(p,point,origin=p){
  const preferred=point?.z??this.shotWindow(p).point.z,pressure=Math.min(20,...this.rivals(p).map(q=>dist(p,q)));
  const distance=this.shotWindow(p).distance,turn=Math.abs(angle(Math.atan2(preferred-origin.z,52*this.direction(p.team)-origin.x),p.face));
  const technique=footSkill(p,p.shooting,p.kickFoot);
  const stress=Math.max(0,3-pressure)*(1.15-(p.composure??p.skill)*.005);
  const error=(this.random()-.5)*(1.4+distance*.14+(100-technique)*.12+stress+turn*.65+Math.max(0,.65-(p.energy??1))*2);
  const toPlane=Math.max(1,52-origin.x*this.direction(p.team)),beyond=(54-origin.x*this.direction(p.team))/toPlane;
  return {x:54*this.direction(p.team),z:origin.z+(preferred-origin.z)*beyond+error};
 }
 startKick(p,kind,target=null,point=null,powerOverride=null,restartContext=null){
  if(this.kick||!p.active||target===p)return false;
  let aim=point;
  if(kind==='shot'){
   if(!restartContext){const raw=point||this.shotWindow(p).point,a=Math.atan2(raw.z-p.z,raw.x-p.x),lateral=-(this.ball.x-p.x)*Math.sin(a)+(this.ball.z-p.z)*Math.cos(a);p.kickFoot=Math.abs(lateral)>.10?(lateral>0?1:0):(p.preferredFoot??p.kickFoot);}
   aim=restartContext?.shotAim?{...restartContext.shotAim}:this.aimShot(p,aim);
   this.emit('shot','Kaleyi deniyor',`${p.name} boşluğu gördü ve şutunu hazırladı.`,p);
  }
  if(!aim&&target)aim={x:target.x,z:target.z};if(!aim)return false;
  const origin=restartContext&&kind!=='throw'?restartContext.spot:p;
  const heading=Math.atan2(aim.z-origin.z,aim.x-origin.x),turn=Math.abs(angle(heading,p.face));
  const lateral=-(this.ball.x-p.x)*Math.sin(heading)+(this.ball.z-p.z)*Math.cos(heading);
  if(!restartContext&&kind!=='shot')p.kickFoot=Math.abs(lateral)>.10?(lateral>0?1:0):(p.preferredFoot??p.kickFoot);
  const aimed={...p,face:heading},cp=this.contactPoint(aimed);
  const setup=Math.hypot(cp[0]-this.ball.x,cp[2]-this.ball.z);
  const oneTouch=p.oneTouchUntil>this.time&&['pass','cutback','through'].includes(kind);
  const duration=Math.max(kind==='throw'?.55:kind==='shot'?.25:oneTouch?.12:.18,turn/7.0,setup/(oneTouch?6:4.8));
  const moving=!this.restart&&!restartContext&&kind!=='throw'&&turn<1.45&&Math.hypot(p.vx,p.vz)>.8;
  this.kick={p,kind,target,point:{...aim},clock:0,duration,powerOverride,moving,oneTouch,restartContext,approach:{vx:p.vx,vz:p.vz},setupImpulse:false};if(target&&['through','cross','cutback'].includes(kind)){target.runIntent={...(target.runIntent?.until>this.time?target.runIntent:{}),point:{...aim},until:this.time+3};}this.phase='windup';this.owner=p;
  if(kind==='pass'&&target&&!restartContext&&!oneTouch&&duration>=.30&&(p.passReviewUntil||0)<=this.time){const speed=this.passSpeed(kind,dist(this.ball,aim),this.t[p.team]);this.kick.passRead={base:this.laneRisk(p,aim,speed,kind),next:.04,badSince:null,motionAt:this.time,motion:new Map(this.rivals(p).map(d=>[d.id,{vx:d.vx,vz:d.vz,ax:0,az:0,seenAt:d.seenAt??this.time}]))};}
  this.action(p,kind==='throw'?'throw':kind==='shot'?'shoot':'pass',duration+.22);p.contactTime=duration;p.kickMoving=moving;return true;
 }
 forecastPassRival(d,motion,seconds){
  const t=Math.max(0,seconds),vx=d.vx,vz=d.vz,moving=Math.hypot(vx,vz)>.05,ax0=moving&&Number.isFinite(motion?.ax)?motion.ax:0,az0=moving&&Number.isFinite(motion?.az)?motion.az:0,scale=Math.min(1,11/(Math.hypot(ax0,az0)||1)),ax=ax0*scale,az=az0*scale,a2=ax*ax+az*az,v2=vx*vx+vz*vz,va=vx*ax+vz*az,cap=Math.max(8,Math.sqrt(v2));
  // Use only a short observed trend. Braking cannot invent a reversal;
  // acceleration stops at a bounded speed and then coasts.
  const stop=a2>1e-8&&va<-.75*Math.sqrt(v2*a2)?Math.sqrt(v2/a2):Infinity;
  const top=a2>1e-8?Math.max(0,(-va+Math.sqrt(Math.max(0,va*va+a2*(cap*cap-v2))))/a2):Infinity;
  const used=Math.min(t,.35,stop,top);let x=d.x+vx*used+ax*used*used*.5,z=d.z+vz*used+az*used*used*.5,ux=vx+ax*used,uz=vz+az*used;
  if(stop<=used+1e-9)ux=uz=0;const speed=Math.hypot(ux,uz);if(speed>cap){ux*=cap/speed;uz*=cap/speed;}
  x+=ux*(t-used);z+=uz*(t-used);return {x,z,vx:ux,vz:uz};
 }
 passReceiverAt(k,seconds){
  seconds=clamp(Number.isFinite(seconds)?seconds:0,0,.45);
  const q=k.target,target=q&&q.team===k.p.team?this.targets.get(q):null;
  return this.receiverAt(q,seconds,target);
 }
 receiverAt(q,seconds,target){
  return this.projectPlayer(q,seconds,target,1.6);
 }
 projectPlayer(q,seconds,target,horizon=1.6){
  horizon=clamp(Number.isFinite(horizon)?horizon:1.6,0,2.4);
  seconds=clamp(Number.isFinite(seconds)?seconds:0,0,horizon);
  if(!q||!q.active)return {player:null,target:null,planned:false};
  const future={...q},planned=!!target&&Number.isFinite(target.x)&&Number.isFinite(target.z)&&Number.isFinite(target.pace)&&target.pace>=0&&!['restart','wall','goal'].includes(target.state);
  if(!planned){future.x+=future.vx*seconds;future.z+=future.vz*seconds;return {player:future,target:null,planned:false};}
  // Only the selected teammate's current command is known. Reuse normal
  // acceleration, braking, turning, stamina and avoidance on isolated copies;
  // do not run a future tactical plan or inspect any opponent command.
  const peers=this.players.filter(p=>p.active&&p.team===q.team&&p.id!==q.id).map(original=>({original,player:{...original}}));
  const context={players:[future,...peers.map(p=>p.player)],owner:null,kick:null,restart:null,flight:this.flight,time:this.time,ball:{...this.ball},effort:Match.prototype.effort};
  let elapsed=0;
  while(elapsed<seconds-1e-9){
   const dt=Math.min(1/60,seconds-elapsed);elapsed+=dt;
   for(const peer of peers){peer.player.x=peer.original.x+peer.original.vx*elapsed;peer.player.z=peer.original.z+peer.original.vz*elapsed;}
   for(const key of ['duelRecovery','feintReaction','receiveClock','holdClock'])future[key]=Math.max(0,(future[key]||0)-dt);
   if(future.actionClock>0){future.actionClock=Math.max(0,future.actionClock-dt);future.actionElapsed+=dt;if(!future.actionClock)future.action='idle';}
   context.ball=BallPhysics.predict(this.ball,elapsed-dt);context.time=this.time+elapsed;
   Match.prototype.move.call(context,future,target,dt);
  }
  return {player:future,target,planned:true};
 }
 passReleaseRisk(k){
  const p=k.p,lead=Math.min(.45,Math.ceil(Math.max(0,k.duration-k.clock)*60-1e-7)/60),future={...p},vx=k.moving?k.approach.vx:0,vz=k.moving?k.approach.vz:0;
  // The kicker's own approach is known. Match the fixed-step acceleration
  // instead of freezing a player who is still slowing into the strike.
  for(let left=lead;left>1e-9;){const dt=Math.min(1/60,left),dx=vx-future.vx,dz=vz-future.vz,change=Math.hypot(dx,dz)||1,factor=Math.min(1,12*dt/change);future.vx+=dx*factor;future.vz+=dz*factor;future.x+=future.vx*dt;future.z+=future.vz*dt;left-=dt;}
  const receiver=this.passReceiverAt(k,lead),coast={x:clamp(k.point.x+(k.target?.vx||0)*lead,-50,50),z:clamp(k.point.z+(k.target?.vz||0)*lead,-32,32)};
  let point=coast;
  if(receiver.planned){const distance=dist(future,receiver.player),flight=clamp(this.passTime('pass',distance,this.passSpeed('pass',distance,this.t[p.team])),.2,1.6),aim=this.receiverPoint(receiver.player,flight*.85,receiver.target);point={x:clamp(aim.x,-50,50),z:clamp(aim.z,-32,32)};}
  const heading=Math.atan2(point.z-future.z,point.x-future.x);future.face=p.face+clamp(angle(heading,p.face),-7*lead,7*lead);future.speed=Math.hypot(future.vx,future.vz);const foot=this.contactPoint(future,'pass'),origin={...future,x:foot[0],z:foot[2]},ball=BallPhysics.predict(this.ball,lead),contactGap=Math.hypot(foot[0]-ball.x,foot[2]-ball.z),facingError=Math.abs(angle(heading,future.face)),contactReady=!!k.setupImpulse&&contactGap<.11+1e-7&&facingError<.07+1e-7;
  const rivals=this.rivals(p).map(d=>{const motion=k.passRead?.motion?.get(d.id),start={x:d.x,z:d.z,vx:d.vx,vz:d.vz},at=this.forecastPassRival(start,motion,lead);return {...at,touchClock:Math.max(0,(d.touchClock||0)-lead),duelRecovery:Math.max(0,(d.duelRecovery||0)-lead),passFuture:t=>this.forecastPassRival(start,motion,lead+t)};});
  const evaluate=aim=>this.laneRisk(origin,aim,this.passSpeed('pass',dist(origin,aim),this.t[p.team]),'pass',rivals),nominalRisk=evaluate(point),receiverSpread=dist(point,coast),coastRisk=receiverSpread>1e-7?evaluate(coast):nominalRisk,midRisk=receiverSpread>1e-7?evaluate({x:(point.x+coast.x)/2,z:(point.z+coast.z)/2}):nominalRisk,risk=Math.max(nominalRisk,coastRisk,midRisk);
  return {risk,nominalRisk,coastRisk,midRisk,receiverSpread,receiverPlanned:receiver.planned,receiver:receiver.player?{x:receiver.player.x,z:receiver.player.z,vx:receiver.player.vx,vz:receiver.player.vz}:null,lead,origin:{x:origin.x,z:origin.z},point,coastPoint:coast,contactGap,facingError,contactReady};
 }
 preparationContext(p){
  const preview=Object.assign(Object.create(Match.prototype),this),known=new Map(this.rivals(p,true).map(q=>[q.id,q]));
  const copies=new Map(this.players.map(q=>{
   const source=q.team===p.team||q.referee?q:known.get(q.id),copy=source?{...source}:{id:q.id,team:q.team,role:q.role,active:false};
   if(copy.task)copy.task=structuredClone(copy.task);if(copy.taskHistory)copy.taskHistory=structuredClone(copy.taskHistory);
   return [q,copy];
  })),byId=new Map([...copies.values()].map(q=>[q.id,q]));
  preview.players=[...copies.values()];preview.ball={...this.ball};preview.telemetry={...this.telemetry};
  // Opponents in this isolated forecast are the actor's observations. The
  // normal movement/contact code may inspect those copies without learning
  // anything new from a hidden opponent or refreshing a scan in the future.
  preview._perceptionActive=false;
  preview.targets=new Map([...this.targets].filter(([q])=>q.team===p.team).map(([q,t])=>[copies.get(q),{...t}]));
  preview.kick=null;preview.restart=null;preview.goalPause=null;preview.owner=copies.get(p);
  preview.reviewPass=()=>false;preview.random=()=>{throw Error('Preparation forecast must not draw randomness');};
  return {preview,copies,byId};
 }
 controlPreparation(p,choice,read=null,seconds=.35){
  // Cancelling a pass can expose an already-forward ball even sooner than
  // completing its setup. Compare that immediate physical cost, too.
  const {preview,copies,byId}=this.preparationContext(p),actor=copies.get(p),dt=1/60,horizon=clamp(Number.isFinite(seconds)?seconds:.35,.15,.75);
  actor.kickMoving=false;preview.action(actor,'idle',0);preview.startCarry(actor,choice);
  let interventionTime=null,firstTouchTime=null;
  for(let tick=1;tick<=Math.round(horizon/dt)&&interventionTime===null;tick++){
   const elapsed=tick*dt;preview.time=this.time+elapsed;
   for(const key of ['duelRecovery','touchClock','receiveClock','feintReaction'])actor[key]=Math.max(0,(actor[key]||0)-dt);
   for(const d of this.rivals(p)){
    const q=byId.get(d.id);Object.assign(q,this.forecastPassRival(d,read?.motion?.get(d.id),elapsed));
    q.duelRecovery=Math.max(0,(q.duelRecovery||0)-dt);q.tackleClock=Math.max(0,(q.tackleClock||0)-dt);
    if(Math.hypot(q.vx,q.vz)>.3)q.face+=clamp(angle(Math.atan2(q.vz,q.vx),q.face),-4.5*dt,4.5*dt);
   }
   const shield=actor.shieldUntil>preview.time,target=dist(actor,preview.ball)>1.1?{x:preview.ball.x+preview.ball.vx*.12,z:preview.ball.z+preview.ball.vz*.12}:choice.point;
   const pressure=Math.min(20,...preview.field(1-p.team).map(q=>dist(q,actor))),counter=preview.transitionUntil[p.team]>preview.time&&preview.t[p.team].onWin==='counter';
   const pace=actor.receiveClock>0?.48:shield?.56:actor.settleUntil>preview.time?.34:counter?1.04:actor.escapeUntil>preview.time?.98:pressure>5&&actor.x*this.direction(p.team)<20?.60:.98;
   preview.move(actor,{...target,state:actor.receiveClock>0?'receive':shield?'shield':'dribble',pace},dt);
   if(actor.touchClock<=0&&actor.receiveClock<=0&&preview.ball.y<.45&&dist(actor,preview.ball)<1.3&&preview.dribbleTouch(actor))firstTouchTime??=elapsed;
   const d=nearest(preview.field(1-p.team),preview.ball);
   if(d){const access=preview.tackleAccess(d,actor);if(access.attempt)interventionTime=elapsed;else if(access.retry)d.tackleClock=access.retry;}
   preview.integrateBall(dt);
  }
  return {interventionTime,firstTouchTime,horizon};
 }
 postReceiveHold(p,choice){
  // A short pause must not reverse a receiver's still-active carrying run
  // into an approaching boot. Compare both commands with ordinary movement
  // and touches; retaining an intention never grants possession or a tackle veto.
  const age=this.time-(this.lastGain?.time??-Infinity),target=p.carryTarget;
  if(choice?.kind!=='carry'||!choice.hold||!Number.isFinite(choice.point?.x)||!Number.isFinite(choice.point?.z)||this.owner!==p||!p.active||p.role==='GK'||this.restart||this.kick||this.lastGain?.player!==p.id||age<0||age>1.5||!['open','protect'].includes(p.receiveMode)||p.receiveClock>0||!(p.carryIntent?.until>this.time)||!Number.isFinite(target?.x)||!Number.isFinite(target?.z)||dist(p,target)<.8||this.ball.y>=.45||dist(p,this.ball)>=1.45)return choice;
  const speed=Math.hypot(p.vx,p.vz),turn=Math.abs(angle(Math.atan2(choice.point.z-p.z,choice.point.x-p.x),Math.atan2(p.vz,p.vx)));
  if(speed<.8||turn<1.1)return choice;
  const threatened=this.rivals(p).some(q=>{const gap=dist(q,p),closing=((p.x-q.x)*(q.vx-p.vx)+(p.z-q.z)*(q.vz-p.vz))/Math.max(.1,gap);return gap<5.5||gap<10&&closing>.75;});
  if(!threatened)return choice;
  const requested=this.controlPreparation(p,choice,null,.75);
  if(requested.interventionTime===null)return choice;
  const continuation={kind:'carry',point:{x:target.x,z:target.z},commit:.35},retained=this.controlPreparation(p,continuation,null,.75);
  if(retained.interventionTime!==null||retained.firstTouchTime===null)return choice;
  return {...continuation,holdContinuation:true};
 }
 passPreparation(p,option,read=null){
  // Run the actual wind-up on isolated copies. No future plan, opponent
  // commands, random draws, strike impulse or real-state writes are allowed.
  const {preview,copies,byId}=this.preparationContext(p);
  let contactTime=null,interventionTime=null,risk=1,arrivalRisk=1,contactGap=null,facingError=null;
  preview.doTackle=(d,carrier)=>{const access=preview.tackleAccess(d,carrier);if(access.attempt)interventionTime??=preview.time-this.time;else if(access.retry)d.tackleClock=access.retry;};
  preview.release=()=>{
   contactTime=preview.time-this.time;const k=preview.kick,foot=preview.contactPoint(k.p,'pass');
   contactGap=Math.hypot(foot[0]-preview.ball.x,foot[2]-preview.ball.z);
   facingError=Math.abs(angle(Math.atan2(k.point.z-k.p.z,k.point.x-k.p.x),k.p.face));
   risk=preview.laneRisk(k.p,k.point,preview.passSpeed('pass',dist(preview.ball,k.point),preview.t[p.team]));
   const speed=preview.passSpeed('pass',dist(preview.ball,k.point),preview.t[p.team]);
   arrivalRisk=preview.receptionSafety(k.p,k.target,k.point,preview.passTime('pass',dist(preview.ball,k.point),speed)).risk;
  };
  const actor=copies.get(p),receiver=copies.get(option.q);
  if(!actor||!receiver?.active||receiver.team!==p.team)return {feasible:false,reason:'unavailable'};
  actor.oneTouchUntil=0;
  if(!preview.startKick(actor,'pass',receiver,option.point))return {feasible:false,reason:'unavailable'};
  const duration=preview.kick.duration,dt=1/60,horizon=.75;
  const rivals=this.rivals(p);
  for(let tick=1;tick<=Math.round(horizon/dt)&&preview.kick&&contactTime===null;tick++){
   const elapsed=tick*dt;preview.time=this.time+elapsed;
   for(const original of this.players){
    const q=copies.get(original);
    for(const key of ['duelRecovery','tackleClock','touchClock','receiveClock','feintReaction','holdClock'])q[key]=Math.max(0,(q[key]||0)-dt);
    if(q.actionClock>0){q.actionClock=Math.max(0,q.actionClock-dt);q.actionElapsed+=dt;if(!q.actionClock)q.action='idle';}
   }
   for(const d of rivals){
    const q=byId.get(d.id),next=this.forecastPassRival(d,read?.motion?.get(d.id),elapsed);
    Object.assign(q,next);q.speed=Math.hypot(q.vx,q.vz);
    if(q.speed>.3)q.face+=clamp(angle(Math.atan2(q.vz,q.vx),q.face),-4.5*dt,4.5*dt);
   }
   for(const [q,target] of preview.targets)preview.move(q,target,dt);
   if(!preview.targets.has(actor))preview.move(actor,{x:actor.x,z:actor.z,pace:1,state:'kick'},dt);
   preview.kickStep(dt);
  }
  const feasible=contactTime!==null&&interventionTime===null&&risk<.35&&arrivalRisk<.65;
  return {feasible,reason:interventionTime!==null?'intervention':contactTime===null?'contact-timeout':risk>=.35?'release-lane':arrivalRisk>=.65?'reception':'ready',duration,contactTime,interventionTime,risk,arrivalRisk,contactGap,facingError,horizon};
 }
 reviewPass(k){
  const read=k.passRead,p=k.p;if(!read||this.kick!==k||k.duration-k.clock<=.12||k.clock+1e-9<read.next)return false;
  read.next=k.clock+.05;const speed=this.passSpeed('pass',dist(this.ball,k.point),this.t[p.team]),risk=this.laneRisk(p,k.point,speed,'pass');
  const elapsed=this.time-(read.motionAt??this.time),previous=read.motion;read.motion=new Map(this.rivals(p).map(d=>{const old=previous?.get(d.id),valid=old&&elapsed>1e-6&&elapsed<=.25&&(d.seenAt===undefined||d.seenAt>(old.seenAt??-Infinity));return [d.id,{vx:d.vx,vz:d.vz,ax:valid?(d.vx-old.vx)/elapsed:0,az:valid?(d.vz-old.vz)/elapsed:0,seenAt:d.seenAt??this.time}];}));read.motionAt=this.time;
  this.telemetry.passReviews=(this.telemetry.passReviews||0)+1;
  if(risk<.75||risk<read.base+.30){read.badSince=null;return false;}
  read.badSince??=this.time;const reaction=clamp(.10+(100-(p.vision??p.skill))*.0015,.11,.19);
  if(this.time-read.badSince<reaction-1e-7)return false;
  const forecast=this.passReleaseRisk(k);read.lastForecast={...forecast,time:this.time,currentRisk:risk};this.telemetry.passReleaseReads=(this.telemetry.passReleaseReads||0)+1;
  if(!forecast.contactReady)this.telemetry.passReleaseUncertain=(this.telemetry.passReleaseUncertain||0)+1;
  if(forecast.contactReady&&forecast.risk<.75){this.telemetry.passReleaseDeferrals=(this.telemetry.passReleaseDeferrals||0)+1;return false;}
  // Reconsider only an early, sustained new threat. One response budget
  // prevents repeated wind-up cancellations while the same press develops.
  const options=this.passOptions(p).filter(o=>o.kind==='pass'&&o.q!==k.target&&o.q.duelRecovery<=0&&o.distance<28&&o.risk<.35&&o.arrivalRisk<.65&&o.space>2.4&&Math.abs(angle(Math.atan2(o.point.z-p.z,o.point.x-p.x),p.face))<2.2);
  const assessed=options.map(o=>({option:o,preparation:this.passPreparation(p,o,read)}));
  const ready=assessed.filter(a=>a.preparation.feasible).sort((a,b)=>(b.option.score-b.preparation.contactTime*(2+this.t[p.team].tempo/25))-(a.option.score-a.preparation.contactTime*(2+this.t[p.team].tempo/25)));
  let selected=ready[0],fallback=null,control=null,emergency=false;
  if(!selected){
   const carry=this.carryOption(p),defender=nearest(this.rivals(p),p);
   fallback=defender&&dist(defender,p)<3&&this.canShield(p)&&carry.clearance<1.4?this.shieldOption(p,defender):carry;
   control=this.controlPreparation(p,fallback,read,Math.max(.15,...assessed.map(a=>a.preparation.contactTime??a.preparation.duration??.35)));
   // No safe option: do not reset into an even earlier reachable tackle.
   // A last-resort outlet remains explicitly risky; it gets no protection.
   if(control.interventionTime!==null){
    selected=assessed.filter(a=>a.preparation.reason==='intervention'&&a.preparation.contactTime!==null&&a.preparation.risk<.35&&a.preparation.arrivalRisk<.65&&a.preparation.interventionTime>control.interventionTime+1/60).sort((a,b)=>(b.preparation.interventionTime-b.preparation.contactTime)-(a.preparation.interventionTime-a.preparation.contactTime)||b.option.score-a.option.score)[0];
    emergency=!!selected;
   }
  }
  const outlet=selected?.option;
  this.telemetry.passPreparationChecks=(this.telemetry.passPreparationChecks||0)+assessed.length;
  this.telemetry.passPreparationRejects=(this.telemetry.passPreparationRejects||0)+assessed.filter(a=>!a.preparation.feasible).length;
  this.lastPassPreparation={time:this.time,playerId:p.id,originalTargetId:k.target.id,selectedTargetId:outlet?.q.id??null,emergency,control,candidates:assessed.map(a=>({targetId:a.option.q.id,score:a.option.score,...a.preparation}))};
  p.passReviewUntil=this.time+.9;this.kick=null;p.oneTouchUntil=0;this.planClock=0;
  this.telemetry.passRethinks=(this.telemetry.passRethinks||0)+1;
  if(outlet&&this.startKick(p,outlet.kind,outlet.q,outlet.point)){
   this.kick.replanned=true;this.telemetry.passRedirects=(this.telemetry.passRedirects||0)+1;
   if(emergency)this.telemetry.passEmergencyOutlets=(this.telemetry.passEmergencyOutlets||0)+1;
  }else{
   p.kickMoving=false;p.carryTime=0;p.decision=.12+(100-this.t[p.team].tempo)*.002;
   this.action(p,'idle',0);this.phase='carry';
   this.startCarry(p,fallback);this.lastPassPreparation.fallback=fallback.shield?'shield':'control';
   this.telemetry.passResets=(this.telemetry.passResets||0)+1;
  }
  return true;
 }
 contactPoint(p,kind){if(kind==='throw')return [p.x+Math.cos(p.face)*.40,1.95,p.z+Math.sin(p.face)*.40];return this.motion?.kickContact(p)||[p.x+Math.cos(p.face)*.88-Math.sin(p.face)*(p.kickFoot===0?-.18:.18),.11,p.z+Math.sin(p.face)*.88+Math.cos(p.face)*(p.kickFoot===0?-.18:.18)];}
 release(){
  const k=this.kick,p=k.p;if(k.restartContext&&!this.restartReady(k.restartContext))return false;const point=this.contactPoint(p,k.kind);if(k.restartContext?.kind==='kickoff'){if(!this.kickoffReady(k.restartContext))return false;point[0]=0;point[2]=0;}this.kick=null;this.owner=null;this.phase='open';
  // Contact changes velocity, never the ball's position. At restarts the boot
  // approaches the fixed ball; a throw has already been lifted to the hands.
  const d=dist(this.ball,k.point)||1,shotPressure=Math.min(10,...this.field(1-p.team).map(q=>dist(q,p)));
  const power=k.powerOverride||(k.kind==='shot'?(21+p.shooting*.085)*(1-Math.max(0,3-shotPressure)*.025):k.kind==='cross'?clamp(d/1.35,15,25):k.kind==='clearance'?29:this.passSpeed(k.kind,d,this.t[p.team]));
  const technique=k.kind==='cross'?(p.crossing??p.passing):p.passing;
  const execution=footSkill(p,technique,p.kickFoot);
  const accuracy=['pass','through','cutback','cross','long-pass'].includes(k.kind)?(this.random()-.5)*(100-execution)/100*(.5+d*.02+(k.moving?.22:0))*(k.kind==='cross'?2.4:1):0;
  const aimed={x:k.point.x-(k.point.z-this.ball.z)/d*accuracy,z:k.point.z+(k.point.x-this.ball.x)/d*accuracy};
  const length=dist(this.ball,aimed)||1;
  this.ball.vx=(aimed.x-this.ball.x)/length*power;this.ball.vz=(aimed.z-this.ball.z)/length*power;
  if(k.kind==='shot'){this.shots[p.team]++;this.xg[p.team]+=this.shotQuality(p);this.telemetry.shotsAfterPasses+=this.chain>=2?1:0;const pressure=Math.min(10,...this.field(1-p.team).map(q=>dist(q,p))),spread=1.6+(100-p.shooting)*.09+Math.max(0,d-12)*.08+(pressure<3?1:0),height=clamp(k.heightTarget!==undefined?k.heightTarget+(this.random()-.5)*(.8+(100-p.shooting)*.04):.85+(this.random()-.5)*spread,.12,3.6);this.ball.vy=BallPhysics.verticalLaunch(d,power,this.ball.y,height,10,.4);}
  else if(k.kind==='cross'){this.ball.vy=BallPhysics.verticalLaunch(d,power,this.ball.y,1.75,11,4);}
  else if(k.kind==='long-pass'||k.kind==='clearance'){this.ball.vy=BallPhysics.verticalLaunch(d,power,this.ball.y,.45,12,4.5);}
  else if(k.kind==='throw'){this.ball.vy=BallPhysics.verticalLaunch(d,power,this.ball.y,.45,7,-1);}
  else this.ball.vy=k.loft?6.2:0;
  this.lastTouch=p;this.lastTeam=p.team;p.touchClock=.24;p.shieldUntil=0;p.dribbleDuel=null;
  if(k.duelOutlet&&['pass','through','long-pass'].includes(k.kind))this.telemetry.duelOutlets++;
  if(k.restartContext?.kind==='free-kick'){
   if(k.kind==='shot')this.telemetry.freeKickShots=(this.telemetry.freeKickShots||0)+1;
   if(k.kind==='cross')this.telemetry.freeKickCrosses=(this.telemetry.freeKickCrosses||0)+1;
   if(k.restartContext.layout?.wall.size)this.activeWall={team:1-p.team,points:k.restartContext.layout.wall,until:this.time+.7};
  }
  this.afterPass(p,k,d);
  this.flight={id:++this.releaseSerial,kind:k.kind,from:p,target:k.target,point:{...k.point},age:0,giveGoReturn:k.giveGoReturn??null,onTarget:false,keepersTried:false,aerialResolved:false,offsidePlayers:(!['throw'].includes(k.kind)&&!['corner','goal-kick','throw'].includes(k.restartContext?.kind))?this.field(p.team).filter(q=>q!==p&&q.x*this.direction(p.team)>Math.max(this.ball.x*this.direction(p.team),this.defenceLine(p.team))+.10&&q.x*this.direction(p.team)>0).map(q=>q.id):[]};
  this.offsidePhase=['throw','corner','goal-kick'].includes(k.restartContext?.kind)||k.kind==='throw'?null:this.captureOffside(p);this.flight.offsidePlayers=this.offsidePhase?.playerIds.slice()||[];this.flight.restartKind=k.restartContext?.kind??null;this.flight.restartIndirect=!!k.restartContext?.indirect;this.penaltyReleased(k,this.flight);
  if(['pass','through','cross','cutback','long-pass'].includes(k.kind))this.passes[p.team]++;
  if(k.supportContinuation)this.telemetry.arrivalSupportReleases=(this.telemetry.arrivalSupportReleases||0)+1;
  if(k.moving&&k.kind==='shot')this.telemetry.movingShots++;
  if(k.moving&&['pass','through','cross','cutback','long-pass'].includes(k.kind))this.telemetry.movingPasses++;
  if(k.oneTouch)this.telemetry.oneTouchPasses++;
  if(k.kind==='long-pass')this.telemetry.longPasses++;
  if(['pass','long-pass'].includes(k.kind)&&Math.abs(k.point.z-p.z)>28){
   const old=this.lastSwitch[p.team];this.telemetry.switches++;this.attackStats[p.team].switches++;
   if(old&&this.time-old.time<9&&Math.sign(k.point.z)===Math.sign(old.fromZ)&&(k.point.x-p.x)*this.direction(p.team)<6)this.attackStats[p.team].returnSwitches++;
   this.lastSwitch[p.team]={time:this.time,fromZ:p.z,toZ:k.point.z,x:p.x};
  }if(k.kind==='clearance')this.telemetry.clearances++;
  if(['pass','through','cross','cutback','long-pass'].includes(k.kind)){const ts=this.tacticalStats[p.team];ts.passDistance+=d;ts.passCount++;if((k.point.x-p.x)*this.direction(p.team)>5)ts.forwardPasses++;}
  if(k.kind==='through'){this.telemetry.throughBalls++;if(k.plannedRun)this.telemetry.alignedThroughBalls++;this.emit('through','Savunma arkasına pas',`${p.name}, ${k.target?.name||'takım arkadaşının'} koşusunu gördü.`,p);}
  if(k.kind==='cross'||k.kind==='cutback'){this.attackStats[p.team][k.kind==='cross'?'crosses':'cutbacks']++;this.telemetry[k.kind==='cross'?'crosses':'cutbacks']++;this.emit(k.kind,k.kind==='cross'?'Ceza sahasına orta':'Geriye çıkarılan top',`${p.name} topu ceza sahasındaki arkadaşına gönderdi.`,p);}
  this.planClock=0;
 }
 afterPass(p,k,d){
  const returned=k.target&&this.giveGoLink(p,k.target);
  if(returned&&['pass','through'].includes(k.kind)&&(k.target.x-returned.origin.x)*this.direction(p.team)>1.8){k.giveGoReturn={passerId:k.target.id,wallId:p.id,epoch:this.attackEpoch[p.team]};this.telemetry.giveGoReturns++;p.comboCooldown=k.target.comboCooldown=this.time+4;}
  if(!['pass','cutback','through'].includes(k.kind)||!k.target||k.restartContext||p.role==='DEF'||p.role==='GK'||this.teamRole(p)==='anchor')return;
  const side=this.direction(p.team),point={x:clamp(side*Math.min(Math.max(p.x*side+7,k.point.x*side+3),this.observedLine(p)-.75),-47,47),z:clamp(p.z+(p.z>=k.point.z?1:-1)*3,-29,29)},advance=(k.point.x-p.x)*side;
  const firstStep={x:p.x+side*1.6,z:p.z+(p.z>=k.point.z?1:-1)*.7},room=Math.min(12,...this.rivals(p).map(q=>segment(q,firstStep,point).d));
  const running=this.field(p.team).some(q=>q!==p&&q!==k.target&&q.runIntent?.until>this.time);
  p.runIntent=null;p.supportIntent=null;
  if(!returned&&k.kind==='pass'&&d<21&&(advance>-1||p.role==='ATT')&&(point.x-p.x)*side>3&&this.t[p.team].playstyle==='possession'&&room>1.8&&!running&&(p.comboCooldown||0)<=this.time&&(k.target.comboCooldown||0)<=this.time){
   p.runIntent={kind:'give-go',partnerId:k.target.id,epoch:this.attackEpoch[p.team],origin:{x:p.x,z:p.z},point,until:this.time+3.2};p.comboCooldown=k.target.comboCooldown=this.time+4;this.telemetry.giveGoes++;return;
  }
  if(d>24||k.kind==='through')return;
  // A blocked wall-pass run becomes a return angle. The passer remains involved
  // without sending every central midfielder beyond the new ball carrier.
  const lateral=p.z>=k.target.z?1:-1;
  const support=p.role==='ATT'?{x:clamp(p.x+side*1.5,-47,47),z:clamp(p.z+lateral*5,-29,29)}:{x:clamp(k.point.x-side*6,-47,47),z:clamp(k.point.z+lateral*7,-29,29)};
  p.supportIntent={qId:k.target.id,epoch:this.attackEpoch[p.team],point:support,until:this.time+1.8};
  this.telemetry.returnSupports++;
 }
 firstControlContact(p){
  const {ready,gap,forward,lateral,turn}=this.touchContact(p);
  return {ready,gap,forward,lateral,turn};
 }
 acquire(p){
  if(this.owner===p||p.duelRecovery>0)return false;
  if(this.offsideTouch(p))return false;
  if(this.penaltyAttempt?.state==='released'&&this.penaltyAttempt.takerId===p.id&&this.lastTouch===p){this.penaltyAttempt.state='settled';this.setRestart('free-kick',1-p.team,{x:p.x,z:p.z});this.restart.indirect=true;this.emit('double-touch','Çift dokunuş','Penaltıyı kullanan oyuncu başka bir oyuncu dokunmadan topa yeniden dokundu.',p,1-p.team);return false;}
  if(this.offsidePhase&&p.team!==this.offsidePhase.team)this.offsidePhase=null;
  const previous=this.lastTouch,flight=this.flight,regained=this.lastTeam!==p.team;
  if(flight?.giveGoReturn?.passerId===p.id&&flight.from.team===p.team&&flight.giveGoReturn.epoch===this.attackEpoch[p.team])this.telemetry.giveGoCompletions++;
  if(flight&&['pass','through','cross','cutback','long-pass'].includes(flight.kind)&&flight.from.team===p.team&&flight.from!==p){this.completed[p.team]++;if(['cross','cutback'].includes(flight.kind))this.attackStats[p.team].completedDeliveries++;this.chain++;if(this.chain===3)this.emit('pass','Paslarla ilerliyorlar',`${p.name} topu aldı; takım pas bağlantısını koruyor.`,p);}
  else if(this.lastTeam!==p.team){this.chain=0;this.transitionUntil[p.team]=this.time+(this.t[p.team].onWin==='counter'?5.5:2.0);this.lossUntil[1-p.team]=this.time+3.2;this.telemetry.turnovers++;if(p.role!=='GK'&&this.time-(this.lastNarratedTurnover||-3)>2){this.lastNarratedTurnover=this.time;this.emit('tackle','Top kazanıldı',`${p.name} araya girdi. Takımı yeniden yerleşiyor.`,p);}}
  if(flight&&flight.from?.team===p.team&&flight.from!==p){p.lastPassFrom=flight.from.id;this.recentPasses.push({from:flight.from.id,to:p.id,time:this.time});this.recentPasses=this.recentPasses.filter(a=>this.time-a.time<8);}
  if(Math.abs(p.z)>19)this.tacticalStats[p.team].wideReceives++;
  if(regained&&this.lossUntil[p.team]>this.time&&this.t[p.team].onLoss==='counterpress')this.telemetry.pressRecoveries++;
  if(regained){this.recoveryUntil[1-p.team]=this.time+8;this.recoveryUntil[p.team]=0;this.attackEpoch[p.team]++;this.attackPlans=[null,null];this.flankPlans=[null,null];this.boxPlans=[null,null];this.supportPlans=[null,null];this.pressUnits=[null,null];this.pressAssignments=[null,null];for(const q of this.players){Intent.clear(q,q.team===p.team?'gain':'loss',this.taskContext(q));q.runIntent=null;q.supportIntent=null;q.offerIntent=null;q.connectionIntent=null;q.carryIntent=null;}}
  else Intent.clear(p,'ball-control',this.taskContext(p));
  p.carryIntent=null;p.supportIntent=null;p.runIntent=null;p.shieldUntil=0;p.dribbleDuel=null;
  this.possessionEpoch++;this.lastGain={player:p.id,team:p.team,time:this.time,x:this.ball.x,z:this.ball.z};
  let reception=flight&&p.reception&&p.reception.flightId===flight.id&&this.time-p.reception.at<.55?p.reception:null;
  const contact=reception&&flight.target===p&&p.role!=='GK'&&['pass','through','cutback'].includes(flight.kind)&&this.ball.y<=BallPhysics.radius+.01&&Math.abs(this.ball.vy)<1e-6?this.firstControlContact(p):null;
  if(this.kick&&this.kick.p!==p)this.kick=null;
  this.owner=p;this.phase='carry';this.flight=null;this.lastTouch=p;this.lastTeam=p.team;p.carryTime=0;p.carryTarget=reception?.point?{...reception.point}:null;p.receiveClock=clamp(.10+(100-p.skill)*.0025+Math.hypot(this.ball.vx-p.vx,this.ball.vz-p.vz)*.002,.10,.32);p.decision=p.receiveClock+.10;p.touchClock=.08;this.telemetry.receives++;
  this.updateTeamPhases();
  // Cushion incoming speed. A first touch may run a little loose; it never relocates the player.
  const arrivalSpeed=Math.hypot(this.ball.vx-p.vx,this.ball.vz-p.vz),arrivalYaw=Math.atan2(this.ball.vz,this.ball.vx),pressure=Math.min(20,...this.field(1-p.team).map(q=>dist(q,p)));
  const turn=Math.abs(angle(p.face,arrivalYaw+Math.PI)),control=clamp((p.skill+(p.dribbling??p.skill))*.005,0,1);
  const difficulty=clamp((arrivalSpeed-10)*.022+turn*.065+Math.max(0,2.5-pressure)*.08-(control-.7)*.6,0,.45);
  this.ball.vx=this.ball.vx*(.10+difficulty*.32)+p.vx*.25;this.ball.vz=this.ball.vz*(.10+difficulty*.32)+p.vz*.25;this.ball.vy=Math.max(0,this.ball.vy*.15);
  if(contact){
   this.telemetry.firstControlChecks=(this.telemetry.firstControlChecks||0)+1;
   if(!contact.ready){
    // Retain the glancing cushion above. Do not steer a ball from behind
    // the body into the old outlet; turn and recover it with normal movement.
    if(reception.mode==='one-touch')this.telemetry.firstControlDeferrals=(this.telemetry.firstControlDeferrals||0)+1;
    reception={...reception,mode:'cushion',point:null,next:null};p.nextAction=null;p.oneTouchUntil=0;
    p.carryTarget={x:this.ball.x+this.ball.vx*.12,z:this.ball.z+this.ball.vz*.12};
    p.receiveClock=Math.max(p.receiveClock,clamp((contact.turn-.9)/4.5,0,.45));p.decision=p.receiveClock+.10;
    this.telemetry.cushionedReceives=(this.telemetry.cushionedReceives||0)+1;
   }
  }
  if(reception){
   this.telemetry.preparedReceives++;p.receiveMode=reception.mode;
   if(reception.mode==='one-touch'){
    p.nextAction={...reception.next,until:this.time+.48};p.oneTouchUntil=this.time+.48;p.receiveClock=.045;p.decision=.045;
   }else if(reception.point){
    const fresh=this.controlOption(p,p,reception.face,0,this.ball);if(fresh){reception.point=fresh;p.carryTarget={...fresh};this.telemetry.firstTouchRechecks++;}
    reception.mode=Math.min(20,...this.rivals(p).map(q=>dist(q,p)))<3?'protect':'open';p.receiveMode=reception.mode;
    const planned=Math.atan2(reception.point.z-this.ball.z,reception.point.x-this.ball.x),a=planned+clamp(angle(arrivalYaw,planned),-1,1)*difficulty*.5,speed=(reception.mode==='protect'?1.1:clamp(1.8+p.speed*.35,1.8,3.8))+difficulty*2.8;
    const plan=contact&&['pass','through','cutback'].includes(flight.kind)?this.touchPlan(p,{vx:Math.cos(a)*speed,vz:Math.sin(a)*speed,vy:this.ball.vy},{mode:'receive',interval:Math.max(p.receiveClock,p.touchClock),target:p.carryTarget,replan:true}):null;
    if(!contact||plan?.ready){
     this.ball.vx=plan?plan.velocity.vx:Math.cos(a)*speed;this.ball.vz=plan?plan.velocity.vz:Math.sin(a)*speed;
     if(plan){this.ball.vy=plan.velocity.vy;p.kickFoot=plan.foot;if(plan.limited)this.telemetry.limitedTouches=(this.telemetry.limitedTouches||0)+1;}
     this.telemetry.directedTouches++;
    }else{
     reception={...reception,mode:'cushion',point:null,next:null};p.receiveMode='cushion';p.nextAction=null;p.oneTouchUntil=0;p.carryTarget={x:this.ball.x+this.ball.vx*.12,z:this.ball.z+this.ball.vz*.12};
     this.telemetry.touchDeferrals=(this.telemetry.touchDeferrals||0)+1;
    }
   }
  }else{p.nextAction=null;p.oneTouchUntil=0;p.receiveMode='settle';}
  p.reception=null;
  if(reception?.mode!=='one-touch'){
   const pressure=Math.min(20,...this.rivals(p).map(q=>dist(q,p))),counter=this.transitionUntil[p.team]>this.time&&this.t[p.team].onWin==='counter';
   if(pressure>5&&!counter)p.decision+=p.role==='DEF'?.65:.30;
  }
  this.action(p,'receive',p.receiveClock);if(p.escapeUntil>this.time){p.carryTarget=p.escapeTarget;p.decision=.20;}this.planClock=0;return true;
 }
 tackleAccess(p,carrier){
  const gap=dist(p,this.ball),approach=angle(Math.atan2(carrier.z-p.z,carrier.x-p.x),p.face);
  if(p.duelRecovery>0||p.tackleClock>0||gap>1.15||Math.abs(approach)>1.4||this.ball.y>.65)return {attempt:false};
  const ballGap=dist(carrier,this.ball),toDefender={x:p.x-carrier.x,z:p.z-carrier.z},toBall={x:this.ball.x-carrier.x,z:this.ball.z-carrier.z};
  const body=segment(carrier,p,this.ball);if(body.u>.08&&body.u<.92&&body.d<.26&&ballGap>.25)return {attempt:false,retry:.20};
  const shield=dot(toDefender,toBall)/(Math.hypot(toDefender.x,toDefender.z)*Math.max(.1,ballGap)||1)<-.25&&ballGap<.95;
  if(shield&&dist(p,carrier)<.65&&gap>.8)return {attempt:false,retry:.35};
  return {attempt:true};
 }
 adjudicateFoul(offender,victim,details={}){
  if(this.done||!offender?.active||!victim?.active||offender.team===victim.team)return null;
  if(this.referee.pendingAdvantage)this.recallAdvantage();
  const decision=RefereeLaws.classifyFoul({offender,victim,spot:details.spot||{x:victim.x,z:victim.z},attackDirection:this.direction(victim.team),players:this.players,ball:this.ball,attemptedBall:details.attemptedBall!==false,...details});
  const record={...decision,id:this.referee.decisions.length+1,offenderId:offender.id,victimId:victim.id,time:this.time,status:'stopped'};this.referee.decisions.push(record);this.fouls[offender.team]++;
  if(record.card!=='none')this.referee.pendingDiscipline.push({playerId:offender.id,card:record.card,reason:record.reason,decisionId:record.id});
  const advance=(this.ball.vx||0)*this.direction(victim.team),ownControl=this.owner?.team===victim.team&&dist(this.owner,this.ball)<1.6;
  const advantage=details.advantage!==false&&record.card!=='red'&&ownControl&&(details.advantage===true||advance>1&&record.restart!=='penalty');
  if(advantage){record.status='advantage';this.referee.pendingAdvantage={decision:record,until:this.time+3,origin:{...record.incident}};this.emit('advantage','Avantaj','Hakem oyunu sürdürüyor; avantaj oluşmazsa faul yerine dönülecek.',victim);}
  else{this.emit(record.restart==='penalty'?'penalty':'foul',record.restart==='penalty'?'Penaltı!':'Faul',`${offender.name} faul yaptı. ${record.restart==='penalty'?'Vuruş penaltı noktasından kullanılacak.':'Serbest vuruş faul yerinden kullanılacak.'}`,victim);this.setRestart(record.restart,record.team,record.spot);}
  return record;
 }
 settleDiscipline(){
  const pending=this.referee?.pendingDiscipline?.splice(0)||[];
  for(const d of pending){const p=this.players[d.playerId];if(!p?.active)continue;
   if(d.card==='yellow'){this.cards[p.team]++;p.yellow=(p.yellow||0)+1;if(p.yellow<2){this.emit('yellow','Sarı kart',`${p.name} kontrolsüz müdahalesi nedeniyle sarı kart gördü.`,p);continue;}}
   p.active=false;p.vx=p.vz=p.speed=0;this.reds[p.team]++;this.emit('red',d.card==='red'?'Doğrudan kırmızı kart':'İkinci sarıdan kırmızı',`${p.name} oyun dışında. ${d.reason==='serious-foul-play'?'Rakibinin güvenliğini tehlikeye soktu.':d.reason==='denial-of-goal-opportunity'?'Bariz gol şansını engelledi.':''}`,p);
   if(this.team(p.team).length<this.rules.minPlayers&&!this.done)this.finishMatch('minimum-players');
  }
 }
 recallAdvantage(){const a=this.referee.pendingAdvantage;if(!a)return false;this.referee.pendingAdvantage=null;a.decision.status='recalled';this.emit('advantage-recall','Avantaj geri alındı','Hakem ilk faulün yerine dönüyor.',null,a.decision.team);this.setRestart(a.decision.restart,a.decision.team,a.decision.spot);return true;}
 refereeRestart(kind,team,spot,taker){const a=this.referee?.pendingAdvantage;if(!a)return null;this.referee.pendingAdvantage=null;a.decision.status='recalled';this.emit('advantage-recall','Avantaj geri alındı','Oyun ilk faulün yerinden başlayacak.',null,a.decision.team);return {kind:a.decision.restart,team:a.decision.team,spot:{...a.decision.spot},taker:null};}
 refereeGoal(team){const a=this.referee.pendingAdvantage;if(!a)return true;if(team!==a.decision.team){this.recallAdvantage();return false;}a.decision.status='realized-goal';this.referee.pendingAdvantage=null;return true;}
 updateReferee(){
  const a=this.referee.pendingAdvantage;if(a){
   const controlled=this.owner?.team===a.decision.team&&dist(this.owner,this.ball)<1.6,ownFlight=this.flight?.from.team===a.decision.team;
   if(this.owner&&this.owner.team!==a.decision.team||!controlled&&!ownFlight||this.time>=a.until&&!controlled)this.recallAdvantage();
   else if((this.ball.x-a.origin.x)*this.direction(a.decision.team)>6||this.time>=a.until&&controlled){a.decision.status='realized';this.referee.pendingAdvantage=null;}
  }
  const p=this.penaltyAttempt;if(p?.state==='released'&&(this.goalPause||this.restart||this.owner&&this.owner.id!==p.takerId||this.lastTouch&&this.lastTouch.id!==p.takerId&&!(this.lastTouch.role==='GK'&&this.lastTouch.team===1-p.team)||Math.hypot(this.ball.vx,this.ball.vy,this.ball.vz)<.3&&!this.flight))p.state='settled';
 }
 planPenalty(r){
  const side=this.direction(r.team),keeper=this.team(1-r.team).find(p=>p.role==='GK'),plans=new Map();let n=0;
  if(!Number.isFinite(r.aimZ))r.aimZ=(this.random()<.5?-1:1)*(1.1+this.random()*1.2);
  if(!r.shotAim)r.shotAim=this.aimShot(r.taker,{x:side*52,z:r.aimZ},r.spot);
  const aim=r.shotAim,a=Math.atan2(aim.z,side*13),l=r.taker.kickFoot===0?-.18:.18;
  r.setupPoint={x:r.spot.x-Math.cos(a)*.88+Math.sin(a)*l,z:r.spot.z-Math.sin(a)*.88-Math.cos(a)*l};
  for(const p of this.players){if(!p.active)continue;let target;
   if(p===r.taker)target={...r.setupPoint,state:'restart',pace:1};
   else if(p===keeper)target={x:side*52,z:clamp(p.z,-3,3),state:'penalty-keeper',pace:.85};
   else if(p.referee)target={x:side*44,z:12,state:'referee',pace:1};
   else{const z=(n%2?1:-1)*(6+Math.floor(n/2)*2);n++;target={x:side*30,z,state:'penalty-wait',pace:1};}
   plans.set(p,target);
  }this.targets=plans;
 }
 penaltyReady(r){const side=this.direction(r.team),gk=this.team(1-r.team).find(p=>p.role==='GK');return !!gk&&Math.abs(gk.x-side*52)<.08&&Math.abs(gk.z)<3.4&&this.players.every(p=>!p.active||p.referee||p===r.taker||p===gk||p.x*side<=35.5&&dist(p,r.spot)>=9.15&&p.x*side<41);}
 penaltyStep(r,dt){r.clock-=dt;if(r.clock>0||!this.penaltyReady(r)||!r.setupPoint||dist(r.taker,r.setupPoint)>.035)return;
  if(this.startKick(r.taker,'shot',null,r.shotAim,23,r)){this.restart=null;this.phase='windup';}
 }
 penaltyReleased(k,flight){if(k.restartContext?.kind==='penalty'){this.penaltyAttempt={state:'released',team:k.p.team,takerId:k.p.id,releaseId:flight.id};flight.penalty=true;}}
 doTackle(p,carrier){
  const access=this.tackleAccess(p,carrier);if(!access.attempt){if(access.retry)p.tackleClock=access.retry;return;}
  const gap=dist(p,this.ball);
  const ballGap=dist(carrier,this.ball),toDefender={x:p.x-carrier.x,z:p.z-carrier.z},toBall={x:this.ball.x-carrier.x,z:this.ball.z-carrier.z};
  const shield=dot(toDefender,toBall)/(Math.hypot(toDefender.x,toDefender.z)*Math.max(.1,ballGap)||1)<-.25&&ballGap<.95;
  // The body can screen the ball; receiving it is not an invulnerability window.
  p.tackleClock=1.6+this.random()*.8;
  for(const [actor,opponent] of [[p,carrier],[carrier,p]]){const old=actor.duelMemory,repeat=old&&old.opponentId===opponent.id&&this.time-old.at<6&&dist(actor,old.origin)<5;actor.duelMemory={opponentId:opponent.id,count:repeat?old.count+1:1,at:this.time,origin:repeat?old.origin:{x:actor.x,z:actor.z}};}
  const aggression=+this.t[p.team].aggression/100,fromBehind=Math.cos(carrier.face-Math.atan2(p.z-carrier.z,p.x-carrier.x))<-.45;
  const closing=(p.vx-carrier.vx)*toBall.x+(p.vz-carrier.vz)*toBall.z;
  const clean=clamp(.62+(p.tackling-(carrier.dribbling??carrier.skill))*.004-aggression*.10-(fromBehind?.18:0)-(shield?.22:0)+clamp(((p.strength??75)-(carrier.strength??75))*.0015+((p.balance??75)-(carrier.balance??75))*.0007,-.12,.12)+Math.max(0,ballGap-.55)*.20-Math.max(0,closing-4)*.012,.16,.94);
  this.action(p,'tackle',.32);this.telemetry.duels++;
  if(this.random()<clean){
   const away=Math.atan2(p.z-carrier.z,p.x-carrier.x),sign=p.personality>.5?1:-1,a=away+sign*.55;
   this.owner=null;this.phase='open';this.flight=null;this.ball.vx=Math.cos(a)*3.7;this.ball.vz=Math.sin(a)*3.7;this.ball.vy=.22;this.lastTouch=p;p.touchClock=.10;
   if(this.kick?.p===carrier)this.kick=null;carrier.duelRecovery=.52;carrier.touchClock=.60;carrier.tackleClock=Math.max(carrier.tackleClock,1.15);p.escapeUntil=this.time+1.45;p.escapeTarget={x:clamp(p.x+Math.cos(a)*6,-49,49),z:clamp(p.z+Math.sin(a)*6,-31,31)};
   this.telemetry.looseBalls++;this.planClock=0;
  }else if(this.random()<.22+aggression*.2){
   const impact=Math.hypot(p.vx-carrier.vx,p.vz-carrier.vz),reckless=this.random()<.10+aggression*.12+(fromBehind?.16:0),serious=impact>7.5&&fromBehind&&aggression>.7;
   this.adjudicateFoul(p,carrier,{attemptedBall:!fromBehind,reckless,serious});
  }
 }
 passSpeed(kind,d,t){return kind==='through'?21:kind==='cutback'?18:kind==='long-pass'?clamp(24+d*.13,25,33):clamp(14.5+d*.12+(t.tempo-55)*.025,13,24);}
 passTime(kind,d,speed){return ['cross','long-pass','clearance','throw'].includes(kind)?BallPhysics.airTime(d,speed):BallPhysics.groundTime(d,speed);}
 threat(p,team){const x=52-p.x*this.direction(team);return Math.exp(-Math.max(0,x-6)/28)*Math.max(.15,1-Math.abs(p.z)/45);}
 captureOffside(p){const side=this.direction(p.team),line=Math.max(this.ball.x*side,this.defenceLine(p.team));return {team:p.team,fromId:p.id,releasedAt:this.time,playerIds:this.field(p.team).filter(q=>q!==p&&q.x*side>line+1e-8&&q.x*side>0).map(q=>q.id)};}
 offsideTouch(p,reason='touch'){
  const phase=this.offsidePhase||(this.flight?{team:this.flight.from?.team,playerIds:this.flight.offsidePlayers||[]}:null);
  if(!phase||phase.team!==p.team||!phase.playerIds.includes(p.id))return false;
  this.telemetry.offsides++;this.emit('offside','Ofsayt',`${p.name} ${reason==='sightline'?'kalecinin görüşünü kapattı':reason==='challenge'?'rakiple top için mücadeleye girdi':'topa dokundu'}; takım arkadaşının son temasında ofsayttaydı.`,p);
  this.setRestart('free-kick',1-p.team,{x:clamp(p.x,-52,52),z:clamp(p.z,-34,34)});if(this.restart)this.restart.indirect=true;return true;
 }
 offsideInterference(){
  const phase=this.offsidePhase;if(!phase)return false;
  for(const id of phase.playerIds){const p=this.players[id];if(!p?.active)continue;
   const challenge=this.team(1-p.team).find(q=>dist(q,p)<.7&&dist(q,this.ball)<1.2&&dist(p,this.ball)<1.1&&p.speed>.5&&this.ball.y<2);
   if(challenge&&this.offsideTouch(p,'challenge'))return true;
   const gk=this.team(1-p.team).find(q=>q.role==='GK');if(this.flight?.kind==='shot'&&gk&&dist(p,gk)<6){const h=segment(p,gk,this.ball),height=1.6+(this.ball.y-1.6)*h.u;if(h.u>.08&&h.u<.92&&h.d<.32&&height>.2&&height<1.9&&this.offsideTouch(p,'sightline'))return true;}
  }return false;
 }
 receiverInterceptPoint(p){
  const b=this.ball,margin=.7,top=Math.max(Math.hypot(p.vx,p.vz),(5.7+((p.pace??p.skill)-75)*.04)*1.13);
  let best=null,closest=null;
  const evaluate=candidate=>{
   if(candidate.read)return candidate.read;
   const future=this.projectPlayer(p,candidate.t,{x:candidate.x,z:candidate.z,state:'receive-run',pace:1.13},2.4).player;
   const gap=dist(future,candidate),ready=Math.max(p.touchClock||0,p.duelRecovery||0)<=candidate.t;
   const read={x:candidate.x,z:candidate.z,t:candidate.t,reachable:ready&&gap<=margin,gap};candidate.read=read;
   if(!best||gap<best.gap)best=read;return read;
  };
  // Test a command against the same acceleration/braking/turn limits that
  // execute it. No opponent orders, future plans or real-state writes.
  for(let i=1;i<=24;i++){
   const t=i*.1,ball=BallPhysics.predict(b,t);if(Math.abs(ball.x)>52||Math.abs(ball.z)>34)break;
   const candidate={x:ball.x,z:ball.z,t,range:dist(p,ball)};
   if(!closest||candidate.range<closest.range)closest=candidate;
   // Loose speed bound only prunes impossible candidates; it never proves reach.
   if(candidate.range>margin+top*t)continue;
   const read=evaluate(candidate);if(read.reachable)return read;
  }
  if(closest)evaluate(closest);
  // If no sample meets the planning margin, use the closest tested approach.
  // This does not prove the real swept contact is impossible or assured.
  return best||{x:clamp(b.x,-52.5,52.5),z:clamp(b.z,-34.3,34.3),t:0,reachable:false,gap:dist(p,b)};
 }
 interceptPoint(p){
  const f=this.flight,b=this.ball;
  if(!this.restart&&!this.kick?.restartContext&&p.active&&p.role!=='GK'&&f?.target===p&&f.from?.team===p.team&&['pass','cutback'].includes(f.kind)&&b.y<=BallPhysics.radius+.01&&Math.abs(b.vy)<1e-6)return this.receiverInterceptPoint(p);
  const top=5.35+((p.pace??80)-75)*.035;let q={x:b.x,y:b.y,z:b.z,vx:b.vx,vy:b.vy,vz:b.vz},result={x:b.x,z:b.z,t:0};for(let i=1;i<=24;i++){BallPhysics.step(q,.1);const t=i*.1;result={x:clamp(q.x,-52.5,52.5),z:clamp(q.z,-34.3,34.3),t};if(q.y<1.1&&dist(p,result)<.7+top*t)return result;}return result;
 }
 teamRole(p){
  if(p.role==='GK')return 'keeper';
  if(p.role==='DEF')return Math.abs(p.homeZ)>20?'fullback':'centre-back';
  if(p.role==='ATT')return Math.abs(p.homeZ)>14?'winger':'striker';
  if(Math.abs(p.homeZ)>20)return 'wide-midfielder';
  const deepest=this.field(p.team).filter(q=>q.role==='MID').sort((a,b)=>a.homeX*this.direction(p.team)-b.homeX*this.direction(p.team))[0];
  return deepest===p?'anchor':p.homeX*this.direction(p.team)>7?'playmaker':'central-midfielder';
 }
 arrivalHelper(p,owner){
  const plan=this.supportPlans[p.team];
  return !!owner&&plan?.ownerId===owner.id&&plan.epoch===this.attackEpoch[p.team]&&plan.handoffUntil>this.time&&plan.points.has(p.id);
 }
 coordinatedAttack(team,owner,line){
  if(!owner)return null;
  const side=this.direction(team),zone=Math.abs(owner.z)>15?Math.sign(owner.z):0,old=this.attackPlans[team];
  if(old&&old.until>this.time&&old.zone===zone&&old.ownerTeam===this.lastTeam&&old.epoch===this.attackEpoch[team]&&old.runner?.id!==owner.id&&old.connectorId!==owner.id&&![old.runner?.id,old.connectorId].some(id=>this.players.some(p=>p.id===id&&this.arrivalHelper(p,owner)))&&(!old.runner||this.players.some(q=>q.id===old.runner.id&&q.active)))return old;
  const pool=this.field(team),opponents=this.rivals(owner),ballDepth=this.ball.x*side,counter=this.transitionUntil[team]>this.time&&this.t[team].onWin==='counter';
  const candidates=pool.filter(p=>p!==owner&&!this.taskReserved(p,['penetration'])&&!this.arrivalHelper(p,owner)&&!(p.supportIntent?.until>this.time)&&!(p.runIntent?.until>this.time)&&(p.role==='ATT'||p.role==='MID'&&p.homeX*side>7)&&p.x*side>owner.x*side-3);
  let runner=null;
  for(const p of candidates){
   const channels=this.t[team].width==='wide'&&Math.abs(p.homeZ)>18?[p.homeZ*1.05,p.homeZ*.85]:[p.homeZ*.65,p.homeZ>=0?12:-12,p.homeZ>=0?-10:10];
   for(const z of channels){
    const point={x:side*Math.min(line-.75,ballDepth+(counter?27:19)),z:clamp(z,-25,25)},space=Math.min(15,...opponents.map(q=>dist({x:q.x+q.vx*.6,z:q.z+q.vz*.6},point)));
    const score=space*.9+(p.pace??80)*.035-dist(p,point)*.08-Math.abs(z-p.z)*.06;
    if(!runner||score>runner.score)runner={id:p.id,point,score};
   }
  }
  if(ballDepth<-12&&!counter||ballDepth>31)runner=null;
  const links=pool.filter(p=>p!==owner&&!this.taskReserved(p,['between-lines'])&&!this.arrivalHelper(p,owner)&&p.id!==runner?.id&&p.role!=='DEF'&&p.role!=='GK'&&this.teamRole(p)!=='anchor'&&!(p.supportIntent?.until>this.time)&&!(p.runIntent?.until>this.time)),centralLinks=links.filter(p=>p.role==='MID'&&Math.abs(p.homeZ)<19);
  const connector=(centralLinks.length?centralLinks:links).sort((a,b)=>(Math.abs(a.x*side-(ballDepth+7))+Math.abs(a.z-owner.z)*.25)-(Math.abs(b.x*side-(ballDepth+7))+Math.abs(b.z-owner.z)*.25))[0];
  const result={ownerTeam:this.lastTeam,epoch:this.attackEpoch[team],zone,until:this.time+2.6,runner,connectorId:connector?.id};
  this.attackPlans[team]=result;
  if(runner)this.telemetry.coordinatedRuns=(this.telemetry.coordinatedRuns||0)+1;
  return result;
 }
 supportRead(owner,p,point,opponents=this.rivals(owner)){
  const travel=dist(p,point),range=dist(owner,point),top=Math.max(3.5,(5.7+((p.pace??p.skill)-75)*.04)*.94),along=travel>.01?((point.x-p.x)*p.vx+(point.z-p.z)*p.vz)/travel:0;
  const eta=travel>.16?travel/top+Math.max(0,top-along)/15.6:0;
  const pressure=Math.min(18,...opponents.map(q=>dist(q,owner))),lead=clamp(owner.supportLead||0,0,1.2),window=clamp(pressure/5.8+.25,.5,2.2)+lead,urgency=clamp((6-pressure)/4,0,1);
  // Preview acceleration, turning and braking at the pressure deadline.
  // A shorter destination alone does not guarantee an earlier open lane.
  const early={x:p.x,z:p.z};let vx=p.vx,vz=p.vz,face=p.face;
  const lane=q=>this.laneRisk(owner,q,this.passSpeed('pass',dist(owner,q),this.t[owner.team]));
  let earlyRisk=lane(early),readyAt=earlyRisk<.35?0:null;
  const horizon=urgency>0?Math.min(2.4,window+.9):0;
  for(let time=0;time<horizon-1e-7;){
   const dt=Math.min(.1,horizon-time),dx=point.x-early.x,dz=point.z-early.z,d=Math.hypot(dx,dz),turn=Math.abs(angle(Math.atan2(dz,dx),face));
   const wanted=d>.16?Math.min(top,d*2,Math.sqrt(16*d))*(1-.45*turn/Math.PI):0,tx=d?dx/d*wanted:0,tz=d?dz/d*wanted:0;
   const change=Math.hypot(tx-vx,tz-vz)||1,acc=(wanted<Math.hypot(vx,vz)?11:7.8)*dt;
   vx+=(tx-vx)*Math.min(1,acc/change);vz+=(tz-vz)*Math.min(1,acc/change);early.x+=vx*dt;early.z+=vz*dt;
   const facing=Math.hypot(vx,vz)<2.8?Math.atan2(owner.z-early.z,owner.x-early.x):Math.atan2(vz,vx);face+=clamp(angle(facing,face),-dt*4.5,dt*4.5);time+=dt;
   const risk=lane(early);if(time<=window+.1)earlyRisk=risk;
   if(readyAt===null&&risk<.35)readyAt=time;
   if(time>=window&&readyAt!==null)break;
  }
  const space=Math.min(12,...opponents.map(q=>dist({x:q.x+q.vx*Math.min(eta,.8)*.5,z:q.z+q.vz*Math.min(eta,.8)*.5},point)));
  return {travel,eta,space,window,urgency,risk:this.laneRisk(owner,point,this.passSpeed('pass',range,this.t[owner.team])),earlyRisk,readyAt:readyAt??horizon+.2};
 }
 supportTargets(owner,supporters,reserved=new Map(),line=Math.max(this.observedLine(owner),this.ball.x*this.direction(owner.team))){
  const result=new Map(),side=this.direction(owner.team),t=this.t[owner.team],opponents=this.rivals(owner),radius=t.passing==='short'?8.5:11.5;
  for(let rank=0;rank<supporters.length;rank++){
   const p=supporters[rank],preferred=rank===0?(p.homeZ>=owner.z?1:-1):-(supporters[0].homeZ>=owner.z?1:-1);
   const evaluate=point=>{
    const range=dist(owner,point),travel=dist(p,point);
    if(range<5.2||range>26||travel>13||point.x*side>line-.7||Math.abs(point.x)>48||Math.abs(point.z)>30)return null;
    if([...result.values()].some(q=>dist(q,point)<6.3)||[...reserved.values()].some(q=>dist(q,point)<3.2))return null;
    const read=this.supportRead(owner,p,point,opponents),{space,risk}=read;
    if(space<1.3)return null;
    const advance=(point.x-owner.x)*side,crowd=[...result.values()].reduce((n,q)=>n+Math.max(0,8-dist(q,point)),0);
    const score=space*.55-risk*13-travel*.22-Math.abs(point.z-p.homeZ)*.035+(rank===1?advance*.17:-Math.max(0,advance-4)*.10)+(Math.sign(point.z-owner.z)===preferred?.65:0)-crowd-Math.max(0,read.eta-read.window)*2-Math.max(0,read.readyAt-read.window)*read.urgency*16-read.earlyRisk*read.urgency*8;
    return {x:point.x,z:point.z,score,risk,space};
   };
   const candidates=[{x:p.x,z:p.z}];
   // Local sideways movements let a marked receiver leave the pass shadow
   // without first running to a distant formation-relative destination.
   for(const lateral of [-5,-3,3,5])for(const forward of [-1.5,0,1.5])candidates.push({x:p.x+side*forward,z:p.z+lateral});
   for(const forward of (rank===0?[-7,-3,2]:[7,3,-3]))for(const lateral of [preferred*radius,-preferred*radius,preferred*radius*.65])candidates.push({x:owner.x+side*forward,z:owner.z+lateral});
   let best=null;for(const point of candidates){const q=evaluate(point);if(q&&(!best||q.score>best.score))best=q;}
   const intent=p.offerIntent,old=intent?.ownerId===owner.id&&intent.epoch===this.attackEpoch[owner.team]&&(!intent.origin||dist(intent.origin,owner)<6)?evaluate(intent.point):null;
   // Continuity never preserves a newly blocked lane or a crowded endpoint.
   let pending=null;
   if(old&&old.risk<.55&&old.space>1.8){
    if(!best||old.score>best.score-1.7||dist(p,old)<1&&old.risk<.25&&old.space>2.4)best=old;
    else if(dist(best,old)>2){
     const since=intent.pending&&dist(intent.pending,best)<1.5?intent.pending.since:this.time;
     if(this.time-since<.32-1e-7){pending={x:best.x,z:best.z,since};best=old;}
    }
   }
   if(best){result.set(p.id,best);const same=old&&dist(best,intent.point)<.1;p.offerIntent={ownerId:owner.id,epoch:this.attackEpoch[owner.team],point:{x:best.x,z:best.z},origin:same?intent.origin||{x:owner.x,z:owner.z}:{x:owner.x,z:owner.z},pending,until:this.time+1.2};}
   else p.offerIntent=null;
  }
  return result;
 }
 connectionPoint(owner,p,baseLine,line){
  const side=this.direction(owner.team),depth=Math.min(line-1.0,Math.max(owner.x*side+6,baseLine+27)),ideal=clamp(owner.z*.4+Math.sign(p.homeZ||-owner.z||1)*9,-18,18);let best=null;
  const evaluate=point=>{const risk=this.laneRisk(owner,point,17),space=Math.min(12,...this.rivals(owner).map(q=>dist(q,point))),score=space*.5-risk*11-dist(p,point)*.16-Math.abs(point.z-ideal)*.035;return {...point,score,risk,space};};
  for(const z of [ideal,ideal-4,ideal+4,clamp(p.z,-20,20)]){const point=evaluate({x:side*depth,z:clamp(z,-22,22)});if(!best||point.score>best.score)best=point;}
  const intent=p.connectionIntent,old=intent?.ownerId===owner.id&&intent.epoch===this.attackEpoch[owner.team]&&intent.until>this.time&&(intent.point.x-owner.x)*side>3&&intent.point.x*side<line-.7?evaluate(intent.point):null;
  if(old&&old.risk<.55&&old.space>1.8&&old.score>best.score-1.5)best=old;
  const same=old&&dist(old,best)<.1;p.connectionIntent={ownerId:owner.id,epoch:this.attackEpoch[owner.team],point:{x:best.x,z:best.z},until:same?intent.until:this.time+1.4};return best;
 }
 supportUnit(team,owner,pool,holding,build,pattern,flank,box,line,connection=null,meeting=null){
  const old=this.supportPlans[team],flight=this.flight;
  const reserved=new Map(box?.points||[]);
  if(build)reserved.set(build.id,build.point);
  if(pattern?.runner)reserved.set(pattern.runner.id,pattern.runner.point);
  if(connection)reserved.set(pattern.connectorId,connection);
  if(flank)reserved.set(flank.fullbackId,flank.point);
  for(const p of pool){if(p.runIntent?.until>this.time)reserved.set(p.id,p.runIntent.point);else if(p.supportIntent?.until>this.time&&p.supportIntent.epoch===this.attackEpoch[team])reserved.set(p.id,p.supportIntent.point);}
  let arrival=null;
  if(!owner){
   const target=flight?.target;
   const abandon=()=>{for(const p of pool)if(old?.arrival&&p.offerIntent?.ownerId===old.ownerId)p.offerIntent=null;this.supportPlans[team]=null;return new Map();};
   if(flight?.from.team!==team||!target?.active||target.team!==team||flight.age>2.4||!['pass','through','cutback','long-pass'].includes(flight.kind)){
    return abandon();
   }
   const meet=meeting||this.interceptPoint(target);
   // This is an observed-ball arrival estimate, not early possession. Helpers
   // move normally while the receiver still has to earn the actual contact.
   if(meet.t>1.2||dist(target,meet)>8||this.ball.y>3)return abandon();
   arrival={flightId:flight.id,lead:meet.t};
   owner={...target,x:meet.x,z:meet.z,supportLead:meet.t};
   if(old?.arrival&&old.ownerId!==owner.id)for(const p of pool)if(p.offerIntent?.ownerId===old.ownerId)p.offerIntent=null;
  }
  const pressure=Math.min(20,...this.rivals(owner).map(q=>dist(owner,q)));
  const eligible=pool.filter(p=>p.id!==owner.id&&p.duelRecovery<=0&&!this.taskReserved(p,['support'])&&!reserved.has(p.id)&&(p.role!=='ATT'||pressure<5.5&&this.teamRole(p)==='winger'&&dist(p,owner)<24)&&(p!==holding||owner.x*this.direction(team)<0)&&(p.role!=='DEF'||Math.abs(p.homeZ)>19&&this.t[team].fullbacks!=='hold')&&!(p.role==='DEF'&&owner.x*this.direction(team)>0&&p.homeZ*owner.z<0)&&dist(p,owner)<32);
  const incumbent=id=>old?.ownerId===owner.id&&old.epoch===this.attackEpoch[team]&&old.points.has(id);
  // Choose helpers by a reachable open angle, not just their distance. Keep
  // the anchor/runner/overlap reservations above even under pressure.
  const costs=new Map(eligible.map(p=>{
   let best=Infinity;const rivals=this.rivals(owner);
   for(const dz of [0,-3,3,-5,5]){
    const q={x:p.x,z:p.z+dz},range=dist(owner,q);if(range<5.2||range>26||q.x*this.direction(team)>line-.7||Math.abs(q.z)>30||[...reserved.values()].some(a=>dist(a,q)<3.2))continue;
    const risk=this.laneRisk(owner,q,this.passSpeed('pass',range,this.t[team])),space=Math.min(12,...rivals.map(a=>dist(a,q)));
    best=Math.min(best,risk*11+Math.max(0,2.4-space)*4+Math.abs(dz)*.5+range*.12-(dz===0&&risk<.25&&space>2.4?1.5:0));
   }
   return [p,best-(incumbent(p.id)?2.0:0)];
  }));
  eligible.sort((a,b)=>costs.get(a)-costs.get(b)||dist(a,owner)-dist(b,owner));
  const points=this.supportTargets(owner,eligible.slice(0,2),reserved,line);
  for(const p of pool)if(!points.has(p.id)&&p.offerIntent?.ownerId===owner.id)p.offerIntent=null;
  if(arrival){
   this.telemetry.arrivalSupportSamples=(this.telemetry.arrivalSupportSamples||0)+1;
   if(old?.arrival?.flightId!==arrival.flightId)this.telemetry.arrivalSupportPlans=(this.telemetry.arrivalSupportPlans||0)+1;
  }else if(old?.arrival&&old.ownerId===owner.id&&old.epoch===this.attackEpoch[team])this.telemetry.arrivalSupportHandoffs=(this.telemetry.arrivalSupportHandoffs||0)+1;
  const handoffUntil=arrival?this.time+1.2:old?.ownerId===owner.id&&old.epoch===this.attackEpoch[team]?old.handoffUntil||0:0;
  this.supportPlans[team]={ownerId:owner.id,epoch:this.attackEpoch[team],until:this.time+1.3,arrival,handoffUntil,points};return points;
 }
 flankSupport(team,owner,line){
  const t=this.t[team],flight=this.flight?.from.team===team?this.flight:null,source=owner?.team===team?owner:flight?.from,side=this.direction(team);
  if(t.fullbacks!=='overlap'||!source||source.role==='DEF'||source.role==='GK'||Math.abs(source.z)<12||source.x*side<-10){this.flankPlans[team]=null;return null;}
  const flank=Math.sign(source.z),pool=this.field(team),old=this.flankPlans[team];
  const fullback=pool.filter(p=>!this.taskReserved(p,['overlap','wide-support'])&&!this.arrivalHelper(p,owner)&&this.teamRole(p)==='fullback'&&p.homeZ*flank>0).sort((a,b)=>dist(a,source)-dist(b,source))[0];
  if(!fullback){this.flankPlans[team]=null;return null;}
  const safePoint=point=>({x:side*Math.min(point.x*side,line-.75),z:point.z});
  const inFlight=flight?.from.id===source.id;
  if(old&&old.epoch===this.attackEpoch[team]&&old.sourceId===source.id&&old.fullbackId===fullback.id&&(old.until>this.time||inFlight&&flight.age<3.5)&&(inFlight||dist(old.origin,source)<6)){
   const point=safePoint(old.point),blocked=this.rivals(source).some(q=>dist(q,point)<1.4);
   if(!blocked)return this.flankPlans[team]={...old,point};
   return this.flankPlans[team]={...old,point:safePoint({x:old.origin.x-side*5,z:flank*22}),state:'wide-support',until:this.time+.8};
  }
  let point=safePoint({x:side*Math.min(44,source.x*side+8),z:Math.sign(fullback.homeZ)*Math.min(31,Math.abs(fullback.homeZ)*1.12)}),state='overlap';
  if(this.rivals(source).some(q=>dist(q,point)<1.4)){point=safePoint({x:source.x-side*5,z:flank*22});state='wide-support';}
  return this.flankPlans[team]={sourceId:source.id,fullbackId:fullback.id,epoch:this.attackEpoch[team],origin:{x:source.x,z:source.z},point,state,until:this.time+3.2};
 }
 buildOutSupport(team,owner){
  const side=this.direction(team);if(!owner||owner.team!==team||this.ball.x*side>-8)return null;
  const old=this.buildPlans[team];
  const pool=this.field(team).filter(p=>p!==owner&&!this.taskReserved(p,['build-support'])&&!this.arrivalHelper(p,owner)&&p.role==='MID'&&Math.abs(p.homeZ)<19);
  const depth=clamp(this.ball.x*side+12,-34,-2),opponents=this.rivals(owner);let best=null;
  const evaluate=(p,point)=>{
   const advance=(point.x-owner.x)*side,range=dist(owner,point);if(advance<6||advance>15.5||range>26||Math.abs(point.z)>22||dist(p,point)>16)return null;
   const read=this.supportRead(owner,p,point,opponents);if(read.space<1.5)return null;
   const score=read.space*.65-read.risk*12-read.travel*.23-Math.abs(point.z-owner.z*.32)*.12-Math.abs(advance-11)*.12-Math.max(0,read.eta-read.window)*2-Math.max(0,read.readyAt-read.window)*read.urgency*16-read.earlyRisk*read.urgency*8;
   return {id:p.id,point:{x:point.x,z:point.z},score,risk:read.risk,space:read.space};
  };
  for(const p of pool){
   const candidates=[{x:p.x,z:p.z},...[-11,-6,6,11].map(z=>({x:side*depth,z}))];
   for(const lateral of [-5,-3,3,5])for(const forward of [-1.5,1.5])candidates.push({x:p.x+side*forward,z:p.z+lateral});
   for(const point of candidates){const q=evaluate(p,point);if(q&&(!best||q.score>best.score))best=q;}
  }
  const incumbent=old?.owner===owner.id&&old.epoch===this.attackEpoch[team]&&old.until>this.time&&dist(old.ball,this.ball)<5?this.players[old.id]:null;
  const retained=incumbent?.active&&incumbent!==owner&&!this.arrivalHelper(incumbent,owner)?evaluate(incumbent,old.point):null;
  if(retained&&retained.risk<.55&&retained.space>1.8&&(!best||retained.score>best.score-1.7))best=retained;
  if(!best){this.buildPlans[team]=null;return null;}
  const same=retained&&best.id===old.id&&dist(best.point,old.point)<.1;
  return this.buildPlans[team]={...best,owner:owner.id,epoch:this.attackEpoch[team],until:same?old.until:this.time+1.4,ball:same?old.ball:{x:this.ball.x,z:this.ball.z}};
 }
 boxAttack(team,owner){
  const flight=this.flight,delivery=flight&&flight.from.team===team&&['cross','cutback'].includes(flight.kind);
  const source=owner?.team===team?owner:delivery?flight.from:null,side=this.direction(team);
  if(!source||source.x*side<23||Math.abs(source.z)<14){this.boxPlans[team]=null;return null;}
  const flank=Math.sign(source.z),old=this.boxPlans[team];
  if(old&&old.source===source.id&&old.flank===flank&&old.epoch===this.attackEpoch[team]&&old.until>this.time&&[...old.points.keys()].every(id=>this.players.some(p=>p.id===id&&p.active&&!this.arrivalHelper(p,owner))))return old;
  const pool=this.field(team).filter(p=>p!==source&&!this.taskReserved(p,['box-run','cutback-support'])&&!(p.runIntent?.until>this.time)&&!(p.supportIntent?.until>this.time)&&!this.arrivalHelper(p,owner)),attackers=pool.filter(p=>p.role==='ATT');
  const near=attackers.slice().sort((a,b)=>Math.abs(a.homeZ)-Math.abs(b.homeZ))[0];
  const wide=pool.filter(p=>p!==near&&(p.role==='ATT'||['winger','wide-midfielder'].includes(this.teamRole(p))));
  const far=wide.sort((a,b)=>(a.homeZ*flank<0?0:30)+Math.abs(a.homeZ+flank*15)*.2-((b.homeZ*flank<0?0:30)+Math.abs(b.homeZ+flank*15)*.2))[0];
  const edge=pool.filter(p=>p!==near&&p!==far&&p.role==='MID'&&Math.abs(p.homeZ)<19&&this.teamRole(p)!=='anchor').sort((a,b)=>dist(a,{x:side*33,z:0})-dist(b,{x:side*33,z:0}))[0];
  const points=new Map();
  if(near)points.set(near.id,{x:side*clamp(source.x*side+6,40,44),z:flank*3.5,state:'box-run',role:'near-post'});
  if(far)points.set(far.id,{x:side*clamp(source.x*side+8,42,46),z:-flank*7,state:'box-run',role:'far-post'});
  if(edge)points.set(edge.id,{x:side*clamp(source.x*side-4,30,35),z:-flank*1.5,state:'cutback-support',role:'edge'});
  return this.boxPlans[team]={source:source.id,flank,epoch:this.attackEpoch[team],until:this.time+3.4,points};
 }
 selectPress(team,owner,pool){
  const ball=this.ball,side=this.direction(team),depth=ball.x*side;
  const bypassed=p=>owner?.team!==team&&(p.x-ball.x)*side>2.5&&this.rivals(p).find(q=>q.id===owner?.id)?.vx*side<-1.5&&dist(p,ball)>4;
  const cost=p=>dist(p,ball)/Math.max(3.5,5.7+((p.pace??80)-75)*.04)+(p.role==='DEF'&&Math.abs(p.homeZ)<20&&depth>-25?4:0)+(p.role==='DEF'&&Math.abs(ball.z)<12&&depth>-20?1.2:0)+(p.role==='DEF'&&Math.abs(p.homeZ)<20&&Math.abs(ball.z)>17&&dist(p,ball)>4?2:0)+(p.duelRecovery>0?3:0)+((p.energy??1)<.5?1.6:0)+(bypassed(p)?3:0);
  const available=owner&&owner.team!==team?pool.filter(p=>p.duelRecovery<=0&&!bypassed(p)):pool;
  const order=available.slice().sort((a,b)=>cost(a)-cost(b)),candidate=order[0],old=this.pressAssignments[team];
  if(!owner||owner.team===team){this.pressAssignments[team]=null;return {presser:candidate,cover:order[1]};}
  const same=old?.ownerId===owner.id&&old.epoch===this.attackEpoch[owner.team],valid=same&&pool.includes(old.player)&&old.player.duelRecovery<=0&&!bypassed(old.player);
  let presser=candidate,reason=valid?'continue':same?'unavailable':'new-owner',challengerId=null,challengerSince=null;
  if(valid){
   presser=old.player;
   if(candidate&&candidate!==presser){
    const advantage=cost(presser)-cost(candidate),urgent=dist(candidate,ball)<2.3&&dist(presser,ball)>4.8;
    if(advantage>.65){challengerId=candidate.id;challengerSince=old.challengerId===candidate.id?old.challengerSince:this.time;}
    // A clear emergency is handed over immediately. Otherwise a materially
    // better arrival must persist across observations, not just a near tie.
    if(urgent||advantage>1.8||challengerId!==null&&this.time-challengerSince>=.32-1e-7){presser=candidate;reason=urgent?'immediate-threat':'arrival-advantage';challengerId=challengerSince=null;}
   }
  }
  let cover=order.find(p=>p!==presser&&p.duelRecovery<=0);
  const previous=same&&old.player===presser?old.cover:null;
  if(previous?.active&&available.includes(previous)&&previous!==presser&&previous.duelRecovery<=0&&cover&&cost(previous)<cost(cover)+.75)cover=previous;
  this.pressAssignments[team]={player:presser,cover,ownerId:owner.id,epoch:this.attackEpoch[owner.team],since:valid&&old.player===presser?old.since:this.time,reason,challengerId,challengerSince};
  return {presser,cover};
 }
 pressPolicy(team,presser,cover,owner){
  if(!presser)return {active:false,reason:'no-presser'};
  const t=this.t[team],side=this.direction(team),ball=this.ball,distance=dist(presser,ball),depth=ball.x*side;
  const engage=(t.press<=40?(depth<0?12:4):t.press>=75?22:16)*(.7+.3*(presser.energy??1));
  if(!owner){
   if(!this.flight)return {active:true,reason:'loose-ball',engage};
   if(this.flight.kind==='shot'||this.flight.kind==='cross'&&ball.y>1.2)return {active:false,reason:'protect-box',engage};
   const point=this.interceptPoint(presser),speed=5.7+((presser.pace??presser.skill)-75)*.04;
   return {active:distance<engage+3&&dist(presser,point)<speed*Math.max(.1,point.t)+1.0,reason:'pass-interception',engage};
  }
  if(owner.team===team)return {active:false,reason:'in-possession',engage};
  const observed=this.rivals(presser).find(q=>q.id===owner.id),read=observed||{x:ball.x,z:ball.z,vx:0,vz:0,face:0,team:owner.team,speed:3,receiveClock:0};
  const bypassed=(presser.x-ball.x)*side>2.5&&read.vx*side<-1.5&&distance>4;
  if(bypassed)return {active:false,reason:'bypassed',engage};
  const support=this.field(team).filter(p=>p!==presser&&p.duelRecovery<=0&&(p.x-read.x)*side<1&&dist(p,presser)<17);
  const heavy=!!observed&&dist(read,ball)>1.1,closed=!!observed&&Math.cos(read.face)*this.direction(owner.team)<-.25;
  const trigger=read.receiveClock>.08||heavy||closed||Math.abs(ball.z)>24||read.speed<1.5;
  const immediate=distance<Math.min(5.5,engage),danger=depth<-30&&distance<15;
  const counter=this.lossUntil[team]>this.time&&t.onLoss==='counterpress'&&distance<12&&support.some(p=>dist(p,ball)<12);
  const active=immediate||danger||support.length>0&&(distance<engage||trigger&&distance<engage+3)||counter;
  return {active,reason:active?(counter?'counterpress':trigger?'trigger':'connected'):'disconnected',engage,trigger,support:support.length};
 }
 pressUnit(team,owner,presser,cover,unit,policy){
  if(!owner||owner.team===team||!presser||!policy.active){this.pressUnits[team]=null;return null;}
  const side=this.direction(team),ball=this.ball,old=this.pressUnits[team],marked=new Set([...unit.assignments.values()].map(q=>q.id));
  const observed=cover?this.rivals(cover):this.rivals(presser),origin=observed.find(q=>q.id===owner.id)||ball;
  let best=null;
  for(const q of observed){
   const range=dist(origin,q),progress=(origin.x-q.x)*side;if(q.id===owner.id||range<4||range>25||progress<-.5)continue;
   const clearance=Math.min(10,...this.field(team).filter(p=>p!==presser&&p!==cover).map(p=>dist(p,q)));
   const score=progress*.28+Math.max(0,16-Math.abs(q.z))*.15+clearance*.22-range*.07-(marked.has(q.id)?2.0:0);
   if(!best||score>best.score)best={q,score};
  }
  const previous=old?.ownerId===owner.id&&old.epoch===this.attackEpoch[owner.team]&&old.until>this.time?observed.find(q=>q.id===old.receiverId):null;
  if(previous?.active&&previous.team!==team&&dist(previous,origin)<25&&(origin.x-previous.x)*side>=-.5){
   const range=dist(origin,previous),clearance=Math.min(10,...this.field(team).filter(p=>p!==presser&&p!==cover).map(p=>dist(p,previous)));
   const score=(origin.x-previous.x)*side*.28+Math.max(0,16-Math.abs(previous.z))*.15+clearance*.22-range*.07-(marked.has(previous.id)?2:0);
   if(!best||score>best.score-1.8)best={q:previous,score};
  }
  const receiver=best?.q,depth=clamp(4.3+(ball.x*side+20)*.035,3.5,5.5),range=receiver?dist(ball,receiver):1;
  let coverPoint=receiver&&range>depth+1?{x:ball.x+(receiver.x-ball.x)*depth/range,z:ball.z+(receiver.z-ball.z)*depth/range}:{x:ball.x-side*depth,z:ball.z*.62};
  coverPoint.x=side*Math.min(coverPoint.x*side,ball.x*side-1.2);
  const central=receiver?{x:receiver.x-ball.x,z:receiver.z-ball.z}:{x:-side*4,z:-ball.z*.5},length=Math.hypot(central.x,central.z)||1;
  // The presser closes from the inside of the dangerous passing lane. The
  // second defender screens that lane instead of joining the same tackle.
  const gap=dist(presser,ball),offset=gap>3?Math.min(2.0,.7+(gap-3)*.15):.65;
  const pressPoint={x:ball.x+central.x/length*offset,z:ball.z+central.z/length*offset};
  const result={ownerId:owner.id,epoch:this.attackEpoch[owner.team],presserId:presser.id,coverId:cover?.id,receiverId:receiver?.id,pressPoint,coverPoint,until:previous?.id===receiver?.id&&previous?old.until:this.time+1.1};
  this.pressUnits[team]=result;return result;
 }
 defensiveUnit(team,owner,baseLine,pool,opponents,presser,cover){
  const side=this.direction(team),ball=this.ball,t=this.t[team],aBall=ball.x*side,defenders=pool.filter(p=>p.role==='DEF');
  const knownOwner=owner&&(opponents.find(q=>q.id===owner.id)||{x:ball.x,z:ball.z});
  const pressure=knownOwner?Math.min(30,...pool.map(p=>dist(p,knownOwner))):30;
  const runners=opponents.filter(q=>q.id!==owner?.id&&q.role!=='GK'&&q.x*side<baseLine+13&&q.vx*side<-1.2);
  // With an unpressured passer, protect the space behind before a pass is hit.
  let line=baseLine-(pressure>3.2&&runners.length&&aBall<12?Math.min(4,1.2+runners.length):0);
  const old=this.defensiveUnits[team];
  if(old&&this.time-old.at<.4&&line>old.line)line=Math.min(line,old.line+.55);
  line=clamp(line,-48.5,13);
  const goalSide=pool.filter(p=>(p.x-ball.x)*side<-1).length,mids=pool.filter(p=>p.role==='MID'),central=defenders.filter(p=>Math.abs(p.homeZ)<20),core=central.length>=2?central:defenders;
  const median=values=>{values=values.slice().sort((a,b)=>a-b);return values.length?(values[(values.length-1)>>1]+values[values.length>>1])/2:null;};
  const actualLine=median(core.map(p=>p.x*side)),actualMid=median(mids.map(p=>p.x*side)),actualGap=actualLine!==null&&actualMid!==null?actualMid-actualLine:null;
  const connected=goalSide>=Math.min(6,pool.length)&&core.filter(p=>(p.x-ball.x)*side<-1).length>=Math.min(2,core.length)&&mids.filter(p=>(p.x-ball.x)*side<-1).length>=Math.min(2,mids.length)&&(actualGap===null||actualGap>=-6&&actualGap<=18);
  const recoveryToken=this.recoveryUntil[team],sameRecovery=old?.recoveryToken===recoveryToken&&old.opponentEpoch===this.attackEpoch[1-team];
  const recoveryStableAt=connected?(sameRecovery&&old.recoveryStableAt!==null?old.recoveryStableAt:this.time):null;
  // Counted bodies behind the ball can still leave two disconnected lines.
  // Finish the return only after the actual block has settled, and let an
  // unfinished return continue past the initial eight-second instruction.
  const recoveryActive=recoveryToken>0&&(recoveryToken>this.time||sameRecovery&&old.recovering),recovering=recoveryActive&&!(connected&&this.time-recoveryStableAt>=.4-1e-7);
  // A centre-back covers a direct threat; a midfielder covers a distant press.
  if(cover?.role==='DEF'&&aBall>-29){const mid=pool.filter(p=>p!==presser&&p.role==='MID').sort((a,b)=>dist(a,ball)-dist(b,ball))[0];if(mid&&dist(mid,ball)<dist(cover,ball)+10)cover=mid;}
  // In midfield the cover player owns the passing lane. Deep box runners
  // retain priority over that reservation when the ball reaches danger.
  const reserveCover=!!presser&&aBall>-28&&cover&&cover.role!=='DEF';
  const free=pool.filter(p=>p!==presser&&(!reserveCover||p!==cover)),assignments=new Map();
  const danger=opponents.filter(q=>q.id!==owner?.id&&q.role!=='GK'&&(q.role==='ATT'||q.x*side<line+19)).sort((a,b)=>(a.x-b.x)*side);
  const previous=old&&this.time-old.at<.4&&old.opponentEpoch===this.attackEpoch[1-team]?old.assignments:null;
  const views=new Map(pool.map(p=>[p,new Map(this.rivals(p).map(q=>[q.id,q]))])),seen=(p,q)=>this._perceptionActive?views.get(p)?.get(q.id):q;
  const eligible=(p,target)=>{const q=seen(p,target);return !!q&&(t.marking==='man'||p.role==='DEF'||p.role==='MID'&&aBall<-20&&q.x*side<-14)&&Math.abs(p.homeZ-q.z)<(t.marking==='man'?40:26)&&(t.marking==='man'||dist(p,q)<18&&q.x*side<line+19);};
  const cost=(p,target)=>{const q=seen(p,target);return q?dist(p,q)+Math.abs(p.homeZ-q.z)*.22+(p.role==='MID'&&q.role==='ATT'?2:0)+(p===cover?.8:0)-(previous?.get(p)?.id===q.id?(t.marking==='man'?3.4:2.2):0):Infinity;};
  for(const q of danger){
   const marker=free.filter(p=>!assignments.has(p)&&eligible(p,q)).sort((a,b)=>cost(a,q)-cost(b,q))[0];
   if(marker)assignments.set(marker,seen(marker,q));
  }
  // Pairwise exchanges let crossing runners be handed over as a unit, rather
  // than two nearest-player decisions repeatedly exchanging the same men.
  const pairs=[...assignments];
  for(let i=0;i<pairs.length;i++)for(let j=i+1;j<pairs.length;j++){
   const a=pairs[i][0],b=pairs[j][0],qa=assignments.get(a),qb=assignments.get(b);
   if(eligible(a,qb)&&eligible(b,qa)&&cost(a,qb)+cost(b,qa)+1.8<cost(a,qa)+cost(b,qb)){assignments.set(a,seen(a,qb));assignments.set(b,seen(b,qa));}
  }
  const cutbackScreeners=new Set(),heldMarkers=new Set(),observedPath=this.flight?BallPhysics.predict(ball,.7):null;
  for(const [p,q] of [...assignments]){
   // A distant central return pass is the midfield's next responsibility.
   // A ball already travelling toward this runner delays the handoff. Its
   // visible trajectory supplies that cue, never the passer's private target.
   const path=observedPath&&segment(q,ball,observedPath),incoming=path&&path.u>0&&path.d<2.5;
   const distant=t.marking==='zone'&&p.role==='DEF'&&aBall<-24&&Math.abs(q.z)<18&&q.x*side>aBall+6&&q.x*side>line+8&&!incoming;
   if(!distant)continue;
   const helpers=mids.filter(a=>a!==presser&&a.duelRecovery<=0&&!assignments.has(a)&&(a!==cover||dist(a,ball)>22)&&seen(a,q)&&dist(a,seen(a,q))<28);
   const cost=a=>{const local=seen(a,q);return dist(a,local)+(a.x*side<local.x*side?0:1)-(previous?.get(a)?.id===q.id?3:0);};
   helpers.sort((a,b)=>cost(a)-cost(b));const helper=helpers[0];
   if(helper){assignments.delete(p);assignments.set(helper,seen(helper,q));cutbackScreeners.add(helper);if(helper===cover)cover=null;
    if(previous?.get(helper)?.id!==q.id)this.telemetry.cutbackHandoffs=(this.telemetry.cutbackHandoffs||0)+1;
   }else heldMarkers.add(p);
  }
  for(const [p,q] of assignments){this.telemetry.markSamples++;if(previous?.has(p)&&previous.get(p)?.id!==q.id)this.telemetry.markHandoffs++;}
  if(assignments.has(cover))cover=pool.filter(p=>p!==presser&&!assignments.has(p)).sort((a,b)=>dist(a,ball)-dist(b,ball)+(a.role==='ATT'?5:0)-(b.role==='ATT'?5:0))[0]||null;
  const flight=this.flight,landing=flight&&['through','long-pass','cross'].includes(flight.kind)&&BallPhysics.predict(ball,.7);
  const interceptor=landing?defenders.filter(p=>landing.x*side<p.x*side+4&&dist(p,landing)<24).sort((a,b)=>dist(a,landing)-dist(b,landing))[0]:null;
  const unit={line,cover,assignments,interceptor,recovering,goalSide,actualLine,actualMid,actualGap,recoveryToken,recoveryStableAt,cutbackScreeners,heldMarkers,midGap:clamp(10.5+(aBall+25)*.25,5.5,10.5),opponentEpoch:this.attackEpoch[1-team],at:this.time};this.defensiveUnits[team]=unit;return unit;
 }
 plan(){
  if(this.restart||this.kick?.restartContext||this.goalPause)return this.planRestart();
  this.updateTeamPhases();
  const meeting=this.flight?.target?.active?this.interceptPoint(this.flight.target):null;
  const ball=this.ball,owner=this.owner,attacking=owner?.team??this.flight?.from.team??this.lastTeam,plans=new Map();
  for(let team=0;team<2;team++){
   const side=this.direction(team),t=this.t[team],has=team===attacking,pool=this.field(team),opponents=this.teamRivals(team),aBall=ball.x*side;
   const context=this.matchContext(team),lineShift=(t.line==='high'?6:t.line==='low'?-6:0)+context.urgency*2,mentality=t.mentality==='attacking'?3:t.mentality==='defensive'?-3:0;
   const counter=has&&this.transitionUntil[team]>this.time&&t.onWin==='counter',counterpress=!has&&this.lossUntil[team]>this.time&&t.onLoss==='counterpress';
   // A block has a home, rather than following a distant opponent all the way
   // into their half. Pressing steps out of this connected shape selectively.
   const blockHome=-22+lineShift+mentality*.5;
   const baseLine=has?clamp(aBall-25+mentality+lineShift*.5,-39,11):clamp(Math.min(aBall-12+lineShift+mentality*.5,blockHome),clamp(aBall-2.3,-48.5,-43),13);
   const trap=!has&&t.offside==='on'&&!this.flight&&opponents.find(q=>q.id===owner?.id)?.receiveClock>0&&aBall>-30?2.8:0;
   const width=t.width==='wide'?1.14:t.width==='narrow'?.73:.94,offsideLine=Math.max(this.teamRivals(team,true).map(q=>q.x*side).sort((a,b)=>b-a)[1]??49,aBall);
   let {presser,cover}=this.selectPress(team,owner,pool);
   const defenders=pool.filter(p=>p.role==='DEF'),holding=pool.filter(p=>p.role==='MID').sort((a,b)=>a.homeX*side-b.homeX*side)[0];
   const build=has?this.buildOutSupport(team,owner):null,pattern=has?this.coordinatedAttack(team,owner,offsideLine):null,flank=has?this.flankSupport(team,owner,offsideLine):null;
   const box=has?this.boxAttack(team,owner):null;
   const connection=pattern?.connectorId!==undefined&&pattern.connectorId!==build?.id&&pattern.connectorId!==flank?.fullbackId&&!box?.points.has(pattern.connectorId)&&owner&&aBall>-12&&aBall<30?this.connectionPoint(owner,this.players[pattern.connectorId],baseLine,offsideLine):null;
   const supports=has?this.supportUnit(team,owner,pool,holding,build,pattern,flank,box,offsideLine,connection,meeting):new Map(),pressurePlan=has?{active:false,reason:'in-possession'}:this.pressPolicy(team,presser,cover,owner);this.pressPolicies[team]=pressurePlan;
   const unit=!has?this.defensiveUnit(team,owner,baseLine,pool,opponents,pressurePlan.active?presser:null,pressurePlan.active?cover:null):null,assignments=unit?.assignments||new Map();
   if(unit)cover=unit.cover;
   if(!has&&!pressurePlan.active)presser=null;
   if(this.pressAssignments[team])this.pressAssignments[team].cover=cover;
   const pressingUnit=!has?this.pressUnit(team,owner,presser,cover,unit,pressurePlan):null;
   if(has)this.pressUnits[team]=null;else this.supportPlans[team]=null;
   this.tacticalPhase[team]=has?(counter?'counter':aBall<-15?'build':aBall>25?'final':'progress'):(pressurePlan.active?(counterpress?'counterpress':'press'):'defend');
   for(const p of this.team(team)){
    p.duty=this.teamRole(p);p.boxRole=null;
    const personal=this.rivals(p),marked=assignments.get(p),observedMark=marked&&personal.find(q=>q.id===marked.id);
    if(marked&&this._perceptionActive){if(observedMark)assignments.set(p,observedMark);else assignments.delete(p);}
    let x=side*(baseLine+(p.role==='DEF'?0:p.role==='MID'?17:34)),z=p.homeZ*width+ball.z*.13,pace=.88,state='shape';
    if(p.role==='GK'){
     const goal=-side*52,covered=owner&&pool.some(q=>{const h=segment(q,owner,{x:goal,z:0});return dist(q,owner)<3||h.u>.04&&h.u<.96&&h.d<3.3&&dist(q,owner)<9;});
     // A central box entry is not automatically a breakaway. With a defender
     // still contesting the shooter, keep depth rather than charging past him.
     const oneOnOne=!has&&owner&&aBall<-36&&Math.abs(ball.z)<9&&!this.flight&&!covered;
     const depth=has?clamp(4+(aBall+35)*.18+(t.line==='high'?2.5:0),3,14.5):oneOnOne?clamp((52+aBall)*.36,2,5.5):clamp(1.5+(aBall+35)*.11,1.2,6);x=goal+side*depth;z=clamp(ball.z*depth/Math.max(7,Math.abs(ball.x-goal)),-3.05,3.05);state='goalkeeper';pace=oneOnOne?1.04:.85;
     if(!has&&!oneOnOne&&dist(p,{x,z})>5){state='keeper-recovery';pace=1.12;}
     if(!has&&this.kick?.kind==='shot'&&this.kick.p.team!==team&&dist(p,{x,z})<.8){x=p.x;z=p.z;state='keeper-set';pace=.5;}
     if(!owner&&!this.flight&&aBall<-30&&dist(p,ball)<12){const lead=this.interceptPoint(p);x=lead.x;z=lead.z;state='keeper-sweep';pace=1.1;}
     if(this.goalThreat(team)&&(this.flight?.age??1)>.10){
      let crossing=this.ballCrossing(p.x,3);const goal=this.ballCrossing(-side*52,3),high=crossing?.y??ball.y;
      // Shuffle while there is time, then set/dive. Feet still use move() limits.
      if(crossing?.t>0&&goal?.t>0&&Math.abs(goal.z)<4.7){x=high>2.3?-side*51.15:p.x;crossing=this.ballCrossing(x,3);if(crossing){z=clamp(crossing.z,-3.6,3.6);pace=1.04;state='keeper-adjust';}}
     }
     // Foot possession is not a ball in the hands. If its cushioning touch
     // rolls beyond kicking reach, approach it before choosing distribution.
     if(owner===p&&!p.holdingBall&&!this.kick&&dist(p,ball)>.95){x=ball.x+ball.vx*.10;z=ball.z+ball.vz*.10;state='keeper-control';pace=1.0;}
    }else if(p===owner){const target=p.carryTarget||{x:p.x+side*5,z:p.z};x=target.x;z=target.z;if(dist(p,ball)>1.1||p.receiveMode==='cushion'&&p.receiveClock>0){x=ball.x+ball.vx*.12;z=ball.z+ball.vz*.12;}const pressure=Math.min(20,...personal.map(q=>dist(q,p))),shield=p.shieldUntil>this.time;pace=p.receiveClock>0?.48:shield?.56:p.settleUntil>this.time?.34:counter?1.04:p.escapeUntil>this.time?.98:pressure>5&&aBall<20?.60:.98;state=p.receiveClock>0?'receive':shield?'shield':'dribble';}
    else if(!owner&&!this.flight){if(p===presser){const q=this.interceptPoint(p);x=q.x;z=q.z;pace=1.12;state='loose-ball';}else if(p===cover){x=ball.x-side*7;z=ball.z*.55+p.homeZ*.45;state='screen';}}
    else if(has){
     if(p.role==='MID'){x=side*(baseLine+(p===holding?15:24)+(counter&&p!==holding?5:0));if(p===holding&&aBall>2)x=Math.min(x*side,aBall-7)*side;}
     if(p.role==='ATT'){x=side*Math.min(offsideLine-.9,baseLine+(counter?47:40));z=clamp(p.homeZ*width*(t.playstyle==='wing'?1.04:1)+ball.z*.10,-30,30);}
     if(supports.has(p.id)&&p!==this.flight?.target){
      const point=supports.get(p.id);x=point.x;z=point.z;state='support';pace=.94;
     }
     if(pattern?.runner?.id===p.id&&!supports.has(p.id)){x=pattern.runner.point.x;z=pattern.runner.point.z;state='penetration';pace=1.07;}
     else if(pattern?.connectorId===p.id&&connection&&!supports.has(p.id)){x=connection.x;z=connection.z;state='between-lines';}
     if(!supports.has(p.id)&&p.role==='DEF'&&Math.abs(p.homeZ)>20&&p.homeZ*ball.z>0&&t.fullbacks!=='hold'&&aBall>-10){x=side*(t.fullbacks==='overlap'&&owner&&Math.abs(owner.z)>12?Math.min(44,aBall+8):Math.min(aBall-8,baseLine+12));z=Math.sign(p.homeZ)*Math.min(31,Math.abs(p.homeZ)*1.12);state=t.fullbacks==='overlap'?'overlap':'wide-support';pace=1.02;}
     if(flank?.fullbackId===p.id){x=flank.point.x;z=flank.point.z;state=flank.state;pace=1.02;}
     if(!supports.has(p.id)&&t.fullbacks==='overlap'&&owner&&Math.abs(owner.z)>12&&p.homeZ*owner.z>0&&['winger','wide-midfielder'].includes(p.duty)&&p!==owner&&p.id!==pattern?.runner?.id){z=Math.sign(p.homeZ)*12.5;x=side*Math.min(offsideLine-1,Math.max(aBall+4,x*side));state='inside-support';}
     if(!supports.has(p.id)&&p.duty==='fullback'&&p.homeZ*ball.z<0&&aBall>0){x=side*Math.min(baseLine+2,aBall-15);z=p.homeZ*.80;state='rest-defence';}
     if(p===holding&&aBall>0){x=side*Math.min(x*side,aBall-10,baseLine+10);state='anchor';}
     if(build?.id===p.id){x=build.point.x;z=build.point.z;state='build-support';pace=.98;}
     if(box?.points.has(p.id)){const q=box.points.get(p.id);x=q.x;z=q.z;state=q.state;pace=q.role==='edge'?.96:1.06;p.boxRole=q.role;}
     if(this.flight?.target===p){const q=['through','cross','long-pass'].includes(this.flight.kind)&&dist(p,ball)>3?this.flight.point:meeting||this.interceptPoint(p);x=q.x;z=q.z;state='receive-run';pace=1.13;}
     else if(this.kick?.target===p){x=this.kick.point.x;z=this.kick.point.z;state='receive-run';pace=1.03;}
     else if(p.runIntent?.until>this.time&&(p.runIntent.epoch===undefined||p.runIntent.epoch===this.attackEpoch[team])){x=p.runIntent.point.x;z=p.runIntent.point.z;state='channel-run';pace=1.08;}
     else if(p.supportIntent?.until>this.time&&p.supportIntent.epoch===this.attackEpoch[team]){x=p.supportIntent.point.x;z=p.supportIntent.point.z;state='return-support';pace=.96;}
     if(p.role!=='DEF'&&!['receive-run'].includes(state)&&!this.flight&&x*side>offsideLine-.6)x=side*(offsideLine-.6);
    }else{
     x=side*(unit.line+trap+(p.role==='DEF'?0:p.role==='MID'?unit.midGap:unit.recovering?18:25));z=clamp(p.homeZ*(t.width==='narrow'?.66:.80)+ball.z*.24,-28,28);
     const distance=dist(p,ball),engage=pressurePlan.engage??0;
     if(p===presser&&pressurePlan.active){const q=this.flight?this.interceptPoint(p):pressingUnit?.pressPoint||{x:ball.x-side*.65,z:ball.z};x=q.x;z=q.z;state=this.flight?'intercept':'press';pace=1.06;this.tacticalStats[team].pressSamples++;}
     else if(pressurePlan.active&&p===cover&&(distance<engage+7||t.press>=75&&presser&&dist(presser,ball)<engage)){const q=pressingUnit?.coverPoint||{x:ball.x-side*4.3,z:ball.z*.70};x=q.x;z=q.z;state='cover';pace=.98;}
     else if(p===holding&&!assignments.has(p)){x=side*clamp(aBall-3,unit.line+4,unit.line+10);z=clamp(ball.z*.43,-11,11);state='screen';pace=.96;}
     else if(assignments.has(p)){const q=assignments.get(p),blend=t.marking==='man'?.84:.44,depth=x*side;x=side*clamp((x*(1-blend)+(q.x-side*1.7)*blend)*side,depth-(t.marking==='man'?8:4.5),depth+(t.marking==='man'?8:4.5));z=z*(1-blend)+q.z*blend;state='mark';}
     if(p===presser&&state==='press'&&t.onLoss==='regroup'&&this.lossUntil[team]>this.time&&distance>1.8&&distance<7&&(p.x-ball.x)*side<-.5&&pool.filter(q=>q.role==='DEF'&&(q.x-ball.x)*side<-2).length<3){x=ball.x-side*2.3;z=ball.z*.88;state='delay';pace=.58;}
     if(p.role==='DEF'&&p!==presser&&assignments.has(p)){
      const q=assignments.get(p),futureX=(q.x+q.vx*.65)*side;
      if(futureX<x*side+1.5&&dist(p,q)<17){x=side*Math.min(x*side,futureX-1.7);z=z*.4+(q.z+q.vz*.4)*.6;state='track-run';pace=1.10;}
     }
     if(assignments.has(p)&&aBall<-24){const q=assignments.get(p);if(q.x*side<-20&&dist(p,q)<18){const hold=unit.heldMarkers.has(p);x=side*(hold?Math.min(q.x*side-1.35,unit.line+6):q.x*side-1.35);z=q.z*.94;state=hold?'screen':'track-run';pace=1.08;}}
     if(unit.cutbackScreeners.has(p)){const q=assignments.get(p);x=q.x-side*1.7;z=q.z*.94;state=dist(p,q)>6?'recovery-screen':'screen';pace=dist(p,q)>6?1.12:.98;}
     const lateMid=p!==cover&&p.role==='MID'&&p.x*side>unit.line+unit.midGap+4;
     if(unit.recovering&&p!==presser&&!assignments.has(p)&&((p.x-ball.x)*side>-1||lateMid)&&aBall<25){x=side*Math.min(x*side,aBall-(p.role==='DEF'?5:2.5));z=clamp(z,-18,18);state='recovery';pace=1.12;}
     if(p===unit.interceptor&&this.flight){const read=this.interceptPoint(p);x=read.x;z=read.z;state='track-run';pace=1.10;}
     if(p!==presser&&aBall<-8&&(p.x-x)*side>5){pace=1.12;if(!['track-run','recovery-screen'].includes(state))state='recovery';}
     if(this.flight?.kind==='shot'&&distance<9){x=ball.x+ball.vx*.15;z=ball.z+ball.vz*.15;state='block';pace=1.05;}
     else if(this.kick?.kind==='shot'&&this.kick.p.team!==team&&personal.some(q=>q.id===this.kick.p.id)){
      const shooter=personal.find(q=>q.id===this.kick.p.id),aim={x:ball.x+Math.cos(shooter.face)*35,z:ball.z+Math.sin(shooter.face)*35},path=segment(p,ball,aim),goalSide=(p.x-ball.x)*side<-.5;
      if(goalSide&&path.u<.85&&path.d<3.2){x=ball.x+(aim.x-ball.x)*path.u;z=ball.z+(aim.z-ball.z)*path.u;state='block';pace=1.08;}
     }
    }
    const pressing=['press','counterpress','intercept'].includes(state);if(pressing&&!p.wasPressing)this.attackStats[team].pressStarts++;if(!pressing&&p.wasPressing)this.attackStats[team].pressDrops++;p.wasPressing=pressing;
    if(this.activeWall?.team===team&&this.activeWall.until>this.time&&this.activeWall.points.has(p.id)&&this.flight){const q=this.activeWall.points.get(p.id);x=q.x;z=q.z;state='wall';pace=.6;}
    // Target spacing uses intended destinations, not a late teleport at contact.
    if(!['support','build-support','between-lines','cover','screen','press','counterpress','intercept','loose-ball','receive-run','dribble','receive','goalkeeper','keeper-sweep','keeper-control','wall'].includes(state))for(const [q,other] of plans){if(q.team!==team||q.role==='GK')continue;const d=Math.hypot(x-other.x,z-other.z);if(d<4.0){const a=Math.atan2(z-other.z,x-other.x)+(d<.01?(p.id%2?1:-1):0);x+=Math.cos(a)*(4-d)*.65;z+=Math.sin(a)*(4-d)*.65;}}
    const chasing=['press','counterpress','intercept','loose-ball','receive-run','dribble','keeper-sweep','keeper-control'].includes(state),limitX=p.role==='GK'?51.75:chasing?52.4:50,point={x:clamp(x,-limitX,limitX),z:clamp(z,chasing?-34.3:-32,chasing?34.3:32),pace,state};
    const purpose=Intent.purposeFor(state),focusId=assignments.get(p)?.id??(['press','counterpress','cover','intercept','delay'].includes(state)?owner?.id:null),partnerId=purpose==='support'?owner?.id??this.flight?.target?.id:purpose==='run'?p.runIntent?.partnerId??p.supportIntent?.qId??owner?.id??this.flight?.from?.id:state==='cover'?presser?.id:null;
    const priority=p===owner?100:['receive-run','block','loose-ball'].includes(state)?110:state==='recovery'?80:purpose==='press'?60:purpose==='mark'||purpose==='cover'?40:['support','run'].includes(purpose)?30:0;
    const coordinatedHandoff=p.task?.purpose==='press'&&p!==presser||p.task?.purpose==='mark'&&p.task.focusId!==focusId;
    const chosen=p.role==='GK'?point:Intent.resolve(p,{...point,focusId:focusId??null,partnerId:partnerId??null,priority},this.taskContext(p,{safe:(actor,task,c)=>this.taskSafe(actor,task,c),forceReason:coordinatedHandoff?'team-handoff':null,ballContact:p===owner,directThreat:['block','loose-ball','recovery'].includes(state)}));
    // Publish the command that survived arbitration to the connection tables.
    // Pass evaluation must not keep promising a helper whose task was rejected.
    if(this.supportPlans[team]){
     if(chosen.state==='support'&&chosen.partnerId===this.supportPlans[team].ownerId)this.supportPlans[team].points.set(p.id,{x:chosen.x,z:chosen.z});
     else this.supportPlans[team].points.delete(p.id);
    }
    if(pattern?.runner?.id===p.id){if(chosen.state==='penetration')pattern.runner.point={x:chosen.x,z:chosen.z};else pattern.runner=null;}
    if(pattern?.connectorId===p.id&&chosen.state==='between-lines'&&p.connectionIntent)p.connectionIntent.point={x:chosen.x,z:chosen.z};
    if(build?.id===p.id){if(chosen.state==='build-support')build.point={x:chosen.x,z:chosen.z};else this.buildPlans[team]=null;}
    if(flank?.fullbackId===p.id){if(['overlap','wide-support'].includes(chosen.state))flank.point={x:chosen.x,z:chosen.z};else this.flankPlans[team]=null;}
    if(box?.points.has(p.id)&&['box-run','cutback-support'].includes(chosen.state))Object.assign(box.points.get(p.id),{x:chosen.x,z:chosen.z});
    if(box?.points.has(p.id)&&!['box-run','cutback-support','receive-run'].includes(chosen.state))box.points.delete(p.id);
    p.intent={...chosen,epoch:this.attackEpoch[team],until:p.task?.expiresAt??this.time+.7};plans.set(p,chosen);
   }
  }
  const ref=this.players.find(p=>p.referee);if(ref)plans.set(ref,{x:clamp(ball.x-7,-42,42),z:clamp(ball.z-8,-26,26),pace:.65,state:'referee'});this.targets=plans;
  // Reception reads the commands just issued to the helpers, not the old
  // passer-centred layout. The receiver still refreshes at his normal rate.
  if(this.flight?.target?.active)this.prepareReception(this.flight.target,meeting);
 }

 restartSpace(point,spot,minimum){
  if(dist(point,spot)>=minimum+.2)return point;
  let best=null;
  for(let i=0;i<64;i++){
   const a=i*Math.PI/32,q={x:spot.x+Math.cos(a)*(minimum+.35),z:spot.z+Math.sin(a)*(minimum+.35)};
   if(Math.abs(q.x)>50.5||Math.abs(q.z)>32.7)continue;
   const cost=dist(q,point);if(!best||cost<best.cost)best={...q,cost};
  }
  if(best){point.x=best.x;point.z=best.z;}return point;
 }
 takerSpace(point,r,p){
  if(!r?.setupPoint||p===r.taker||dist(point,r.setupPoint)>=1.2)return point;
  const dx=point.x-r.setupPoint.x,dz=point.z-r.setupPoint.z,d=Math.hypot(dx,dz),a=d>.01?Math.atan2(dz,dx):Math.atan2(p.z-r.setupPoint.z,p.x-r.setupPoint.x);
  point.x=clamp(r.setupPoint.x+Math.cos(a)*1.25,-51,51);point.z=clamp(r.setupPoint.z+Math.sin(a)*1.25,-32,32);return point;
 }
 freeKickLayout(r){
  if(!r||r.kind!=='free-kick')return null;
  if(r.layout&&[...r.layout.wall.keys()].every(id=>this.players[id]?.active))return r.layout;
  const side=this.direction(r.team),spot=r.spot,goal={x:side*52,z:0},distance=dist(spot,goal);
  if(spot.x*side<10||distance>42)return null;
  const flank=Math.sign(spot.z)||1,aim={x:goal.x,z:flank*1.4},length=dist(spot,aim)||1;
  const forward={x:(aim.x-spot.x)/length,z:(aim.z-spot.z)/length},across={x:-forward.z,z:forward.x};
  const defenders=this.field(1-r.team),angleToGoal=Math.atan2(Math.abs(spot.z),Math.max(.2,52-spot.x*side)),count=distance<12||distance>35?0:angleToGoal>.85?2:distance<22?5:distance<29?4:3;
  const centre={x:spot.x+forward.x*9.4,z:spot.z+forward.z*9.4};
  const chosen=defenders.slice().sort((a,b)=>dist(a,centre)+(a.role==='DEF'?8:0)-(dist(b,centre)+(b.role==='DEF'?8:0))).slice(0,count).sort((a,b)=>(a.x-b.x)*across.x+(a.z-b.z)*across.z);
  // A very shallow arc keeps the whole wall at the legal radius. Rotate the
  // group when a goal-line/touchline would otherwise clip a member's target.
  const base=Math.atan2(forward.z,forward.x),radius=9.4,spacing=.62/radius;let wallPoints=[];
  for(let turn=0;turn<160&&!wallPoints.length;turn++)for(const sign of (turn?[1,-1]:[1])){
   const heading=base+sign*turn*.025,points=chosen.map((p,i)=>{const a=heading+(i-(chosen.length-1)/2)*spacing;return {x:spot.x+Math.cos(a)*radius,z:spot.z+Math.sin(a)*radius};});
   if(points.every(q=>Math.abs(q.x)<=50.5&&Math.abs(q.z)<=32.7)){wallPoints=points;break;}
  }
  const wall=new Map();chosen.forEach((p,i)=>wall.set(p.id,{...wallPoints[i],state:'wall',pace:.96}));
  const attack=new Map(),candidates=this.field(r.team).filter(p=>p!==r.taker).sort((a,b)=>(a.role==='ATT'?0:a.role==='MID'?20:60)+Math.abs(a.homeZ)*.1-((b.role==='ATT'?0:b.role==='MID'?20:60)+Math.abs(b.homeZ)*.1)).slice(0,4);
  candidates.forEach((p,i)=>{
   const point={x:side*(i===0?43:i===1?41:i===2?44:34),z:[0,-8,8,-flank*12][i],state:'fk-attack',pace:.95};
   // Advancing a crowded attacker can move him through the wall and leave
   // him inside its release exclusion area. Find the nearest clear target
   // against the whole wall instead; players still walk there normally.
   if([...wall.values()].some(q=>dist(point,q)<1.6)){
    let clear=null;
    for(let ring=1;ring<=32&&!clear;ring++)for(let n=0;n<32;n++){
     const a=n*Math.PI/16,q={x:point.x+Math.cos(a)*ring*.4,z:point.z+Math.sin(a)*ring*.4};
     if(Math.abs(q.x)<=50.5&&Math.abs(q.z)<=31.5&&[...wall.values()].every(w=>dist(q,w)>=1.6)){clear=q;break;}
    }
    if(clear){point.x=clear.x;point.z=clear.z;}
   }
   attack.set(p.id,point);
  });
  const marking=new Map(),remaining=defenders.filter(p=>!wall.has(p.id));
  for(const [id,point] of attack){const marker=remaining.filter(p=>!marking.has(p.id)).sort((a,b)=>dist(a,point)-dist(b,point))[0];if(marker)marking.set(marker.id,{x:point.x+side*1.5,z:point.z,state:'fk-mark',pace:.95,opponent:id});}
  const keeper=this.team(1-r.team).find(p=>p.role==='GK'),keeperPoint={x:goal.x-side*1.8,z:clamp(-flank*1.6+spot.z*.03,-2.5,2.5)};
  r.layout={side,distance,wall,attack,marking,keeperId:keeper?.id,keeperPoint};
  if(wall.size){this.telemetry.wallSetups=(this.telemetry.wallSetups||0)+1;this.emit('wall','Baraj hazırlanıyor',`${wall.size} oyuncu baraja geçiyor; kaleci açık tarafı koruyacak.`,null,1-r.team);}
  return r.layout;
 }
 planFreeKick(r,layout){
  const plans=new Map(),side=layout.side;
  for(let team=0;team<2;team++)for(const p of this.team(team)){
   let point;
   if(p===r.taker){const a=Math.atan2(-r.spot.z,side*22);point={x:r.setupPoint?.x??r.spot.x-Math.cos(a)*.75,z:r.setupPoint?.z??r.spot.z-Math.sin(a)*.75,state:'restart',pace:1.05};}
   else if(layout.wall.has(p.id))point={...layout.wall.get(p.id)};
   else if(p.id===layout.keeperId)point={...layout.keeperPoint,state:'goalkeeper',pace:.9};
   else if(p.role==='GK')point={x:-side*48.5,z:0,state:'goalkeeper',pace:.85};
   else if(team===r.team)point=layout.attack.has(p.id)?{...layout.attack.get(p.id)}:{x:side*clamp(r.spot.x*side-(p.role==='DEF'?23:9),-35,24),z:p.homeZ*.85,state:'fk-cover',pace:.9};
   else point=layout.marking.has(p.id)?{...layout.marking.get(p.id)}:{x:side*clamp(r.spot.x*side+13,35,45),z:p.homeZ*.55,state:'fk-cover',pace:.9};
   if(team!==r.team&&layout.distance>=12&&dist(point,r.spot)<9.4){const dx=point.x-r.spot.x,dz=point.z-r.spot.z,d=Math.hypot(dx,dz)||1;point.x=r.spot.x+dx/d*9.4;point.z=r.spot.z+dz/d*9.4;}
   this.takerSpace(point,r,p);point.x=clamp(point.x,-51,51);point.z=clamp(point.z,-32,32);plans.set(p,point);
  }
  const ref=this.players.find(p=>p.referee);if(ref)plans.set(ref,{x:clamp(r.spot.x-side*5,-46,46),z:clamp(r.spot.z+(r.spot.z>0?-7:7),-29,29),state:'referee',pace:.7});
  this.targets=plans;
 }
 freeKickChoice(r){
  const layout=this.freeKickLayout(r),p=r.taker;if(!layout)return null;
  if(!r.indirect&&layout.distance>=14&&layout.distance<=31&&Math.abs(r.spot.z)<23&&p.shooting>=74){
   let best=null;const power=clamp(18.5+layout.distance*.14+p.shooting*.025,22,27),defenders=this.field(1-r.team),keeper=this.players[layout.keeperId];
   for(const z of [-2.6,-1.3,0,1.3,2.6]){
    const point={x:layout.side*52,z},d=dist(r.spot,point),time=d/power,height=1.85,vy=(height-.11+4.905*time*time)/time;
    let block=0;for(const q of defenders){const h=segment(q,r.spot,point),t=time*h.u,y=.11+vy*t-4.905*t*t;if(h.u>.02&&h.u<.98&&y<1.98)block=Math.max(block,clamp((.62-h.d)/.62,0,1));}
    const score=(1-block)*8-(keeper?Math.exp(-Math.abs(z-keeper.z)/1.7)*2:0);
    if(!best||score>best.score)best={kind:'shot',q:null,point,power,height,score};
   }
   if(best.score>2.5)return best;
  }
  const targets=[...layout.attack.keys()].map(id=>this.players[id]).filter(p=>p.active).sort((a,b)=>Math.abs(a.z)-Math.abs(b.z));
  if(targets.length&&layout.distance<40){const q=targets[0];return {kind:'cross',q,point:{x:q.x,z:q.z},power:null};}
  return null;
 }
 planRestart(){
  const restart=this.restart||this.kick?.restartContext;
  if(restart?.kind==='penalty'){this.planPenalty(restart);return;}
  const layout=this.freeKickLayout(restart);if(layout){this.planFreeKick(restart,layout);return;}
  const ball=this.ball,owner=this.owner,attacking=owner?.team??this.flight?.from.team??this.lastTeam;
  const plans=new Map();
  for(let team=0;team<2;team++){
   const side=this.direction(team),t=this.t[team],has=team===attacking;
   const defenders=this.field(team).slice().sort((a,b)=>dist(a,ball)-dist(b,ball));
   // Only the nearest player actively hunts the ball. The next protects the route inside.
   const press=defenders[0],cover=defenders[1],aBall=ball.x*side;
   const mentality=t.mentality==='attacking'?3:t.mentality==='defensive'?-3:0;
   const baseLine=clamp((has?aBall-24:aBall-17)+mentality+(t.line==='high'?5:t.line==='low'?-5:0),-39,has?5:14);
   const opponents=this.field(1-team),offsideLine=this.defenceLine(team);
   for(const p of this.team(team)){
    let x,z,pace=.85,state='shape';
    if(restart?.taker===p){const r=restart,a=Math.atan2(-r.spot.z,side*12);x=r.setupPoint?.x??r.spot.x-Math.cos(a)*.75;z=r.setupPoint?.z??r.spot.z-Math.sin(a)*.75;pace=1.05;state='restart';}
    else if(p.role==='GK'){
     const gx=-side*50,intersection=clamp(ball.z*(Math.abs(ball.x-gx)<30?.35:.15),-3.1,3.1);
     x=gx+side*(has?2.1:clamp((aBall+45)*.045,0,1.5));z=intersection;pace=.85;state='goalkeeper';
    }else if(restart){
     const r=restart;
     if(p===r.taker){const toward=r.kind==='kickoff'?0:Math.atan2(-r.spot.z,side*12);x=r.spot.x-Math.cos(toward)*.75;z=r.spot.z-Math.sin(toward)*.75;state='restart';pace=1.05;}
     else if(r.kind==='kickoff'){
      x=side*(p.role==='DEF'?-29:p.role==='MID'?-16:-4);z=p.homeZ;
      if(team!==r.team&&Math.hypot(x,z)<9.5)z=z>=0?10:-10;
     }else if(r.kind==='corner'){
      x=side*(has?(p.role==='ATT'?43:p.role==='MID'?34:-2):(p.role==='DEF'?-45:p.role==='MID'?-38:-12));z=clamp(p.homeZ*.45,-14,14);
     }else{x=side*(p.role==='DEF'?baseLine:baseLine+(p.role==='MID'?13:25));z=p.homeZ*.8+ball.z*.12;}
     // Goal kicks require opponents outside the penalty area, rather than a
     // free-kick circle that still lets them stand beside the short receiver.
     if(team!==r.team){
      if(r.kind==='goal-kick'){
       const ownSide=this.direction(r.team);if(x*ownSide<-35.25&&Math.abs(z)<20.4)x=-ownSide*35.25;
      }else{
       const minimum=r.kind==='throw'?2:9.15;
       if(dist(p,r.spot)<minimum){const dd=Math.hypot(x-r.spot.x,z-r.spot.z)||1;x=r.spot.x+(x-r.spot.x)/dd*(minimum+.35);z=r.spot.z+(z-r.spot.z)/dd*(minimum+.35);}
      }
     }
    }else if(p===owner){
     const target=p.carryTarget||{x:p.x+side*5,z:p.z};x=target.x;z=target.z;
     if(dist(p,ball)>1.15){x=ball.x+ball.vx*.12;z=ball.z+ball.vz*.12;}
     pace=p.receiveClock>0?.25:1.05;state=p.receiveClock>0?'receive':'dribble';
    }else if(!owner&&!this.flight){
     if(p===press){x=ball.x+ball.vx*.18;z=ball.z+ball.vz*.18;pace=1.1;state='loose-ball';}
     else{x=side*(baseLine+(p.role==='DEF'?0:p.role==='MID'?13:25));z=p.homeZ*.85+ball.z*.12;}
    }else if(has){
     const counter=this.transitionUntil[team]>this.time;
     const roleX=p.role==='DEF'?baseLine:p.role==='MID'?baseLine+27:baseLine+(counter?48:42);
     x=side*clamp(roleX,-42,Math.min(47,Math.max(aBall+2,offsideLine-1.2)));
     z=clamp(p.homeZ*(p.role==='ATT'?1.08:1.0)+ball.z*.13,-29,29);
     const separation=owner?dist(owner,p):30;
     if(owner&&p.role==='MID'&&separation<24&&p.personality>.33){x=owner.x-side*(p.personality>.5?7:11);z=owner.z+(p.homeZ>=owner.z?1:-1)*(p.personality>.5?11:8);state='support';}
     if(owner&&p.role==='ATT'&&p.homeZ*owner.z>0&&Math.abs(owner.z)>15){x=owner.x+side*10;z=owner.z*.55;state='channel-run';pace=1.05;}
     if(this.flight?.target===p){const landing=this.flight.point;const useRun=['through','cross','cutback'].includes(this.flight.kind)&&dist(p,ball)>2.5;x=useRun?landing.x:ball.x+ball.vx*clamp(dist(p,ball)/18,.1,.65);z=useRun?landing.z:ball.z+ball.vz*clamp(dist(p,ball)/18,.1,.65);state='receive-run';pace=1.12;}
     else if(p.runIntent?.until>this.time){x=p.runIntent.point.x;z=p.runIntent.point.z;state='channel-run';pace=1.1;}
     if(owner&&p.role==='ATT'&&owner.x*side>27&&Math.abs(owner.z)>12){x=side*(p.index%2?45:40);z=p.index%2?-5:5;state='box-run';pace=1.05;}
    }else{
     x=side*(baseLine+(p.role==='DEF'?0:p.role==='MID'?12:24));z=clamp(p.homeZ*.78+ball.z*.18,-25,25);
     const pressDistance=dist(p,ball),engage=9+(+t.press)*.10;
     if(p===press&&pressDistance<engage){x=ball.x-side*.55;z=ball.z;state='press';pace=1.05;}
     else if(p===cover&&pressDistance<engage+5){x=ball.x-side*6;z=ball.z*.65+p.homeZ*.35;state='cover';pace=.92;}
     else if(p.role==='DEF'){
      const danger=nearest(this.field(attacking).filter(a=>a.role==='ATT'),p);
      if(danger&&dist(danger,p)<12){x=x*.65+(danger.x-side*1.6)*.35;z=z*.60+danger.z*.40;state='mark';}
     }
    }
    if(this.goalPause){x=p.x;z=p.z;pace=.3;state='goal';}
    // Keep team-mates from selecting the same patch of grass.
    if(p!==owner&&!['loose-ball','receive-run','restart','press'].includes(state)){for(const q of this.team(team)){if(q===p)continue;const d=dist(p,q);if(d<2.8&&d>.01){x+=(p.x-q.x)/d*(2.8-d)*.55;z+=(p.z-q.z)/d*(2.8-d)*.55;}}}
    if(restart?.kind==='goal-kick'&&team!==restart.team&&x*this.direction(restart.team)<-35.25&&Math.abs(z)<20.4)x=-this.direction(restart.team)*35.25;
    const pursuing=['loose-ball','receive-run','restart','press','dribble','receive'].includes(state);
    const point={x:clamp(x,pursuing?-52:-50.5,pursuing?52:50.5),z:clamp(z,pursuing?-34.25:-32.7,pursuing?34.25:32.7),pace,state};
    if(restart){this.takerSpace(point,restart,p);if(team!==restart.team&&['free-kick','corner','throw'].includes(restart.kind))this.restartSpace(point,restart.spot,restart.kind==='throw'?2:9.15);}
    plans.set(p,point);
   }
  }
  const ref=this.players.find(p=>p.referee);plans.set(ref,{x:clamp(ball.x-7,-42,42),z:clamp(ball.z-8,-26,26),pace:.65,state:'referee'});
  this.targets=plans;
 }
 effort(p,target,dt){
  if(p.referee)return;
  const hard=p.speed>4.2||['press','counterpress','penetration','overlap','track-run'].includes(target.state)&&p.speed>3;
  const endurance=clamp(1+((p.endurance??75)-75)*.006,.70,1.15);
  p.energy=clamp((p.energy??1)+dt*(hard?-.023/endurance:p.speed<2?.030*endurance:.006*endurance),.25,1);
  p.stamina=Math.max(Math.min(45,(p.fitness??100)*.45),p.stamina-dt*(.0006+Math.max(0,p.speed-1)*.00085+(hard?.0011:0))/endurance);
 }
 move(p,target,dt){
  if(!p.active||!target)return;
  this.effort(p,target,dt);
  if(p.holdingBall&&p.holdClock>0){p.vx=p.vz=p.speed=0;p.brainRole='keeper-hold';return;}
  if(['dive','catch-ready'].includes(p.action)&&p.actionClock>0){p.vx=p.vz=p.speed=0;return;}
  let kickRecovery=false;
  if(this.kick?.p===p){
   const k=this.kick,stationary=!!k.restartContext||k.kind==='throw',vx=k.moving?k.approach.vx:0,vz=k.moving?k.approach.vz:0;
   kickRecovery=!stationary&&!Match.prototype.touchContact.call(this,p,this.ball,p.kickFoot).ready;
   if(!kickRecovery){
    const dx=vx-p.vx,dz=vz-p.vz,d=Math.hypot(dx,dz)||1,a=Math.min(1,12*dt/d);
    p.vx+=dx*a;p.vz+=dz*a;if(stationary)p.vx=p.vz=0;
    p.x+=p.vx*dt;p.z+=p.vz*dt;p.speed=Math.hypot(p.vx,p.vz);p.anim+=p.speed*dt*2.3;p.brainRole='kick';return;
   }
   target={x:this.ball.x+this.ball.vx*.08,z:this.ball.z+this.ball.vz*.08,pace:.9,state:'kick-recovery'};
  }
  if(!kickRecovery&&(p.action==='shoot'||p.action==='pass')&&p.actionClock>.05&&!p.kickMoving){p.vx=p.vz=p.speed=0;return;}
  const dx=target.x-p.x,dz=target.z-p.z,d=Math.hypot(dx,dz),heading=Math.atan2(dz,dx);
  const fatigue=p.model?(p.fitness>0?clamp(p.stamina/p.fitness,0,1):1):p.stamina/100;
  const turn=Math.abs(angle(heading,p.face)),top=(p.role==='GK'?4.4+((p.pace??75)-75)*.025:5.7+((p.pace??p.skill)-75)*.040)*(.78+.22*fatigue)*(.83+.17*(p.energy??1))*target.pace*(p.duelRecovery>0?.20:1)*(p.feintReaction>0?.82:1);
  const wanted=d>(['restart','penalty-keeper'].includes(target.state)?.025:.16)?Math.min(top,d*2,Math.sqrt(16*d))*(1-.45*turn/Math.PI):0;
  let vx=d?dx/d*wanted:0,vz=d?dz/d*wanted:0;
  if(!['restart','goal','wall'].includes(target.state))for(const q of this.players){if(q===p||!q.active||q.referee||q.team!==p.team)continue;const ax=(p.x+p.vx*.28)-(q.x+q.vx*.28),az=(p.z+p.vz*.28)-(q.z+q.vz*.28),gap=Math.hypot(ax,az);if(gap>.05&&gap<1.5){const push=(1.5-gap)*1.9;vx+=ax/gap*push;vz+=az/gap*push;}}
  const dead=this.restart||this.kick?.restartContext;
  if(dead&&p.team!==dead.team&&target.state!=='wall'&&['free-kick','corner'].includes(dead.kind)){
   const applicable=dead.kind!=='free-kick'||dist(dead.spot,{x:this.direction(dead.team)*52,z:0})>=12,gap=dist(p,dead.spot);
   if(applicable&&gap<9.8){
    // Avoidance cannot balance a player inside the referee's exclusion area.
    // Steer towards a legal point with ordinary acceleration, never snap him.
    const exit=this.restartSpace({x:p.x,z:p.z},dead.spot,9.35),dx=exit.x-p.x,dz=exit.z-p.z,length=Math.hypot(dx,dz);
    if(length>.01){const nx=dx/length,nz=dz/length,along=vx*nx+vz*nz,escape=Math.min(3,Math.max(0,9.7-gap)*4);if(along<escape){vx+=nx*(escape-along);vz+=nz*(escape-along);}}
   }
  }
  const magnitude=Math.hypot(vx,vz);if(magnitude>top){vx*=top/magnitude;vz*=top/magnitude;}
  const acc=(wanted<p.speed?11:7.8*clamp(.70+(p.acceleration??75)*.004,.70,1.10))*dt,dvx=vx-p.vx,dvz=vz-p.vz,delta=Math.hypot(dvx,dvz)||1;
  p.vx+=dvx*Math.min(1,acc/delta);p.vz+=dvz*Math.min(1,acc/delta);p.x+=p.vx*dt;p.z+=p.vz*dt;p.speed=Math.hypot(p.vx,p.vz);
  // Decelerate into the field, without repositioning a player to the ball.
  p.x=clamp(p.x,-53.5,53.5);p.z=clamp(p.z,-35,35);
  let facing=p.speed>.3?Math.atan2(p.vz,p.vx):p.face;
  if((p.role==='GK'&&target.state!=='keeper-recovery')||target.state==='delay'||p===this.owner&&p.receiveClock>0||target.state==='press'&&dist(p,this.ball)<4.5&&p.speed<3.2||['mark','cover','screen','recovery-screen','build-support','support','wall','fk-mark','fk-attack','fk-cover'].includes(target.state)&&p.speed<2.8)facing=Math.atan2(this.ball.z-p.z,this.ball.x-p.x);
  if(target.state==='receive-run'&&p.reception)facing=Match.prototype.receptionFacing.call(this,p,facing);
  if(target.state==='shield'&&Number.isFinite(p.shieldFace))facing=p.shieldFace;
  const turnRate=4.5*clamp(.70+(p.agility??75)*.004,.70,1.10);
  if(!kickRecovery)p.face+=clamp(angle(facing,p.face),-dt*turnRate,dt*turnRate);p.anim+=p.speed*dt*2.3;p.brainRole=target.state;
  if(p.actionClock<=0){p.action=p.speed>3.2?'run':p.speed>.4?'jog':'idle';p.kickMoving=false;}
 }
 aerial(previous){
  const f=this.flight,b=this.ball;if(!f||f.kind!=='cross'||f.aerialResolved||b.vy>0||b.y<1.60||b.y>2.15)return false;
  const candidates=this.players.filter(p=>p.active&&!p.referee&&p.role!=='GK'&&!(p.duelRecovery>0)).map(p=>({p,h:segment(p,previous,b)})).filter(o=>o.h.d<.43);
  if(!candidates.length)return false;
  candidates.sort((a,c)=>((c.p.heading??c.p.skill)-c.h.d*28)-((a.p.heading??a.p.skill)-a.h.d*28));
  const p=candidates[0].p;if(this.offsideTouch(p))return true;this.offsidePhase=this.captureOffside(p);p.headerHeight=b.y;f.aerialResolved=true;this.action(p,'header',.5);p.actionElapsed=.18;p.actionClock=.32;p.touchClock=.5;this.lastTouch=p;this.owner=null;
  const window=this.shotWindow(p);
  if(p.team===f.from.team&&window.distance<22&&window.quality>.09&&window.open>=.4){
   const skill=p.heading??p.skill,pressure=Math.min(12,...this.field(1-p.team).map(q=>dist(q,p))),scatter=1.0+(100-skill)*.10+window.distance*.065+Math.max(0,2.5-pressure)*.6;
   const toPlane=Math.max(1,52-p.x*this.direction(p.team)),aim={x:54*this.direction(p.team),z:p.z+(window.point.z-p.z)*(54-p.x*this.direction(p.team))/toPlane+(this.random()-.5)*scatter*2};
   const d=dist(b,aim)||1,power=12+skill*.055+Math.min(2,Math.hypot(b.vx,b.vz)*.04),t=d/power,height=clamp(.85+(this.random()-.5)*(3.0+(100-skill)*.13+window.distance*.07),.10,4.0);
   b.vx=(aim.x-b.x)/d*power;b.vz=(aim.z-b.z)/d*power;b.vy=BallPhysics.verticalLaunch(d,power,b.y,height,7,-7);
   this.flight={id:++this.releaseSerial,kind:'shot',from:p,target:null,age:0,offsidePlayers:this.offsidePhase.playerIds.slice()};this.shots[p.team]++;this.xg[p.team]+=window.quality*.65;this.telemetry.headers++;this.emit('header','Kafa vuruşu!',`${p.name} ortayı kaleye yönlendirdi.`,p);
  }else if(p.team===f.from.team){
   const option=this.passOptions(p).find(o=>o.kind==='pass'&&o.risk<.5&&o.distance<20);
   if(option){const d=dist(b,option.point)||1;b.vx=(option.point.x-b.x)/d*11;b.vz=(option.point.z-b.z)/d*11;b.vy=.5;this.flight={id:++this.releaseSerial,kind:'pass',from:p,target:option.q,point:option.point,age:0,offsidePlayers:this.offsidePhase.playerIds.slice()};this.passes[p.team]++;this.telemetry.headedPasses=(this.telemetry.headedPasses||0)+1;this.emit('header','Kafayla indirdi',`${p.name} topu arkadaşının önüne bıraktı.`,p);}
   else{b.vx=this.direction(p.team)*6;b.vz*=.25;b.vy=-1;this.flight=null;}
  }else{
   b.vx=this.direction(p.team)*12;b.vz=(b.z>=0?1:-1)*8;b.vy=3;this.flight=null;this.emit('clearance','Savunma uzaklaştırdı',`${p.name} hava topunda araya girdi.`,p);
  }
  this.phase='open';this.planClock=0;return true;
 }
 integrateBall(dt){BallPhysics.step(this.ball,dt);}
 ballCrossing(x,limit=3){
  const b=this.ball,c=this.ballForecast;
  if(!c||c.ball!==b||c.time!==this.time||c.x!==b.x||c.y!==b.y||c.z!==b.z||c.vx!==b.vx||c.vy!==b.vy||c.vz!==b.vz)this.ballForecast={ball:b,time:this.time,x:b.x,y:b.y,z:b.z,vx:b.vx,vy:b.vy,vz:b.vz,planes:new Map()};
  const key=x+'|'+limit,cache=this.ballForecast.planes;if(!cache.has(key))cache.set(key,BallPhysics.atX(b,x,limit));return cache.get(key);
 }
 ballExit(exit){
  const b=this.ball,side=exit.sign;
  if(exit.kind==='touchline'){
   const team=1-(this.lastTouch?.team??0);this.setRestart('throw',team,{x:clamp(exit.point.x,-52,52),z:side*34});
   if(this.restart?.kind==='throw')this.emit('throw','Taç','Topun tamamı taç çizgisini geçti.',null,team);return;
  }
  const scoring=this.direction(0)===side?0:1,defending=1-scoring;
  if(PitchLaws.goalMouth(exit.point)){
   const f=this.flight;if(f?.restartKind&&((f.from.team!==scoring)||f.restartIndirect||f.restartKind==='throw')){const corner=f.from.team===defending;this.setRestart(corner?'corner':'goal-kick',corner?scoring:defending,corner?{x:side*51.8,z:33.8}:{x:side*47,z:5});this.emit('restart-goal-disallowed','Doğrudan gol geçersiz','Bu yeniden başlatmadan başka bir oyuncu dokunmadan gol olmaz.',null,defending);return;}
   if(!this.refereeGoal(scoring))return;
   this.score[scoring]++;if(this.flight?.kind==='shot'&&this.flight.from.team===scoring)this.onTarget[scoring]++;
   this.emit('goal','GOOOL!',this.lastTouch?.team===scoring?`${this.lastTouch.name} topu ağlara gönderdi!`:'Top savunmadan ağlara gitti.',this.lastTouch,scoring);
   if(this.lastTouch)this.action(this.lastTouch,'celebrate',2.2);this.owner=null;this.flight=null;this.kick=null;this.offsidePhase=null;this.phase='goal';this.goalPause={clock:1.6,team:defending};this.stoppageSerial++;b.x=exit.point.x+side*1e-7;b.vx*=.25;b.vz*=.25;this.planClock=0;this.settleDiscipline();return;
  }
  const corner=this.lastTouch?.team===defending,team=corner?scoring:defending;
  this.setRestart(corner?'corner':'goal-kick',team,corner?{x:side*51.8,z:(exit.point.z>=0?1:-1)*33.8}:{x:side*47,z:exit.point.z>=0?5:-5});
  if(this.restart?.kind===(corner?'corner':'goal-kick'))this.emit(corner?'corner':'goal-kick',corner?'Korner':'Aut',corner?'Top savunmadan kale çizgisini geçti.':'Topun tamamı kale çizgisini geçti.',null,team);
 }
 ballStep(dt){
  if(this.owner?.holdingBall&&this.owner.holdClock>0)return;
  if(this.offsideInterference())return;
  let remaining=dt;
  for(let contacts=0;remaining>1e-9&&contacts<5;contacts++){
   const b=this.ball,previous={x:b.x,y:b.y,z:b.z};this.integrateBall(remaining);
   const next={x:b.x,y:b.y,z:b.z},exit=PitchLaws.firstWholeBallExit(previous,next),frame=PitchLaws.sweepFrame(previous,next),hit=frame&&(!exit||frame.t<=exit.t)?frame:null,limit=hit||exit;
   if(limit){b.x=limit.point.x;b.y=limit.point.y;b.z=limit.point.z;}
   if(this.flight)this.flight.age+=remaining*(limit?.t??1);
   const incoming={vx:b.vx,vy:b.vy,vz:b.vz},owned=this.owner;
   if(!this.owner)this.keeper(previous,remaining*(limit?.t??1));
   if(this.owner!==owned||b.vx!==incoming.vx||b.vz!==incoming.vz)return;
   if(this.offsideInterference()||this.aerial(previous))return;
   const flight=this.flight,lastTouch=this.lastTouch;this.fieldBallContact(previous);
   if(this.restart||this.done||this.owner!==owned||this.lastTouch!==lastTouch||this.flight!==flight)return;
   if(hit){
    const v=PitchLaws.reflected({x:b.vx,y:b.vy,z:b.vz},hit.normal);b.vx=v.x;b.vy=v.y;b.vz=v.z;b.x+=hit.normal.x*1e-6;b.y+=hit.normal.y*1e-6;b.z+=hit.normal.z*1e-6;
    this.emit(hit.name,hit.name==='post'?'Direkten döndü!':'Üst direkten döndü!','Top kale çerçevesine çarptı ve oyunda kaldı.',this.lastTouch);this.telemetry.frameHits=(this.telemetry.frameHits||0)+1;
    remaining*=1-hit.t;continue;
   }
   if(exit)this.ballExit(exit);return;
  }
 }
 fieldBallContact(previous){
  const b=this.ball;
  // Blocks, interceptions and first touches happen only near the physical ball.
  if(b.y<1.05||this.flight?.kind==='shot'&&Math.min(b.y,previous.y)<1.9){
   const candidates=this.players.filter(p=>p.active&&!p.referee&&p.touchClock<=0&&!(p.duelRecovery>0)&&p.action!=='dive'&&!(p.role==='GK'&&this.flight?.kind==='shot'&&this.flight.from.team!==p.team)).map(p=>({p,hit:segment(p,previous,b)})).filter(o=>{const h=previous.y+(b.y-previous.y)*o.hit.u,radius=h>1.65?.28:h>1.05?.43:(o.p.role==='GK'?1.05:this.flight?.target===o.p?1.10:this.flight?.from.team===o.p.team?.92:.72);return h<1.90&&o.hit.d<radius;});
   candidates.sort((a,c)=>a.hit.u-c.hit.u||a.hit.d-c.hit.d);
   for(const {p,hit} of candidates){
    if(p===this.owner)continue;if(this.offsideTouch(p))return;
    const speed=Math.hypot(b.vx-p.vx,b.vz-p.vz);
    if(this.flight?.kind==='shot'&&p.team!==this.flight.from.team&&p.role!=='GK'){
     b.x=previous.x+(b.x-previous.x)*hit.u;b.y=previous.y+(b.y-previous.y)*hit.u;b.z=previous.z+(b.z-previous.z)*hit.u;
     const heading=Math.atan2(b.vz,b.vx);b.vx=-Math.cos(heading)*(4+this.random()*4);b.vz+=(this.random()-.5)*8;b.vy=1+this.random();this.lastTouch=p;this.flight=null;this.owner=null;this.phase='open';p.touchClock=.3;this.emit('block','Savunma kapattı',`${p.name} şutun önüne vücudunu koydu. Top oyunda!`,p);return;
    }
    if(b.y>=1.05)continue;
    if(speed>21&&p.role!=='GK'){b.vx*=.45;b.vz*=.45;b.vy=1.3;p.touchClock=.35;this.lastTouch=p;this.owner=null;this.flight=null;this.phase='open';this.telemetry.looseBalls++;return;}
    if(!this.owner||p.team!==this.owner.team&&dist(this.owner,b)>1.6){this.acquire(p);return;}
   }
  }
 }
 goalThreat(team){
  const b=this.ball,side=this.direction(team);if(b.vx*side>=0)return false;const crossing=this.ballCrossing(-side*52,1.6);return !!crossing&&Math.abs(crossing.z)<4.7&&crossing.y<2.9;
 }
 keeperVisibility(gk){
  for(const p of this.players){
   if(!p.active||p.referee||p===gk)continue;
   const hit=segment(p,gk,this.ball),height=1.62+(this.ball.y-1.62)*hit.u;
   if(hit.u>.06&&hit.u<.94&&hit.d<.43&&height>.18&&height<1.85)return false;
  }
  return true;
 }
 keeper(previous,dt){
  const f=this.flight,b=this.ball,team=this.direction(0)*b.vx>0?1:0;
  if(!this.goalThreat(team))return;
  if(this.lastTouch?.team===team&&['pass','throw','through','cutback','long-pass'].includes(f?.kind))return;
  const gk=this.team(team).find(p=>p.role==='GK');if(!gk)return;
  if(f&&!f.id)f.id=++this.releaseSerial;
  const key=f?.id??'loose-'+this.releaseSerial+'-'+this.lastTouch?.id;
  if(!gk.keeperRead||gk.keeperRead.key!==key)gk.keeperRead={key,visibleAt:null,screened:false};
  const read=gk.keeperRead,visible=this.keeperVisibility(gk);
  if(!visible&&!read.screened){read.screened=true;this.telemetry.screenedReads++;}
  if(visible&&read.visibleAt===null)read.visibleAt=this.time;
  const crossing=this.ballCrossing(gk.x,2.5),arrival=crossing?.t??-1,reaction=clamp(.23-((gk.reactions??gk.skill)-60)*.003,.12,.23);
  const reacted=read.visibleAt!==null&&this.time-read.visibleAt>=reaction,catchCapacity=17+(gk.handling??gk.skill)*.13;
  const lateral=arrival>0?Math.abs(crossing.z-gk.z):0,diveWindow=clamp(.20+lateral*.11,.28,.56);
  // Raising both hands for a central catch can begin before the narrower
  // dive commitment window. Judge catch preparation at the arrival speed.
  const catchable=crossing&&lateral<.55&&crossing.y>.08&&crossing.y<2.35&&Math.hypot(crossing.vx,crossing.vz)<catchCapacity&&gk.speed<2.3;
  const prepareWindow=catchable?Math.max(.40,diveWindow):diveWindow;
  if(!['dive','catch-ready'].includes(gk.action)&&reacted&&arrival>.025&&arrival<prepareWindow){
   const z=crossing.z,y=crossing.y;
   if(catchable){this.action(gk,'catch-ready',.65);gk.catchPoint={x:gk.x,y,z};}
   else if(Math.abs(z-gk.z)<3.1&&y<2.75){this.action(gk,'dive',1.05);gk.saveTarget={x:gk.x,y:Math.max(.16,y),z};gk.diveContactTime=Math.max(.08,arrival);gk.diveSide=Math.sign(z-gk.z)||1;}
  }
  if(!['dive','catch-ready'].includes(gk.action))return;
  const hands=this.motion?.saveHands(gk)||[{x:gk.x,y:1,z:gk.z}];
  const handContacts=hands.map(hand=>{
   const h=Array.isArray(hand)?{x:hand[0],y:hand[1],z:hand[2]}:hand,s=segment(h,previous,b);
   return {s,h,hit:Math.hypot(s.d,h.y-(previous.y+(b.y-previous.y)*s.u))<.25};
  }).filter(c=>c.hit).sort((a,c)=>a.s.u-c.s.u),handHits=handContacts.length;
  if(handHits){
   const u=handContacts[0].s.u;b.x=previous.x+(b.x-previous.x)*u;b.y=previous.y+(b.y-previous.y)*u;b.z=previous.z+(b.z-previous.z)*u;
   const speed=Math.hypot(b.vx,b.vz),pressure=Math.min(15,...this.field(1-team).map(p=>dist(p,gk))),inside=gk.x*this.direction(gk.team)<-35.5&&Math.abs(gk.z)<20,backpass=this.lastTouch?.team===team&&['pass','throw','through','cutback','long-pass'].includes(f?.kind);
   if(gk.action==='catch-ready'&&inside&&!backpass&&speed<catchCapacity&&(speed<22||handHits>=2)&&Math.abs(b.z-gk.z)<.9&&b.y>.08&&b.y<2.05&&pressure>2){
    const gatherStart=clamp(gk.actionElapsed/.22,0,1);
    if(f?.kind==='shot')this.onTarget[f.from.team]++;this.acquire(gk);gk.holdingBall=true;gk.holdClock=.75;gk.catchPoint={x:b.x,y:b.y,z:b.z};gk.gatherLift=b.y<.75?{height:b.y}:null;gk.gatherStart=gatherStart;gk.receiveClock=.75;gk.decision=.8;this.action(gk,'catch',.75);b.vx=b.vy=b.vz=0;
    this.telemetry.keeperCatches++;if(speed>=22)this.telemetry.fastCatches++;this.emit('save','Kaleci kontrol etti',`${gk.name} topu tuttu; takımının yerleşmesini bekliyor.`,gk);return;
   }
   if(f?.kind==='shot')this.onTarget[f.from.team]++;this.emit('save','Kaleciden kurtarış',`${gk.name} topu çeldi; seken top hâlâ oyunda!`,gk);
   b.vx=this.direction(team)*(4+this.random()*4);b.vz=(gk.diveSide||1)*(4+this.random()*4);b.vy=2+this.random();this.lastTouch=gk;this.owner=null;this.flight=null;this.phase='open';gk.touchClock=.8;this.telemetry.looseBalls++;this.planClock=0;
  }
 }
 kickoffReady(r){
  if(!r||r.kind!=='kickoff')return true;
  for(const p of this.players){if(!p.active||p.referee||p===r.taker)continue;
   if(p.x*this.direction(p.team)>.02)return false;
   if(p.team!==r.team&&Math.hypot(p.x,p.z)<9.15)return false;
  }
  return true;
 }
 restartReady(r){
  if(r?.kind==='penalty')return this.penaltyReady(r);
  if(!this.kickoffReady(r))return false;
  if(r?.kind==='free-kick'){
   const goal={x:this.direction(r.team)*52,z:0};if(dist(r.spot,goal)>=12&&this.team(1-r.team).some(p=>dist(p,r.spot)<9.15-1e-6))return false;
   const layout=this.freeKickLayout(r);
   if(layout){
    for(const [id,point] of layout.wall)if(dist(this.players[id],point)>.5)return false;
    if(layout.keeperId!==undefined&&dist(this.players[layout.keeperId],layout.keeperPoint)>1.2)return false;
    if(layout.wall.size>=3&&this.field(r.team).some(p=>p!==r.taker&&[...layout.wall.keys()].some(id=>dist(p,this.players[id])<1)))return false;
   }
  }
  if(r?.kind==='goal-kick')return this.team(1-r.team).every(p=>p.referee||p.x*this.direction(r.team)>=-35.5||Math.abs(p.z)>=20.16);
  return true;
 }
 restartStep(dt){
  const r=this.restart;if(!r?.taker?.active){if(r)this.setRestart(r.kind,r.team,r.spot);return;}
  if(r.kind==='penalty'){this.penaltyStep(r,dt);return;}
  r.clock-=dt;
  if(r.clock>0||dist(r.taker,r.spot)>1.4&&!r.setupPoint)return;
  if(!this.restartReady(r))return;
  const p=r.taker,options=this.passOptions(p),free=r.kind==='free-kick'?this.freeKickChoice(r):null;let best=free||options.find(o=>o.q.role!=='GK')||options[0],power=free?.power??null,height=free?.height;
  if(r.kind==='corner'){
   const pool=this.field(r.team).filter(q=>q!==p),forwards=pool.filter(q=>q.role==='ATT'),box={x:this.direction(r.team)*43,z:0};
   const target=nearest(forwards.length?forwards:pool,box);
   if(target){best={q:target,point:{x:target.x+target.vx*.4,z:target.z+target.vz*.4},kind:'cross'};power=22;}
  }
  // A short-passing instruction cannot make a dead ball wait forever when all
  // partners are outside the normal open-play range. Use a real distant outlet.
  if(!best){const q=nearest(this.team(r.team).filter(q=>q!==p),r.spot);if(q)best={q,point:{x:q.x,z:q.z},kind:dist(q,r.spot)>30?'long-pass':'pass'};}
  if(!best)return;
  let aim=best.point;
  let kind=free?.kind??(r.kind==='throw'?'throw':r.kind==='corner'?'cross':r.kind==='goal-kick'&&best.kind==='long-pass'?'long-pass':'pass');
  if(kind==='shot'){if(!r.shotAim)r.shotAim=this.aimShot(p,aim,r.spot);aim=r.shotAim;}
  if(r.kind!=='throw'){
   if(!r.setupPoint){r.pass={q:best.q,point:{...aim},kind,power,height};const a=Math.atan2(aim.z-r.spot.z,aim.x-r.spot.x),l=(p.kickFoot===0?-.18:.18);r.setupPoint={x:r.spot.x-Math.cos(a)*.88+Math.sin(a)*l,z:r.spot.z-Math.sin(a)*.88-Math.cos(a)*l};this.planClock=0;return;}
   if(dist(p,r.setupPoint)>.03)return;best.q=r.pass.q;aim=r.pass.point;kind=r.pass.kind;power=r.pass.power;height=r.pass.height;
  }
  this.restart=null;this.owner=p;this.phase='carry';this.lastTeam=r.team;
  this.startKick(p,kind,best.q,aim,r.kind==='throw'?clamp(dist(p,aim)/1.1,8,17):power,r);
  if(this.kick){this.kick.restartContext=r;this.kick.heightTarget=height;if(r.kind==='corner')this.kick.loft=true;}
 }
 kickStep(dt){
  const k=this.kick,p=k.p,b=this.ball;k.clock+=dt;
  if(k.kind==='pass'&&k.target?.active&&!k.loft&&!k.restartContext){const flight=clamp(this.passTime('pass',dist(p,k.target),this.passSpeed('pass',dist(p,k.target),this.t[p.team])),.2,1.6),point=this.receiverPoint(k.target,flight*.85);k.point={x:clamp(point.x,-50,50),z:clamp(point.z,-32,32)};}
  p.actionElapsed=k.clock;p.actionClock=Math.max(0,p.actionDuration-k.clock);
  const origin=k.restartContext&&k.kind!=='throw'?k.restartContext.spot:p;
  const a=Math.atan2(k.point.z-origin.z,k.point.x-origin.x),facing=!k.restartContext&&k.kind!=='throw'&&!this.touchContact(p,b,p.kickFoot).ready?Math.atan2(b.z-p.z,b.x-p.x):a;p.face+=clamp(angle(facing,p.face),-dt*7,dt*7);
  let point=this.contactPoint(p,k.kind);
  if(k.restartContext?.kind==='kickoff'){point[0]=k.restartContext.spot.x;point[2]=k.restartContext.spot.z;}
  if(k.restartContext&&k.kind!=='throw'){
   // The placed ball stays on its mark while the taker plants and turns.
   if(k.clock>k.duration+1.5&&Math.hypot(point[0]-b.x,point[2]-b.z)>.11){const r=k.restartContext;r.clock=0;this.kick=null;this.owner=null;this.restart=r;this.phase='restart';this.planClock=0;return;}
  }else if(k.kind==='throw'){
   if(k.kind==='throw')b.y+=clamp(point[1]-b.y,-4*dt,4*dt);
   const dx=point[0]-b.x,dz=point[2]-b.z,reach=Math.hypot(dx,dz),limit=3.5*dt;
   if(reach>0){b.x+=dx*Math.min(1,limit/reach);b.z+=dz*Math.min(1,limit/reach);}
  }else{
   // A short preparation touch gives the ball velocity; the ball then rolls freely.
   // The target includes the runner's travel, so running passes do not freeze the body.
   const gap=dist(p,b),reach=Math.hypot(point[0]-b.x,point[2]-b.z);
   if(gap<1.55&&this.time>=(k.nextControlTry||0)&&(!k.setupImpulse||k.clock>=k.duration&&reach>.10&&this.time>=(k.nextSetup||0))){
    const travel=k.setupImpulse?.09:Math.max(dt,k.duration-k.clock+dt),future={...p,x:p.x+p.vx*Math.max(0,travel-dt),z:p.z+p.vz*Math.max(0,travel-dt),face:a};
    const contact=this.contactPoint(future,k.kind),vx=(contact[0]-b.x)/travel,vz=(contact[2]-b.z)/travel,speed=Math.hypot(vx,vz)||1,limit=Math.min(10,p.speed+4.8),factor=Math.min(1,limit/speed);
    const impulse=Math.min(limit+1,BallPhysics.launchForGround(Math.hypot(contact[0]-b.x,contact[2]-b.z),travel));
    const plan=this.touchPlan(p,{vx:vx/speed*impulse,vz:vz/speed*impulse,vy:0},{mode:'setup',interval:k.setupImpulse?.09:Math.max(dt,k.duration-k.clock),target:k.point});
    if(plan.ready){Object.assign(b,plan.velocity);k.setupImpulse=true;k.nextSetup=this.time+.09;p.touchPosition={x:b.x,z:b.z};if(plan.limited)this.telemetry.limitedSetupTouches=(this.telemetry.limitedSetupTouches||0)+1;}
    else{k.nextControlTry=this.time+.05;this.telemetry.setupTouchDeferrals=(this.telemetry.setupTouchDeferrals||0)+1;}
   }
   this.integrateBall(dt);
   if(dist(p,b)>2.4||k.clock>k.duration+1.2){this.kick=null;this.owner=null;p.kickMoving=false;p.actionClock=0;p.decision=.1;this.phase='open';this.planClock=0;this.telemetry.abortedKicks=(this.telemetry.abortedKicks||0)+1;return;}
   if(k.clock>.08&&k.clock<k.duration+.4){const challenger=nearest(this.field(1-p.team),b);if(challenger&&dist(challenger,b)<1.02)this.doTackle(challenger,p);}
   if(this.reviewPass(k))return;
  }
  const reach=Math.hypot(point[0]-b.x,point[2]-b.z);
  if(this.kick===k&&k.clock+1e-9>=k.duration){
   const foot=this.touchContact(p,b,p.kickFoot),available=k.restartContext||k.kind==='throw'||foot.ready&&foot.footClock<=0&&(p.receiveClock||0)<=0&&b.y<.45;
   if(available&&reach<.11&&Math.abs(angle(a,p.face))<.07&&this.restartReady(k.restartContext))this.release();
   else{p.contactTime=k.clock+dt;p.actionDuration=p.contactTime+.22;p.actionClock=.22;}
  }
 }
 beginSecondHalf(){
  this.period=2;this.lifecycle='playing';this.half=true;this.offsidePhase=null;this.penaltyAttempt=null;
  for(const p of this.players){if(p.referee)continue;p.homeX*=-1;p.homeZ*=-1;const side=this.direction(p.team);p.x=side*(p.role==='GK'?-49:clamp(p.homeX*side-22,-42,-2));p.z=p.homeZ;p.vx=p.vz=p.speed=0;p.face=side===1?0:Math.PI;p.action='idle';p.actionClock=0;}
  const taker=this.field(1).find(p=>p.role==='MID')||this.field(1)[0]||this.team(1)[0];
  if(taker){taker.x=-.7*this.direction(1);taker.z=0;}
  this.setRestart('kickoff',1,{x:0,z:0},taker,true);this.emit('whistle','İkinci devre başladı','Takımlar kaleleri değiştirdi. İkinci devrenin santrası yapılıyor.',null,1);
 }
 resumeHalf(){if(!MatchRules.resume(this.matchClock))return false;this.beginSecondHalf();return true;}
 finishMatch(reason='full-time'){
  if(this.done)return;this.settleDiscipline?.();if(this.done)return;this.done=true;this.lifecycle='finished';this.matchClock.phase='finished';this.phase='finished';this.finishReason=reason;this.referee.pendingAdvantage=null;
  this.owner=null;this.kick=null;this.flight=null;this.restart=null;this.goalPause=null;this.targets.clear();for(const p of this.players){p.vx=p.vz=p.speed=0;}
  this.emit('end',reason==='minimum-players'?'Maç tatil edildi':'Maç sona erdi',reason==='minimum-players'?'Bir takım müsabakanın asgari oyuncu sayısının altına düştü.':`${this.score[0]}–${this.score[1]} · Hakem son düdüğü çaldı.`);
 }
 advanceClock(dt,stoppedReason,stoppageId){
  const result=MatchRules.tick(this.matchClock,dt,{stoppedReason,stoppageId,penaltyPending:!!this.penaltyAttempt&&this.penaltyAttempt.state!=='settled'});
  this.period=this.matchClock.period;this.lifecycle=this.matchClock.phase;
  if(result.announcedAdded>0)this.emit('added-time','Ek süre',`Hakem bu devre için en az ${Math.ceil(result.announcedAdded)} saniye ekledi.`);
  if(result.transition==='halftime'){
   this.settleDiscipline?.();this.referee.pendingAdvantage=null;this.offsidePhase=null;this.penaltyAttempt=null;this.owner=null;this.kick=null;this.flight=null;this.restart=null;this.goalPause=null;this.targets.clear();
   for(const p of this.players){p.vx=p.vz=p.speed=0;p.actionClock=0;p.action='idle';}
   this.phase='halftime';this.emit('half','Devre arası','Maç saati durdu. Takımlar ikinci devrede kaleleri değiştirecek.');
  }else if(result.transition==='second-half')this.beginSecondHalf();else if(result.transition==='finished')this.finishMatch();
 }
 step(dt=1/60){
  if(this.done||!Number.isFinite(dt)||dt<=0)return;
  if(this.lifecycle==='playing'&&!this.restart&&!this.kick?.restartContext&&!this.goalPause&&!this.substitutionPause?.remaining&&(!this.penaltyAttempt||this.penaltyAttempt.state==='settled')){const remaining=MatchRules.clockView(this.matchClock).remaining;if(remaining>1e-8&&remaining<dt)dt=remaining;}
  this.time+=dt;
  if(this.lifecycle==='halftime'){this.advanceClock(dt,null,null);return;}
  const stoppedReason=this.substitutionPause?.remaining>0?'substitution':this.goalPause?'goal':this.restart||this.kick?.restartContext?'restart':null,stoppageId=(this.restart||this.kick?.restartContext)?.id??this.stoppageSerial;
  if(this.substitutionPause?.remaining>0){this.substitutionPause.remaining=Math.max(0,this.substitutionPause.remaining-dt);this.advanceClock(dt,stoppedReason,stoppageId);return;}
  if(!this.restart&&!this.kick?.restartContext&&!this.goalPause){const t=this.owner?.team??this.flight?.from.team;if(t===0||t===1)this.possession[t]+=dt;}
  for(const p of this.players){p.duelRecovery=Math.max(0,(p.duelRecovery||0)-dt);p.feintCooldown=Math.max(0,(p.feintCooldown||0)-dt);p.feintReaction=Math.max(0,(p.feintReaction||0)-dt);p.feintClock=Math.max(0,(p.feintClock||0)-dt);p.touchClock=Math.max(0,(p.touchClock||0)-dt);p.tackleClock=Math.max(0,(p.tackleClock||0)-dt);p.receiveClock=Math.max(0,(p.receiveClock||0)-dt);p.footTouch=Math.max(0,(p.footTouch||0)-dt);if(p.actionClock>0){p.actionClock=Math.max(0,p.actionClock-dt);p.actionElapsed+=dt;if(p.actionClock===0)p.action='idle';}
   if(p.holdClock>0){p.holdClock=Math.max(0,p.holdClock-dt);
    if(p.gatherLift&&this.owner===p){const t=clamp((.75-p.holdClock)/.60,0,1),u=t*t*(3-2*t),height=p.gatherLift.height+(.95-p.gatherLift.height)*u;this.ball.y+=clamp(height-this.ball.y,-1.8*dt,1.8*dt);if(p.catchPoint)p.catchPoint.y=this.ball.y;}
    if(!p.holdClock){p.holdingBall=false;p.catchPoint=null;p.gatherLift=null;p.gatherStart=null;p.receiveClock=.15;p.decision=.18;if(this.owner===p)this.ball.vy=-.3;}}
  }
  Perception.update(this.players,this.time,dt,{scanAllowed:!this.restart&&!this.kick?.restartContext&&!this.goalPause});this._perceptionActive=true;
  this.planClock-=dt;
  if(this.planClock<=0){this.plan();this.planClock=.16;}
  for(const [p,target] of this.targets)this.move(p,target,dt);
  // Small separation impulses keep shoulders from occupying the same space.
  const bodies=this.players.filter(p=>p.active&&!p.referee);
  for(let i=0;i<bodies.length;i++)for(let j=i+1;j<bodies.length;j++){const a=bodies[i],b=bodies[j],dx=a.x-b.x,dz=a.z-b.z,d=Math.hypot(dx,dz);if(d<.58){const n=d||1,nx=d?dx/n:(a.id%2?1:-1),nz=d?dz/n:0,push=Math.min((.58-d)*.35,dt*.8);if(this.kick?.p!==a){a.x+=nx*push;a.z+=nz*push;}if(this.kick?.p!==b){b.x-=nx*push;b.z-=nz*push;}}}
  if(this.goalPause){
   this.goalPause.clock-=dt;const b=this.ball;b.x+=b.vx*dt;b.z+=b.vz*dt;b.y=Math.max(.11,b.y+b.vy*dt);b.vy-=9.81*dt;b.vx*=.96;b.vz*=.96;
   if(Math.abs(b.x)>54){b.x=Math.sign(b.x)*54;b.vx*=-.15;}b.z=clamp(b.z,-3.5,3.5);
   if(this.goalPause.clock<=0){const team=this.goalPause.team;this.setRestart('kickoff',team,{x:0,z:0});this.restart.clock=1.5;}
  }else if(this.restart)this.restartStep(dt);
  else if(this.kick)this.kickStep(dt);
  else{
   if(this.owner){
    const p=this.owner;p.carryTime=(p.carryTime||0)+dt;
    if(!p.active||dist(p,this.ball)>3.2){this.owner=null;this.phase='open';this.telemetry.looseBalls++;this.planClock=0;}
    else if(p.holdingBall){/* Hands retain a caught ball until the keeper drops it. */}
    else{
     p.decision-=dt;
     if(p.decision<=0&&p.receiveClock<=0&&this.ball.y<.45&&dist(p,this.ball)<1.45){
      const choice=this.postReceiveHold(p,this.preparedChoice(p)||this.choose(p));p.decision=.16+(100-(+this.t[p.team].tempo))*.004+this.random()*.10;
      if(choice.holdContinuation)this.telemetry.holdContinuations=(this.telemetry.holdContinuations||0)+1;
      const decisionType=['pass','through','cross','cutback','long-pass'].includes(choice.kind)?'pass':choice.kind;this.telemetry.decisions[decisionType]=(this.telemetry.decisions[decisionType]||0)+1;
      if(choice.kind==='carry'||choice.kind==='feint'){
       this.startCarry(p,choice);
      }
      else if(choice.kind==='shot')this.startKick(p,'shot',null,choice.point);
      else{this.startKick(p,choice.kind,choice.q,choice.point);if(this.kick){this.kick.plannedRun=choice.plannedRun;this.kick.duelOutlet=choice.duelOutlet;this.kick.supportContinuation=choice.supportContinuation;}}
     }
     if(!this.kick&&p.touchClock<=0&&p.receiveClock<=0&&this.ball.y<.45&&dist(p,this.ball)<1.3){
      this.dribbleTouch(p);
     }
     if(!this.kick){const defender=nearest(this.field(1-p.team),this.ball);if(defender)this.doTackle(defender,p);}
    }
   }
   if(!this.restart&&!this.kick)this.ballStep(dt);
  }
  const carrier=this.owner,duel=carrier?.dribbleDuel;
  if(duel){const defender=this.players[duel.opponentId];if(!defender?.active||this.time-duel.at>4.5)carrier.dribbleDuel=null;else if((carrier.x-defender.x)*this.direction(carrier.team)>1.5&&dist(carrier,defender)>2.5&&dist(carrier,this.ball)<1.3){this.telemetry.beatenDefenders++;carrier.dribbleDuel=null;}}
  this.updateReferee?.(dt);if(!this.done)this.advanceClock(dt,stoppedReason,stoppageId);
 }
 advance(seconds){const n=Math.round(seconds*60);for(let i=0;i<n&&!this.done;i++)this.step();}
 canSubstitute(){const r=this.restart,decision=MatchRules.substitutionAllowance(this.rules,this.substitutionState,{phase:this.lifecycle,deadBall:!!r||!!this.goalPause,stoppageId:r?.id??(this.goalPause?'goal-'+this.releaseSerial:null)});return {...decision,reason:decision.error,remaining:decision.remainingSubstitutions,windowsRemaining:decision.remainingWindows};}
 bench(){const ids=this.startingRosterIds||this.cfg.starters||[];return (this.cfg.players||[]).filter(p=>p.owned!==false&&!ids.includes(p.id)&&!this.usedBench.has(p.id));}
 substitute(index,id){
  const decision=this.canSubstitute();if(!decision.ok)return {ok:false,error:decision.reason};
  const p=this.players.find(p=>p.team===0&&p.index===index&&p.active),b=this.bench().find(p=>p.id===id);
  if(!p||!b||this.done)return {ok:false,error:'Uygun bir oyuncu ve kullanılmamış yedek seç.'};
  if(this.restart?.taker===p)return {ok:false,error:'Duran topu kullanacak oyuncu hazırlıkta; başka bir oyuncu seç.'};
  if(this.owner===p||this.kick?.p===p||this.flight?.target===p)return {ok:false,error:'Oyuncunun top aksiyonu sürüyor; pozisyon bitince tekrar dene.'};
  const old=p.name,profile=PlayerModel.forSlot(b,PlayerModel.slotFor(this.cfg.formation||'4-3-3',p.index));
  Object.assign(p,profile,{id:p.id,index:p.index,team:p.team,role:p.role,position:p.position,rosterId:b.id,name:b.name,num:b.number,portraitId:b.face,yellow:0,energy:1,kickFoot:profile.preferredFoot,reception:null,nextAction:null,runIntent:null,supportIntent:null,offerIntent:null,connectionIntent:null,carryIntent:null,keeperRead:null,shieldUntil:0,shieldReadyAt:0,duelMemory:null,dribbleDuel:null});
  Intent.clear(p,'substitution',this.taskContext(p));Perception.clear(p,this.time);
  this.usedBench.add(b.id);MatchRules.recordSubstitution(this.substitutionState,decision);this.subCount=this.substitutionState.count;this.subWindowsUsed=this.substitutionState.windowsUsed;
  if(this.lifecycle!=='halftime')this.substitutionPause={remaining:(this.substitutionPause?.remaining||0)+this.rules.substitutionPauseSeconds};
  this.emit('sub','Oyuncu değişikliği',`${old} çıktı, ${b.name} oyuna girdi.`,p);return {ok:true};
 }
}
const api={Match,formations,segment,distance:dist,BallPhysics};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.TribunFootball=api;
})(typeof window!=='undefined'?window:globalThis);
