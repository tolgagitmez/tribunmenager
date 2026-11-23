'use strict';

// Read-only presentation cues sampled after each fixed simulation step.
(function(root){
const poseFields=[
 'face','vx','vz','speed','action','actionClock','actionDuration','actionElapsed',
 'kickFoot','kickMoving','contactTime','footTouch','touchPosition','dribbleFoot',
 'diveSide','diveForward','diveContactTime','saveTarget','catchPoint','gatherStart',
 'headerHeight','jumpHeight','chestContactHeight','receiveClock','receiveMode','holdingBall','holdClock'
];
const keeperPreparation=action=>action==='catch-ready'||action==='dive';
const cueWindowSeconds=2;

function create(){
 let observed=null,previousTime,previousOwner,previousFlight,eventIndex,tick=0,serial=0;
 const cues=[],keeperActions=new Map();
 function reset(){
  observed=null;tick=0;serial=0;cues.length=0;keeperActions.clear();
 }
 function observe(match){
  if(observed!==match||match.time<previousTime){
   reset();observed=match;previousTime=match.time;previousOwner=match.owner;
   previousFlight=match.flight;eventIndex=match.events.length;
   for(const p of match.players)if(p.active&&p.role==='GK')keeperActions.set(p.id,p.action);
   return;
  }
  if(match.time===previousTime)return;
  tick++;
  const flight=match.flight;
  function record(kind,p,f=flight){
   const actor={x:p.x,z:p.z};
   for(const key of poseFields){
    const value=p[key];
    if(value!==undefined)actor[key]=value&&typeof value==='object'?{...value}:value;
   }
   cues.push({id:++serial,tick,time:match.time,kind,playerId:p.id,
    flightId:f?.id??null,kickKind:f?.kind??null,targetId:f?.target?.id??null,
    ball:{...match.ball},actor});
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
  previousTime=match.time;previousOwner=match.owner;previousFlight=flight;
 }
 return {observe,reset,recent:()=>cues.slice()};
}
const api={create,poseFields};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else root.TribunContactEvents=api;
})(typeof window!=='undefined'?window:globalThis);
