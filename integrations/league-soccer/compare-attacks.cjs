'use strict';
// Paired descriptive comparison; no synthetic success targets, no automatic rollout.
const fs=require('node:fs');
const sum=a=>a.reduce((x,y)=>x+y,0);
const metrics=['goals','shots','onTarget','completed','boxCrossings','controlledBoxCrossings','controlledBoxMs','controlledFinalThirdMs','controlledForwardMeters','controlledBackwardMeters','controlledWithForwardOutletMs','controlledWithTwoBoxAttackersMs','wideControlMs','wideControlWithBoxOutletMs','looseOwnBoxMs','looseOwnBoxKeeperClosingMs','opponentControlledWithCentralCoverMs','pressuredControlMs','pressuredSameCarrierMs','pressuredForwardMeters'];
function values(r){
 if(r.engine!=='league-soccer'||!r.sampled)throw Error('Complete native attack telemetry required');
 const pairs={goals:r.score,shots:r.shots,onTarget:r.onTarget,completed:r.completed,boxCrossings:r.sampled.observedBoxCrossings,controlledBoxCrossings:r.sampled.controlledBoxCrossings,controlledBoxMs:r.sampled.controlledBoxMs,controlledFinalThirdMs:r.sampled.controlledFinalThirdMs,controlledForwardMeters:r.sampled.controlledForwardMeters,controlledBackwardMeters:r.sampled.controlledBackwardMeters,controlledWithForwardOutletMs:r.sampled.controlledWithForwardOutletMs,controlledWithTwoBoxAttackersMs:r.sampled.controlledWithTwoBoxAttackersMs,wideControlMs:r.sampled.wideControlMs,wideControlWithBoxOutletMs:r.sampled.wideControlWithBoxOutletMs,looseOwnBoxMs:r.sampled.looseOwnBoxMs,looseOwnBoxKeeperClosingMs:r.sampled.looseOwnBoxKeeperClosingMs,opponentControlledWithCentralCoverMs:r.sampled.opponentControlledWithCentralCoverMs,pressuredControlMs:r.sampled.pressuredControlMs,pressuredSameCarrierMs:r.sampled.pressuredSameCarrierMs,pressuredForwardMeters:r.sampled.pressuredForwardMeters};
 for(const a of Object.values(pairs))if(!Array.isArray(a)||a.length!==2||a.some(x=>!Number.isFinite(x)||x<0))throw Error('Invalid native metric');
 const result=Object.fromEntries(metrics.map(k=>[k,sum(pairs[k])]));
 if(r.combinations){
  for(const k of ['attempts','returned','completed']){
   const a=r.combinations[k];
   if(!Array.isArray(a)||a.length!==2||a.some(x=>!Number.isSafeInteger(x)||x<0))throw Error('Invalid combination counters');
   result['combination_'+k]=sum(a);
  }
 }
 if(r.rebounds)for(const k of ['deflections','recoveries','followupShots']){
  const a=r.rebounds[k];
  if(!Array.isArray(a)||a.length!==2||a.some(x=>!Number.isSafeInteger(x)||x<0))throw Error('Invalid rebound counters');
  result['rebound_'+k]=sum(a);
 }
 return result;
}
function compare(pairs){
 if(!pairs.length||new Set(pairs.map(p=>p.seed)).size!==pairs.length)throw Error('Unique paired seeds required');
 const comboKeys=['combination_attempts','combination_returned','combination_completed'];
 const withCombos=pairs.every(p=>p.baseline.combinations&&p.shortMatch.combinations);
 const reboundKeys=['rebound_deflections','rebound_recoveries','rebound_followupShots'];
 const withRebounds=pairs.every(p=>p.baseline.rebounds&&p.shortMatch.rebounds);
 const keys=[...metrics,...(withCombos?comboKeys:[]),...(withRebounds?reboundKeys:[])];
 const rows=pairs.map(({seed,baseline,shortMatch})=>{
  const a=values(baseline),b=values(shortMatch);
  return {seed,baseline:a,shortMatch:b,delta:Object.fromEntries(keys.map(k=>[k,b[k]-a[k]]))};
 });
 return {schema:1,mode:'descriptive-native-paired-experiment',pairCount:rows.length,rows,meanDelta:Object.fromEntries(keys.map(k=>[k,sum(rows.map(r=>r.delta[k]))/rows.length])),note:'Initial seeds are equal; deterministic execution and statistical significance are not established. No automatic profile promotion.'};
}
if(require.main===module){
 const [prefix,...seeds]=process.argv.slice(2);
 if(!prefix||!seeds.length)throw Error('Usage: compare-attacks.cjs prefix seed...');
 const read=(s,p)=>JSON.parse(fs.readFileSync(prefix+'.'+s+'.'+p+'.ndjson.attack.json','utf8'));
 const r=compare(seeds.map(seed=>({seed,baseline:read(seed,'baseline'),shortMatch:read(seed,'short-match')})));
 fs.writeFileSync(prefix+'.comparison.json',JSON.stringify(r,null,2)+'\n');console.log(JSON.stringify(r));
}
module.exports={compare};
