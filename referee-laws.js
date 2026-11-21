'use strict';
(function(root){
const insidePenaltyArea=(p,side)=>p.x*side>=35.5-1e-8&&p.x*side<=52+1e-8&&Math.abs(p.z)<=20.16+1e-8;
function classifyFoul(c){
 const side=c.attackDirection,incident={x:c.spot.x,z:c.spot.z},penalty=insidePenaltyArea(incident,side),v=c.victim;
 const control=c.ball&&Math.hypot(c.ball.x-v.x,c.ball.z-v.z)<1.6&&c.ball.y<1.5;
 const forward=(v.vx||0)*side>.3||Math.cos(v.face||0)*side>.65;
 const cover=(c.players||[]).filter(p=>p.active!==false&&p.team===c.offender.team&&p.id!==c.offender.id&&p.role!=='GK'&&(p.x-v.x)*side>0&&Math.abs(p.z-v.z)<7);
 const dogso=!!control&&forward&&52-incident.x*side<35&&Math.abs(incident.z)<20&&cover.length===0;
 const card=c.serious||c.violent?'red':dogso?(penalty&&c.attemptedBall?'yellow':'red'):c.reckless?'yellow':'none';
 return {restart:penalty?'penalty':'free-kick',team:v.team,spot:penalty?{x:41*side,z:0}:{...incident},incident,card,dogso,reason:c.violent?'violent-conduct':c.serious?'serious-foul-play':dogso?'denial-of-goal-opportunity':c.reckless?'reckless':'careless'};
}
// Law 11: only playing parts (head, trunk, feet), never hands or arms.
// Explicit observed rig landmarks may be supplied in offsideBodyParts. For
// ordinary engine players, conservative physical head/foot projections are
// derived from position and orientation at the pass contact.
function offsideBodyPoint(p,side){
 const supplied=p.offsideBodyParts;
 if(supplied){
  const parts=Array.isArray(supplied)?supplied:Object.entries(supplied).map(([part,point])=>({part,...point}));
  const legal=parts.filter(point=>['head','torso','body','leftFoot','rightFoot','foot','leftLeg','rightLeg'].includes(point.part)&&Number.isFinite(point.x));
  if(legal.length)return Math.max(...legal.map(point=>point.x*side));
 }
 const heading=Math.cos(p.face||0)*side;
 const body=p.x*side,head=body+heading*.23,frontFoot=body+heading*.16+Math.min(.15,Math.abs(p.speed||0)*.012);
 return Math.max(body,head,frontFoot);
}
function offsideLineOfDefenders(defenders,side){
 const positions=defenders.filter(p=>p.active!==false).map(p=>offsideBodyPoint(p,side)).sort((a,b)=>b-a);
 return positions[1]??52;
}
function penaltyPositionSnapshot({players,team,side,takerId,spot}){
 const keeper=players.find(p=>p.active!==false&&p.team===1-team&&p.role==='GK');
 const attacking=[],defending=[];
 for(const p of players){
  if(p.active===false||p.referee||p.id===takerId||p===keeper)continue;
  const feet=Array.isArray(p.penaltyFeet)?p.penaltyFeet:[{x:p.x,z:p.z}];
  if(feet.some(q=>q.x*side>35.5+1e-7&&Math.abs(q.z)<20.16+1e-7||
    Math.hypot(q.x-spot.x,q.z-spot.z)<9.15-1e-7||q.x*side>spot.x*side+1e-7)){
   (p.team===team?attacking:defending).push(p.id);
  }
 }
 // A foot on / vertically above / behind the goal line is lawful.
 const feet=keeper?(Array.isArray(keeper.penaltyFeet)?keeper.penaltyFeet:
  [{x:keeper.x+Math.cos(keeper.face||0)*.12},{x:keeper.x-Math.cos(keeper.face||0)*.12}]):[];
 const keeperOffLine=!!keeper&&feet.length>0&&feet.every(f=>f.x*side<52-1e-7);
 return {attacking,defending,keeperId:keeper?.id??null,keeperOffLine};
}
// The revised Law 14 punishes early entry only if the player impacts play.
// A GK off the line requires a retake when the GK prevents a goal, but a
// scored goal stands and an unaffected miss is not automatically retaken.
function penaltyDecision({keeperOffLine=false,goal=false,keeperSaved=false,
 attackingImpact=false,defendingImpact=false,keeperDistractedKicker=false}={}){
 if(attackingImpact&&defendingImpact)return {kind:'retake',reason:'both-teams-impact'};
 // If an early attacker clearly distracted the goalkeeper and the kick
 // scored, retake; an entrant who actually plays a rebound is dealt with
 // earlier as an indirect free kick by the engine's touch adjudicator.
 if(goal)return {kind:attackingImpact?'retake':'goal',reason:attackingImpact?'attacker-impact':'scored'};
 if(attackingImpact)return {kind:'indirect-free-kick',reason:'attacker-impact'};
 if(defendingImpact)return {kind:'retake',reason:'defender-impact'};
 if(keeperOffLine&&(keeperSaved||keeperDistractedKicker))return {kind:'retake',reason:'keeper-line'};
 return {kind:'play-on',reason:'no-material-impact'};
}
const api={insidePenaltyArea,classifyFoul,offsideBodyPoint,offsideLineOfDefenders,penaltyPositionSnapshot,penaltyDecision};root.TribunRefereeLaws=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
