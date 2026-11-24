'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {cases,config,summarize,combine}=require('../tools/audit-match-balance.cjs');
const row=(c,goals=[0,0],shots=[0,0])=>({...c,finishReason:'full-time',ticks:18000,seconds:{controlled:200,dead:50,loose:50},pairs:{goals,shots,onTarget:[0,0],passes:[20,30],completed:[10,20],fouls:[1,2],yellows:[0,1],reds:[0,0],xg:[0,0],possessionSeconds:[120,80],finalThirdEntries:[1,2],boxEntries:[0,0]},counters:{offsides:1,abortedKicks:0}});
test('144 distinct natural cases at twelve seeds; paired side assignments and complete shard partition',()=>{
 const all=cases(12);assert.equal(all.length,144);assert.equal(new Set(all.map(c=>c.id)).size,144);
 assert.deepEqual(Array.from({length:6},(_,i)=>cases(12,6,i)).flat().map(c=>c.id).sort(),all.map(c=>c.id).sort());
 for(let i=0;i<all.length;i+=2){const a=config(all[i]),b=config(all[i+1]);assert.equal(a.seed,b.seed);assert.equal(a.formation,b.awayFormation);assert.equal(a.awayFormation,b.formation);assert.deepEqual(a.tactics,b.awayTactics);assert.deepEqual(a.players.map(p=>p.rating),b.awayPlayers.map(p=>p.rating));assert.equal(a.players.length,11);assert.equal(a.individualAI,true);}
});
test('ratio-of-totals and zero denominators, unfinished games excluded from averages',()=>{
 const [a,b,c]=cases(1),report=summarize([row(a,[1,0],[2,1]),row(b),{...row(c,[9,9],[9,9]),finishReason:'minimum-players'}]);
 assert.equal(report.fullTime,2);assert.equal(report.otherFinishes,1);assert.equal(report.shotsPerMatch,1.5);assert.equal(report.goalsPerMatch,.5);assert.equal(report.passAccuracyPct,60);assert.equal(report.zeroShotMatchPct,50);assert.equal(report.sideA.wins,1);assert.equal(summarize([row(b)]).goalsPerShotPct,null);
});
test('merge rejects missing, duplicated, mixed-source and mismatched-seed results',()=>{
 const rows=cases(1).map(c=>row(c)),part={schema:1,seeds:1,sources:{engine:'a'},rows};
 const combined=combine([part]);assert.equal(combined.overall.matches,12);assert.equal(combined.scenarios.length,6);
 assert.throws(()=>combine([{...part,rows:rows.slice(1)}]),/incomplete/);
 assert.throws(()=>combine([part,part]),/duplicate/);
 assert.throws(()=>combine([part,{...part,sources:{engine:'b'}}]));
 assert.throws(()=>combine([part,{...part,seeds:2}]));
});
