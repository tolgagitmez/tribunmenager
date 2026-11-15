'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {buildGLB,PARENT}=require('../tools/export-character-glb.cjs');
const {bakeClip,CLIPS,multiply,translation}=require('../tools/character-animation-baker.cjs');
const Assets=require('../assets/player/player-model-data.js');
const Rig=require('../humanoid-rig.js');
const Renderer=require('../player-renderer.js');
const Scenarios=require('../animation-scenarios.js');
function close(a,b,tol=2e-4){assert(Math.abs(a-b)<=tol,'expected '+a+' ~ '+b+' (diff '+(a-b)+')');}
function compose(t,q){
 const [x,y,z,w]=q,xx=x*x,yy=y*y,zz=z*z,xy=x*y,xz=x*z,yz=y*z,wx=w*x,wy=w*y,wz=w*z;
 return Float64Array.from([
  1-2*(yy+zz),2*(xy+wz),2*(xz-wy),0,
  2*(xy-wz),1-2*(xx+zz),2*(yz+wx),0,
  2*(xz+wy),2*(yz-wx),1-2*(xx+yy),0,
  ...t,1
 ]);
}
function framesFromClip(clip,at){
 const index=Object.fromEntries(Assets.bones.map((b,i)=>[b.name,i]));
 const out=[];
 for(let i=0;i<Assets.bones.length;i++){
  const ch=clip.channels[i],local=compose(ch.translation.slice(at*3,at*3+3),ch.rotation.slice(at*4,at*4+4));
  const parent=PARENT[Assets.bones[i].name],pi=parent?index[parent]:-1;
  out[i]=pi>=0?multiply(out[pi],local):local;
 }
 return out;
}
function worldFromRenderer(name,frames,wanted){
 const scenario=Scenarios.create(name==='idle'?'walk':name),out=[];
 for(let tick=0;tick<=frames;tick++){
  const p=scenario.p,t=tick/60;
  if(name==='idle')Object.assign(p,{x:0,z:0,face:0,speed:0,action:'idle',actionClock:0});
  else Scenarios.sample(scenario,t,Rig);
  const pose=Rig.update(p,1/60);
  if(wanted.includes(tick)){
   const palette=Renderer.palette(p,Assets,pose);
   out.push({tick,skin:palette});
  }
 }
 return out;
}
test('soccer GLB includes named clip channels, 19 hierarchical joint tracks and valid timelines',()=>{
 const {json:g}=buildGLB({animations:true,fps:30});
 assert.equal(g.animations.length,CLIPS.length);
 assert.deepEqual(g.animations.map(a=>a.name),CLIPS.map(c=>c.name));
 for(let k=0;k<CLIPS.length;k++){
  const a=g.animations[k],def=CLIPS[k];
  assert.equal(a.channels.length,38);
  assert.equal(a.samplers.length,38);
  assert.equal(a.extras.duration,def.duration);
  assert.equal(a.extras.fps,30);
  const targets=new Set();
  for(let i=0;i<38;i++){
   const ch=a.channels[i],sp=a.samplers[ch.sampler],ac=g.accessors[sp.input],dst=g.accessors[sp.output];
   assert.equal(sp.interpolation,'LINEAR');
   assert.equal(ac.type,'SCALAR');
   assert.equal(ac.count,def.duration*30+1);
   assert.deepEqual(ac.min,[0]);
   assert.deepEqual(ac.max,[def.duration]);
   assert(ch.target.node>=1&&ch.target.node<=19);
   assert(['translation','rotation'].includes(ch.target.path));
   targets.add(ch.target.node+':'+ch.target.path);
   assert.equal(dst.count,ac.count);
   assert.equal(dst.type,ch.target.path==='rotation'?'VEC4':'VEC3');
   assert.equal(dst.componentType,5126);
  }
  assert.equal(targets.size,38);
 }
 const mesh=g.meshes[0].primitives;
 assert(mesh.length>=8);
});
test('all baked quaternions are normalized and sign-continuous',()=>{
 for(const def of CLIPS){
  const clip=bakeClip({...def,parents:PARENT,fps:30});
  assert.equal(clip.times[0],0);
  close(clip.times.at(-1),def.duration,1e-6);
  for(const channel of clip.channels){
   const rot=channel.rotation;
   for(let i=0;i<rot.length;i+=4){
    const q=rot.slice(i,i+4);
    close(Math.hypot(...q),1,2e-5);
    for(const n of q)assert(Number.isFinite(n));
    if(i){const prev=rot.slice(i-4,i);assert(q.reduce((a,b,j)=>a+b*prev[j],0)>=-1e-6,'quaternion discontinuity');}
   }
   for(const v of channel.translation)assert(Number.isFinite(v));
  }
 }
});
test('GLB hierarchy reconstructs the renderer bone palette at contact and moving keyframes',()=>{
 for(const name of ['run','sprint','turn','pass','shoot','run-pass','run-shoot','dive-left','dive-right']){
  const config=CLIPS.find(c=>c.name===name),clip=bakeClip({...config,parents:PARENT,fps:30});
  const ticks=[0,18,Math.min(Math.round((config.contactTime||.8)*60),Math.round(config.duration*60)),Math.round(config.duration*60)]
   .map(v=>v+(v%2)).filter((v,i,a)=>v<=config.duration*60&&a.indexOf(v)===i);
  const ref=worldFromRenderer(name,Math.round(config.duration*60),ticks);
  for(const {tick,skin} of ref){
   const world=framesFromClip(clip,tick/2);
   for(let i=0;i<Assets.bones.length;i++){
    const result=multiply(world[i],Float64Array.from(Assets.bones[i].inverseBind));
    for(let j=0;j<16;j++)close(result[j],skin[i*16+j],3e-4);
   }
  }
 }
});
test('animated GLB is deterministic and rejects invalid sample frequencies',()=>{
 const a=buildGLB({animations:true,lod:2,fps:30,clips:CLIPS.slice(0,3)});
 const b=buildGLB({animations:true,lod:2,fps:30,clips:CLIPS.slice(0,3)});
 assert.equal(Buffer.compare(Buffer.from(a.glb),Buffer.from(b.glb)),0);
 assert.equal(a.stats.clips,3);
 assert.throws(()=>buildGLB({animations:true,fps:29}),/FPS/);
 assert.throws(()=>buildGLB({animations:true,clips:[]}),/clip/i);
});

test('committed animated GLB is byte-for-byte reproducible from the 60 Hz source',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const target=path.resolve(__dirname,'../assets/player/tribun-base-footballer-animated.glb');
 const binary=fs.readFileSync(target);
 const baked=Buffer.from(buildGLB({lod:0,animations:true,fps:30}).glb);
 const mismatch=Array.from(binary).findIndex((byte,i)=>byte!==baked[i]);
 assert.equal(Buffer.compare(binary,baked),0,'committed GLB mismatch: stored='+binary.length+' generated='+baked.length+' firstDifference='+mismatch+' storedByte='+binary[mismatch]+' generatedByte='+baked[mismatch]);
 assert(binary.byteLength>500000);
});
