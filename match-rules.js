'use strict';
/* Competition configuration and period clocks. Physics and referee decisions
   remain in Match; this module contains no player or ball repositioning. */
(function(root){
const finite=(value,fallback,low,high)=>typeof value==='number'&&Number.isFinite(value)?Math.max(low,Math.min(high,value)):fallback;
const integer=(value,fallback,low,high)=>Math.round(finite(value,fallback,low,high));
const epsilon=1e-8;
function normalize(config={}){
 const raw=config?.rules&&typeof config.rules==='object'?config.rules:{},minutes=[5,15,90].includes(Number(config.matchMinutes))?Number(config.matchMinutes):5;
 return {
  periodSeconds:finite(raw.periodSeconds,minutes*30,.1,5400),
  halftimeSeconds:finite(raw.halftimeSeconds,8,0,900),
  maxSubstitutions:integer(raw.maxSubstitutions,5,0,11),
  substitutionWindows:integer(raw.substitutionWindows,3,0,11),
  minPlayers:integer(raw.minPlayers,7,1,11),
  substitutionPauseSeconds:finite(raw.substitutionPauseSeconds,3,0,60),
  restartGraceSeconds:finite(raw.restartGraceSeconds,8,0,60),
  roundSeconds:finite(raw.roundSeconds,1,.01,60),
  addedTime:raw.addedTime!==false,
  maxAddedSeconds:raw.maxAddedSeconds===null||raw.maxAddedSeconds===undefined?null:finite(raw.maxAddedSeconds,null,0,1800)
 };
}
function createClock(rules){
 return {rules:{...rules},period:1,phase:'playing',periodElapsed:0,elapsed:0,breakElapsed:0,
  lostSeconds:[0,0],announcedAdded:[null,null],addedAfterAnnouncement:[0,0],
  periodLengths:[null,null],stoppageId:null,stoppageElapsed:0};
}
function capAdded(clock,seconds){return clock.rules.maxAddedSeconds===null?seconds:Math.min(clock.rules.maxAddedSeconds,seconds);}
function addedTarget(clock){const i=clock.period-1;return clock.rules.addedTime?capAdded(clock,(clock.announcedAdded[i]??0)+clock.addedAfterAnnouncement[i]):0;}
function announce(clock){
 const i=clock.period-1;if(clock.announcedAdded[i]!==null)return null;
 const rounded=clock.rules.addedTime?Math.ceil(Math.max(0,clock.lostSeconds[i]-epsilon)/clock.rules.roundSeconds)*clock.rules.roundSeconds:0;
 clock.announcedAdded[i]=capAdded(clock,rounded);return clock.announcedAdded[i];
}
function resume(clock){
 if(clock.phase!=='halftime')return false;
 clock.period=2;clock.phase='playing';clock.periodElapsed=0;clock.stoppageId=null;clock.stoppageElapsed=0;return true;
}
function tick(clock,seconds,context={}){
 const result={transition:null,announcedAdded:null};
 if(clock.phase==='finished'||!(seconds>=0)||!Number.isFinite(seconds))return result;
 clock.elapsed+=seconds;
 if(clock.phase==='halftime'){
  clock.breakElapsed=Math.min(clock.rules.halftimeSeconds,clock.breakElapsed+seconds);
  if(clock.breakElapsed+epsilon>=clock.rules.halftimeSeconds){resume(clock);result.transition='second-half';}
  return result;
 }
 const reason=context.stoppedReason||null,key=reason?(context.stoppageId??reason):null;
 if(key!==clock.stoppageId){clock.stoppageId=key;clock.stoppageElapsed=0;}
 const i=clock.period-1,nominal=clock.rules.periodSeconds;
 function apply(dt){
  let lost=0;
  if(reason){
   const before=clock.stoppageElapsed;clock.stoppageElapsed+=dt;
   const grace=reason==='restart'?clock.rules.restartGraceSeconds:0;
   lost=Math.max(0,clock.stoppageElapsed-grace)-Math.max(0,before-grace);
  }
  clock.periodElapsed+=dt;
  if(clock.rules.addedTime){clock.lostSeconds[i]+=lost;if(clock.announcedAdded[i]!==null)clock.addedAfterAnnouncement[i]+=lost;}
 }
 // Split a large controlled tick at the nominal end. Pre-announcement delays
 // are rounded once; delays in added time extend that minimum separately.
 if(clock.announcedAdded[i]===null&&clock.periodElapsed<nominal-epsilon&&clock.periodElapsed+seconds>=nominal-epsilon){
  const first=Math.min(seconds,Math.max(0,nominal-clock.periodElapsed));apply(first);result.announcedAdded=announce(clock);apply(Math.max(0,seconds-first));
 }else{
  if(clock.announcedAdded[i]===null&&clock.periodElapsed>=nominal-epsilon)result.announcedAdded=announce(clock);
  apply(seconds);
  if(clock.announcedAdded[i]===null&&clock.periodElapsed>=nominal-epsilon)result.announcedAdded=announce(clock);
 }
 if(clock.periodElapsed+epsilon>=nominal+addedTarget(clock)&&!context.penaltyPending){
  clock.periodLengths[i]=clock.periodElapsed;
  if(clock.period===1){clock.phase='halftime';clock.breakElapsed=0;result.transition='halftime';}
  else{clock.phase='finished';result.transition='finished';}
 }
 return result;
}
function clockView(clock){
 const period=clock.period,nominal=clock.rules.periodSeconds,elapsed=clock.periodElapsed;
 return {period,phase:clock.phase,periodElapsed:elapsed,elapsed:clock.elapsed,
  displaySeconds:(period-1)*nominal+Math.min(nominal,elapsed),
  nominalElapsed:(period-1)*nominal+Math.min(nominal,elapsed),
  addedElapsed:Math.max(0,elapsed-nominal),announcedAddedSeconds:clock.announcedAdded[period-1],
  addedTargetSeconds:addedTarget(clock),remaining:Math.max(0,nominal+addedTarget(clock)-elapsed),
  breakRemaining:clock.phase==='halftime'?Math.max(0,clock.rules.halftimeSeconds-clock.breakElapsed):0,
  regulationSeconds:nominal*2,lostSeconds:[...clock.lostSeconds]};
}
function durationLabel(seconds){const rounded=Math.max(0,Math.floor(seconds+epsilon));return String(Math.floor(rounded/60)).padStart(2,'0')+':'+String(rounded%60).padStart(2,'0');}
function formatClock(clock){const view=clockView(clock);return durationLabel(view.displaySeconds)+(view.periodElapsed>=clock.rules.periodSeconds-epsilon&&(view.announcedAddedSeconds>0||view.addedElapsed>epsilon)?' +'+durationLabel(view.addedElapsed):'');}
function createSubstitutionState(){return {count:0,windowsUsed:0,usedWindows:[]};}
function substitutionAllowance(rules,state,context={}){
 const result={ok:false,error:'',usesWindow:false,windowKey:null,remainingSubstitutions:Math.max(0,rules.maxSubstitutions-state.count),remainingWindows:Math.max(0,rules.substitutionWindows-state.windowsUsed)};
 if(context.phase==='finished'||context.phase==='abandoned'){result.error='Maç bittikten sonra oyuncu değişikliği yapılamaz.';return result;}
 if(state.count>=rules.maxSubstitutions){result.error='Müsabakanın oyuncu değişikliği hakkı doldu.';return result;}
 const halftime=context.phase==='halftime';
 if(!halftime&&!context.deadBall){result.error='Oyuncu değişikliği için oyunun durmasını bekle.';return result;}
 if(!halftime){
  if(context.stoppageId===undefined||context.stoppageId===null){result.error='Oyuncu değişikliği için bir sonraki duruşu bekle.';return result;}
  result.windowKey=String(context.stoppageId);result.usesWindow=!state.usedWindows.includes(result.windowKey);
  if(result.usesWindow&&state.windowsUsed>=rules.substitutionWindows){result.error='Müsabakanın oyuncu değişikliği pencereleri doldu.';return result;}
 }
 result.ok=true;return result;
}
function recordSubstitution(state,decision){
 if(!decision.ok)return false;state.count++;
 if(decision.usesWindow){state.windowsUsed++;state.usedWindows.push(decision.windowKey);}
 return true;
}
function abandonment(rules,counts){const team=counts.findIndex(count=>count<rules.minPlayers);return team<0?null:{team,reason:'minimum-players',minimum:rules.minPlayers,remaining:counts[team]};}
const api={normalize,createClock,tick,resume,clockView,formatClock,createSubstitutionState,substitutionAllowance,recordSubstitution,abandonment};
root.TribunMatchRules=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
