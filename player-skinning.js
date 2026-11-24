'use strict';
/* Rigid dual-quaternion skinning shared by GPU upload and mesh verification.
   Quaternion order is XYZW. This module only reads presentation transforms. */
(function(root){
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function quaternion(m){
 let x,y,z,w,s;const trace=m[0]+m[5]+m[10];
 if(trace>0){s=2*Math.sqrt(trace+1);w=s/4;x=(m[6]-m[9])/s;y=(m[8]-m[2])/s;z=(m[1]-m[4])/s;}
 else if(m[0]>m[5]&&m[0]>m[10]){s=2*Math.sqrt(1+m[0]-m[5]-m[10]);w=(m[6]-m[9])/s;x=s/4;y=(m[4]+m[1])/s;z=(m[8]+m[2])/s;}
 else if(m[5]>m[10]){s=2*Math.sqrt(1+m[5]-m[0]-m[10]);w=(m[8]-m[2])/s;x=(m[4]+m[1])/s;y=s/4;z=(m[9]+m[6])/s;}
 else{s=2*Math.sqrt(1+m[10]-m[0]-m[5]);w=(m[1]-m[4])/s;x=(m[8]+m[2])/s;y=(m[9]+m[6])/s;z=s/4;}
 const n=Math.hypot(x,y,z,w),sign=w<0?-1:1;return [x,y,z,w].map(v=>v*sign/n);
}
function fromMatrices(matrices,reuse=null){
 if(!matrices||matrices.length%16)throw Error('Skin palette must contain complete rigid matrices');
 const count=matrices.length/16,size=count*4;
 const real=reuse?.real instanceof Float32Array&&reuse.real.length===size?reuse.real:new Float32Array(size);
 const dual=reuse?.dual instanceof Float32Array&&reuse.dual.length===size&&reuse.dual!==real?reuse.dual:new Float32Array(size);
 // One scratch matrix for all bones, instead of a sliced matrix and three
 // allocated column arrays for each bone. Preserve the rigid-transform gate.
 const m=new Float64Array(16);
 for(let i=0;i<count;i++){
  for(let j=0;j<16;j++)m[j]=matrices[i*16+j];
  const norm=o=>m[o]*m[o]+m[o+1]*m[o+1]+m[o+2]*m[o+2];
  const prod=(a,b)=>m[a]*m[b]+m[a+1]*m[b+1]+m[a+2]*m[b+2];
  const determinant=(m[1]*m[6]-m[2]*m[5])*m[8]+(m[2]*m[4]-m[0]*m[6])*m[9]+(m[0]*m[5]-m[1]*m[4])*m[10];
  if(!m.every(Number.isFinite)||[0,4,8].some(o=>Math.abs(norm(o)-1)>2e-4)||Math.abs(prod(0,4))>2e-4||Math.abs(prod(0,8))>2e-4||Math.abs(prod(4,8))>2e-4||determinant<.9998||Math.abs(m[3])+Math.abs(m[7])+Math.abs(m[11])+Math.abs(m[15]-1)>2e-4)throw Error('Bone '+i+' is not a rigid transform; scaled or stretched bones are unsupported');
  const q=quaternion(m),tx=m[12],ty=m[13],tz=m[14],offset=i*4;
  real.set(q,offset);
  dual[offset]=(tx*q[3]+(ty*q[2]-tz*q[1]))*.5;
  dual[offset+1]=(ty*q[3]+(tz*q[0]-tx*q[2]))*.5;
  dual[offset+2]=(tz*q[3]+(tx*q[1]-ty*q[0]))*.5;
  dual[offset+3]=-(tx*q[0]+ty*q[1]+tz*q[2])*.5;
 }
 return {real,dual,count};
}
function blend(palette,joints,weights){
 if(joints.length!==weights.length||!weights.length)throw Error('Skin influences are empty or mismatched');
 let reference=0;weights.forEach((w,i)=>{if(!Number.isFinite(w)||w<0)throw Error('Invalid skin weight');if(w>weights[reference])reference=i;});
 if(weights[reference]<=0)throw Error('Skin weights must have a positive sum');
 const ref=palette.real.slice(joints[reference]*4,joints[reference]*4+4),r=[0,0,0,0],d=[0,0,0,0];
 weights.forEach((weight,i)=>{if(!weight)return;const index=joints[i];if(!Number.isInteger(index)||index<0||index>=palette.count)throw Error('Invalid skin joint');const q=palette.real.slice(index*4,index*4+4),sign=dot(ref,q)<0?-1:1;for(let k=0;k<4;k++){r[k]+=q[k]*weight*sign;d[k]+=palette.dual[index*4+k]*weight*sign;}});
 const n=Math.hypot(...r);if(n<1e-9)throw Error('Degenerate quaternion blend');for(let k=0;k<4;k++){r[k]/=n;d[k]/=n;}
 const projection=dot(r,d);for(let k=0;k<4;k++)d[k]-=r[k]*projection;
 return {real:r,dual:d};
}
function rotate(q,p){const c=cross(q,p),cc=cross(q,c);return p.map((v,k)=>v+2*(q[3]*c[k]+cc[k]));}
function transform(q,p){const r=q.real,d=q.dual,c=cross(r,d),t=r.slice(0,3).map((v,k)=>2*(r[3]*d[k]-d[3]*v+c[k]));return rotate(r,p).map((v,k)=>v+t[k]);}
function deform(palette,joints,weights,point){return transform(blend(palette,joints,weights),point);}
// A world-space crossfade can keep every rotation rigid while pulling a child
// away from its parent's joint. Reattach bind anchors in hierarchy order; only
// the root owns world translation. Segment rotations and lengths stay intact.
function connectHierarchy(matrices,bones){
 if(matrices.length!==bones.length*16)throw Error('Skeleton and palette sizes differ');
 const out=new Float32Array(matrices),visited=new Set(),active=new Set();
 const point=(offset,p)=>[0,1,2].map(k=>out[offset+k]*p[0]+out[offset+4+k]*p[1]+out[offset+8+k]*p[2]+out[offset+12+k]);
 function attach(i){
  if(visited.has(i))return;if(active.has(i))throw Error('Skeleton parent cycle');active.add(i);
  const bone=bones[i],parent=bone.parent;
  if(!Number.isInteger(parent)||parent< -1||parent>=bones.length)throw Error('Invalid bone parent');
  if(parent>=0){attach(parent);const target=point(parent*16,bone.head),current=point(i*16,bone.head);for(let k=0;k<3;k++)out[i*16+12+k]+=target[k]-current[k];}
  active.delete(i);visited.add(i);
 }
 bones.forEach((_,i)=>attach(i));return out;
}
const API=Object.freeze({mode:'dual-quaternion-rigid-v1',fromMatrices,blend,rotate,transform,deform,connectHierarchy});
if(typeof module!=='undefined'&&module.exports)module.exports=API;root.TribunPlayerSkinning=API;
})(typeof window!=='undefined'?window:globalThis);
