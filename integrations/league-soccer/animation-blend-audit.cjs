'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
const all={bodyBalance:true,footPlant:true,contactSync:true,strikeMotion:true,controlMotion:true,duelMotion:true,tackleMotion:true,keeperMotion:true,aerialMotion:true};
function run(options){
 const r=R.create(frames,null,options),previous=new Map(),report={samples:0,contactSamples:0,localTargetDeltaSum:0,localTargetDeltaMax:0,maxBoneError:0};
 const local=(p,v)=>{const x=v[0]-p.x,z=v[2]-p.z,c=Math.cos(p.face),s=Math.sin(p.face);return [x*c+z*s,v[1],-x*s+z*c];};
 for(let t=0;t<=Math.min(30000,r.duration);t+=1000/60){
  const frame=r.sample(t,Rig,1/60);
  for(const p of frame.players){
   const pose=Rig.getPose(p),key=p.team+':'+p.id+':'+p.databaseId;
   const points=[pose.torsoUpper,...pose.arms.map(a=>a.wrist),...pose.legs.map(l=>l.ankle)].map(v=>local(p,v));
   const prior=previous.get(key);previous.set(key,points);
   if(p.nativeContact||p.nativeAerial||p.nativeKeeper)report.contactSamples++;
   if(prior)for(let i=0;i<points.length;i++){
    const d=Math.hypot(...points[i].map((v,j)=>v-prior[i][j]));
    report.samples++;report.localTargetDeltaSum+=d;report.localTargetDeltaMax=Math.max(report.localTargetDeltaMax,d);
   }
   for(const l of pose.legs)report.maxBoneError=Math.max(report.maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh),Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin));
  }
 }
 report.meanLocalDelta=report.samples?report.localTargetDeltaSum/report.samples:null;return report;
}
console.log(JSON.stringify({schema:1,authoritative:false,baseline:run(all),candidate:run({animationBlend:true}),note:'First 30 seconds at 60 Hz. Local procedural endpoint changes include normal locomotion, not measured visual jerk or final mesh contact.'},null,2));
