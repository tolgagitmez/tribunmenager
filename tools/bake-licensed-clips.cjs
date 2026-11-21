'use strict';
/* Standard glTF animation for the licensed footballer. A joint's bind frame
   contains orientation as well as its head: G_i(t) = S_i(t) * B_i.
   Parent-relative TRS is derived from those full world frames. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const Rig=require('../humanoid-rig'),Renderer=require('../player-renderer');
const Scenarios=require('../animation-scenarios');
const Assets=require('../assets/player/player-model-data');
const CLIPS=Object.freeze([
 Object.freeze({name:'idle',duration:1}),Object.freeze({name:'run',duration:2}),
 Object.freeze({name:'shoot',duration:1.3,contactTime:.38}),
 Object.freeze({name:'dive-right',duration:1.3,contactTime:.34})
]);
const RIG_SHA256='c66a9fcdb884fdf3cda3f7e92fc4c9ebe1dbbec32fa1bfdb0a8c020099125480';
const sha256=b=>crypto.createHash('sha256').update(b).digest('hex');
function multiply(a,b){const o=new Float64Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)o[c*4+r]+=a[k*4+r]*b[c*4+k];return o;}
function rigidInverse(m){const o=new Float64Array(16);for(let c=0;c<3;c++)for(let r=0;r<3;r++)o[c*4+r]=m[r*4+c];o[15]=1;for(let r=0;r<3;r++)o[12+r]=-(o[r]*m[12]+o[r+4]*m[13]+o[r+8]*m[14]);return o;}
function decompose(m){
 const scale=[0,1,2].map(c=>Math.hypot(m[c*4],m[c*4+1],m[c*4+2]));
 if(scale.some(v=>Math.abs(v-1)>2e-5))throw Error('Licensed bone must remain rigid');
 const [a,b,c,d,e,f,g,h,i]=[m[0],m[4],m[8],m[1],m[5],m[9],m[2],m[6],m[10]];
 let q,s;const trace=a+e+i;
 if(trace>0){s=Math.sqrt(trace+1)*2;q=[(h-f)/s,(c-g)/s,(d-b)/s,s/4];}
 else if(a>e&&a>i){s=Math.sqrt(1+a-e-i)*2;q=[s/4,(b+d)/s,(c+g)/s,(h-f)/s];}
 else if(e>i){s=Math.sqrt(1+e-a-i)*2;q=[(b+d)/s,s/4,(f+h)/s,(c-g)/s];}
 else{s=Math.sqrt(1+i-a-e)*2;q=[(c+g)/s,(f+h)/s,s/4,(d-b)/s];}
 const n=Math.hypot(...q);q=q.map(v=>v/n);
 return {translation:Array.from(m.slice(12,15)),rotation:q,scale:[1,1,1]};
}
function sampleClip(clip,{fps=30,assets=Assets}={}){
 if(fps!==30)throw Error('The interchange fixture is fixed at 30 fps');
 const scenario=Scenarios.create(clip.name==='idle'?'walk':clip.name),steps=Math.round(clip.duration*60);
 if(steps%2)throw Error('Duration must align with 30 fps');
 const count=steps/2+1,times=new Float32Array(count);
 const channels=assets.bones.map(()=>({translation:new Float32Array(count*3),rotation:new Float32Array(count*4)}));
 const worlds=[],palettes=[];let key=0;
 for(let tick=0;tick<=steps;tick++){
  const p=scenario.p,t=tick/60;
  if(clip.name==='idle')Object.assign(p,{x:0,z:0,face:0,speed:0,action:'idle',actionClock:0});
  else Scenarios.sample(scenario,t,Rig);
  const pose=Rig.update(p,1/60);if(tick%2)continue;
  const palette=Renderer.palette(p,assets,pose);
  const world=assets.bones.map((bone,j)=>multiply(palette.subarray(j*16,j*16+16),bone.matrix));
  times[key]=t;worlds.push(world);palettes.push(palette);
  assets.bones.forEach((bone,j)=>{
   const local=bone.parent<0?world[j]:multiply(rigidInverse(world[bone.parent]),world[j]);
   const trs=decompose(local),channel=channels[j];
   if(key&&trs.rotation.reduce((sum,v,k)=>sum+v*channel.rotation[(key-1)*4+k],0)<0)trs.rotation=trs.rotation.map(v=>-v);
   channel.translation.set(trs.translation,key*3);channel.rotation.set(trs.rotation,key*4);
  });key++;
 }
 return {...clip,fps,times,channels,worlds,palettes};
}
function parseGLB(bytes){
 if(bytes.readUInt32LE(0)!==0x46546c67||bytes.readUInt32LE(4)!==2||bytes.readUInt32LE(8)!==bytes.length)throw Error('Expected complete GLB 2.0');
 let json,bin;for(let at=12;at<bytes.length;){const length=bytes.readUInt32LE(at),type=bytes.readUInt32LE(at+4),chunk=bytes.subarray(at+8,at+8+length);if(type===0x4e4f534a)json=JSON.parse(chunk.toString());else if(type===0x004e4942)bin=chunk;at+=8+length;}
 if(!json||!bin)throw Error('Missing GLB chunks');return {json,bin};
}
function packGLB(json,bin){
 const text=Buffer.from(JSON.stringify(json)),j=Buffer.alloc((text.length+3)&~3,32),b=Buffer.alloc((bin.length+3)&~3);text.copy(j);bin.copy(b);
 const out=Buffer.alloc(28+j.length+b.length);out.writeUInt32LE(0x46546c67,0);out.writeUInt32LE(2,4);out.writeUInt32LE(out.length,8);out.writeUInt32LE(j.length,12);out.writeUInt32LE(0x4e4f534a,16);j.copy(out,20);out.writeUInt32LE(b.length,20+j.length);out.writeUInt32LE(0x004e4942,24+j.length);b.copy(out,28+j.length);return out;
}
function bakeLicensedGLB({source=path.join(__dirname,'../assets/player/footballer.glb')}={}){
 if(sha256(fs.readFileSync(path.join(__dirname,'../humanoid-rig.js')))!==RIG_SHA256)throw Error('Reviewed canonical rig pin changed');
 const bytes=fs.readFileSync(source),parsed=parseGLB(bytes),json=parsed.json,bin=Buffer.from(parsed.bin),blobs=[bin];let length=bin.length;
 // The inherited runtime color multiplier includes 1.05 highlights. Standard
 // glTF COLOR_0 must be in [0,1]; normalize only this derivative, never source.
 let clampedColorComponents=0,maximumSourceColor=0;
 const colorAccessors=new Set(json.meshes.flatMap(mesh=>mesh.primitives.map(p=>p.attributes.COLOR_0)).filter(id=>id!==undefined));
 for(const id of colorAccessors){const a=json.accessors[id],view=json.bufferViews[a.bufferView],width=a.type==='VEC3'?3:4;if(a.componentType!==5126)throw Error('Expected floating source vertex color');for(let i=0;i<a.count;i++)for(let c=0;c<width;c++){const at=(view.byteOffset||0)+(a.byteOffset||0)+i*(view.byteStride||width*4)+c*4,value=bin.readFloatLE(at);maximumSourceColor=Math.max(maximumSourceColor,value);if(value<0||value>1){bin.writeFloatLE(Math.max(0,Math.min(1,value)),at);clampedColorComponents++;}}}
 const skinAttributes=new Map();for(const mesh of json.meshes)for(const p of mesh.primitives)skinAttributes.set(p.attributes.JOINTS_0,p.attributes.WEIGHTS_0);
 for(const [jointId,weightId] of skinAttributes){const a=json.accessors[jointId],w=json.accessors[weightId],av=json.bufferViews[a.bufferView],wv=json.bufferViews[w.bufferView],bytesPerJoint=a.componentType===5121?1:a.componentType===5123?2:0;if(!bytesPerJoint||w.componentType!==5126)throw Error('Unexpected source skin attribute storage');for(let i=0;i<a.count;i++)for(let c=0;c<4;c++){const weight=bin.readFloatLE((wv.byteOffset||0)+(w.byteOffset||0)+i*(wv.byteStride||16)+c*4);if(weight===0)bin[bytesPerJoint===1?'writeUInt8':'writeUInt16LE'](0,(av.byteOffset||0)+(a.byteOffset||0)+i*(av.byteStride||4*bytesPerJoint)+c*bytesPerJoint);}}
 // Skinned mesh nodes are scene roots, retaining identity object transforms.
 const meshNodes=json.nodes.map((n,i)=>n.skin!==undefined?i:-1).filter(i=>i>=0);
 for(const i of meshNodes){for(const node of json.nodes)if(node.children)node.children=node.children.filter(child=>child!==i);for(const scene of json.scenes)if(!scene.nodes.includes(i))scene.nodes.push(i);}
 const joints=json.skins[0].joints;
 if(joints.length!==Assets.bones.length)throw Error('Licensed skeleton joint count changed');
 function accessor(data,type,metadata={}){
  const padding=(4-length%4)%4;if(padding){blobs.push(Buffer.alloc(padding));length+=padding;}
  const view=json.bufferViews.length,b=Buffer.from(data.buffer,data.byteOffset,data.byteLength);
  json.bufferViews.push({buffer:0,byteOffset:length,byteLength:b.length});blobs.push(b);length+=b.length;
  const id=json.accessors.length;json.accessors.push({bufferView:view,byteOffset:0,componentType:5126,type,count:data.length/(type==='SCALAR'?1:type==='VEC3'?3:4),...metadata});return id;
 }
 joints.forEach((nodeId,j)=>{const node=json.nodes[nodeId];if(node.name!==Assets.bones[j].name)throw Error('Licensed joint order changed');Object.assign(node,decompose(node.matrix));delete node.matrix;});
 json.asset.generator='Tribun licensed canonical TRS animation baker';
 json.asset.extras={license:'CC0-1.0',sourceSHA256:sha256(bytes),rigSHA256:RIG_SHA256};
 json.extras={...json.extras,animationClips:CLIPS.length,unit:'metre',upAxis:'+Y',forwardAxis:'+X',simulationHz:60,keyframesPerSecond:30,skinConvention:'linear blend skinning; runtime DQS is a separate rendering comparison',colorNormalization:{rule:'COLOR_0 clamped to glTF required [0,1]',clampedColorComponents,maximumSourceColor}};
 json.animations=CLIPS.map(clip=>{
  const baked=sampleClip(clip),input=accessor(baked.times,'SCALAR',{min:[0],max:[clip.duration]}),animation={name:clip.name,samplers:[],channels:[],extras:{...clip,fps:30,simulationHz:60}};
  joints.forEach((nodeId,j)=>{for(const p of ['translation','rotation']){const output=accessor(baked.channels[j][p],p==='translation'?'VEC3':'VEC4');animation.samplers.push({input,output,interpolation:'LINEAR'});animation.channels.push({sampler:animation.samplers.length-1,target:{node:nodeId,path:p}});}});return animation;
 });
 json.buffers[0].byteLength=length;const glb=packGLB(json,Buffer.concat(blobs));return {glb,json,sourceSHA256:sha256(bytes)};
}
if(require.main===module){const args=process.argv.slice(2),at=args.indexOf('--output');if(at<0)throw Error('Usage: node tools/bake-licensed-clips.cjs --output /tmp/footballer.canonical.glb');const result=bakeLicensedGLB(),out=path.resolve(args[at+1]);fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,result.glb);console.log(JSON.stringify({output:out,bytes:result.glb.length,sha256:sha256(result.glb),clips:CLIPS}));}
module.exports={CLIPS,RIG_SHA256,Assets,sampleClip,multiply,rigidInverse,decompose,parseGLB,packGLB,bakeLicensedGLB};
