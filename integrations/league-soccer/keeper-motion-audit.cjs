'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
if(!frames.every(f=>Array.isArray(f.nativeKeeperEvents)))throw Error('Native keeper events missing');
const events=frames.flatMap(f=>f.nativeKeeperEvents),start=frames[0].elapsedMs,r=R.create(frames,null,{keeperMotion:true});
const report={schema:1,authoritative:false,total:events.length,kinds:{},profiles:{},sampled:0,palmSamples:0,palmErrorSum:0,note:'Native catch/deflect branches, not verified shots on target or saved goals. Procedural palm target errors, not rendered gloves.'};
for(const e of events)report.kinds[e.kind]=(report.kinds[e.kind]||0)+1;
for(const e of events.slice(0,100)){
 const t=e.timeMs-start;if(t<100||t>r.duration)continue;
 r.reset(Rig);for(let ms=t-100;ms<t;ms+=10)r.sample(ms,Rig,.01);
 const p=r.sample(t,Rig,.01).players.find(p=>p.id===e.playerId&&p.databaseId===e.databaseId&&p.team===e.team);
 if(!p)continue;const k=Rig.getPose(p).nativeKeeper;if(!k)continue;
 report.sampled++;report.profiles[k.profile]=(report.profiles[k.profile]||0)+1;
 if(k.targets){report.palmSamples+=k.targets;report.palmErrorSum+=k.meanPalmError*k.targets;}
}
report.meanPalmError=report.palmSamples?report.palmErrorSum/report.palmSamples:null;
console.log(JSON.stringify(report,null,2));
