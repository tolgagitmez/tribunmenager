'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {convert,serialize,demo,nativeStats}=require('./fixture-adapter.cjs');
test('both selected elevens preserve identity, role and native coordinates',()=>{
 const c=demo(),m=convert(c);
 assert.equal(m.teams.length,2);
 for(const t of m.teams){
  assert.equal(t.players.length,11);
  assert.equal(t.players[0].role,'GK');
  assert.deepEqual(new Set(t.players.map(p=>p.rosterId)),new Set(t.team?c.awayStarters:c.starters));
  for(const p of t.players){
   assert.ok(Math.abs(p.x)<=1&&Math.abs(p.y)<=1);
   assert.equal(Object.keys(p.stats).length,Object.keys(nativeStats).length);
   assert.ok(Object.values(p.stats).every(v=>v>=.01&&v<=1));
  }
 }
 assert.equal(new Set(m.teams.flatMap(t=>t.players.map(p=>p.nativeId))).size,22);
 assert.equal(m.teams[0].tactics.team_pressure,.85);
 assert.equal(m.teams[1].tactics.team_pressure,.30);
 assert.ok(m.teams[0].tactics.counter_attack>m.teams[1].tactics.counter_attack);
 assert.ok(m.teams[0].players.find(p=>p.slot===1).stats.technical_shot>m.teams[1].players.find(p=>p.slot===0).stats.technical_shot);
 assert.equal(serialize(m).trim().split('\n').length,25);
});
test('invalid starter, ownership and unsupported formation fail closed',()=>{
 for(const mutate of [c=>c.starters[0]='missing',c=>c.starters[0]=c.starters[1],c=>c.players[0].owned=false,c=>c.formation='bad']){
  const c=demo();mutate(c);assert.throws(()=>convert(c));
 }
});
test('all supported formations produce a native eleven',()=>{
 const Model=require('../../player-model.js');
 for(const f of Object.keys(Model.slots)){
  const c=demo();c.formation=f;
  c.players=Model.demoTeam(0,f);c.starters=c.players.map(p=>p.id);
  assert.equal(convert(c).teams[0].players.filter(p=>p.role==='GK').length,1);
 }
});
