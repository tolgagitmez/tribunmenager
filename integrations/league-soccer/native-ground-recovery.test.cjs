'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture({state='trip',speed=0,tripType=3}={}){
 const p={id:1,team:0,databaseId:1,position:[0,0,0],velocity:[speed,0,0],direction:[1,0,0],heightMetres:1.8};
 const trip={timeMs:500,playerId:1,databaseId:1,team:0,opponentId:2,tripType,kind:'tackle-trip',direction:[1,0,0],displacement:0,relativeSpeed:4,balance:.4,possession:false};
 return Array.from({length:21},(_,i)=>({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===20,inPlay:true,setPiece:false,score:[0,0],ball:[.4,0,.11],ballVelocity:[0,0,0],players:[{...p,groundAction:i>=5&&i<14?state:'other'},{...p,id:2,team:1,databaseId:2,position:[.6,0,0],groundAction:'other'}],nativeDuels:i===5?[trip]:[]}));
}
const parsed=f=>R.parse(f.map(JSON.stringify).join('\n'));
test('stage94 ground envelope is bounded and rises after contact',()=>{
 const c={kind:'fall',age:300};assert.equal(Rig.groundEnvelope(c,0).phase,'ground');
 assert.ok(Rig.groundEnvelope(c,0).weight>Rig.groundEnvelope({...c,age:750},0).weight);
 assert.equal(Rig.groundEnvelope(c,2.2).weight,0);
 assert.equal(Rig.groundEnvelope({...c,age:0},0).weight,0);
});
test('stage94 confirmed slow trip lowers pose then recovers without changing physical state',()=>{
 const f=parsed(fixture()),a=R.create(f,null,{contactPrecision:true}),b=R.create(f,null,{groundRecovery:true});let low=Infinity,late=0;
 for(let t=0;t<1500;t+=10){
  const x=a.sample(t,Rig),y=b.sample(t,Rig),p=y.players[0],q=Rig.getPose(p),an=Rig.anatomyFor(p);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  for(const k of ['x','z','vx','vz','face','speed'])assert.equal(x.players[0][k],p[k]);
  assert.equal(y.players[1].nativeGroundRecovery,null);
  if(t===800){assert.equal(q.nativeGroundRecovery.phase,'ground');assert.ok(q.pelvis[1]<Rig.getPose(x.players[0]).pelvis[1]);low=q.pelvis[1];}
  if(t===1300)late=q.pelvis[1];
  for(const l of q.legs){
   assert.ok(Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-an.thigh)<1e-5);
   assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-an.shin)<1e-5);
  }
  for(const arm of q.arms)assert.ok(Math.abs(Math.hypot(...arm.wrist.map((v,j)=>v-arm.elbow[j]))-an.forearm)<1e-5);
 }
 assert.ok(late>low);
});
test('stage94 no ground fall without confirmed state, severe trip, or slow movement',()=>{
 for(const options of [{state:'other'},{speed:4},{tripType:1}]){
  const r=R.create(parsed(fixture(options)),null,{groundRecovery:true});
  assert.equal(r.sample(800,Rig).players[0].nativeGroundRecovery,null);
 }
 const f=fixture();f[8].setPiece=true;
 assert.equal(R.create(parsed(f),null,{groundRecovery:true}).sample(800,Rig).players[0].nativeGroundRecovery,null);
 f[8].players[0].groundAction='invented';assert.throws(()=>parsed(f));
});
