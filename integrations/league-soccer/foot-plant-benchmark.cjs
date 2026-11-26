'use strict';
// Presentation diagnostic, not native physics or video ground truth.
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[2]-b[2]);
function measure(frames,footPlant){
 const replay=R.create(frames,null,{bodyBalance:true,footPlant});
 const limit=Math.min(30000,replay.duration),dt=1000/60;
 let requested=0,rejected=0,contacts=0,consecutive=0,slip=0,maxSlip=0,landings=0,moving=0,maxBoneError=0;
 const previous=new Map();
 for(let ms=0;ms<=limit;ms+=dt){
  const {players}=replay.sample(ms,Rig,dt/1000),active=new Set();
  for(const p of players){
   if(p.role==='GK'||!p.nativeBodyBalance?.valid){previous.delete(p.id);continue;}
   active.add(p.id);const pose=Rig.getPose(p),old=previous.get(p.id);
   const continuous=old&&old.actor===p&&Math.hypot(old.x-p.x,old.z-p.z)<.5;
   if(p.speed>.35)moving++;
   for(let i=0;i<2;i++){
    const l=pose.legs[i],prior=continuous?old.legs[i]:null;
    maxBoneError=Math.max(maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-Rig.ANATOMY.thigh),Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-Rig.ANATOMY.shin));
    if(l.requestedStance){requested++;if(!l.stance)rejected++;}
    if(l.stance){contacts++;if(prior&&!prior.stance)landings++;}
    if(l.stance&&prior?.stance){const d=dist(l.ankle,prior.ankle);slip+=d;maxSlip=Math.max(maxSlip,d);consecutive++;}
   }
   previous.set(p.id,{actor:p,x:p.x,z:p.z,legs:pose.legs});
  }
  for(const id of previous.keys())if(!active.has(id))previous.delete(id);
 }
 replay.reset(Rig);
 return {sampledMs:limit,moving,requested,rejected,contacts,consecutive,landings,slip,maxSlip,maxBoneError,
  rejectedShare:requested?rejected/requested:null,meanSlip:consecutive?slip/consecutive:null};
}
function compare(frames){
 const baseline=measure(frames,false),candidate=measure(frames,true);
 return {schema:1,authoritative:false,productionEnabled:false,baseline,candidate,
  note:'Same recording, 60 Hz procedural rig samples, at most first 30 s; not final GPU blended soles or native contact.',
  sufficient:baseline.moving>=100&&candidate.moving>=100&&baseline.consecutive>=100&&candidate.consecutive>=100};
}
module.exports={compare};
if(require.main===module)console.log(JSON.stringify(compare(R.parse(fs.readFileSync(process.argv[2],'utf8'))),null,2));
