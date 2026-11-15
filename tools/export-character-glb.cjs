'use strict';
/* Self-contained glTF 2.0 binary exporter for Tribun Manager's procedural
   humanoid. Zero npm dependencies, no third-party mesh or animation assets. */
const fs = require('node:fs');
const path = require('node:path');
const Assets = require('../assets/player/procedural-player-model-data.js');
const {bakeClip,CLIPS}=require('./character-animation-baker.cjs');

const PARENT = Object.freeze({
 pelvis:null, spine:'pelvis',chest:'spine',neck:'chest',head:'neck',
 'clavicle.L':'chest','upper_arm.L':'clavicle.L','forearm.L':'upper_arm.L','hand.L':'forearm.L',
 'thigh.L':'pelvis','shin.L':'thigh.L','foot.L':'shin.L',
 'clavicle.R':'chest','upper_arm.R':'clavicle.R','forearm.R':'upper_arm.R','hand.R':'forearm.R',
 'thigh.R':'pelvis','shin.R':'thigh.R','foot.R':'shin.R'
});
const MAT = [
 ['Skin',[.72,.49,.35,1],.9],['Jersey',[.075,.29,.68,1],.86],
 ['Shorts',[.86,.87,.9,1],.88],['Socks',[.68,.72,.76,1],.9],
 ['Boots',[.045,.06,.085,1],.45],['Hair',[.11,.07,.05,1],.9],
 ['EyeWhite',[.86,.87,.83,1],.28],['Iris',[.19,.30,.21,1],.25],
 ['Pupil',[.008,.009,.012,1],.17],['Brow',[.075,.06,.05,1],.9]
];
const align4 = n => (n+3)&~3;
function utf8(text){
 const bytes=[];
 for(const ch of text){
  const x=ch.codePointAt(0);
  if(x<128)bytes.push(x);
  else if(x<2048)bytes.push(192|(x>>6),128|(x&63));
  else if(x<65536)bytes.push(224|(x>>12),128|((x>>6)&63),128|(x&63));
  else bytes.push(240|(x>>18),128|((x>>12)&63),128|((x>>6)&63),128|(x&63));
 }
 return new Uint8Array(bytes);
}
function bytesOf(typed){return new Uint8Array(typed.buffer,typed.byteOffset,typed.byteLength);}
function buildGLB({lod=0,assets=Assets,animations=false,fps=30,clips=CLIPS}={}){
 if(!Number.isInteger(lod)||lod<0||lod>=assets.lods.length)throw Error('LOD 0, 1 or 2 required');
 if(assets.bones.length!==19)throw Error('Expected nineteen mapped bones');
 const raw=assets.lods[lod],vbytes=Buffer.from(raw.vertices,'base64'),ibytes=Buffer.from(raw.indices,'base64');
 if(vbytes.length!==raw.vertexCount*80||ibytes.length!==raw.indexCount*2)throw Error('Corrupt source mesh stride');
 const vertices=new Float32Array(vbytes.buffer,vbytes.byteOffset,raw.vertexCount*20);
 const indices=new Uint16Array(ibytes.buffer,ibytes.byteOffset,raw.indexCount);
 const gltf={
  asset:{version:'2.0',generator:'Tribun Manager procedural skinned model exporter',copyright:'Original procedural model generated for Tribun Manager'},
  scene:0,scenes:[{name:'Base footballer',nodes:[0,1]}],
  nodes:[{name:'Footballer mesh',mesh:0,skin:0}],
  meshes:[{name:'Tribun Base Footballer LOD'+lod,primitives:[]}],
  skins:[],materials:MAT.map(([name,color,roughness])=>({
   name,pbrMetallicRoughness:{baseColorFactor:color,metallicFactor:0,roughnessFactor:roughness},
   doubleSided:false
  })),
  buffers:[{byteLength:0}],bufferViews:[],accessors:[]
 };
 const blobs=[];let binaryLength=0;
 function bufferView(data,target){
  const bytes=bytesOf(data),aligned=align4(binaryLength);
  if(aligned>binaryLength)blobs.push({offset:binaryLength,bytes:new Uint8Array(aligned-binaryLength)});
  const id=gltf.bufferViews.length,view={buffer:0,byteOffset:aligned,byteLength:bytes.byteLength};
  if(target)view.target=target;
  gltf.bufferViews.push(view);blobs.push({offset:aligned,bytes});
  binaryLength=aligned+bytes.length;return id;
 }
 function accessor(data,type,componentType,target,metadata={}){
  const view=bufferView(data,target),count=data.length/({SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16}[type]);
  if(!Number.isInteger(count))throw Error('Accessor count must be integer');
  const id=gltf.accessors.length;
  gltf.accessors.push({bufferView:view,byteOffset:0,componentType,count,type,...metadata});
  return id;
 }
 const pos=new Float32Array(raw.vertexCount*3),normals=new Float32Array(raw.vertexCount*3);
 const uv=new Float32Array(raw.vertexCount*2),joints=new Uint8Array(raw.vertexCount*4),weights=new Float32Array(raw.vertexCount*4);
 const limits={min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]};
 for(let i=0;i<raw.vertexCount;i++){
  const p=i*20;
  for(let c=0;c<3;c++){
   const n=vertices[p+c];if(!Number.isFinite(n))throw Error('Non-finite model coordinate');
   pos[3*i+c]=n;normals[3*i+c]=vertices[p+3+c];
   limits.min[c]=Math.min(limits.min[c],n);limits.max[c]=Math.max(limits.max[c],n);
  }
  for(let c=0;c<2;c++)uv[2*i+c]=vertices[p+6+c];
  let total=0;
  for(let c=0;c<4;c++){
   const j=vertices[p+8+c],w=vertices[p+12+c];
   if(!Number.isInteger(j)||j<0||j>=19||!Number.isFinite(w)||w<0)throw Error('Invalid skin weight');
   joints[4*i+c]=j;weights[4*i+c]=w;total+=w;
  }
  if(Math.abs(total-1)>1e-5)throw Error('Skin weights not normalized');
 }
 const attrs={
  POSITION:accessor(pos,'VEC3',5126,34962,limits),
  NORMAL:accessor(normals,'VEC3',5126,34962),
  TEXCOORD_0:accessor(uv,'VEC2',5126,34962),
  JOINTS_0:accessor(joints,'VEC4',5121,34962),
  WEIGHTS_0:accessor(weights,'VEC4',5126,34962)
 };
 const partition=MAT.map(()=>[]);
 for(let i=0;i<indices.length;i+=3){
  const a=indices[i],b=indices[i+1],c=indices[i+2];
  if(a>=raw.vertexCount||b>=raw.vertexCount||c>=raw.vertexCount)throw Error('Invalid index');
  const m=[a,b,c].map(i=>Math.round(vertices[i*20+16]));
  const material=m[0]===m[1]||m[0]===m[2]?m[0]:m[1]===m[2]?m[1]:m[0];
  if(material<0||material>=MAT.length)throw Error('Unknown material '+material);
  partition[material].push(a,b,c);
 }
 for(let m=0;m<partition.length;m++)if(partition[m].length){
  const id=accessor(new Uint16Array(partition[m]),'SCALAR',5123,34963);
  gltf.meshes[0].primitives.push({attributes:attrs,indices:id,material:m,mode:4});
 }
 const index=Object.fromEntries(assets.bones.map((b,i)=>[b.name,i]));
 for(const bone of assets.bones){
  if(!(bone.name in PARENT))throw Error('Unmapped bone '+bone.name);
  if(!bone.head.every(Number.isFinite))throw Error('Invalid bone head');
  const parent=PARENT[bone.name];
  const base=parent?assets.bones[index[parent]].head:[0,0,0];
  gltf.nodes.push({
   name:bone.name,
   translation:bone.head.map((n,i)=>n-base[i])
  });
 }
 for(const [i,b] of assets.bones.entries()){
  const parent=PARENT[b.name];
  if(parent)gltf.nodes[index[parent]+1].children=(gltf.nodes[index[parent]+1].children||[]).concat(i+1);
 }
 const ibm=new Float32Array(assets.bones.length*16);
 for(let i=0;i<assets.bones.length;i++){
  const m=assets.bones[i].inverseBind;
  if(m.length!==16||!m.every(Number.isFinite))throw Error('Invalid inverse bind matrix');
  ibm.set(m,i*16);
 }
 const ibmAccessor=accessor(ibm,'MAT4',5126,null);
 gltf.skins.push({name:'Tribun Humanoid 19',joints:assets.bones.map((_,i)=>i+1),skeleton:1,inverseBindMatrices:ibmAccessor});
 if(animations){
  if(!Array.isArray(clips)||clips.length===0)throw Error('Animation clip list cannot be empty');
  gltf.animations=[];
  for(const clip of clips){
   const baked=bakeClip({...clip,assets,parents:PARENT,fps});
   const timeline=accessor(baked.times,'SCALAR',5126,null,{min:[0],max:[baked.duration]});
   const animation={name:baked.name,samplers:[],channels:[],extras:{fps:baked.fps,duration:baked.duration}};
   if(baked.contactTime!==null)animation.extras.contactTime=baked.contactTime;
   if(baked.loopReady)animation.extras.loopReady=true;
   for(let i=0;i<assets.bones.length;i++){
    for(const path of ['translation','rotation']){
     const output=accessor(baked.channels[i][path],path==='translation'?'VEC3':'VEC4',5126,null);
     animation.samplers.push({input:timeline,output,interpolation:'LINEAR'});
     animation.channels.push({sampler:animation.samplers.length-1,target:{node:i+1,path}});
    }
   }
   gltf.animations.push(animation);
  }
 }
 const bin=new Uint8Array(align4(binaryLength));
 for(const {offset,bytes} of blobs)bin.set(bytes,offset);
 gltf.buffers[0].byteLength=bin.length;
 const jsonBytes=utf8(JSON.stringify(gltf)),jsonPadded=align4(jsonBytes.length),binPadded=align4(bin.length);
 const size=12+8+jsonPadded+8+binPadded;
 const glb=new Uint8Array(size),dv=new DataView(glb.buffer);
 dv.setUint32(0,0x46546c67,true);dv.setUint32(4,2,true);dv.setUint32(8,size,true);
 dv.setUint32(12,jsonPadded,true);dv.setUint32(16,0x4e4f534a,true);
 glb.set(jsonBytes,20);glb.fill(32,20+jsonBytes.length,20+jsonPadded);
 const second=20+jsonPadded;dv.setUint32(second,binPadded,true);dv.setUint32(second+4,0x004e4942,true);
 glb.set(bin,second+8);
 return {glb,json:gltf,stats:{lod,vertices:raw.vertexCount,triangles:raw.indexCount/3,primitives:gltf.meshes[0].primitives.length,bytes:glb.length,bones:19,clips:gltf.animations?.length||0}};
}
if(require.main===module){
 const args=process.argv.slice(2),get=(key,fallback)=>{const p=args.indexOf(key);return p<0?fallback:args[p+1];};
 const animations=args.includes('--animations'),fps=Number(get('--fps','30'));
 const lod=Number(get('--lod','0')),output=path.resolve(get('--output',animations?'dist/tribun-base-footballer-animated.glb':'assets/player/tribun-base-footballer.glb'));
 const result=buildGLB({lod,animations,fps});fs.mkdirSync(path.dirname(output),{recursive:true});
 fs.writeFileSync(output,Buffer.from(result.glb));
 console.log(JSON.stringify({output,...result.stats},null,2));
}
module.exports={buildGLB,PARENT,MAT};
