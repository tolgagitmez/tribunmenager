'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture({kind='control',foot=0,movement=[2,0,0],out=[3,0,0],knockOn=false,opponentDistance=3,skill=.6,uniquePossession=true,legacy=false}={}){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:movement,direction:[1,0,0]};
 const event={timeMs:500,playerId:1,databaseId:1,team:0,foot,kind,technique:'none',ball:[.49,.15,.11],impulseVelocity:out};
 if(!legacy)event.controlContext={incomingVelocity:[-5,0,0],playerVelocity:movement,direction:[1,0,0],opponentDistance,dribbleSkill:skill,controlSkill:skill,knockOn,uniquePossession};
 return Array.from({length:11},(_,i)=>{const t=i*100;return {schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===1000,inPlay:true,setPiece:false,score:[0,0],ball:[.49,.15,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,goalkeeper:true}],nativeContacts:t===500?[event]:[]};});
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
const sample=(options,time=500)=>{const r=R.create(parsed(fixture(options)),null,{controlMotion:true,bodyBalance:true,footPlant:true});let p;for(let t=0;t<=time;t+=10)p=r.sample(t,Rig).players[0];return {p,pose:Rig.getPose(p)};};
test('stage83 control profiles use recorded context and preserve match state',()=>{
 for(const [options,profile] of [[{kind:'trap'},'cushion'],[{},'close-control'],[{movement:[5,0,0]},'running-control'],[{out:[0,3,0]},'turn-control'],[{knockOn:true},'knock-on']]){
  const f=parsed(fixture(options)),a=R.create(f),b=R.create(f,null,{controlMotion:true});
  const x=a.sample(500,Rig),y=b.sample(500,Rig);
  assert.equal(x.players[0].nativeContact,undefined);
  assert.equal(y.players[0].nativeContact.control.profile,profile);
  assert.equal(y.players[1].nativeContact,null);
  assert.equal(y.players[0].nativeContact.weight,1);
  for(const k of ['x','z','face','vx','vz','speed'])assert.equal(x.players[0][k],y.players[0][k]);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
 }
});
test('stage83 contact foot, pressure, skill and anatomical lengths',()=>{
 const left=sample({foot:0,opponentDistance:.5,skill:.9}),right=sample({foot:1,opponentDistance:.5,skill:.3});
 assert.equal(left.pose.legs[0].nativeContact,true);assert.equal(left.pose.legs[1].nativeContact,false);
 assert.equal(right.pose.legs[1].nativeContact,true);assert.equal(right.pose.legs[0].nativeContact,false);
 assert.ok(left.pose.nativeControl.pressure>.5);assert.ok(left.pose.nativeControl.skill>right.pose.nativeControl.skill);
 assert.equal(sample({opponentDistance:.5,uniquePossession:false}).pose.nativeControl.pressure,0);
 assert.equal(sample({opponentDistance:.5,knockOn:true}).pose.nativeControl.pressure,0);
 for(const {pose} of [left,right,sample({kind:'trap'},560)])for(const l of pose.legs){
  assert.ok(Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
  assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
 }
});
test('stage83 no invented contact or context, and legacy compatibility',()=>{
 const old=sample({legacy:true});assert.equal(old.pose.nativeControl.profile,'close-control');assert.equal(old.pose.nativeControl.contextRecorded,false);
 for(const mutate of [f=>f[5].nativeContacts[0].foot=-1,f=>f[5].nativeContacts[0].ball[2]=1,f=>f[5].setPiece=true,f=>f[5].nativeContacts=[],f=>{f[5].nativeContacts[0].kind='shot';}]){
  const f=fixture();mutate(f);assert.equal(R.create(parsed(f),null,{controlMotion:true}).sample(500).players[0].nativeContact,null);
 }
 const bad=fixture();bad[5].nativeContacts[0].controlContext.opponentDistance=-1;assert.throws(()=>parsed(bad));
 assert.equal(sample({},700).pose.nativeControl,undefined);
});
