'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8')),start=frames[0].elapsedMs;
const events=frames.flatMap(f=>[...(f.nativeContacts||[]).filter(e=>e.headContact||e.foot>=0&&e.ball[2]<=.35),...(f.nativeKeeperEvents||[])]);
const r=R.create(frames,null,{contactPrecision:true}),groups={foot:[],palm:[],head:[]},counts={foot:0,palm:0,head:0};
for(const e of events){
 const kind=e.kind==='catch'||e.kind==='parry'?'palm':e.headContact?'head':'foot';
 if(counts[kind]++>=100)continue;
 const t=e.timeMs-start;if(t<100||t>r.duration)continue;
 r.reset(Rig);for(let ms=t-100;ms<t;ms+=10)r.sample(ms,Rig,.01);
 const p=r.sample(t,Rig,.01).players.find(p=>p.id===e.playerId&&p.team===e.team&&p.databaseId===e.databaseId);
 if(!p)continue;
 const cue=kind==='foot'?p.nativeContact:kind==='palm'?p.nativeKeeper:p.nativeAerial;
 if(cue?.timeMs!==e.timeMs)continue;
 for(const m of Rig.getPose(p).nativeContactPrecision||[])if(m.kind===kind)groups[kind].push(m);
}
const stat=rows=>{
 const mean=k=>rows.length?100*rows.reduce((s,m)=>s+m[k],0)/rows.length:null;
 return {samples:rows.length,improved:rows.filter(m=>m.after<m.before-1e-7).length,unchanged:rows.filter(m=>Math.abs(m.after-m.before)<=1e-7).length,baselineMeanCm:mean('before'),candidateMeanCm:mean('after'),maxCorrectionCm:rows.length?100*Math.max(...rows.map(m=>m.correction)):null};
};
console.log(JSON.stringify({schema:1,authoritative:false,counts,metrics:Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,stat(v)])),note:'Per-event before/after procedural point-to-sphere distances; head uses scaled spherical radius approximation. Not actual mesh penetration, physical collisions or measured video quality. Zero samples are inconclusive.'},null,2));
