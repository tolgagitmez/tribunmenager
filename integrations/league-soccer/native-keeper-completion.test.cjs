'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture({lateral=1.15,state='deflect',hand=1,kind='parry',height=1.25,held=false}={}){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0],goalkeeper:true,heightMetres:1.88};
 const ball=[.25,-lateral,height],event={timeMs:500,playerId:1,databaseId:1,team:0,kind,hand,ball,incomingVelocity:[-12,0,0]};
 return Array.from({length:14},(_,i)=>({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===13,inPlay:true,setPiece:false,score:[0,0],ball,ballVelocity:[0,0,0],players:[{...p,keeperAction:i>=3&&i<=9?state:'other'},{...p,id:2,databaseId:2,team:1,goalkeeper:false,position:[3,0,0]}],nativeKeeperEvents:i===5?[event]:[],ballRetainerId:held&&i>=5?1:null}));
}
const parsed=f=>R.parse(f.map(JSON.stringify).join('\n'));
test('stage95 lateral save envelope mirrors direction and bounds root display shift',()=>{
 const c={lateral:1.4,weight:1,ball:{y:1.2},deltaMs:0};
 const a=Rig.keeperDiveProfile(c),b=Rig.keeperDiveProfile({...c,lateral:-1.4});
 assert.equal(a.shift,-b.shift);assert.equal(a.tilt,-b.tilt);assert.ok(Math.abs(a.shift)<=.36);
 assert.equal(a.phase,'reach');assert.equal(Rig.keeperDiveProfile({...c,deltaMs:100}).phase,'recover');
});
test('stage95 confirmed lateral deflect uses bounded posture and preserves match',()=>{
 const frames=parsed(fixture()),a=R.create(frames,null,{groundRecovery:true}),b=R.create(frames,null,{keeperCompletion:true});
 let samples=0;
 for(let t=0;t<1200;t+=10){
  const x=a.sample(t,Rig),y=b.sample(t,Rig),p=y.players[0],q=Rig.getPose(p),an=Rig.anatomyFor(p);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  for(const k of ['x','z','vx','vz','face','speed'])assert.equal(p[k],x.players[0][k]);
  if(q.nativeKeeperDive){samples++;assert.ok(Math.abs(q.nativeKeeperDive.shift)<=.360001);}
  if(t===500){assert.ok(q.nativeKeeperDive?.weight>0);assert.ok(q.arms[1].contactTarget);assert.equal(q.arms[0].contactTarget,undefined);}
  if(t===1100)assert.equal(q.nativeKeeperDive,undefined);
  for(const l of q.legs){
   assert.ok(Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-an.thigh)<1e-5);
   assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-an.shin)<1e-5);
  }
  for(const arm of q.arms)assert.ok(Math.abs(Math.hypot(...arm.wrist.map((v,j)=>v-arm.elbow[j]))-an.forearm)<1e-5);
 }
 assert.ok(samples>0);
});
test('stage95 no invented dive without state, known parry hand, or lateral reach',()=>{
 for(const opt of [{state:'other'},{hand:-1},{lateral:.2},{held:true}]){
  const r=R.create(parsed(fixture(opt)),null,{keeperCompletion:true});
  assert.equal(r.sample(500,Rig).players[0].nativeKeeperDive,null);
 }
});
