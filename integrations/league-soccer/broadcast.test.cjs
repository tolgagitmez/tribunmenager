'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{once}=require('node:events');
const Replay=require('./native-replay.js'),Broadcast=require('./broadcast-clock.js'),{report}=require('./attack-report.cjs'),{createServer}=require('./broadcast-server.cjs');
const stats={shots:[3,2],onTarget:[1,1],passes:[20,18],completed:[15,12],fouls:[1,0],possessionMs:[800,700]};
function frames(){
 return [0,100,200,300,400,500,600].map((ms,i)=>({schema:1,engine:'league-soccer',elapsedMs:ms,matchMs:i===6?5400000:i*1000,done:i===6,score:i===6?[1,0]:[0,0],ball:[i<2?37:i<4?40:i===4?0:-40,0,.11],ballVelocity:[1,0,0],inPlay:i!==4,attackDirection:i>=5?[-1,1]:[1,-1],stats,players:[{id:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0],uniquePossession:true,goalkeeper:false},{id:2,team:1,position:[0,0,0],velocity:[0,0,0],direction:[-1,0,0],uniquePossession:false,goalkeeper:true}]}));
}
test('broadcast takes exactly 300 seconds regardless of source duration; no early final',()=>{
 const c=Broadcast.create(frames());
 assert.equal(c.at(-1).phase,'scheduled');assert.equal(c.at(0).index,0);
 assert.equal(c.at(150000).nativeMs,300);
 assert.equal(c.at(299999).phase,'playing');assert.notEqual(c.at(299999).index,6);
 assert.equal(c.at(300000).index,6);assert.equal(c.at(300000).remainingMs,0);
 assert.equal(c.at(500000).phase,'finished');
 const f=frames();f[6].elapsedMs=f[5].elapsedMs;assert.notEqual(Broadcast.create(f).at(299999).index,6);
 f[6].done=false;assert.throws(()=>Broadcast.create(f));
});
test('attack report uses native possession, direction, play state and shot counts',()=>{
 const f=frames(),r=report(Replay.parse(f.map(JSON.stringify).join('\n')));
 assert.deepEqual(r.shots,[3,2]);assert.deepEqual(r.score,[1,0]);
 assert.deepEqual(r.sampled.observedBoxCrossings,[1,0]);assert.deepEqual(r.sampled.controlledBoxCrossings,[1,0]);
 assert.deepEqual(r.sampled.controlledBoxMs,[200,0]);assert.equal(r.sampled.observedOpenPlayMs,400);
 delete f[0].inPlay;assert.equal(report(f).sampled,null);
});
test('two clients, no spectators, late join and backwards system clock cannot change score or schedule',async()=>{
 let now=900;const s=createServer(frames(),{kickoffMs:1000,now:()=>now});
 s.listen(0,'127.0.0.1');await once(s,'listening');
 const url='http://127.0.0.1:'+s.address().port+'/api/native-pilot/broadcast';
 const get=()=>fetch(url).then(r=>r.json());
 try{
  assert.equal((await get()).frame,null);
  now=151000;const a=await get(),b=await get();assert.deepEqual(a,b);assert.equal(a.elapsedMs,150000);assert.deepEqual(a.frame.score,[0,0]);
  now=1200;assert.equal((await get()).elapsedMs,150000);
  now=301000;const end=await get();assert.equal(end.phase,'finished');assert.deepEqual(end.frame.score,[1,0]);
  assert.equal((await fetch(url,{method:'POST'})).status,405);
 }finally{s.closeAllConnections();await new Promise(r=>s.close(r));}
});

test('collective metrics measure sustained forward outlets and two box attackers',()=>{
 const f=frames();
 for(const row of f){
  const d=row.attackDirection[0];
  row.players[0].position=[d*35,0,0];
  row.players.push({id:3,team:0,position:[d*41,8,0],velocity:[0,0,0],direction:[d,0,0],uniquePossession:false,goalkeeper:false});
  row.players.push({id:4,team:0,position:[d*43,-8,0],velocity:[0,0,0],direction:[d,0,0],uniquePossession:false,goalkeeper:false});
 }
 const r=report(Replay.parse(f.map(JSON.stringify).join('\n')));
 assert.deepEqual(r.sampled.controlledWithForwardOutletMs,[400,0]);
 assert.deepEqual(r.sampled.controlledWithTwoBoxAttackersMs,[400,0]);
});
