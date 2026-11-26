'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
if(frames.some(f=>f.players.some(p=>!p.motionIdentity)))throw Error('Player motion identity trace missing');
const r=R.create(frames,null,{playerMotionIdentity:true}),base=R.create(frames,null,{motionMatching:true}),rows=new Map();
let samples=0,maxBoneError=0,physicalMismatches=0;
for(let t=0;t<=Math.min(30000,r.duration);t+=1000/60){
 const a=base.sample(t,Rig,1/60),b=r.sample(t,Rig,1/60);
 if(JSON.stringify(a.ball)!==JSON.stringify(b.ball)||JSON.stringify(a.score)!==JSON.stringify(b.score))physicalMismatches++;
 for(let i=0;i<b.players.length;i++){
  const p=b.players[i],q=a.players[i],pose=Rig.getPose(p),m=pose.nativeMotionIdentity;
  if(['x','z','vx','vz','face','speed'].some(k=>p[k]!==q[k]))physicalMismatches++;
  if(!m)continue;samples++;
  const key=p.team+':'+p.databaseId,row=rows.get(key)||{team:p.team,databaseId:p.databaseId,samples:0,strideScaleSum:0,durationScaleSum:0,freshnessMin:1,freshnessMax:0};
  row.samples++;row.strideScaleSum+=m.stride;row.durationScaleSum+=m.duration;row.freshnessMin=Math.min(row.freshnessMin,m.freshness);row.freshnessMax=Math.max(row.freshnessMax,m.freshness);rows.set(key,row);
  for(const l of pose.legs)maxBoneError=Math.max(maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-Rig.ANATOMY.thigh),Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-Rig.ANATOMY.shin));
 }
}
if(physicalMismatches||maxBoneError>1e-5)throw Error('Presentation invariant failed');
console.log(JSON.stringify({schema:1,authoritative:false,samples,maxBoneError,physicalMismatches,players:[...rows.values()].map(x=>({...x,meanStrideScale:x.strideScaleSum/x.samples,meanDurationScale:x.durationScaleSum/x.samples})),note:'Same 30-second trace, procedural parameters; not measured visual distinctiveness or actual fatigue effect on match outcomes.'},null,2));
