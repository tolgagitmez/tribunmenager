'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture(kind='foot'){
 const p={id:1,team:0,databaseId:1,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0],heightMetres:1.8,goalkeeper:kind==='palm'};
 const ball=kind==='head'?[.18,0,2.15]:kind==='palm'?[.5,-.3,1.2]:[.52,.13,.11];
 const e={timeMs:500,playerId:1,databaseId:1,team:0,kind:'shot',technique:'shot',foot:kind==='head'?-1:0,headContact:kind==='head',ball,impulseVelocity:[15,0,0]};
 const k={timeMs:500,playerId:1,databaseId:1,team:0,kind:'parry',hand:1,ball,incomingVelocity:[-15,0,0]};
 return Array.from({length:11},(_,i)=>({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===10,inPlay:true,setPiece:false,score:[0,0],ball,ballVelocity:[0,0,0],players:[p,{...p,id:2,team:1,databaseId:2,goalkeeper:false,position:[0,3,0]}],nativeContacts:i===5&&kind!=='palm'?[e]:[],nativeKeeperEvents:i===5&&kind==='palm'?[k]:[]}));
}
const parsed=f=>R.parse(f.map(JSON.stringify).join('\n'));
test('stage93 sphere metric uses actual radius and handles coincident points',()=>{
 assert.ok(Math.abs(Rig.surfaceError([.2,0,0],[0,0,0])-.09)<1e-9);
 for(const p of [[.2,0,0],[0,0,0]])assert.ok(Rig.surfaceError(Rig.sphereSurface(p,[0,0,0]),[0,0,0])<1e-9);
});
for(const kind of ['foot','palm','head'])test('stage93 '+kind+' correction is bounded, non-increasing and physical-state invariant',()=>{
 const f=parsed(fixture(kind)),a=R.create(f,null,{playerAnatomy:true}),b=R.create(f,null,{contactPrecision:true});let found=0;
 for(let t=0;t<900;t+=10){
  const x=a.sample(t,Rig),y=b.sample(t,Rig),p=y.players[0],pose=Rig.getPose(p),base=Rig.getPose(x.players[0]),an=Rig.anatomyFor(p);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  for(const k of ['x','z','vx','vz','face','speed'])assert.equal(p[k],x.players[0][k]);
  if(t===500){assert.ok(pose.nativeContactPrecision?.some(m=>m.kind===kind));}
  for(const m of pose.nativeContactPrecision||[]){
   found++;assert.ok(m.after<=m.before+1e-9);assert.ok(m.correction<=.160001);
   if(kind==='foot')assert.deepEqual(pose.legs[1],base.legs[1]);
  }
  if(Math.abs(t-500)>35)assert.equal(pose.nativeContactPrecision,undefined);
  for(const l of pose.legs){
   assert.ok(Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-an.thigh)<1e-5);
   assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-an.shin)<1e-5);
  }
  for(const arm of pose.arms)assert.ok(Math.abs(Math.hypot(...arm.wrist.map((v,j)=>v-arm.elbow[j]))-an.forearm)<1e-5);
 }
 assert.ok(found>0);
});
test('stage93 no correction on unrecorded events or stoppage',()=>{
 const f=fixture();f[5].setPiece=true;
 assert.equal(Rig.getPose(R.create(parsed(f),null,{contactPrecision:true}).sample(500,Rig).players[0]).nativeContactPrecision,undefined);
});
