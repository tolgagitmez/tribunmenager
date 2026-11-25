'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{compare}=require('./compare-attacks.cjs');
const make=n=>({engine:'league-soccer',score:[1,0],shots:[n,1],onTarget:[1,1],completed:[10,12],sampled:{observedBoxCrossings:[n,2],controlledBoxCrossings:[n,1],controlledBoxMs:[100,200],controlledFinalThirdMs:[400,300],controlledForwardMeters:[n,2],controlledBackwardMeters:[1,2],controlledWithForwardOutletMs:[100,200],controlledWithTwoBoxAttackersMs:[50,0],wideControlMs:[80,90],wideControlWithBoxOutletMs:[40,30],looseOwnBoxMs:[100,120],looseOwnBoxKeeperClosingMs:[60,50],opponentControlledWithCentralCoverMs:[20,40],pressuredControlMs:[100,200],pressuredSameCarrierMs:[60,100],pressuredForwardMeters:[3,2]}});
test('paired comparison reports observed differences without inventing data',()=>{
 const r=compare([{seed:'1',baseline:make(2),shortMatch:make(4)},{seed:'2',baseline:make(5),shortMatch:make(4)}]);
 assert.equal(r.pairCount,2);assert.equal(r.meanDelta.shots,.5);assert.equal(r.meanDelta.goals,0);assert.equal(r.rows[1].delta.shots,-1);
});
test('missing telemetry and duplicate seed fail closed',()=>{
 assert.throws(()=>compare([{seed:'1',baseline:{engine:'league-soccer'},shortMatch:make(1)}]));
 const p={seed:'1',baseline:make(1),shortMatch:make(2)};assert.throws(()=>compare([p,p]));
});

test('combination delta only uses actual counters when both profiles have telemetry',()=>{
 const a=make(2),b=make(3);
 a.combinations={attempts:[0,0],returned:[0,0],completed:[0,0]};
 b.combinations={attempts:[3,2],returned:[2,1],completed:[1,1]};
 assert.equal(compare([{seed:'a',baseline:a,shortMatch:b}]).meanDelta.combination_completed,2);
 delete a.combinations;
 assert.equal(compare([{seed:'a',baseline:a,shortMatch:b}]).meanDelta.combination_completed,undefined);
});
