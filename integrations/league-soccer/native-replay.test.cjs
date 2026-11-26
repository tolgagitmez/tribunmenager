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
 assert.equal(mid.ball.x,2);assert.ok(Math.abs(mid.ball.y-.555)<1e-9);assert.equal(mid.ball.z,-3);assert.equal(mid.ball.vx,4);assert.equal(mid.ball.vy,1);assert.equal(mid.ball.vz,-2);
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

const Rig=require('../../humanoid-rig.js');
test('stage79 is opt-in; trace-derived acceleration uses replay axes and preserves simulation',()=>{
 const f=fixture();f[0].players[1].velocity=[2,0,0];f[1].players[1].velocity=[3,1,0];
 const baseline=R.create(parse(f)),candidate=R.create(parse(f),null,{bodyBalance:true});
 const a=baseline.sample(50),b=candidate.sample(50);
 assert.equal(a.players[1].nativeBodyBalance,undefined);
 assert.equal(b.players[1].nativeBodyBalance.valid,true);
 assert.deepEqual(b.players[1].nativeBodyBalance,{ax:10,az:-10,valid:true});
 for(const k of ['x','z','vx','vz','face','speed'])assert.equal(a.players[1][k],b.players[1][k]);
 assert.deepEqual(a.ball,b.ball);assert.deepEqual(a.score,b.score);
 assert.equal(b.players[0].nativeBodyBalance.valid,false);
 assert.equal(f[0].players[1].velocity[0],2);
});
test('stage79 rejects stopped play, gaps and teleport cues and bounds outliers',()=>{
 for(const mutate of [f=>f[1].inPlay=false,f=>f[0].setPiece=true,f=>f[1].elapsedMs=400,f=>f[1].players[1].position=[20,10,0]]){
  const f=fixture();mutate(f);const r=R.create(parse(f),null,{bodyBalance:true});
  assert.equal(r.sample(20).players[1].nativeBodyBalance.valid,false);
 }
 const f=fixture();f[1].players[1].velocity=[100,100,0];
 const cue=R.create(parse(f),null,{bodyBalance:true}).sample(20).players[1].nativeBodyBalance;
 assert.ok(Math.hypot(cue.ax,cue.az)<=15.000001);
});
test('stage79 body lean, brake crouch, and special action isolation',()=>{
 const p={x:0,z:0,face:0,speed:4,action:'run',actionClock:0,nativeBodyBalance:{ax:5,az:6,valid:true}};
 let pose;
 for(let i=0;i<30;i++){p.x+=.04;pose=Rig.update(p,.01);}
 assert.ok(pose.nativeBalance.pitch>.05);assert.ok(pose.nativeBalance.roll>.05);
 p.nativeBodyBalance={ax:-8,az:0,valid:true};
 for(let i=0;i<30;i++){p.x+=.04;pose=Rig.update(p,.01);}
 assert.ok(pose.nativeBalance.pitch<0);assert.ok(pose.nativeBalance.drop>.02);
 for(const leg of pose.legs)assert.ok(Math.abs(Math.hypot(...leg.knee.map((v,i)=>v-leg.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
 p.action='shoot';p.actionClock=.4;p.kickFoot=0;
 pose=Rig.update(p,.01);assert.deepEqual(pose.nativeBalance,{pitch:0,roll:0,drop:0});
 Rig.reset(p);p.action='run';p.actionClock=0;pose=Rig.update(p,0);
 assert.deepEqual(pose.nativeBalance,{pitch:0,roll:0,drop:0});
});
test('stage79 replay animation time follows recording, not display playback rate',()=>{
 const f=fixture(),calls=[],rig={update:(p,dt)=>{if(p.id===1)calls.push(dt)},reset:()=>{}};
 const r=R.create(parse(f),null,{bodyBalance:true});
 r.sample(0,rig,.1);r.sample(20,rig,.09);r.sample(20,rig,.09);r.sample(5,rig,.09);
 assert.deepEqual(calls,[0,.02,0,0]);
});
