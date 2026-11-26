'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
function measure(options){
 const r=R.create(frames,null,options),previous=new Map();
 const m={profiles:{},stepProfiles:{},validSamples:0,profileSwitches:0,requested:0,rejected:0,consecutive:0,slipSum:0,maxSlip:0,landings:0,maxBoneError:0,contactSamples:0};
 for(let t=0;t<=Math.min(30000,r.duration);t+=1000/60){
  const active=new Set();
  for(const p of r.sample(t,Rig,1/60).players){
   const key=p.team+':'+p.id+':'+p.databaseId;
   if(p.role==='GK'||!p.nativeBlend){previous.delete(key);continue;}
   active.add(key);m.validSamples++;const pose=Rig.getPose(p),old=previous.get(key),profile=pose.nativeMotionMatch?.profile;
   if(profile){m.profiles[profile]=(m.profiles[profile]||0)+1;if(old?.profile&&old.profile!==profile)m.profileSwitches++;}
   if(p.nativeContact)m.contactSamples++;
   for(let i=0;i<2;i++){
    const l=pose.legs[i],prior=old?.legs[i];
    if(l.stepProfile)m.stepProfiles[l.stepProfile]=(m.stepProfiles[l.stepProfile]||0)+1;
    if(l.requestedStance){m.requested++;if(!l.stance)m.rejected++;}
    if(l.stance&&prior&&!prior.stance)m.landings++;
    if(l.stance&&prior?.stance){const d=Math.hypot(l.ankle[0]-prior.ankle[0],l.ankle[2]-prior.ankle[2]);m.consecutive++;m.slipSum+=d;m.maxSlip=Math.max(m.maxSlip,d);}
    m.maxBoneError=Math.max(m.maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-Rig.ANATOMY.thigh),Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-Rig.ANATOMY.shin));
   }
   previous.set(key,{profile,legs:pose.legs});
  }
  for(const key of previous.keys())if(!active.has(key))previous.delete(key);
 }
 m.meanSlip=m.consecutive?m.slipSum/m.consecutive:null;m.rejectedShare=m.requested?m.rejected/m.requested:null;return m;
}
console.log(JSON.stringify({schema:1,authoritative:false,baseline:measure({animationBlend:true}),candidate:measure({motionMatching:true}),note:'Same first 30 seconds, 60 Hz procedural IK ankles. No claim of final mesh motion or actual motion-capture matching.'},null,2));
