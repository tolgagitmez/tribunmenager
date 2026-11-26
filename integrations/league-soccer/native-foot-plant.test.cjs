'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js'),B=require('./foot-plant-benchmark.cjs');
function fixture(){
 let x=0,y=0;const frames=[];
 for(let i=0;i<=100;i++){
  const t=i*.1,speed=t<2?t*2:t<5?4:t<7?Math.max(0,4-(t-5)*2):2;
  const angle=t<3?0:t<5?(t-3)*.7:1.4;
  const vx=speed*Math.cos(angle),vy=speed*Math.sin(angle);
  const p={id:1,team:0,databaseId:1,position:[x,y,0],velocity:[vx,vy,0],direction:[Math.cos(angle),Math.sin(angle),0]};
  frames.push({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===100,inPlay:true,setPiece:false,score:[0,0],ball:[0,0,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,team:1,databaseId:2,goalkeeper:true}]});
  x+=vx*.1;y+=vy*.1;
 }
 return frames;
}
test('stage80 remains opt-in and does not change native match state',()=>{
 const f=fixture(),a=R.create(f,null,{bodyBalance:true}),b=R.create(f,null,{bodyBalance:true,footPlant:true});
 for(let ms=0;ms<=10000;ms+=20){
  const left=a.sample(ms,Rig),right=b.sample(ms,Rig);
  assert.equal(left.players[0].nativeFootPlant,undefined);
  assert.equal(right.players[1].nativeFootPlant,false);
  for(const k of ['x','z','vx','vz','speed','face'])assert.equal(left.players[0][k],right.players[0][k]);
  assert.deepEqual(left.ball,right.ball);assert.deepEqual(left.score,right.score);
 }
});
test('stage80 measures actual IK ankles and rejects anatomical drift',()=>{
 const report=B.compare(fixture());
 assert.equal(report.sufficient,true);
 for(const m of [report.baseline,report.candidate]){
  assert.ok(m.landings>4);assert.ok(m.requested>0);assert.ok(m.rejected<=m.requested);
  assert.ok(m.maxBoneError<1e-5);assert.ok(Number.isFinite(m.meanSlip));
 }
 console.log('Synthetic foot diagnostic (not match evidence): '+JSON.stringify(report));
});
test('stage80 pauses, resets on gaps and preserves special contact priority',()=>{
 const f=fixture();f[5].setPiece=true;
 const r=R.create(f,null,{bodyBalance:true,footPlant:true});
 assert.equal(r.sample(0,Rig).players[0].nativeFootPlant,true);
 assert.equal(r.sample(450,Rig).players[0].nativeFootPlant,false);
 const p=r.sample(600,Rig).players[0];
 const pose=Rig.getPose(p);r.sample(600,Rig);assert.equal(Rig.getPose(p),pose);
 const actor={x:0,z:0,face:0,speed:2,vx:2,vz:0,action:'shoot',actionClock:.4,kickFoot:0};
 const normal=Rig.update(actor,.016);const other={...actor,nativeFootPlant:true};
 assert.deepEqual(Rig.update(other,.016),normal);
});
