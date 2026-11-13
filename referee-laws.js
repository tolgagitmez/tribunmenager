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
const api={insidePenaltyArea,classifyFoul};root.TribunRefereeLaws=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
