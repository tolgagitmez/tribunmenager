'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{metrics}=require('./broadcast-design.js');
test('no fabricated statistics; valid data and zero values distinct',()=>{
 assert.deepEqual(metrics(null),[]);
 assert.deepEqual(metrics({shots:[-1,4],completed:[NaN,2],possessionMs:[0,0]}),[]);
 const [r]=metrics({shots:[0,0]});assert.equal(r.empty,true);assert.deepEqual(r.values,['0','0']);
});
test('ratios and possession rounding preserve observed totals',()=>{
 const [a,b]=metrics({shots:[3,1],possessionMs:[1,2]});
 assert.equal(a.homeShare,.75);assert.equal(a.awayShare,.25);
 assert.deepEqual(b.values,['33%','67%']);
});
