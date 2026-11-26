'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
const events=frames.flatMap(f=>f.nativeContacts||[]).filter(e=>e.kind==='trap'||e.kind==='control');
if(events.some(e=>!e.controlContext))throw Error('Stage83 control context missing from new trace');
const r=R.create(frames,null,{controlMotion:true,bodyBalance:true,footPlant:true}),start=frames[0].elapsedMs;
const report={schema:1,authoritative:false,productionEnabled:false,total:events.length,eligible:0,sampled:0,profiles:{},pressureCues:0,footChanges:0,maxBoneError:0,note:'First 100 eligible recorded low-ball control contacts; profiles are presentation labels, not measured dribble success.'};
const prior=new Map();
for(const e of events){
 if(e.foot<0||e.ball[2]>.35||report.eligible>=100)continue;
 report.eligible++;
 const ms=e.timeMs-start;if(ms<100||ms>r.duration)continue;
 r.reset(Rig);for(let t=ms-100;t<ms;t+=10)r.sample(t,Rig,.01);
 const p=r.sample(ms,Rig,.01).players.find(p=>p.id===e.playerId&&p.team===e.team&&p.databaseId===e.databaseId);
 if(!p||p.nativeContact?.timeMs!==e.timeMs)continue;
 const pose=Rig.getPose(p),cue=pose.nativeControl;
 if(!cue||!pose.legs[e.foot].nativeContact)continue;
 report.sampled++;report.profiles[cue.profile]=(report.profiles[cue.profile]||0)+1;if(cue.pressure>0)report.pressureCues++;
 const key=e.team+':'+e.databaseId;if(prior.has(key)&&prior.get(key)!==e.foot)report.footChanges++;prior.set(key,e.foot);
 for(const l of pose.legs)report.maxBoneError=Math.max(report.maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh),Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin));
}
console.log(JSON.stringify(report,null,2));
