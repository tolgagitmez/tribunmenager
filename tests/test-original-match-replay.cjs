'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {validDuration}=require('../original-match-replay.js');
test('local recording must be finite positive and no longer than 300 seconds',()=>{
 for(const seconds of [1,299.85,300])assert.equal(validDuration(seconds),true);
 for(const seconds of [0,-1,300.001,Infinity,NaN,'300',null])assert.equal(validDuration(seconds),false);
});
