'use strict';
/* Bake the exact fixed-step WebGL pose into glTF node TRS animation samples.
   World joint transform = GPU skin palette * T(rest joint head).
   Local joint transform = inverse(parent world) * joint world.
   This preserves the renderer's bind pose and avoids double-rotating children. */
const Rig=require('../humanoid-rig.js');
const Scenarios=require('../animation-scenarios.js');
const Renderer=require('../player-renderer.js');
const Assets=require('../assets/player/player-model-data.js');

const CLIPS=Object.freeze([
 {name:'idle',duration:1},
 {name:'walk',duration:2},
 {name:'jog',duration:2},
 {name:'run',duration:2},
 {name:'sprint',duration:2},
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
function bakeClip({name,duration,assets=Assets,parents,fps=30}){
 if(!parents)throw Error('A bone parent table is required');
 if(!Number.isInteger(fps)||fps<1||fps>60||60%fps!==0)throw Error('FPS must divide 60 Hz');
 if(!Number.isFinite(duration)||duration<=0||duration>12||Math.abs(duration*fps-Math.round(duration*fps))>1e-6)throw Error('Duration must align with keyframes');
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
module.exports={bakeClip,framesToLocal,rigidInverse,multiply,translation,quaternion,CLIPS};
