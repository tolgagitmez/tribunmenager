'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture(technique='shot',foot=0,kind=technique==='shot'?'shot':'pass',speed=22){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0]};
 return Array.from({length:11},(_,i)=>{const t=i*100;return {schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===1000,inPlay:true,setPiece:false,score:[0,0],ball:[.53,.15,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,goalkeeper:true}],nativeContacts:t===500?[{timeMs:500,playerId:1,databaseId:1,team:0,foot,kind,technique,ball:[.53,.15,.11],impulseVelocity:[speed,0,0]}]:[]};});
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
test('stage82 profiles follow explicit engine action and remain opt-in',()=>{
 for(const technique of ['short-pass','long-pass','high-pass','shot']){
  const f=parsed(fixture(technique)),a=R.create(f,null,{contactSync:true}),b=R.create(f,null,{strikeMotion:true});
  const x=a.sample(500,Rig),y=b.sample(500,Rig);
  assert.equal(x.players[0].nativeContact.strike,undefined);
  assert.equal(y.players[0].nativeContact.strike.profile,technique);
  assert.equal(y.players[0].nativeContact.weight,1);
  assert.equal(y.players[1].nativeContact,null);assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  assert.equal(x.players[0].x,y.players[0].x);
 }
});
test('stage82 prep and follow-through vary by technique and preserve bones',()=>{
 const sample=(kind,time,foot=0,power=22)=>{const r=R.create(parsed(fixture(kind,foot,undefined,power)),null,{strikeMotion:true,bodyBalance:true,footPlant:true});let p;for(let t=0;t<=time;t+=10)p=r.sample(t,Rig).players[0];return Rig.getPose(p);};
 const shot=sample('shot',400),pass=sample('short-pass',400);
 assert.equal(shot.nativeStrike.profile,'shot');assert.equal(pass.nativeStrike.profile,'short-pass');
 assert.notDeepEqual(shot.legs[0].ankle,pass.legs[0].ankle);
 assert.ok(sample('shot',650).nativeStrike);assert.equal(sample('short-pass',750).nativeStrike,undefined);
 const right=sample('shot',500,1);assert.equal(right.legs[1].nativeContact,true);assert.equal(right.legs[0].nativeContact,false);
 for(const pose of [shot,pass,right])for(const l of pose.legs){
  assert.ok(Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
  assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
 }
 assert.ok(sample('shot',500,0,30).nativeStrike.power>sample('shot',500,0,8).nativeStrike.power);
});
test('stage82 old pass uses generic motion, unknown foot and stopped play do not animate',()=>{
 const f=fixture('short-pass');delete f[5].nativeContacts[0].technique;
 assert.equal(R.create(parsed(f),null,{strikeMotion:true}).sample(500).players[0].nativeContact.strike.profile,'pass');
 for(const mutate of [f=>f[5].nativeContacts[0].foot=-1,f=>f[5].nativeContacts[0].ball[2]=1,f=>f[5].setPiece=true]){
  const f=fixture();mutate(f);assert.equal(R.create(parsed(f),null,{strikeMotion:true}).sample(500).players[0].nativeContact,null);
 }
 const control=fixture('none',0,'control');
 assert.equal(R.create(parsed(control),null,{strikeMotion:true}).sample(500).players[0].nativeContact,null);
});
