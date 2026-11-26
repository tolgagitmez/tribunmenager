'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
function fixture({kind='bump',balance=.5,direction=[0,-1,0],displacement=.06,tripType=0}={}){
 const p={id:1,databaseId:1,team:0,position:[0,0,0],velocity:[0,0,0],direction:[1,0,0]};
 const d={timeMs:500,playerId:1,databaseId:1,team:0,opponentId:2,tripType,kind,direction,displacement,relativeSpeed:4,balance,possession:true};
 return Array.from({length:11},(_,i)=>{const t=i*100;return {schema:1,engine:'league-soccer',elapsedMs:t,matchMs:t,done:t===1000,inPlay:true,setPiece:false,score:[0,0],ball:[.49,.15,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,databaseId:2,team:1,position:[0,.6,0]}],nativeDuels:t===500?[d]:[]};});
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
const sample=(opts,t=500)=>{const r=R.create(parsed(fixture(opts)),null,{duelMotion:true});let p;for(let ms=0;ms<=t;ms+=10)p=r.sample(ms,Rig).players[0];return Rig.getPose(p);};
test('stage84 only reacts after recorded collision, does not alter simulation',()=>{
 const f=parsed(fixture()),a=R.create(f),b=R.create(f,null,{duelMotion:true});
 for(const t of [400,500,550,700]){
  const x=a.sample(t,Rig),y=b.sample(t,Rig);
  assert.equal(x.players[0].nativeDuel,undefined);assert.equal(y.players[1].nativeDuel,null);
  if(t===500)assert.equal(y.players[0].nativeDuel.kind,'bump');
  if(t===400||t===700)assert.equal(y.players[0].nativeDuel,null);
  for(const k of ['x','z','vx','vz','face','speed'])assert.equal(x.players[0][k],y.players[0][k]);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
 }
});
test('stage84 direction, balance and recovery change the pose without scaling bones',()=>{
 const left=sample({direction:[0,1,0]}),right=sample({direction:[0,-1,0]});
 assert.ok(left.nativeDuel.lateral<0&&right.nativeDuel.lateral>0);
 assert.notDeepEqual(left.torsoUpper,right.torsoUpper);
 assert.ok(sample({balance:.1}).nativeDuel.weight>sample({balance:.9}).nativeDuel.weight);
 const trip=sample({kind:'trip',tripType:2}),later=sample({kind:'trip',tripType:2},750);
 assert.ok(trip.nativeDuel.drop>later.nativeDuel.drop);
 for(const pose of [left,right,trip,later])for(const l of pose.legs){
  assert.ok(Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-Rig.ANATOMY.thigh)<1e-5);
  assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-Rig.ANATOMY.shin)<1e-5);
 }
});
test('stage84 ignores legacy records, wrong identity and stopped play',()=>{
 for(const mutate of [f=>f.forEach(x=>delete x.nativeDuels),f=>f[5].nativeDuels[0].databaseId=99,f=>f[5].setPiece=true]){
  const f=fixture();mutate(f);assert.equal(R.create(parsed(f),null,{duelMotion:true}).sample(500).players[0].nativeDuel,null);
 }
 const f=fixture();f[5].nativeDuels[0].relativeSpeed=-1;assert.throws(()=>parsed(f));
});
