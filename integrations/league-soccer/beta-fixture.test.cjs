'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),B=require('./beta-fixture.cjs');
test('beta fixture is deterministic and maps selected tactics to native manifest',()=>{
 const opts={seed:7,homeFormation:'4-4-2',awayFormation:'3-5-2',homeStyle:'counter',awayStyle:'possession',homePress:80,awayPress:25,homePassing:'direct',awayPassing:'short'};
 const a=B.make(opts);assert.deepEqual(a,B.make(opts));
 assert.equal(a.config.matchMinutes,5);
 assert.equal(a.manifest.teams[0].formation,'4-4-2');
 assert.equal(a.manifest.teams[1].formation,'3-5-2');
 assert.equal(a.manifest.teams[0].tactics.team_pressure,.8);
 assert.equal(a.manifest.teams[1].tactics.team_pressure,.25);
 assert.equal(a.manifest.teams[0].tactics.counter_attack,.9);
 assert.equal(a.manifest.teams[1].tactics.counter_attack,.2);
 assert.equal(a.manifest.teams[0].tactics.support_distance,.8);
 assert.equal(a.manifest.teams[1].tactics.support_distance,.2);
 for(const t of a.manifest.teams){assert.equal(t.players.length,11);assert.equal(t.substitutions.length,0);}
});
test('invalid controls do not silently normalize',()=>{
 for(const o of [{homePress:101},{seed:-1},{awayFormation:'unknown'},{homeStyle:'unknown'},{homePassing:'unknown'}])assert.throws(()=>B.make(o));
});
