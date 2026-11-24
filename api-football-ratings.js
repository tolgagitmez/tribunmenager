'use strict';
// Versioned game-design priors, NOT measured footballer abilities.
// No names, team, age, nationality, market value or invented precise positions
// enter the synthetic rating calculation. Stable UID controls only variation.
(function(root){
const Model=typeof module!=='undefined'&&module.exports?require('./player-model.js'):root.TribunPlayerModel;
const VERSION=1;
const blends=Object.freeze({GK:['goalkeeper'],DEF:['stopper','fullback'],MID:['playmaker','ballWinner'],ATT:['poacher','winger','targetForward']});
const weights=Object.freeze({
 GK:{goalkeeping:30,handling:25,reactions:20,composure:10,agility:10,passing:5},
 DEF:{tackling:30,heading:15,strength:15,pace:10,composure:10,passing:10,endurance:10},
 MID:{passing:25,vision:20,dribbling:15,composure:10,tackling:10,endurance:10,balance:10},
 ATT:{shooting:30,dribbling:20,pace:15,acceleration:10,composure:10,heading:10,vision:5}
});
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
const physical=new Set(['pace','acceleration','agility','strength','balance','endurance']);
const technical=new Set(['passing','shooting','tackling','dribbling','heading','crossing','weakFoot','handling','goalkeeping']);
const baseKeys=Object.keys(Model.profiles.playmaker);
function hash(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function random(uid,label){return hash('tribun-rating-v'+VERSION+':'+uid+':'+label)/4294967295}
function baseline(pos){
 const types=blends[pos];if(!types)throw Error('Unknown broad position');
 return Object.fromEntries(baseKeys.map(k=>[k,types.reduce((n,t)=>n+Model.profiles[t][k],0)/types.length]));
}
function overall(pos,skills){
 const w=weights[pos],base=baseline(pos);
 let total=0;
 for(const [k,v] of Object.entries(w)){
  if(typeof skills[k]!=='number'||!Number.isFinite(skills[k])||skills[k]<1||skills[k]>99)throw Error('Invalid skill: '+k);
  total+=v*(skills[k]-base[k]);
 }
 // Center each position around the same neutral rating, rather than
 // penalizing keepers for shooting or attackers for goalkeeping.
 return clamp(Math.round(80+total/100),1,99);
}
function buildProfile(uid,pos,mode='neutral'){
 if(typeof uid!=='string'||!/^api-football:player:[1-9][0-9]*$/.test(uid)||!Object.hasOwn(blends,pos))throw Error('Invalid profile identity');
 if(!['neutral','synthetic-varied'].includes(mode))throw Error('Unknown rating mode');
 if(mode==='neutral')return {skills:{},rating:80,ratingSource:'synthetic-neutral',skillSource:'position-default',ratingProvenance:{version:VERSION,mode,observed:false,confidence:null,attributes:{}}};
 const types=blends[pos],base=baseline(pos);
 // Mix broad role templates, no invented fine position. Minimum 20% weight
 // per template before normalization prevents extreme role specialization.
 const mix=types.map((_,i)=>.2+.6*random(uid,'style-'+i)),sum=mix.reduce((a,b)=>a+b,0);
 const quality=(random(uid,'quality')-.5)*12;
 const axes={physical:(random(uid,'physical')-.5)*8,technical:(random(uid,'technical')-.5)*8,mental:(random(uid,'mental')-.5)*8};
 const skills={};
 for(const k of baseKeys){
  const blended=types.reduce((a,t,i)=>a+mix[i]/sum*Model.profiles[t][k],0);
  const axis=physical.has(k)?axes.physical:technical.has(k)?axes.technical:axes.mental;
  // Keep very low out-of-role skills low; no fictitious elite keeper/striker.
  const delta=(blended-base[k])*.75+(quality+axis+(random(uid,k)-.5)*4)*(base[k]<40?.4:1);
  skills[k]=clamp(Math.round(base[k]+delta),1,99);
 }
 skills.freeKick=clamp(Math.round(.4*skills.shooting+.35*skills.passing+.25*skills.composure),1,99);
 skills.corner=clamp(Math.round(.75*skills.crossing+.15*skills.passing+.1*skills.composure),1,99);
 skills.penalty=clamp(Math.round(.65*skills.shooting+.35*skills.composure),1,99);
 return {skills,rating:overall(pos,skills),ratingSource:'synthetic-role-weighted',skillSource:'synthetic-role-mixture',
  ratingProvenance:{version:VERSION,mode,observed:false,confidence:null,attributes:Object.fromEntries(Object.keys(skills).map(k=>[k,'synthetic']))}};
}
const api={VERSION,baseline,overall,buildProfile};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.TribunApiRatings=api;
})(typeof window!=='undefined'?window:globalThis);
