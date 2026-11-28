'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {target,correction}=require('../original-shared-replay.js');
test('late join, round trip compensation and shared finish',()=>{
 const state={durationSeconds:300,serverTimeMs:130000,startTimeMs:100000};
 assert.equal(target(state,100,100,0),30);
 assert.equal(target(state,100,200,100),30.15);
 assert.equal(target(state,100,400000,0),300);
 assert.equal(target({...state,serverTimeMs:90000},100,100,0),0);
 for(const s of [{...state,durationSeconds:301},{...state,serverTimeMs:NaN}])
  assert.throws(()=>target(s,100,100,0));
});
test('recover big divergence by seeking, small divergence without jumps',()=>{
 assert.deepEqual(correction(12,30),{seek:30,rate:1});
 assert.deepEqual(correction(30.01,30),{seek:null,rate:1});
 assert(correction(29.7,30).rate>1);
 assert(correction(30.3,30).rate<1);
});
