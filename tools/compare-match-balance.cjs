'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{summarize}=require('./audit-match-balance.cjs');
const sum=a=>a.reduce((x,y)=>x+y,0),round=n=>Math.round(n*1000)/1000;
function compare(base,candidate){
 assert.equal(base.schema,1);assert.equal(candidate.schema,1);assert.equal(base.seeds,candidate.seeds);
 assert(base.sources['tools/audit-match-balance.cjs']&&base.sources['tools/audit-match-balance.cjs']===candidate.sources['tools/audit-match-balance.cjs'],'different audit harness');
 const ordered=rows=>rows.slice().sort((a,b)=>a.id.localeCompare(b.id)),a=ordered(base.rows),b=ordered(candidate.rows);
 assert(a.length&&a.length===b.length&&new Set(a.map(r=>r.id)).size===a.length,'missing/duplicate cases');
 assert.equal(new Set(a.map(r=>r.configDigest)).size,a.length,'duplicate baseline match inputs');
 assert.equal(new Set(b.map(r=>r.configDigest)).size,b.length,'duplicate candidate match inputs');
 const matched=a.map((r,i)=>{const t=b[i];assert.equal(r.id,t.id);assert.equal(r.seed,t.seed);assert.equal(r.swap,t.swap);assert.deepEqual(r.a,t.a);assert.deepEqual(r.b,t.b);assert(r.configDigest&&r.configDigest===t.configDigest,'different match inputs');return [r,t];});
 function group(pairs){
  const full=pairs.filter(([r,t])=>r.finishReason==='full-time'&&t.finishReason==='full-time');
  if(!full.length)return {pairs:pairs.length,fullTimePairs:0,excluded:pairs.length,baseline:null,candidate:null,delta:null};
  const baseline=summarize(full.map(p=>p[0])),candidate=summarize(full.map(p=>p[1]));
  const delta=Object.fromEntries(Object.keys(baseline).filter(k=>typeof baseline[k]==='number'&&typeof candidate[k]==='number'&&!['matches','uniqueInputs','duplicateInputs','fullTime','otherFinishes'].includes(k)).map(k=>[k,round(candidate[k]-baseline[k])]));
  const shotDelta=full.map(([r,t])=>sum(t.pairs.shots)-sum(r.pairs.shots));
  return {pairs:pairs.length,fullTimePairs:full.length,excluded:pairs.length-full.length,baseline,candidate,delta,shotPairs:{improved:shotDelta.filter(n=>n>0).length,unchanged:shotDelta.filter(n=>n===0).length,worse:shotDelta.filter(n=>n<0).length}};
 }
 return {schema:1,method:'Identical seed, lineup, tactic and config digest per pair. Full-time pairs only; no significance or realism claim from small pilot. Rates are ratios of totals, changes are percentage points.',baselineSources:base.sources,candidateSources:candidate.sources,overall:group(matched),scenarios:[...new Set(a.map(r=>r.scenario))].map(id=>({id,...group(matched.filter(p=>p[0].scenario===id))}))};
}
module.exports={compare};
if(require.main===module){const [a,b,out]=process.argv.slice(2);assert(a&&b&&out,'usage: compare-match-balance.cjs BASE CANDIDATE OUT');const r=compare(JSON.parse(fs.readFileSync(a)),JSON.parse(fs.readFileSync(b)));fs.writeFileSync(out,JSON.stringify(r,null,2)+'\n');console.log('PAIRED_BALANCE '+JSON.stringify(r.overall));}
