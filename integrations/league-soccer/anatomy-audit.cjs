'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
if(frames.some(f=>f.players.some(p=>p.heightMetres===undefined)))throw Error('Native height trace missing');
const r=R.create(frames,null,{playerAnatomy:true}),heights=new Map();let maxBoneError=0,samples=0;
for(let t=0;t<=Math.min(30000,r.duration);t+=1000/60)for(const p of r.sample(t,Rig,1/60).players){
 const pose=Rig.getPose(p),a=Rig.anatomyFor(p);samples++;
 heights.set(p.team+':'+p.databaseId,p.nativeAnatomy.height);
 for(const l of pose.legs)maxBoneError=Math.max(maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-a.thigh),Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-a.shin));
}
if(maxBoneError>1e-5)throw Error('Scaled anatomical length invariant failed');
console.log(JSON.stringify({schema:1,authoritative:false,samples,maxBoneError,heights:[...heights.entries()],distinctHeights:new Set(heights.values()).size,note:'Native database height, which may be a default; no independently verified real-player measurements. Rig bone audit, not final mesh contact.'},null,2));
