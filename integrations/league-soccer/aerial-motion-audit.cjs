'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
const all=frames.flatMap(f=>f.nativeContacts||[]);
if(all.some(e=>typeof e.headContact!=='boolean'))throw Error('Native head contact classification missing');
const events=all.filter(e=>e.headContact),start=frames[0].elapsedMs,r=R.create(frames,null,{aerialMotion:true});
const report={schema:1,authoritative:false,total:events.length,kinds:{},profiles:{},sampled:0,nearOpponent:0,headProxyErrorSum:0,note:'Explicit head body-part contacts only. Head-center distance proxy, not forehead collision or successful aerial duel.'};
for(const e of events)report.kinds[e.kind]=(report.kinds[e.kind]||0)+1;
for(const e of events.slice(0,100)){
 const t=e.timeMs-start;if(t<100||t>r.duration)continue;
 r.reset(Rig);for(let ms=t-100;ms<t;ms+=10)r.sample(ms,Rig,.01);
 const p=r.sample(t,Rig,.01).players.find(p=>p.id===e.playerId&&p.databaseId===e.databaseId&&p.team===e.team);
 if(!p)continue;const k=Rig.getPose(p).nativeAerial;if(!k)continue;
 report.sampled++;report.profiles[k.profile]=(report.profiles[k.profile]||0)+1;
 if(k.contested)report.nearOpponent++;
 report.headProxyErrorSum+=k.headError;
}
report.meanHeadProxyError=report.sampled?report.headProxyErrorSum/report.sampled:null;
console.log(JSON.stringify(report,null,2));
