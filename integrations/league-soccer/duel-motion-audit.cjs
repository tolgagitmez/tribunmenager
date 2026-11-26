'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
if(!frames.every(f=>Array.isArray(f.nativeDuels)))throw Error('Native duel trace missing');
const events=frames.flatMap(f=>f.nativeDuels),r=R.create(frames,null,{duelMotion:true}),start=frames[0].elapsedMs;
const report={schema:1,authoritative:false,total:events.length,kinds:{},sampled:0,reactions:0,maxBoneError:0,note:'First 150 recorded native duel events, procedural rig only. Not overlap or tackle success measurement.'};
for(const e of events)report.kinds[e.kind]=(report.kinds[e.kind]||0)+1;
for(const e of events.slice(0,150)){
 const ms=e.timeMs-start;if(ms<20||ms>r.duration)continue;
 r.reset(Rig);r.sample(ms-20,Rig,.02);
 const p=r.sample(ms,Rig,.02).players.find(p=>p.id===e.playerId&&p.team===e.team&&p.databaseId===e.databaseId);
 if(!p)continue;report.sampled++;
 const pose=Rig.getPose(p);if(!pose.nativeDuel)continue;report.reactions++;
 for(const l of pose.legs)report.maxBoneError=Math.max(report.maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh),Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin));
}
console.log(JSON.stringify(report,null,2));
