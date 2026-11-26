'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture(kind='sliding-tackle'){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0]};
 const event={timeMs:500,playerId:1,databaseId:1,team:0,foot:0,kind,technique:'none',ball:[.45,.15,.11],impulseVelocity:[5,0,1]};
 const trip={timeMs:500,playerId:2,databaseId:2,team:1,opponentId:1,tripType:3,kind:'tackle-trip',direction:[1,0,0],displacement:0,relativeSpeed:4,balance:.4,possession:false};
 return Array.from({length:17},(_,i)=>{const t=i*100;return {schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===1600,inPlay:true,setPiece:false,score:[0,0],ball:[.45,.15,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,position:[.65,0,0]}],nativeContacts:t===500?[event]:[],nativeDuels:t===500?[trip]:[],nativeFouls:t===500?[{timeMs:500,playerId:1,victimId:2,team:0,tackleType:3}]:[]};});
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
const sample=(kind,t)=>{const r=R.create(parsed(fixture(kind)),null,{tackleMotion:true});let p;for(let ms=0;ms<=t;ms+=10)p=r.sample(ms,Rig).players;return p.map(Rig.getPose);};
test('stage85 separates ball touch, victim reaction and referee event; opt-in unchanged match state',()=>{
 const f=parsed(fixture()),a=R.create(f),b=R.create(f,null,{tackleMotion:true});
 const x=a.sample(500,Rig),y=b.sample(500,Rig);
 assert.equal(x.players[0].nativeContact,undefined);
 assert.equal(y.players[0].nativeContact.tackle.sliding,true);
 assert.equal(y.players[1].nativeContact,null);assert.equal(y.players[1].nativeDuel.fall,true);
 assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
 assert.equal(f[5].nativeFouls[0].victimId,2);
});
test('stage85 sliding pose is lower and recovery decays with fixed bone lengths',()=>{
 const slide=sample('sliding-tackle',500)[0],stand=sample('standing-tackle',500)[0];
 assert.ok(slide.pelvis[1]<stand.pelvis[1]);assert.equal(slide.legs[0].nativeContact,true);
 const victim=sample('sliding-tackle',700)[1],late=sample('sliding-tackle',1250)[1];
 assert.ok(victim.nativeRecovery.drop>late.nativeRecovery.drop);
 for(const pose of [slide,stand,victim,late])for(const l of pose.legs){
  assert.ok(Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
  assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
 }
});
test('stage85 does not invent ball touch from foul or trip; invalid foul rejected',()=>{
 const f=fixture();f[5].nativeContacts=[];
 assert.equal(R.create(parsed(f),null,{tackleMotion:true}).sample(500).players[0].nativeContact,null);
 f[5].nativeFouls[0].timeMs=600;assert.throws(()=>parsed(f));
});
