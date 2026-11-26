'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const traits=(value=.5,fatigueFactor=1)=>({agility:value,velocity:value,acceleration:value,balance:value,dribble:value,control:value,fatigueFactor});
function fixture(){
 return Array.from({length:41},(_,i)=>{
  const p={id:1,team:0,databaseId:1,position:[i*.6,0,0],velocity:[6,0,0],direction:[1,0,0],motionIdentity:traits(.9,1-i*.01)};
  return {schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===40,inPlay:true,setPiece:false,score:[0,0],ball:[i*.6+.5,0,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,team:1,databaseId:2,position:[i*.6,2,0],motionIdentity:traits(.2,.7)}]};
 });
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
test('stage90 raw traits and fatigue tune bounded profiles independently',()=>{
 const high={agility:.9,velocity:.9,acceleration:.9,balance:.9,freshness:1},low={agility:.2,velocity:.2,acceleration:.2,balance:.2,freshness:1};
 assert.ok(Rig.motionIdentityFactors(high,'sprint').stride>Rig.motionIdentityFactors(low,'sprint').stride);
 assert.ok(Rig.motionIdentityFactors(high,'pivot').duration<Rig.motionIdentityFactors(low,'pivot').duration);
 const tired=Rig.motionIdentityFactors({...high,freshness:.3},'run'),fresh=Rig.motionIdentityFactors(high,'run');
 assert.ok(tired.stride<fresh.stride&&tired.duration>fresh.duration&&tired.lift<fresh.lift&&tired.duty>fresh.duty);
 assert.equal(Rig.motionIdentityFactors(null,'walk'),null);
});
test('stage90 different identities with identical physical speed preserve match and bones',()=>{
 const f=parsed(fixture()),a=R.create(f,null,{motionMatching:true}),b=R.create(f,null,{playerMotionIdentity:true});let distinct=0;
 for(let t=0;t<3900;t+=20){
  const x=a.sample(t,Rig),y=b.sample(t,Rig);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  for(let i=0;i<2;i++){
   const p=y.players[i],pose=Rig.getPose(p);
   assert.equal(x.players[i].nativeMotionIdentity,undefined);
   for(const k of ['x','z','vx','vz','face','speed'])assert.equal(p[k],x.players[i][k]);
   for(const l of pose.legs){
    assert.ok(Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-Rig.ANATOMY.thigh)<1e-5);
    assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-Rig.ANATOMY.shin)<1e-5);
   }
  }
  const [l,r]=y.players.map(p=>Rig.getPose(p).nativeMotionIdentity);
  if(l&&r&&l.strideMetres!==r.strideMetres)distinct++;
 }
 assert.ok(distinct>100);
});
test('stage90 old records, stoppages and invalid traits are handled without inventing identity',()=>{
 const f=fixture();for(const frame of f)for(const p of frame.players)delete p.motionIdentity;
 const frames=parsed(f),a=R.create(frames,null,{motionMatching:true}),b=R.create(frames,null,{playerMotionIdentity:true});
 for(let t=0;t<500;t+=20){
  const x=a.sample(t,Rig).players[0],y=b.sample(t,Rig).players[0];
  assert.equal(y.nativeMotionIdentity,null);assert.deepEqual(Rig.getPose(x),Rig.getPose(y));
 }
 const bad=fixture();bad[0].players[0].motionIdentity.agility='fast';assert.throws(()=>parsed(bad));
 const stop=fixture();stop[5].setPiece=true;
 assert.equal(R.create(parsed(stop),null,{playerMotionIdentity:true}).sample(450,Rig).players[0].nativeMotionIdentity,null);
});
