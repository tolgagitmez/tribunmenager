'use strict';
/* Presentation-only constraints for rigid world-space skin palettes. Crossfades
   interpolate each bone independently; this final pass restores the skeleton's
   attachments and anatomical limits without changing a cached rig or player. */
(function(root){
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]),mul=(a,s)=>a.map(v=>v*s);
const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const length=a=>Math.hypot(...a),unit=a=>mul(a,1/(length(a)||1));
function nearestAngle(value,minimum,maximum){
 if(value<minimum)return minimum-value<value+Math.PI*2-maximum?minimum:maximum;
 if(value>maximum)return value-maximum<minimum+Math.PI*2-value?maximum:minimum;
 return value;
}
function rotationBetween(from,to){
 const axis=cross(from,to),sine=length(axis),cosine=clamp(dot(from,to),-1,1);
 if(sine<1e-12){
  if(cosine>0)return v=>v.slice();
  const a=unit(cross(from,Math.abs(from[0])<.8?[1,0,0]:[0,0,1]));
  return v=>sub(mul(a,2*dot(a,v)),v);
 }
 const a=mul(axis,1/sine);
 return v=>add(add(mul(v,cosine),mul(cross(a,v),sine)),mul(a,dot(a,v)*(1-cosine)));
}
function constrain(matrices,bones,limits){
 if(!matrices||!Array.isArray(bones)||matrices.length!==bones.length*16)throw Error('Skeleton and palette sizes differ');
 if(!limits?.shoulder||!limits?.hip||!limits?.elbow||!limits?.knee)throw Error('Anatomical joint limits required');
 if(!Array.from(matrices).every(Number.isFinite))throw Error('Palette must contain finite rigid matrices');
 const out=new Float64Array(matrices),children=bones.map(()=>[]),names=new Map(),visited=new Set(),active=new Set();
 bones.forEach((bone,i)=>{
  if(!Number.isInteger(bone.parent)||bone.parent< -1||bone.parent>=bones.length)throw Error('Invalid bone parent');
  if(!bone.head||!bone.tail||![...bone.head,...bone.tail].every(Number.isFinite))throw Error('Invalid bone endpoints');
  if(bone.parent>=0)children[bone.parent].push(i);names.set(bone.name,i);
 });
 const point=(i,p)=>[0,1,2].map(k=>out[i*16+k]*p[0]+out[i*16+4+k]*p[1]+out[i*16+8+k]*p[2]+out[i*16+12+k]);
 const direction=i=>unit(sub(point(i,bones[i].tail),point(i,bones[i].head)));
 function attach(i){
  if(visited.has(i))return;if(active.has(i))throw Error('Skeleton parent cycle');active.add(i);
  const parent=bones[i].parent;
  if(parent>=0){attach(parent);const shift=sub(point(parent,bones[i].head),point(i,bones[i].head));for(let k=0;k<3;k++)out[i*16+12+k]+=shift[k];}
  active.delete(i);visited.add(i);
 }
 bones.forEach((_,i)=>attach(i));
 function rotateSubtree(index,target){
  const from=direction(index),to=unit(target);
  if(dot(from,to)>1-1e-14)return;
  const pivot=point(index,bones[index].head),rotate=rotationBetween(from,to);
  function apply(i){
   const offset=i*16;
   for(let column=0;column<3;column++){
    const v=rotate([out[offset+column*4],out[offset+column*4+1],out[offset+column*4+2]]);
    for(let k=0;k<3;k++)out[offset+column*4+k]=v[k];
   }
   const translation=add(pivot,rotate(sub(Array.from(out.slice(offset+12,offset+15)),pivot)));
   for(let k=0;k<3;k++)out[offset+12+k]=translation[k];
   children[i].forEach(apply);
  }
  apply(index);
 }
 const chest=names.get('chest'),left=names.get('clavicle.L'),right=names.get('clavicle.R');
 if(chest===undefined||left===undefined||right===undefined)throw Error('Canonical chest and clavicle bones required');
 const up=direction(chest),span=sub(point(right,bones[right].tail),point(left,bones[left].tail));
 let lateral=sub(span,mul(up,dot(span,up)));
 if(length(lateral)<1e-8){
  // A 180-degree world fade can briefly fold both clavicles together. The
  // rendered chest's lateral basis gives a deterministic perpendicular axis.
  const offset=chest*16,bindRight=[out[offset+8],out[offset+9],out[offset+10]];
  lateral=sub(bindRight,mul(up,dot(bindRight,up)));
 }
 if(length(lateral)<1e-8)lateral=cross(Math.abs(up[0])<.8?[1,0,0]:[0,0,1],up);
 const bodyRight=unit(lateral),forward=unit(cross(up,bodyRight));
 // Matching clavicles preserve shoulder width and keep the root-angle frame
 // orthogonal even when independent SLERPs would fold the shoulders inward.
 rotateSubtree(left,mul(bodyRight,-1));rotateSubtree(right,bodyRight);
 function rootCone(index,side,limit){
  const v=direction(index),flex=Math.atan2(dot(v,forward),-dot(v,up)),abduct=Math.atan2(dot(v,bodyRight)*side,Math.hypot(dot(v,forward),dot(v,up)));
  const f=nearestAngle(flex,limit.flexMin,limit.flexMax),a=clamp(abduct,limit.abductMin,limit.abductMax);
  if(Math.abs(f-flex)<1e-10&&Math.abs(a-abduct)<1e-10)return;
  rotateSubtree(index,add(add(mul(forward,Math.sin(f)*Math.cos(a)),mul(up,-Math.cos(f)*Math.cos(a))),mul(bodyRight,side*Math.sin(a))));
 }
 function hinge(proximal,distal,limit){
  const upper=direction(proximal),lower=direction(distal),bend=Math.acos(clamp(dot(upper,lower),-1,1)),bounded=clamp(bend,limit.min,limit.max);
  if(Math.abs(bounded-bend)<1e-10)return;
  let pole=sub(lower,mul(upper,dot(lower,upper)));
  if(length(pole)<1e-9){pole=sub(forward,mul(upper,dot(forward,upper)));if(length(pole)<1e-9)pole=sub(bodyRight,mul(upper,dot(bodyRight,upper)));}
  rotateSubtree(distal,add(mul(upper,Math.cos(bounded)),mul(unit(pole),Math.sin(bounded))));
 }
 for(const [side,sign] of [['L',-1],['R',1]]){
  const arm=names.get('upper_arm.'+side),forearm=names.get('forearm.'+side),thigh=names.get('thigh.'+side),shin=names.get('shin.'+side);
  if([arm,forearm,thigh,shin].some(i=>i===undefined))throw Error('Canonical arm and leg bones required');
  rootCone(arm,sign,limits.shoulder);rootCone(thigh,sign,limits.hip);
  hinge(arm,forearm,limits.elbow);hinge(thigh,shin,limits.knee);
 }
 // Rotations preserve connections analytically; reattaching also removes
 // accumulated floating-point error before the Float32 GPU upload.
 visited.clear();bones.forEach((_,i)=>attach(i));
 return new Float32Array(out);
}
const API=Object.freeze({constrain});
if(typeof module!=='undefined'&&module.exports)module.exports=API;root.TribunCharacterConstraints=API;
})(typeof window!=='undefined'?window:globalThis);
