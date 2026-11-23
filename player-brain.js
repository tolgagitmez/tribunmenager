'use strict';
/* Deterministic, local-information player tendencies. Never reads global opponents,
   changes ball physics or draws RNG: Match remains the authority for feasibility. */
(function(root){
const clamp=(x,min,max)=>Math.max(min,Math.min(max,x));
const stat=(p,key,fallback=75)=>Number.isFinite(p?.[key])?clamp(p[key],0,100):fallback;
const advance=(p,point,forward)=>Number.isFinite(point?.x)?(point.x-p.x)*forward:0;
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
function passBias(p,{kind='pass',forwardGain=0,pressure=12,risk=0,space=5,arrivalRisk=0}={}){
 const vision=stat(p,'vision'),passing=stat(p,'passing'),composure=stat(p,'composure');
 const skill=.52*vision+.48*passing,progress=clamp(forwardGain/24,0,1),exposure=clamp((5-pressure)/5,0,1);
 const dependable=clamp((skill-74)/24,-.85,1),calm=clamp((composure-70)/30,-.6,1);
 const danger=clamp(risk,0,1)*.7+clamp(arrivalRisk,0,1)*.3;
 if(kind==='through'){
  // Reward the *read*, never erase an offside, interception or arrival check.
  return clamp((dependable*4.1+calm*.8)*progress*(.55+.45*clamp(space/7,0,1))
   -Math.max(0,exposure-.45)*(1-calm)*2-Math.max(0,danger-.45)*3,-4,5);
 }
 return clamp(dependable*2.0*progress+calm*.45*progress-danger*Math.max(0,2.1-passing/55)
  -exposure*Math.max(0,74-composure)*.035,-2.5,2.8);
}
function canThread(p,{forwardGain=0,aligned=false,pressure=10}={}){
 return (p?.role==='MID'||p?.role==='ATT')&&stat(p,'vision')>=86&&stat(p,'passing')>=82
  &&stat(p,'composure')>=72&&forwardGain>3.5&&aligned&&pressure>2.4;
}
function carryBias(p,{forwardGain=0,clearance=0,turn=0,point=null}={}){
 const control=.48*stat(p,'dribbling')+.29*stat(p,'agility')+.23*stat(p,'acceleration');
 const attacking=['LW','RW','LM','RM','AM','CF','ST'].includes(p?.position)||p?.role==='ATT';
 const forward=clamp(forwardGain/5.5,0,1),space=clamp((clearance-.8)/2.8,0,1);
 const foot=p?.footPreference;
 const naturalCut=point&&Math.abs(point.z)<Math.abs(p.z)-.8
  &&(foot==='both'||foot==='right'&&p.z<0||foot==='left'&&p.z>0);
 const bias=(control-75)*.15*forward*space*(attacking?1:.65);
 return clamp(bias+(naturalCut&&attacking?.9:0)-turn*(100-stat(p,'agility'))*.008,-2.5,4.5);
}
function shouldDrive(p,carry,pass,{forward=1,pressure=10,carryTime=0,goalDistance=50}={}){
 if(!carry?.point||!Number.isFinite(carry.clearance)||p?.role==='GK')return false;
 if(p?.role==='DEF'&&!['LWB','RWB','LB','RB'].includes(p.position))return false;
 const control=.46*stat(p,'dribbling')+.30*stat(p,'agility')+.24*stat(p,'acceleration');
 const gain=advance(p,carry.point,forward),bestGain=pass?.point?advance(p,pass.point,forward):0;
 if(control<83||stat(p,'dribbling')<81||stat(p,'energy',100)<.45*100)return false;
 if(pressure<2.4||pressure>9.5||carry.clearance<2.1||gain<2.6||goalDistance<13||carryTime>1.35)return false;
 if(pass?.kind==='through'&&pass.risk<.55)return false;
 // Do not overlook a clearly available, useful and physically safe pass.
 if(pass&&pass.risk<.35&&pass.arrivalRisk<.55&&pass.space>2.5&&bestGain>5&&pass.score>6)return false;
 return true;
}
function canFeint(p,defender,{pressure=10}={}){
 if(!defender||p?.role==='GK'||pressure<1.25||pressure>3.35)return false;
 if(stat(p,'dribbling')<82||stat(p,'agility')<78||stat(p,'energy',100)<43)return false;
 const technique=.60*stat(p,'dribbling')+.40*stat(p,'agility');
 const defensiveRead=.65*stat(defender,'tackling')+.35*stat(defender,'composure');
 return technique-defensiveRead>=-13;
}
function canHoldUp(p,defender,pass,{forward=1,pressure=10}={}){
 if(!defender||p?.role!=='ATT'||!['ST','CF'].includes(p.position)&&p.archetype!=='targetForward')return false;
 if(stat(p,'strength')<80||stat(p,'balance')<76||stat(p,'composure')<71||stat(p,'energy',100)<38)return false;
 if(pressure<1.15||pressure>3.25)return false;
 // Body points towards midfield while a real defender protects the goal side.
 if(Math.cos(p.face)*forward>-.20||(defender.x-p.x)*forward<-.7)return false;
 if(pass?.risk<.35&&pass?.arrivalRisk<.55&&pass?.space>2.5&&advance(p,pass.point,forward)>5)return false;
 return true;
}
const api={passBias,canThread,carryBias,shouldDrive,canFeint,canHoldUp};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.TribunPlayerBrain=api;
})(typeof window!=='undefined'?window:globalThis);
