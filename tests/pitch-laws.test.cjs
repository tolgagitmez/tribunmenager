'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const P=require('../pitch-laws');
const p=(x=0,y=.11,z=0)=>({x,y,z});
for(const sign of [-1,1]){
 test(`a ball overlapping the touchline remains in play (${sign})`,()=>{assert.equal(P.firstWholeBallExit(p(0,.11,33.9*sign),p(0,.11,34.10*sign)),null);assert.equal(P.firstWholeBallExit(p(0,.11,33.9*sign),p(0,.11,34.11*sign)),null);const e=P.firstWholeBallExit(p(1,.11,33.9*sign),p(3,.11,34.4*sign));assert.equal(e.kind,'touchline');assert.equal(e.sign,sign);assert(Math.abs(e.point.z-34.11*sign)<1e-9);assert(e.point.x>1&&e.point.x<3);});
 test(`whole ball and complete goal mouth are required (${sign})`,()=>{assert.equal(P.firstWholeBallExit(p(51.9*sign),p(52.1*sign)),null);const e=P.firstWholeBallExit(p(51.9*sign,1,0),p(52.4*sign,1,0));assert.equal(e.kind,'goal-line');assert(P.goalMouth(e.point));assert.equal(P.goalMouth(p(52.2,2.34,0)),false);assert.equal(P.goalMouth(p(52.2,1,3.56)),false);});
 test(`a fast shot cannot tunnel through either post (${sign})`,()=>{for(const flank of [-1,1]){const h=P.sweepFrame(p(50*sign,1,3.72*flank),p(54*sign,1,3.72*flank));assert(h);assert.equal(h.name,'post');assert.equal(h.side,sign);assert(h.t<.5);const v=P.reflected({x:60*sign,y:0,z:0},h.normal);assert(v.x*sign<0);assert(Math.hypot(v.x,v.y,v.z)<=60);}});
 test(`crossbar and post/bar joint have swept contacts (${sign})`,()=>{for(const z of [0,3.72,-3.72]){const h=P.sweepFrame(p(50*sign,2.5,z),p(54*sign,2.5,z));assert(h);assert(h.t<.5);assert.equal(h.side,sign);}});
}
test('the first crossed boundary wins rather than a fixed touchline-first branch',()=>{const a=P.firstWholeBallExit(p(51,1,33),p(54,1,35));assert.equal(a.kind,'goal-line');const b=P.firstWholeBallExit(p(51,1,33),p(53,1,36));assert.equal(b.kind,'touchline');});
test('a central low trajectory clears all frame members',()=>{assert.equal(P.sweepFrame(p(50,1,0),p(54,1,0)),null);});
test('a departing ball does not bounce a second time off the same frame surface',()=>{assert.equal(P.sweepFrame(p(51.82,1,3.72),p(51,1,3.72)),null);});
