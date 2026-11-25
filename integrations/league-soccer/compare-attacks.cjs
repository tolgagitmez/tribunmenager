'use strict';
// Paired descriptive comparison; no synthetic success targets, no automatic rollout.
const fs=require('node:fs');
const sum=a=>a.reduce((x,y)=>x+y,0);
const metrics=['goals','shots','onTarget','completed','boxCrossings','controlledBoxCrossings','controlledBoxMs','controlledFinalThirdMs'];
function values(r){
 if(r.engine!=='league-soccer'||!r.sampled)throw Error('Complete native attack telemetry required');
 const pairs={goals:r.score,shots:r.shots,onTarget:r.onTarget,completed:r.completed,boxCrossings:r.sampled.observedBoxCrossings,controlledBoxCrossings:r.sampled.controlledBoxCrossings,controlledBoxMs:r.sampled.controlledBoxMs,controlledFinalThirdMs:r.sampled.controlledFinalThirdMs};
 for(const a of Object.values(pairs))if(!Array.isArray(a)||a.length!==2||a.some(x=>!Number.isFinite(x)||x<0))throw Error('Invalid native metric');
 return Object.fromEntries(metrics.map(k=>[k,sum(pairs[k])]));
}
function compare(pairs){
 if(!pairs.length||new Set(pairs.map(p=>p.seed)).size!==pairs.length)throw Error('Unique paired seeds required');
 const rows=pairs.map(({seed,baseline,shortMatch})=>{
  const a=values(baseline),b=values(shortMatch);
  return {seed,baseline:a,shortMatch:b,delta:Object.fromEntries(metrics.map(k=>[k,b[k]-a[k]]))};
 });
 return {schema:1,mode:'descriptive-native-paired-experiment',pairCount:rows.length,rows,meanDelta:Object.fromEntries(metrics.map(k=>[k,sum(rows.map(r=>r.delta[k]))/rows.length])),note:'Initial seeds are equal; deterministic execution and statistical significance are not established. No automatic profile promotion.'};
}
if(require.main===module){
 const [prefix,...seeds]=process.argv.slice(2);
 if(!prefix||!seeds.length)throw Error('Usage: compare-attacks.cjs prefix seed...');
 const read=(s,p)=>JSON.parse(fs.readFileSync(prefix+'.'+s+'.'+p+'.ndjson.attack.json','utf8'));
 const r=compare(seeds.map(seed=>({seed,baseline:read(seed,'baseline'),shortMatch:read(seed,'short-match')})));
 fs.writeFileSync(prefix+'.comparison.json',JSON.stringify(r,null,2)+'\n');console.log(JSON.stringify(r));
}
module.exports={compare};
