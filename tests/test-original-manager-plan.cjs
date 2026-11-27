'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const plan=require('../original-manager-plan.js');
test('saved lineup and explicit tactics are preserved without storage writes',()=>{
 const data={formation:'4-3-3',players:Array.from({length:11},(_,i)=>({name:'Player '+i,subposition:'CM'})),
 starters:Array.from({length:11},(_,i)=>10-i),tactics:{press:82,tempo:61,mentality:'attacking'}};
 const before=JSON.stringify(data);
 const storage={getItem:key=>{assert.equal(key,'tribun-manager-pro09');return before;},
 setItem:()=>assert.fail('storage must never change')};
 const out=plan.read(storage);
 assert.equal(out.lineup[0].name,'Player 10');
 assert.equal(out.lineup.length,11);
 assert.equal(out.tactics.find(t=>t.key==='press').value,82);
 assert.equal(out.tactics.length,3);
 assert.equal(out.nativeApplied,false);
 assert.equal(out.readOnly,true);
 assert.equal(JSON.stringify(data),before);
});
test('missing data and malformed values are not replaced by fabricated defaults',()=>{
 assert.equal(plan.inspect({}),null);
 assert.equal(plan.read({getItem:()=>'{broken'}),null);
 assert.equal(plan.read({getItem:()=>{throw Error('blocked')}}),null);
 assert.equal(plan.inspect({formation:'invalid',tactics:{press:101,tempo:'50',mentality:'constructor'}}),null);
 const out=plan.inspect({formation:'4-4-2',starters:Array(11).fill(0),players:[{name:'A'}]});
 assert.equal(out.lineup,null);
 assert.deepEqual(out.tactics,[]);
});
test('invalid or unowned starter rejects the lineup rather than repairing it',()=>{
 const data={formation:'4-3-3',players:Array.from({length:11},(_,i)=>({name:'P'+i})),
 starters:Array.from({length:11},(_,i)=>i)};
 data.players[3].owned=false;
 assert.equal(plan.inspect(data).lineup,null);
 data.players[3].owned=true;
 data.starters[3]=50;
 assert.equal(plan.inspect(data).lineup,null);
});
