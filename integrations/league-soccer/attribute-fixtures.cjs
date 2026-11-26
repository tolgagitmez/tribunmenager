'use strict';
// Synthetic mirrored rosters: one attribute group varies; overall ratings, condition,
// slot fit, goalkeeper, all other attributes and tactics remain fixed.
const fs=require('node:fs'),path=require('node:path');
const Model=require('../../player-model.js');
const {demo,convert,nativeStats}=require('./fixture-adapter.cjs');
const axes=Object.freeze({
 dribbling:['dribbling','balance','agility'],
 passing:['passing','crossing'],
 shooting:['shooting','strength'],
 pace:['pace','acceleration'],
 decisions:['vision','composure']
});
function create(axis,highTeam){
 if(!Object.hasOwn(axes,axis)||![0,1].includes(highTeam))throw Error('Invalid axis or side');
 const formation='4-4-2';
 const baseline=Model.demoTeam(0,formation).map(p=>({...p,rating:80,fitness:100,form:100,preferredFoot:'both'}));
 const teams=[0,1].map(t=>baseline.map(p=>{
   const copy={...p,name:'Synthetic '+t+' / '+p.id};
   // Fix non-treatment attributes; no profile-specific fallback or rating manipulation.
   for(const attr of Object.keys(nativeStats).map(k=>nativeStats[k]))copy[attr]=70;
   if(p.pos!=='GK')for(const attr of axes[axis])copy[attr]=t===highTeam?90:55;
   return copy;
 }));
 return {...demo(),seed:3100+Object.keys(axes).indexOf(axis),formation,awayFormation:formation,
     players:teams[0],awayPlayers:teams[1],starters:teams[0].map(p=>p.id),awayStarters:teams[1].map(p=>p.id),
     tactics:{press:55,passing:'mixed'},awayTactics:{press:55,passing:'mixed'}};
}
function verifyPair(a,b,axis){
 const ma=convert(a),mb=convert(b);
 if(ma.seed!==mb.seed||ma.teams.some((t,k)=>JSON.stringify(t.tactics)!==JSON.stringify(mb.teams[k].tactics)))throw Error('Mismatch in controls');
 for(let team=0;team<2;team++){
   const hi=ma.teams[team].players,lo=mb.teams[team].players;
   for(const p of hi){
     const q=lo.find(x=>x.slot===p.slot);
     if(!q||p.nativeId!==q.nativeId||p.role!==q.role||p.rating!==q.rating||p.x!==q.x||p.y!==q.y||p.startFitness!==q.startFitness)throw Error('Roster controls changed');
     for(const [key,attr] of Object.entries(nativeStats)){
       const treated=p.role!=='GK'&&axes[axis].includes(attr);
       const expected=treated?(team===0?.35:-.35):0;
       if(Math.abs(p.stats[key]-q.stats[key]-expected)>1e-6)throw Error('Attribute contrast invalid '+axis+' '+key);
     }
   }
 }
 return [ma,mb];
}
if(require.main===module){
 const out=process.argv[2];if(!out)throw Error('Output directory required');
 fs.mkdirSync(out,{recursive:true});
 for(const axis of Object.keys(axes)){
   const a=create(axis,0),b=create(axis,1);
   verifyPair(a,b,axis);
   for(const [idx,config] of [a,b].entries())fs.writeFileSync(path.join(out,axis+'-'+idx+'.json'),JSON.stringify(config,null,2)+'\n');
   console.log(JSON.stringify({axis,seed:a.seed,high:90,low:55,overall:80,formation:a.formation}));
 }
}
module.exports={axes,create,verifyPair};
