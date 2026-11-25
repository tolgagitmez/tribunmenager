'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js');
// Synthetic renderer-contract samples only; never claim these are engine results.
function fixture(){
 const players=Array.from({length:22},(_,i)=>({id:i,team:i<11?0:1,databaseId:i+1,position:[i<11?-10:10,i%11,0],velocity:[1,2,0],direction:[1,0,0],goalkeeper:i%11===0}));
 const frame={schema:1,engine:'league-soccer',elapsedMs:100,matchMs:0,done:false,score:[0,0],ball:[0,2,.11],ballVelocity:[4,2,1],players};
 const next=structuredClone(frame);next.elapsedMs=200;next.matchMs=1800;next.ball=[4,4,1];next.players[1].position=[-9,2,0];next.players[1].direction=[0,1,0];next.score=[1,0];next.done=true;
 return [frame,next];
}
const parse=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
test('native axes, velocities, interpolation, actual score and persistent render identity',()=>{
 const f=fixture(),r=R.create(parse(f)),first=r.sample(0),actor=first.players[1],mid=r.sample(50);
 assert.equal(mid.players[1],actor);assert.equal(mid.players.length,22);
 assert.deepEqual(mid.ball,{x:2,y:.555,z:-3,vx:4,vy:1,vz:-2});
 assert.equal(actor.x,-9.5);assert.equal(actor.z,-1.5);assert.ok(Math.abs(actor.face+Math.PI/4)<1e-9);
 assert.equal(mid.players[0].role,'GK');assert.deepEqual(mid.score,[0,0]);
 const end=r.sample(100);assert.deepEqual(end.score,[1,0]);assert.equal(end.done,true);
 assert.equal(r.sample(0).done,false);assert.equal(f[0].players[1].position[0],-10);
});
test('rejects duplicate IDs, missing velocity, backwards clock, data after final',()=>{
 for(const change of [f=>f[0].players[1].id=0,f=>delete f[0].ballVelocity,f=>f[1].elapsedMs=99,f=>f[0].done=true]){
  const f=fixture();change(f);assert.throws(()=>parse(f));
 }
});
test('no invented players or interpolation across discontinuous gaps',()=>{
 const f=fixture();f[1].elapsedMs=2000;f[1].players.pop();
 const r=R.create(parse(f));assert.equal(r.sample(500).ball.x,0);assert.equal(r.sample(1900).players.length,21);
});
test('manifest mismatch fails instead of mislabeling native actors',()=>{
 const f=fixture(),manifest={schema:1,teams:[0,1].map(team=>({team,players:f[0].players.filter(p=>p.team===team).map((p,i)=>({nativeId:p.databaseId,slot:i,role:i===0?'GK':'CF',name:'Player '+p.id,rosterId:'r'+p.id}))}))};
 const r=R.create(parse(f),manifest);assert.equal(r.sample(0).players[0].rosterId,'r0');
 manifest.teams[0].players[0].nativeId=99;assert.throws(()=>R.create(parse(f),manifest));
});
module.exports={fixture};
