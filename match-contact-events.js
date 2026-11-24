'use strict';

// Read-only presentation cues sampled after each fixed simulation step.
(function(root){
const poseFields=[
 'face','vx','vz','speed','action','actionClock','actionDuration','actionElapsed',
 'kickFoot','kickMoving','contactTime','footTouch','touchPosition','dribbleFoot',
 'diveSide','diveForward','diveContactTime','saveTarget','catchPoint','gatherStart',
 'headerHeight','jumpHeight','chestContactHeight','receiveClock','receiveMode','holdingBall','holdClock',
 'brainRole','touchMode','shieldFace','feintClock','feintSign',
 'feintResponseClock','feintResponseSign','wallPassClock','wallPassFoot'
];
const keeperPreparation=action=>action==='catch-ready'||action==='dive';
const cueWindowSeconds=2;
const groundPassKinds=new Set(['pass','through','cutback']);

function rollingOnTurf(ball){
 const radius=root.TribunFootball?.BallPhysics?.radius;
 return Number.isFinite(radius)&&ball?.y===radius&&ball.vy===0;
}

function groundControl(match,p,flight){
 const {kickFoot:foot,receiveMode:mode}=p;
 const {lastGain,ball}=match;
 if(flight?.target!==p||flight.from?.team!==p.team||flight.from===p||!groundPassKinds.has(flight.kind)||
  p.action!=='receive'||(mode!=='open'&&mode!=='protect')||(foot!==0&&foot!==1))return null;
 if(lastGain?.time!==match.time||lastGain.player!==p.id||lastGain.x!==ball.x||lastGain.z!==ball.z)return null;
 if(![p.x,p.z,p.face,ball.x,ball.z,ball.vx,ball.vz].every(Number.isFinite))return null;
 // A prepared rolling ground pass keeps these modes only if the receive
 // touch plan succeeds and writes the selected foot to the actor.
 return {foot,mode};
}

function create(){
 let observed=null,previousTime,previousOwner,previousFlight,previousRolling,eventIndex,tick=0,serial=0;
 const cues=[],keeperActions=new Map();
 function reset(){
  observed=null;tick=0;serial=0;cues.length=0;keeperActions.clear();
 }
 function observe(match){
  if(observed!==match||match.time<previousTime){
   reset();observed=match;previousTime=match.time;previousOwner=match.owner;
   previousFlight=match.flight;previousRolling=rollingOnTurf(match.ball);eventIndex=match.events.length;
   for(const p of match.players)if(p.active&&p.role==='GK')keeperActions.set(p.id,p.action);
   return;
  }
  if(match.time===previousTime)return;
  tick++;
  const flight=match.flight,rolling=rollingOnTurf(match.ball);
  function record(kind,p,f=flight){
   const actor={x:p.x,z:p.z};
   for(const key of poseFields){
    const value=p[key];
    if(value!==undefined)actor[key]=value&&typeof value==='object'?{...value}:value;
   }
   const cue={id:++serial,tick,time:match.time,kind,playerId:p.id,
    flightId:f?.id??null,kickKind:f?.kind??null,targetId:f?.target?.id??null,
    ball:{...match.ball},actor};
   if(kind==='receive'&&previousRolling&&rolling){
    const control=groundControl(match,p,f);
    if(control)cue.control=control;
   }
   cues.push(cue);
   if(cues.length>64)cues.shift();
  }
  if(flight&&flight!==previousFlight&&flight.age<=match.time-previousTime+1e-6){
   record('release',flight.from);
  }
  for(const p of match.players){
   if(!p.active||p.role!=='GK')continue;
   if(keeperPreparation(p.action)&&p.action!==keeperActions.get(p.id))record('keeper-prepare',p);
   keeperActions.set(p.id,p.action);
  }
  if(match.owner&&match.owner!==previousOwner&&match.owner.role!=='GK')record('receive',match.owner,previousFlight);
  for(;eventIndex<match.events.length;eventIndex++){
   const event=match.events[eventIndex];
   if(event.type==='save'){
    const keeper=match.players.find(p=>p.id===event.playerId&&p.role==='GK');
    if(keeper)record('keeper-contact',keeper,previousFlight);
   }
  }
  while(cues.length&&match.time-cues[0].time>cueWindowSeconds)cues.shift();
  previousTime=match.time;previousOwner=match.owner;previousFlight=flight;previousRolling=rolling;
 }
 return {observe,reset,recent:()=>cues.slice()};
}
const api={create,poseFields};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else root.TribunContactEvents=api;
})(typeof window!=='undefined'?window:globalThis);
