'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const row=[[.1,-.45,-.1],[.1,-.45,.1]],next=[[.3,-.35,-.1],[.3,-.35,.1]],bank={idle:{samples:[row,next]},run:{samples:[row,next]},shoot:{samples:[row,next]},'dive-right':{samples:[row,next]}};
function fixture(){
 const p={id:1,team:0,databaseId:1,position:[0,0,0],velocity:[2.5,0,0],direction:[1,0,0],heightMetres:1.8};
 return Array.from({length:11},(_,i)=>({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===10,inPlay:true,setPiece:false,score:[0,0],ball:[.4,0,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,team:1,databaseId:2,goalkeeper:true}]}));
}
test('stage92 clip interpolation and contact priority',()=>{
 assert.ok(Math.abs(Rig.sampleClipArms(bank,'run',.5)[0][0]-.2)<1e-9);
 const p={nativeClipLibrary:bank,nativeBlend:true,role:'FIELD',speed:3};
 assert.equal(Rig.nativeClipCue(p,.3,null,null).name,'run');
 assert.equal(Rig.nativeClipCue(p,.3,{kind:'shot',strike:{},deltaMs:0,weight:1},null),null);
 assert.equal(Rig.nativeClipCue(p,.3,{kind:'shot',strike:{},deltaMs:-170,weight:.7},null).name,'shoot');
 assert.equal(Rig.nativeClipCue(p,.3,{kind:'control',weight:1},null),null);
 assert.equal(Rig.nativeClipCue({...p,role:'GK'},.3,null,null),null);
});
test('stage92 shared library only changes bounded arm targets; no physical state or leg changes',()=>{
 const f=R.parse(fixture().map(JSON.stringify).join('\n')),a=R.create(f,null,{playerAnatomy:true}),b=R.create(f,null,{clipLibrary:bank});
 let used=0;
 for(let t=0;t<900;t+=20){
  const x=a.sample(t,Rig),y=b.sample(t,Rig);assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  const p=y.players[0],q=Rig.getPose(p),base=Rig.getPose(x.players[0]);
  assert.deepEqual(q.legs,base.legs);assert.equal(p.x,x.players[0].x);
  if(q.nativeClip){used++;assert.equal(q.nativeClip.name,'run');}
  assert.equal(Rig.getPose(y.players[1]).nativeClip,undefined);
  const anatomy=Rig.anatomyFor(p);for(const arm of q.arms)assert.ok(Math.abs(Math.hypot(...arm.wrist.map((v,i)=>v-arm.elbow[i]))-anatomy.forearm)<1e-5);
 }
 assert.ok(used>0);
});
