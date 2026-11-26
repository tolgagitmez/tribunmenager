'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture({kind='catch',hand=0,ball=[.45,.15,.8],held=false,face=[1,0,0]}={}){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:face,goalkeeper:true};
 const e={timeMs:500,playerId:1,databaseId:1,team:0,kind,hand,ball,incomingVelocity:[-12,0,0]};
 return Array.from({length:13},(_,i)=>{const t=i*100;return {schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===1200,inPlay:true,setPiece:false,score:[0,0],ball,ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,goalkeeper:false}],nativeKeeperEvents:t===500?[e]:[],ballRetainerId:held&&t>=500&&t<=900?1:null};});
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
const sample=(opts,t=500)=>{const r=R.create(parsed(fixture(opts)),null,{keeperMotion:true});let p;for(let ms=0;ms<=t;ms+=10)p=r.sample(ms,Rig).players[0];return Rig.getPose(p);};
test('stage86 only reacts to recorded keeper events, remains opt-in and preserves match state',()=>{
 const f=parsed(fixture()),a=R.create(f),b=R.create(f,null,{keeperMotion:true});
 for(const t of [200,500,950]){
  const x=a.sample(t,Rig),y=b.sample(t,Rig);
  assert.equal(x.players[0].nativeKeeper,undefined);assert.equal(y.players[1].nativeKeeper,null);
  if(t===500)assert.equal(y.players[0].nativeKeeper.kind,'catch');
  else assert.equal(y.players[0].nativeKeeper,null);
  for(const k of ['x','z','vx','vz','face','speed'])assert.equal(x.players[0][k],y.players[0][k]);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
 }
});
test('stage86 low/high/side gestures and known parry hand preserve limb lengths',()=>{
 const low=sample({ball:[.35,0,.25]}),high=sample({ball:[.35,0,2.05]}),side=sample({kind:'parry',hand:1,ball:[.35,-.9,1.2]});
 assert.equal(low.nativeKeeper.profile,'low');assert.equal(high.nativeKeeper.profile,'high');assert.ok(low.pelvis[1]<high.pelvis[1]);
 assert.equal(side.nativeKeeper.profile,'side');assert.equal(side.nativeKeeper.targets,1);assert.equal(side.arms[0].contactTarget,undefined);assert.ok(side.arms[1].contactTarget);
 assert.equal(sample({kind:'parry',hand:-1}).nativeKeeper.targets,0);
 for(const pose of [low,high,side]){
  for(const l of pose.legs)assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
  for(const a of pose.arms)assert.ok(Math.abs(Math.hypot(...a.wrist.map((v,i)=>v-a.elbow[i]))-Rig.ANATOMY.forearm)<1e-5);
 }
});
test('stage86 holding requires native retainer and old records do not invent events',()=>{
 assert.equal(sample({held:true},800).nativeKeeper.kind,'hold');
 assert.equal(sample({held:false},800).nativeKeeper.kind,'catch');
 assert.equal(sample({held:true},1000).nativeKeeper,undefined);
 for(const mutate of [f=>f.forEach(x=>delete x.nativeKeeperEvents),f=>f[5].nativeKeeperEvents[0].databaseId=99,f=>f[5].setPiece=true]){
  const f=fixture();mutate(f);assert.equal(R.create(parsed(f),null,{keeperMotion:true}).sample(500).players[0].nativeKeeper,null);
 }
 const f=fixture();f[5].nativeKeeperEvents[0].hand=3;assert.throws(()=>parsed(f));
});
