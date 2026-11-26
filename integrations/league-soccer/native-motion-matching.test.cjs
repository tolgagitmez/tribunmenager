'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture(){
 let x=0,y=0;const frames=[];
 for(let i=0;i<=100;i++){
  const t=i*.1,forward=t<2?2.5:t<4?6:t<6?0:t<8?-2.6:0,lateral=t>=4&&t<6?2.8:0;
  const p={id:1,team:0,databaseId:1,position:[x,y,0],velocity:[forward,lateral,0],direction:[1,0,0]};
  const e={timeMs:3000,playerId:1,databaseId:1,team:0,kind:'shot',technique:'shot',foot:0,ball:[x+.4,y+.12,.11],impulseVelocity:[20,0,0]};
  frames.push({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===100,inPlay:true,setPiece:false,score:[0,0],ball:[x+.4,y+.12,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,team:1,databaseId:2,goalkeeper:true}],nativeContacts:i===30?[e]:[]});
  x+=forward*.1;y+=lateral*.1;
 }
 return frames;
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
test('stage89 matches distinct speed and local direction features with hysteresis',()=>{
 const cases=[[{},'idle'],[{forward:1.1},'walk'],[{forward:2.5},'jog'],[{forward:4.3},'run'],[{forward:6.7},'sprint'],[{lateral:-2.8},'shuffle-left'],[{lateral:2.8},'shuffle-right'],[{forward:-2.6},'backpedal'],[{forward:3.4,brake:6},'brake'],[{forward:1.5,turn:4},'pivot']];
 for(const [input,id] of cases)assert.equal(Rig.matchNativeStep(input).profile.id,id);
 assert.equal(Rig.matchNativeStep({forward:3.4},'jog').profile.id,'jog');
 assert.equal(Rig.matchNativeStep({forward:3.4},'run').profile.id,'run');
});
test('stage89 profiles and step latches preserve physical state and actual contact',()=>{
 const f=parsed(fixture()),a=R.create(f,null,{animationBlend:true}),b=R.create(f,null,{motionMatching:true}),seen=new Set();let steps=0;
 for(let t=0;t<=9900;t+=20){
  const x=a.sample(t,Rig),y=b.sample(t,Rig),p=y.players[0],pose=Rig.getPose(p);
  assert.equal(x.players[0].nativeMotionMatch,undefined);assert.equal(y.players[1].nativeMotionMatch,false);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  for(const k of ['x','z','vx','vz','face','speed'])assert.equal(x.players[0][k],p[k]);
  if(pose.nativeMotionMatch)seen.add(pose.nativeMotionMatch.profile);
  for(const l of pose.legs){
   if(l.stepProfile)steps++;
   assert.ok(Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
   assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
  }
  if(t===3000){assert.equal(p.nativeContact.deltaMs,0);assert.equal(pose.legs[0].nativeContact,true);}
 }
 assert.ok(seen.has('jog')&&seen.has('sprint')&&seen.has('shuffle-left')&&seen.has('backpedal'));assert.ok(steps>0);
});
test('stage89 seek reset and invalid interval',()=>{
 const f=fixture();f[5].setPiece=true;const frames=parsed(f),r=R.create(frames,null,{motionMatching:true});
 assert.equal(r.sample(450,Rig).players[0].nativeMotionMatch,false);
 r.sample(1200,Rig);const p=r.sample(100,Rig).players[0],fresh=R.create(frames,null,{motionMatching:true}).sample(100,Rig).players[0];
 assert.deepEqual(Rig.getPose(p).pelvis,Rig.getPose(fresh).pelvis);
});
