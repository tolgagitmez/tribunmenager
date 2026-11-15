'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Rig=require('../humanoid-rig-procedural.js');
const Scenarios=require('../animation-scenarios.js');
const Renderer=require('../player-renderer-procedural.js');
const Assets=require('../assets/player/procedural-player-model-data.js');

// CPU implementation of the same four-weight skin transform used by WebGL
// (per-index material and vertex positions from the committed GLB source).
const raw=Buffer.from(Assets.lods[0].vertices,'base64');
const v=new Float32Array(raw.buffer,raw.byteOffset,raw.length/4);
const boot={L:[],R:[]};
for(let i=0;i<v.length;i+=20){
 if(Math.round(v[i+16])!==4||v[i+1]>=.03)continue;
 const joints=[v[i+8],v[i+9],v[i+10],v[i+11]];
 if(joints.includes(11))boot.L.push(i);
 if(joints.includes(18))boot.R.push(i);
}
function skinHeight(vertex,palette){
 const x=v[vertex],y=v[vertex+1],z=v[vertex+2];
 let h=0;
 for(let j=0;j<4;j++){
  const weight=v[vertex+12+j];if(weight<=0)continue;
  const base=v[vertex+8+j]*16;
  h+=weight*(palette[base+1]*x+palette[base+5]*y+palette[base+9]*z+palette[base+13]);
 }
 return h;
}
function read(mode,frames=180){
 const s=Scenarios.create(mode==='idle'?'walk':mode);
 const out={L:{contact:0,min:Infinity,maxContact:-Infinity,maxPenetration:0},
   R:{contact:0,min:Infinity,maxContact:-Infinity,maxPenetration:0}};
 for(let tick=0;tick<frames;tick++){
  const t=tick/60,p=s.p;
  if(mode==='idle'){Object.assign(p,{x:0,z:0,face:0,speed:0,action:'idle',actionClock:0});}
  else Scenarios.sample(s,t,Rig);
  const pose=Rig.update(p,1/60),palette=Renderer.palette(p,Assets,pose);
  for(const [side,index] of [['L',0],['R',1]]){
   const min=Math.min(...boot[side].map(j=>skinHeight(j,palette))),stat=out[side];
   assert(Number.isFinite(min));
   stat.min=Math.min(stat.min,min);
   stat.maxPenetration=Math.max(stat.maxPenetration,-min);
   if(pose.legs[index].stance){
    stat.contact++;
    stat.maxContact=Math.max(stat.maxContact,min);
    assert(min>=-.005&&min<=.012,mode+'/'+side+' planted sole must meet pitch: '+min);
   }
  }
 }
 return out;
}
test('deformed 3D outsole—not just ankle IK—reaches the pitch without penetrating during planted frames',()=>{
 assert(boot.L.length>=100&&boot.R.length>=100);
 for(const mode of ['idle','walk','run','sprint','run-shoot','run-pass']){
  const res=read(mode);
  for(const side of ['L','R']){
   assert(res[side].contact>=6,mode+' lacks '+side+' ground-contact frames');
   assert(res[side].maxPenetration<.005,mode+' boot enters turf');
  }
 }
});
