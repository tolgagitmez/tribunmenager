'use strict';
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {evaluate}=require('../tools/compare-specialist-kicks.cjs');
const {Match}=require('../football-sim');
for(const kind of ['penalty','free-kick','corner']){
 for(const mode of ['automatic','manager']){
  test(kind+' '+mode+' uses its specialist for real heading and first landing',()=> {
   const low=evaluate(kind,20,mode),high=evaluate(kind,94,mode);\n   if(kind==='corner')console.log('CORNER_DIAGNOSTIC',JSON.stringify({low:{skill:low.skill,context:low.releaseContext,angle:low.targetDeviationDegrees},high:{skill:high.skill,context:high.releaseContext,angle:high.targetDeviationDegrees}}));
   assert(high.skill>low.skill+45,'specialized rating must reach foot execution');
   assert.equal(high.targetAngle,low.targetAngle,'selected heading must not depend on the execution score');
   assert(high.targetDeviationDegrees<low.targetDeviationDegrees*.85,
    'higher specialist skill must reduce the deviation from the chosen heading');
   assert.notDeepEqual(high.rawVelocity,low.rawVelocity,'skill must change the real ball at the boot');
   assert(low.firstLanding&&high.firstLanding,'both actual launches must have a physical first landing');
   assert.notDeepEqual(high.firstLanding,low.firstLanding,
    'different execution must change the physical landing, not just display a number');
   for(const result of [low,high]){
    for(const number of [result.firstLanding.x,result.firstLanding.z,result.firstLanding.time,
     result.targetDeviationDegrees,result.firstLandingDeviationMeters,result.keeper.checks,
     result.keeper.saves,result.keeper.catches,result.keeper.goals])
     assert(Number.isFinite(number),'goalkeeper and landing measurements must be real numbers');
   }
  });
 }
 test(kind+' automatic and manager control with identical intention use identical impulse',()=>{
  for(const rating of [20,94]){
   const ai=evaluate(kind,rating,'automatic');
   const same=evaluate(kind,rating,'automatic',Match,true);\n   if(kind==='corner')console.log('CORNER_CONTROL_PARITY',JSON.stringify({rating,ai:ai.releaseContext,same:same.releaseContext}));
   assert.deepEqual(ai.rawVelocity,same.rawVelocity);
   assert.equal(ai.seedAtRelease,same.seedAtRelease,'RNG draws must match');
   assert.deepEqual(ai.firstLanding,same.firstLanding);
  }
 });
}
