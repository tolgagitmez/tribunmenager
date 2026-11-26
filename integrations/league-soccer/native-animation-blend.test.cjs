'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture(){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0]};
 const d={timeMs:500,playerId:1,databaseId:1,team:0,opponentId:2,kind:'trip',tripType:2,direction:[0,-1,0],displacement:0,relativeSpeed:4,balance:.4,possession:false};
 const e={timeMs:1000,playerId:1,databaseId:1,team:0,kind:'shot',technique:'shot',foot:0,ball:[.5,.15,.11],impulseVelocity:[20,0,0]};
 const h={...e,timeMs:1100,foot:-1,headContact:true,ball:[.2,0,2.1]};
 return Array.from({length:21},(_,i)=>{const t=i*100;return {schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===2000,inPlay:true,setPiece:false,score:[0,0],ball:[.5,.15,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,position:[0,.6,0]}],nativeDuels:t===500?[d]:[],nativeContacts:t===1000?[e]:t===1100?[h]:[]};});
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
const all={bodyBalance:true,footPlant:true,contactSync:true,strikeMotion:true,controlMotion:true,duelMotion:true,tackleMotion:true,keeperMotion:true,aerialMotion:true};
test('stage88 combined profile keeps match and contacting foot authoritative',()=>{
 const f=parsed(fixture()),a=R.create(f,null,all),b=R.create(f,null,{animationBlend:true});
 for(let t=0;t<=1600;t+=10){
  const x=a.sample(t,Rig),y=b.sample(t,Rig),p=y.players[0],pose=Rig.getPose(p);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  for(const k of ['x','z','vx','vz','speed','face'])assert.equal(x.players[0][k],p[k]);
  for(const l of pose.legs){
   assert.ok(Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
   assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
  }
  if(t===1000){assert.equal(p.nativeContact.deltaMs,0);assert.equal(p.nativeAerial,null);assert.equal(pose.legs[0].nativeContact,true);assert.equal(pose.nativeBlend.contactProtection,1);}
  if(t===1100){assert.equal(p.nativeContact,null);assert.equal(p.nativeAerial.deltaMs,0);assert.ok(pose.nativeAerial);}
 }
});
test('stage88 filters abrupt collision torso target while preserving contact priority',()=>{
 const f=parsed(fixture()),a=R.create(f,null,all),b=R.create(f,null,{animationBlend:true});
 let prevA,prevB,da=0,db=0;
 for(let t=0;t<=550;t+=10){
  const pa=Rig.getPose(a.sample(t,Rig).players[0]),pb=Rig.getPose(b.sample(t,Rig).players[0]);
  if(t===500){da=Math.abs(pa.pelvis[1]-prevA.pelvis[1]);db=Math.abs(pb.pelvis[1]-prevB.pelvis[1]);}
  prevA=pa;prevB=pb;
 }
 assert.ok(da>0);assert.ok(db<da);
});
test('stage88 invalid interval clears layers; backward seek resets filters',()=>{
 const f=fixture();f[6].setPiece=true;
 const r=R.create(parsed(f),null,{animationBlend:true});
 assert.equal(r.sample(550,Rig).players[0].nativeBlend,false);
 assert.equal(r.sample(550,Rig).players[0].nativeDuel,null);
 r.sample(1000,Rig);
 const p=r.sample(100,Rig).players[0],fresh=R.create(parsed(f),null,{animationBlend:true}).sample(100,Rig).players[0];
 assert.deepEqual(Rig.getPose(p).pelvis,Rig.getPose(fresh).pelvis);
});
