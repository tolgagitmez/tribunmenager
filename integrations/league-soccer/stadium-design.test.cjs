'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),D=require('./stadium-design.js'),G=require('../../pitch-laws.js').dimensions;
function capture(mode){
 const calls=[],m={};for(const k of ['box','quad','tri','segment'])m[k]=(...args)=>calls.push([k,...args]);
 D.build(m,G,mode);return calls;
}
test('stadium is deterministic, quality bounded, laws unchanged',()=>{
 const before=JSON.stringify(G),a=capture('performance'),b=capture('quality');
 assert.deepEqual(a,capture('performance'));assert.ok(b.length>a.length);assert.ok(b.length<9000);assert.equal(JSON.stringify(G),before);
 assert.throws(()=>capture('invalid'));
});
test('goal frames remain on actual goal planes and use law dimensions',()=>{
 const calls=capture('balanced'),segments=calls.filter(c=>c[0]==='segment');
 for(const s of [-1,1])for(const z of [-1,1]){
  const x=s*G.halfLength,w=z*(G.goalHalfWidth+G.postRadius),h=G.goalHeight+G.postRadius;
  assert.ok(segments.some(c=>JSON.stringify(c.slice(1,4))===JSON.stringify([[x,0,w],[x,h,w],G.postRadius])));
 }
});
test('new turf stays flat and does not change field boundaries',()=>{
 const quads=capture('balanced').filter(c=>c[0]==='quad'&&c.slice(1,5).every(p=>p[1]===0));
 assert.equal(quads.length,144);
 for(const q of quads)for(const p of q.slice(1,5)){assert.ok(Math.abs(p[0])<=G.halfLength+1e-8);assert.ok(Math.abs(p[2])<=G.halfWidth+1e-8);}
});
