/* Sample the project's existing Blender GLB once. No mesh or imported
 * animation mixer per player; the library contains local wrist vectors. */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createStandardAssetLoader} from '../../gltf-asset-loader.mjs';
export async function loadNativeClipLibrary(){
 const loader=createStandardAssetLoader({THREE,GLTFLoader});
 const url=new URL('../../assets/interchange/footballer.blender.glb',import.meta.url).href;
 const asset=await loader.load({url,timeoutMs:20000});
 const scene=asset.scene,parser=asset.parser||asset.gltf?.parser,doc=asset.document||parser?.json||{};
 const bones=new Map();
 scene.traverse(o=>{if(o.isBone){const source=doc.nodes?.[parser?.associations?.get(o)?.nodes]?.name||o.userData?.name||o.name;bones.set(source,o);}});
 const find=name=>{const b=bones.get(name)||bones.get(name.replaceAll('.',''));if(!b)throw Error('Klip kemiği eksik: '+name);return b;};
 const chest=find('chest'),neck=find('neck'),upper=[find('upper_arm.L'),find('upper_arm.R')],hands=[find('hand.L'),find('hand.R')];
 const pos=b=>b.getWorldPosition(new THREE.Vector3()),mixer=new THREE.AnimationMixer(scene),bank={};
 const clips=new Map(asset.animations.map(c=>[c.name,c]));
 for(const name of ['idle','run','shoot','dive-right']){
  const clip=clips.get(name);if(!clip||!Number.isFinite(clip.duration)||clip.duration<=0)throw Error('Klip eksik: '+name);
  mixer.stopAllAction();mixer.clipAction(clip).reset().setLoop(THREE.LoopOnce,1).play().clampWhenFinished=true;
  const samples=[],count=Math.max(2,Math.ceil(clip.duration*30));
  for(let i=0;i<=count;i++){
   mixer.setTime(Math.min(clip.duration-.00001,clip.duration*i/count));scene.updateMatrixWorld(true);
   const shoulders=upper.map(pos),up=pos(neck).sub(pos(chest)).normalize(),right=shoulders[1].clone().sub(shoulders[0]).normalize();
   const forward=up.clone().cross(right).normalize();right.crossVectors(forward,up).normalize();
   if(Math.min(up.length(),right.length(),forward.length())<.9)throw Error('Geçersiz klip eksenleri');
   const row=hands.map((h,j)=>{const d=pos(h).sub(shoulders[j]),v=[d.dot(forward),d.dot(up),d.dot(right)];if(!v.every(Number.isFinite)||d.length()>.85)throw Error('Geçersiz klip kol hedefi');return Object.freeze(v);});
   samples.push(Object.freeze(row));
  }
  bank[name]=Object.freeze({duration:clip.duration,samples:Object.freeze(samples)});
 }
 mixer.stopAllAction();
 return Object.freeze(bank);
}
