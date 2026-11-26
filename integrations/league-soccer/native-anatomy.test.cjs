'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js'),Renderer=require('../../player-renderer.js');
function fixture(){
 const p={id:1,team:0,databaseId:1,position:[2,0,0],velocity:[0,0,0],direction:[1,0,0],heightMetres:1.65};
 return Array.from({length:11},(_,i)=>({schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:i*100,done:i===10,inPlay:true,setPiece:false,score:[0,0],ball:[2.4,0,.11],ballVelocity:[0,0,0],players:[p,{...p,id:2,team:1,databaseId:2,position:[2,2,0],heightMetres:2.02}]}));
}
const parsed=f=>R.parse(f.map(x=>JSON.stringify(x)).join('\n'));
test('stage91 engine height scales each skeleton before IK; physical match unchanged',()=>{
 const f=parsed(fixture()),a=R.create(f,null,{playerMotionIdentity:true}),b=R.create(f,null,{playerAnatomy:true});
 for(let t=0;t<900;t+=20){
  const x=a.sample(t,Rig),y=b.sample(t,Rig);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  for(let i=0;i<2;i++){
   const p=y.players[i],pose=Rig.getPose(p),m=Rig.anatomyFor(p);
   assert.equal(x.players[i].nativeAnatomy,undefined);
   for(const k of ['x','z','vx','vz','face','speed'])assert.equal(x.players[i][k],p[k]);
   assert.equal(p.nativeAnatomy.preferredFoot,'unknown');
   for(const l of pose.legs){
    assert.ok(Math.abs(Math.hypot(...l.knee.map((v,j)=>v-l.hip[j]))-m.thigh)<1e-5);
    assert.ok(Math.abs(Math.hypot(...l.ankle.map((v,j)=>v-l.knee[j]))-m.shin)<1e-5);
   }
   for(const a of pose.arms)assert.ok(Math.abs(Math.hypot(...a.wrist.map((v,j)=>v-a.elbow[j]))-m.forearm)<1e-5);
  }
  assert.ok(Rig.getPose(y.players[1]).headTop[1]>Rig.getPose(y.players[0]).headTop[1]);
 }
});
test('stage91 rigid palette normalization and mesh scale share actor origin',()=>{
 const p={x:3,z:-4,nativeAnatomy:{scale:1.1}},point=[3.8,1.7,-3.2],s=Renderer.renderBodyScale(p);
 const q=Renderer.normalizedBoneOrigin(p,point,s);
 const restored=[p.x+(q[0]-p.x)*s,q[1]*s,p.z+(q[2]-p.z)*s];
 for(let i=0;i<3;i++)assert.ok(Math.abs(restored[i]-point[i])<1e-9);
 const data=new Float32Array(45*4);
 Renderer.packInstance(data,0,{real:new Float32Array(76),dual:new Float32Array(76)},p);
 assert.equal(data[38*4+3],3);assert.equal(data[39*4+3],-4);assert.ok(Math.abs(data[40*4+3]-s)<1e-6);
});
test('stage91 unknown or implausible height preserves canonical anatomy and no foot inference',()=>{
 const f=fixture();for(const frame of f){delete frame.players[0].heightMetres;frame.players[1].heightMetres=9;}
 const r=R.create(parsed(f),null,{playerAnatomy:true});
 for(const p of r.sample(0,Rig).players){assert.equal(p.nativeAnatomy.height,null);assert.equal(p.nativeAnatomy.scale,1);assert.equal(Rig.anatomyFor(p),Rig.ANATOMY);}
 const invalid=fixture();invalid[0].players[0].heightMetres='1.8';assert.throws(()=>parsed(invalid));
});
