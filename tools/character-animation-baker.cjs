'use strict';
/* Bake the exact fixed-step WebGL pose into glTF node TRS animation samples.
   World joint transform = GPU skin palette * T(rest joint head).
   Local joint transform = inverse(parent world) * joint world.
   This preserves the renderer's bind pose and avoids double-rotating children. */
const Rig=require('../humanoid-rig.js');
const Scenarios=require('../animation-scenarios.js');
const Renderer=require('../player-renderer-procedural.js');
const Assets=require('../assets/player/procedural-player-model-data.js');

const CLIPS=Object.freeze([
 {name:'idle',duration:1},
 {name:'walk',duration:2},
 {name:'jog',duration:2},
 {name:'run',duration:2},
 {name:'sprint',duration:2},
 // Independent in-place cycles, cut after warm-up and closed at the seam.
 {name:'walk-loop',duration:2.2333333333333334,loop:true},
 {name:'run-loop',duration:1.4333333333333333,loop:true},
 {name:'sprint-loop',duration:1.5666666666666667,loop:true},
 {name:'turn',duration:4.5},
 {name:'pass',duration:1.3,contactTime:.31},
 {name:'shoot',duration:1.3,contactTime:.38},
 {name:'run-pass',duration:2.4,contactTime:1.06},
 {name:'run-shoot',duration:2.4,contactTime:1.13},
 {name:'dive-left',duration:1.3,contactTime:.34},
 {name:'dive-right',duration:1.3,contactTime:.34}
]);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function multiply(a,b){
 const out=new Float64Array(16);
 for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];
 return out;
}
function rigidInverse(m){
 const out=new Float64Array(16);
 for(let r=0;r<3;r++)for(let c=0;c<3;c++)out[c*4+r]=m[r*4+c];
 out[15]=1;
 for(let r=0;r<3;r++)out[12+r]=-(out[r]*m[12]+out[r+4]*m[13]+out[r+8]*m[14]);
 return out;
}
function translation(x,y,z){
 return new Float64Array([1,0,0,0,0,1,0,0,0,0,1,0,x,y,z,1]);
}
function quaternion(matrix){
 const m=matrix;
 const m00=m[0],m11=m[5],m22=m[10];
 const trace=m00+m11+m22;
 let x,y,z,w,s;
 if(trace>0){
  s=2*Math.sqrt(Math.max(0,trace+1));w=.25*s;
  x=(m[6]-m[9])/s;y=(m[8]-m[2])/s;z=(m[1]-m[4])/s;
 }else if(m00>m11&&m00>m22){
  s=2*Math.sqrt(Math.max(0,1+m00-m11-m22));w=(m[6]-m[9])/s;x=.25*s;y=(m[4]+m[1])/s;z=(m[8]+m[2])/s;
 }else if(m11>m22){
  s=2*Math.sqrt(Math.max(0,1+m11-m00-m22));w=(m[8]-m[2])/s;x=(m[4]+m[1])/s;y=.25*s;z=(m[9]+m[6])/s;
 }else{
  s=2*Math.sqrt(Math.max(0,1+m22-m00-m11));w=(m[1]-m[4])/s;x=(m[8]+m[2])/s;y=(m[9]+m[6])/s;z=.25*s;
 }
 const norm=Math.hypot(x,y,z,w);
 if(!(norm>1e-8))throw Error('Cannot decompose bone rotation');
 return [x/norm,y/norm,z/norm,w/norm];
}
function framesToLocal(palette,assets,parents){
 const index=Object.fromEntries(assets.bones.map((b,i)=>[b.name,i]));
 const world=assets.bones.map((bone,i)=>{
  const skin=Float64Array.from(palette.slice(i*16,(i+1)*16));
  return multiply(skin,translation(...bone.head));
 });
 return assets.bones.map((bone,i)=>{
  const parent=parents[bone.name],matrix=parent?multiply(rigidInverse(world[index[parent]]),world[i]):world[i];
  const t=[matrix[12],matrix[13],matrix[14]],q=quaternion(matrix);
  if(![...t,...q].every(Number.isFinite))throw Error('Non-finite animation transform for '+bone.name);
  return {translation:t,rotation:q};
 });
}
function qNormalize(v){const m=Math.hypot(...v)||1;return v.map(n=>n/m);}
function qMul(a,b){
 const [x,y,z,w]=a,[X,Y,Z,W]=b;
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z];
}
function qSlerp(a,b,t){
 let q=b.slice(),dot=a.reduce((s,x,i)=>s+x*b[i],0);
 if(dot<0){q=q.map(x=>-x);dot=-dot;}
 if(dot>.9995)return qNormalize(a.map((v,i)=>v+(q[i]-v)*t));
 const a0=Math.acos(clamp(dot,-1,1)),sin=Math.sin(a0);
 return a.map((v,i)=>(v*Math.sin((1-t)*a0)+q[i]*Math.sin(t*a0))/sin);
}
function alignedPalette(palette,p){
 // Undo circular inspection trajectory while leaving the body's local gait.
 const c=Math.cos(p.face||0),s=Math.sin(p.face||0);
 const rotation=new Float64Array([c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1]);
 const align=multiply(rotation,translation(-(p.x||0),0,-(p.z||0)));
 const out=new Float32Array(palette.length);
 for(let i=0;i<palette.length;i+=16){
  out.set(multiply(align,Float64Array.from(palette.subarray(i,i+16))),i);
 }
 return out;
}
function bakeGaitLoop({name,duration,assets,parents,fps}){
 const mode=name.slice(0,-5);
 if(!['walk','run','sprint'].includes(mode))throw Error('Unsupported gait loop '+name);
 const warmup=180,sampleStride=60/fps,steps=Math.round(duration*60),keys=steps/sampleStride+1;
 const sc=Scenarios.create(mode),channels=assets.bones.map(()=>({
  translation:new Float32Array(keys*3),rotation:new Float32Array(keys*4)
 })),times=new Float32Array(keys);
 let frame=0;
 for(let tick=0;tick<=warmup+steps;tick++){
  const t=tick/60,p=sc.p;Scenarios.sample(sc,t,Rig);
  const pose=Rig.update(p,1/60);
  if(tick<warmup||(tick-warmup)%sampleStride)continue;
  const local=framesToLocal(alignedPalette(Renderer.palette(p,assets,pose),p),assets,parents);
  const relativeTick=tick-warmup;
  times[frame]=relativeTick/60;
  for(let i=0;i<local.length;i++){
   channels[i].translation.set(local[i].translation,frame*3);
   let q=local[i].rotation;
   if(frame){
    const prev=channels[i].rotation.slice((frame-1)*4,frame*4);
    if(q.reduce((sum,x,j)=>sum+x*prev[j],0)<0)q=q.map(x=>-x);
   }
   channels[i].rotation.set(q,frame*4);
  }
  frame++;
 }
 if(frame!==keys)throw Error('Unexpected gait key count: '+name);
 // Correct the small drift left by rounding the exact step period to 30 Hz.
 // A smooth correction over the last 25% makes every joint seam periodic.
 const begin=Math.max(1,keys-1-Math.ceil((keys-1)*.25));
 for(const channel of channels){
  const startT=Array.from(channel.translation.slice(0,3)),
        endT=Array.from(channel.translation.slice((keys-1)*3,keys*3)),
        startQ=Array.from(channel.rotation.slice(0,4)),
        endQ=Array.from(channel.rotation.slice((keys-1)*4,keys*4)),
        deltaT=endT.map((v,i)=>v-startT[i]),
        qInv=[-endQ[0],-endQ[1],-endQ[2],endQ[3]],
        deltaQ=qNormalize(qMul(qInv,startQ));
  for(let j=begin;j<keys;j++){
   const u=(j-begin)/(keys-1-begin),w=u*u*(3-2*u);
   for(let k=0;k<3;k++)channel.translation[j*3+k]-=deltaT[k]*w;
   const q=Array.from(channel.rotation.slice(j*4,j*4+4));
   channel.rotation.set(qNormalize(qMul(q,qSlerp([0,0,0,1],deltaQ,w))),j*4);
  }
  // Hermite-like seam velocity correction in the last few keys. The
  // penultimate key is exactly one negative first-frame delta before start,
  // so both position AND the first derivative agree at the wrap.
  const last=keys-1,tailStart=Math.max(1,last-8);
  const firstDelta=Array.from(channel.translation.slice(3,6)).map((v,i)=>v-startT[i]);
  const firstNextQ=Array.from(channel.rotation.slice(4,8));
  const step=qNormalize(qMul([-startQ[0],-startQ[1],-startQ[2],startQ[3]],firstNextQ));
  const backward=[-step[0],-step[1],-step[2],step[3]];
  for(let j=tailStart;j<=last;j++){
   const remaining=last-j;
   const u=(j-tailStart)/Math.max(1,last-1-tailStart);
   const w=j>=last-1?1:u*u*(3-2*u);
   for(let i=0;i<3;i++){
    const at=j*3+i,target=startT[i]-remaining*firstDelta[i];
    channel.translation[at]=channel.translation[at]*(1-w)+target*w;
   }
   const q=Array.from(channel.rotation.slice(j*4,j*4+4));
   const backwardRotation=qNormalize(qMul(startQ,qSlerp([0,0,0,1],backward,remaining)));
   channel.rotation.set(qSlerp(q,backwardRotation,w),j*4);
  }
  channel.translation.set(startT,(keys-1)*3);
  channel.rotation.set(startQ,(keys-1)*4);
 }
 return {name,duration,fps,times,channels,contactTime:null,loopReady:true};
}
function bakeClip({name,duration,assets=Assets,parents,fps=30}){
 if(!parents)throw Error('A bone parent table is required');
 if(!Number.isInteger(fps)||fps<1||fps>60||60%fps!==0)throw Error('FPS must divide 60 Hz');
 if(!Number.isFinite(duration)||duration<=0||duration>12||Math.abs(duration*fps-Math.round(duration*fps))>1e-6)throw Error('Duration must align with keyframes');
 if(name.endsWith('-loop'))return bakeGaitLoop({name,duration,assets,parents,fps});
 const scenario=Scenarios.create(name==='idle'?'walk':name);
 const steps=Math.round(duration*60),stride=60/fps,numKeys=steps/stride+1;
 const channels=assets.bones.map(()=>({translation:new Float32Array(numKeys*3),rotation:new Float32Array(numKeys*4)}));
 const times=new Float32Array(numKeys),worldMatrices=[];
 let frame=0;
 for(let tick=0;tick<=steps;tick++){
  const t=tick/60,p=scenario.p;
  if(name==='idle')Object.assign(p,{x:0,z:0,face:0,speed:0,action:'idle',actionClock:0});
  else Scenarios.sample(scenario,t,Rig);
  const pose=Rig.update(p,1/60);
  if(tick%stride!==0)continue;
  const palette=Renderer.palette(p,assets,pose),local=framesToLocal(palette,assets,parents);
  times[frame]=t;
  for(let i=0;i<local.length;i++){
   const c=channels[i],joint=local[i],last=frame?Array.from(c.rotation.slice((frame-1)*4,frame*4)):null;
   let q=joint.rotation;
   if(last&&q.reduce((sum,x,k)=>sum+x*last[k],0)<0)q=q.map(x=>-x);
   c.translation.set(joint.translation,frame*3);
   c.rotation.set(q,frame*4);
  }
  frame++;
 }
 if(frame!==numKeys)throw Error('Unexpected frame count for '+name);
 return {name,duration,fps,times,channels,contactTime:CLIPS.find(c=>c.name===name)?.contactTime??null};
}
module.exports={bakeClip,framesToLocal,rigidInverse,multiply,translation,quaternion,CLIPS,alignedPalette,bakeGaitLoop};
