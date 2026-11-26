'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function frames(foot=0,kind='shot'){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0]};
 return [0,100,200,300,400].map(t=>({schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===400,inPlay:true,setPiece:false,score:[0,0],ball:[.53,.15,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,goalkeeper:true}],nativeContacts:t===200?[{timeMs:180,playerId:1,databaseId:1,team:0,foot,kind,ball:[.53,.15,.11],impulseVelocity:[8,0,0]}]:[]}));
}
const parse=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
test('stage81 uses timestamp and identity, not nearby players or velocity guesses',()=>{
 const f=parse(frames()),a=R.create(f),b=R.create(f,null,{contactSync:true});
 for(const t of [0,100,180,220,300]){
  const x=a.sample(t,Rig),y=b.sample(t,Rig);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  assert.equal(x.players[0].nativeContact,undefined);assert.equal(y.players[1].nativeContact,null);
  if(t===180){const cue=y.players[0].nativeContact;assert.equal(cue.deltaMs,0);assert.equal(cue.foot,0);assert.equal(cue.weight,1);}
  if(t===300)assert.equal(y.players[0].nativeContact,null);
 }
});
test('stage81 only targets recorded foot and preserves anatomical bone lengths',()=>{
 const r=R.create(parse(frames(1,'control')),null,{contactSync:true,bodyBalance:true,footPlant:true});
 let p;for(let t=0;t<=180;t+=10)p=r.sample(t,Rig).players[0];
 const pose=Rig.getPose(p);
 assert.equal(pose.legs[0].nativeContact,false);assert.equal(pose.legs[1].nativeContact,true);
 assert.equal(pose.legs[1].stance,false);
 for(const l of pose.legs)assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
});
test('stage81 ignores unsupported limb, high ball, stopped play and legacy records',()=>{
 for(const mutate of [f=>f[2].nativeContacts[0].foot=-1,f=>f[2].nativeContacts[0].ball[2]=1,f=>f[1].setPiece=true,f=>f.forEach(x=>delete x.nativeContacts)]){
  const f=frames();mutate(f);const r=R.create(parse(f),null,{contactSync:true});
  assert.equal(r.sample(180,Rig).players[0].nativeContact,null);
 }
 const f=frames();f[2].nativeContacts[0].timeMs=250;assert.throws(()=>parse(f));
});
