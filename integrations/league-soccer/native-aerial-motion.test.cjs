'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture({height=2.2,headContact=true,foot=-1,speed=0,distance=.7,kind='shot'}={}){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0]};
 const ball=[.24,.12,height];
 const e={timeMs:500,playerId:1,databaseId:1,team:0,kind,technique:kind==='shot'?'shot':'none',foot,headContact,ball,impulseVelocity:[8,0,0],
 controlContext:{incomingVelocity:[-5,0,0],playerVelocity:[speed,0,0],direction:[1,0,0],opponentDistance:distance,dribbleSkill:.5,controlSkill:.5,knockOn:false,uniquePossession:false}};
 return Array.from({length:13},(_,i)=>{const t=i*100;return {schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===1200,inPlay:true,setPiece:false,score:[0,0],ball,ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,position:[0,.8,0]}],nativeContacts:t===500?[e]:[]};});
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
const sample=(opts,t=500)=>{const r=R.create(parsed(fixture(opts)),null,{aerialMotion:true,bodyBalance:true,footPlant:true});let p;for(let ms=0;ms<=t;ms+=10)p=r.sample(ms,Rig).players[0];return Rig.getPose(p);};
test('stage87 explicit head event drives only its player and leaves physical state identical',()=>{
 const f=parsed(fixture()),a=R.create(f),b=R.create(f,null,{aerialMotion:true});
 for(const t of [100,400,500,700,900]){
  const x=a.sample(t,Rig),y=b.sample(t,Rig);
  assert.equal(x.players[0].nativeAerial,undefined);assert.equal(y.players[1].nativeAerial,null);
  if(t===500)assert.equal(y.players[0].nativeAerial.weight,1);
  if(t===100||t===900)assert.equal(y.players[0].nativeAerial,null);
  for(const k of ['x','z','vx','vz','face','speed'])assert.equal(x.players[0][k],y.players[0][k]);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
 }
});
test('stage87 height, movement context and landing select bounded poses',()=>{
 const jump=sample({height:2.2}),stoop=sample({height:1.2}),run=sample({height:1.75,speed:4}),stand=sample({height:1.75});
 assert.equal(jump.nativeAerial.profile,'jump');assert.equal(stoop.nativeAerial.profile,'stoop');
 assert.equal(run.nativeAerial.profile,'running');assert.equal(stand.nativeAerial.profile,'standing');
 assert.ok(jump.nativeAerial.jump>0&&jump.nativeAerial.jump<=.36);
 assert.ok(jump.pelvis[1]>stoop.pelvis[1]);assert.ok(jump.legs.every(l=>!l.stance));
 assert.ok(sample({},700).nativeAerial.landing>0);
 assert.equal(sample({distance:3}).nativeAerial.contested,false);
 for(const pose of [jump,stoop,run,stand])for(const l of pose.legs){
  assert.ok(Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
  assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
 }
});
test('stage87 no inferred head contact on high ball, unknown limb, or stoppage',()=>{
 for(const mutate of [f=>delete f[5].nativeContacts[0].headContact,f=>f[5].nativeContacts[0].headContact=false,f=>f[5].nativeContacts[0].foot=0,f=>f[5].setPiece=true,f=>f[5].nativeContacts[0].databaseId=99]){
  const f=fixture();mutate(f);assert.equal(R.create(parsed(f),null,{aerialMotion:true}).sample(500).players[0].nativeAerial,null);
 }
 const f=fixture();f[5].nativeContacts[0].headContact='true';assert.throws(()=>parsed(f));
});
