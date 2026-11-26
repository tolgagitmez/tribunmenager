'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
const events=frames.flatMap(f=>f.nativeContacts||[]);
if(!frames.every(f=>Array.isArray(f.nativeContacts)))throw Error('Native contact trace missing');
const counts={};for(const e of events)counts[e.kind]=(counts[e.kind]||0)+1;
if(!events.length)throw Error('No accepted contact recorded');
const start=frames[0].elapsedMs;
const report={schema:1,authoritative:false,productionEnabled:false,counts,total:events.length,eligible:0,measured:0,baselineErrorSum:0,candidateErrorSum:0,note:'Same native trace, sampled procedural toe to ball surface distance at recorded contact; no final GPU sole measurement; only low-ball known-foot events, first 60 eligible events.'};
const a=R.create(frames,null,{bodyBalance:true,footPlant:true}),b=R.create(frames,null,{bodyBalance:true,footPlant:true,contactSync:true});
for(const e of events){
 if(e.foot<0||e.ball[2]>.35||report.eligible>=60)continue;
 report.eligible++;
 const ms=e.timeMs-start;if(ms<100||ms>a.duration)continue;
 a.reset(Rig);b.reset(Rig);
 for(let t=ms-100;t<ms;t+=10){a.sample(t,Rig,.01);b.sample(t,Rig,.01);}
 const x=a.sample(ms,Rig,.01).players.find(p=>p.id===e.playerId&&p.team===e.team&&p.databaseId===e.databaseId);
 const y=b.sample(ms,Rig,.01).players.find(p=>p.id===e.playerId&&p.team===e.team&&p.databaseId===e.databaseId);
 if(!x||!y||y.nativeContact?.timeMs!==e.timeMs)continue;
 const p=Rig.getPose(x).legs[e.foot],q=Rig.getPose(y).legs[e.foot];if(!q.nativeContact)continue;
 const c=R.coord(e.ball),error=l=>Math.abs(Math.hypot(l.toe[0]-c.x,l.toe[1]-c.y,l.toe[2]-c.z)-Rig.BALL_RADIUS);
 report.measured++;report.baselineErrorSum+=error(p);report.candidateErrorSum+=error(q);
}
report.baselineMean=report.measured?report.baselineErrorSum/report.measured:null;
report.candidateMean=report.measured?report.candidateErrorSum/report.measured:null;
console.log(JSON.stringify(report,null,2));
