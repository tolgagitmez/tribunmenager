'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const A=require('./upstream-arm-bank.js'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const row=[[.12,-.45,-.1],[.12,-.45,.1]],next=[[.25,-.32,-.1],[-.25,-.32,.1]];
const sample={schema:1,source:'upstream-raw-retarget',clips:{idle:{duration:.24,samples:[row,next]},run:{duration:.24,samples:[row,next]}}};
test('reject invalid arm banks and freeze valid ones',()=>{
 const b=A.parse(sample);assert.ok(Object.isFrozen(b.run.samples[0][0]));
 assert.throws(()=>A.parse({...sample,source:'other'}));
 const bad=JSON.parse(JSON.stringify(sample));bad.clips.run.samples[0][0]=[1,0,0];assert.throws(()=>A.parse(bad));
});
test('real converted data when supplied and safe gait-only cues',()=>{
 const b=A.parse(process.env.TRIBUN_ARM_BANK?JSON.parse(fs.readFileSync(process.env.TRIBUN_ARM_BANK)):sample);
 const p={nativeClipLibrary:b,nativeBlend:true,role:'FIELD',speed:3};
 const cue=Rig.nativeClipCue(p,.5,null,null);assert.equal(cue.source,'upstream-raw-retarget');assert.ok(cue.weight<=.32);
 assert.equal(Rig.nativeClipCue(p,0,null,null),null);
 assert.equal(Rig.nativeClipCue(p,.5,{kind:'shot',strike:{},deltaMs:-170,weight:1},null),null);
 assert.equal(Rig.nativeClipCue(p,.5,{kind:'control',weight:1},null),null);
 assert.equal(Rig.nativeClipCue({...p,role:'GK'},.5,null,null),null);
});
test('same recorded score, ball and leg pose with imported arms',()=>{
 const bank=A.parse(process.env.TRIBUN_ARM_BANK?JSON.parse(fs.readFileSync(process.env.TRIBUN_ARM_BANK)):sample);
 const p={id:1,team:0,databaseId:1,position:[0,0,0],velocity:[2.5,0,0],direction:[1,0,0],heightMetres:1.8};
 const f=R.parse(Array.from({length:11},(_,i)=>JSON.stringify({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===10,inPlay:true,setPiece:false,score:[0,0],ball:[.4,0,.11],ballVelocity:[0,0,0],players:[{...p,position:[i*.25,0,0]},{...p,id:2,databaseId:2,team:1,goalkeeper:true}]})).join('\n'));
 const a=R.create(f,null,{playerAnatomy:true}),b=R.create(f,null,{clipLibrary:bank});
 let used=0;
 for(let t=0;t<900;t+=20){
  const x=a.sample(t,Rig),y=b.sample(t,Rig),pose=Rig.getPose(y.players[0]),base=Rig.getPose(x.players[0]);
  assert.deepEqual(x.score,y.score);assert.deepEqual(x.ball,y.ball);assert.deepEqual(pose.legs,base.legs);
  assert.equal(x.players[0].x,y.players[0].x);
  if(pose.nativeClip){used++;assert.equal(pose.nativeClip.source,'upstream-raw-retarget');}
  const anatomy=Rig.anatomyFor(y.players[0]);for(const arm of pose.arms)assert.ok(Math.abs(Math.hypot(...arm.wrist.map((v,i)=>v-arm.elbow[i]))-anatomy.forearm)<1e-5);
 }
 assert.ok(used>0);
});
