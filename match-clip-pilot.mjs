/* Pilot: Blender-validated glTF clips supply upper-body animation for ONE
 * actual footballer. Lower-body IK and the planted boot remain the licensed
 * match rig: the clip never drives the ball or player coordinates. */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { createStandardAssetLoader } from './gltf-asset-loader.mjs';
import { createCustomRuntimeAdapter } from './gltf-runtime-adapter.mjs';

const keepProcedural=name=>name==='pelvis'||/^(thigh|shin|foot)\./.test(name);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function create({playerId=0}={}){
 const contact=window.TribunContactPilot.create({playerId});
 let status='loading',reason=null,asset=null,adapter=null,actor=null,mixer=null;
 let bones=null,clips=null,selected=null,action=null,clipTime=0,travel=0,lastPoint=null;
 let palette=null,stats={samples:0,blenderSamples:0,contactFrames:0,maxSupportHeightError:0,
  maxContactGap:0,clip:null,source:'Blender GLB'};
 const ready=(async()=>{
  try{
   const loader=createStandardAssetLoader({THREE,GLTFLoader});
   asset=await loader.load({url:'assets/interchange/footballer.blender.glb',timeoutMs:20000});
   adapter=createCustomRuntimeAdapter(asset,{THREE});
   if(!adapter.supported)throw Error(adapter.reasons.join('; '));
   clips=new Map(asset.animations.map(clip=>[clip.name,clip]));
   for(const name of ['idle','run','shoot','dive-right'])
    if(!clips.has(name))throw Error('Blender clip missing: '+name);
   actor=cloneSkeleton(asset.scene);
   mixer=new THREE.AnimationMixer(actor);
   bones=new Map();
   actor.traverse(object=>{if(object.isBone)bones.set(object.name,object)});
   status='ready';return true;
  }catch(error){reason=String(error.message||error);status='fallback';return false;}
 })();
 function select(name){
  const next=clips.get(name);
  if(selected===name)return next;
  mixer.stopAllAction();
  action=mixer.clipAction(next);action.reset().setLoop(THREE.LoopOnce,1);
  action.clampWhenFinished=true;action.play();
  selected=name;return next;
 }
 function observe(match,dt){
  const step=contact.observe(match,dt);
  if(step?.release&&match.flight?.age<=1e-8&&match.ball){
   // Exact release frame only: Match.release() did not teleport the ball.
   const boot=window.TribunHumanoidRig.kickContact(step.player),ball=match.ball;
   const gap=Math.hypot(boot[0]-ball.x,boot[1]-ball.y,boot[2]-ball.z);
   stats.maxContactGap=Math.max(stats.maxContactGap,gap);
   stats.contactReleaseSamples=(stats.contactReleaseSamples||0)+1;
  }
  if(step?.visual&&dt>0){
   const point=step.visual;
   if(lastPoint){
    const delta=Math.hypot(point.x-lastPoint.x,point.z-lastPoint.z);
    if(delta<1.5)travel+=delta;
   }
   lastPoint={x:point.x,z:point.z};
  }
  return step;
 }
 function paletteForPlayer(p,dt,bridge,assets){
  if(p.id!==playerId||!p.active)return null;
  const c=contact.state(),proxy=c.visual;if(!proxy)return null;
  const Rig=window.TribunHumanoidRig,Renderer=window.TribunPlayerRenderer;
  const pose=Rig.getPose(proxy),raw=Renderer.palette(proxy,assets,pose);
  let result=raw;
  // Keep the procedural shoulder fake and shield pose on the selected pilot.
  // A generic imported run clip would otherwise overwrite those upper joints.
  if(status==='ready'&&!(proxy.feintClock>0||proxy.brainRole==='shield'||proxy.feintResponseClock>0||proxy.wallPassClock>0)){
   try{
    const name=proxy.actionClock>0&&['shoot','pass'].includes(proxy.action)?'shoot':(proxy.speed||0)>.45?'run':'idle';
    const clip=select(name);
    // Run phase follows physical distance. Stopping/braking arrests the
    // clip's root advancement, and turns follow the *actual* player yaw.
    clipTime=name==='run'?(travel/2.2*clip.duration)%Math.max(.01,clip.duration-.0001):
     name==='shoot'?Math.min(clip.duration-.0001,
      Math.max(0,proxy.actionElapsed||0)/Math.max(.1,proxy.contactTime||.38)*.38):
      (travel*.13)%Math.max(.01,clip.duration-.0001);
    mixer.setTime(clipTime);
    const pelvis=bones.get('pelvis'),restPosition=clip.tracks.find(t=>/(^|\.)pelvis\.position$/.test(t.name))?.values;
    const cx=restPosition?pelvis.position.x-restPosition[0]:0,cz=restPosition?pelvis.position.z-restPosition[2]:0;
    const co=Math.cos(proxy.face||0),si=Math.sin(proxy.face||0);
    actor.rotation.y=-(proxy.face||0);
    actor.position.set(proxy.x-cx*co+cz*si,0,proxy.z-cx*si-cz*co);
    actor.updateMatrixWorld(true);
    const imported=adapter.getPalette(actor),index=new Map(adapter.boneNames.map((bone,i)=>[bone,i]));
    const aligned=raw.slice(),weight=name==='shoot'?.65:
      clamp(.64*(proxy.speed||0)/4.5+.12*(1-c.brake),0,.62);
    for(let i=0;i<assets.bones.length;i++){
     const bone=assets.bones[i],j=index.get(bone.name);
     if(j===undefined||keepProcedural(bone.name))continue;
     aligned.set(imported.subarray(j*16,j*16+16),i*16);
    }
    // The shared rigid crossfader preserves calibrated joint lengths. The
    // lower-body palette is overwritten with the exact procedural IK again.
    const mixed=new Float32Array(raw.length);
    window.TribunMatchAnimationBridge.mixRigid(raw,aligned,mixed,weight*(1-.35*c.turn));
    for(let i=0;i<assets.bones.length;i++)if(keepProcedural(assets.bones[i].name))
     mixed.set(raw.subarray(i*16,i*16+16),i*16);
    result=mixed;stats.blenderSamples++;stats.clip=name;
   }catch(error){status='fallback';reason=String(error.message||error);}
  }
  const foot=proxy.kickFoot===0?0:1,support=pose.legs[1-foot];
  if(proxy.actionClock>0&&['shoot','pass'].includes(proxy.action)){
   stats.contactFrames++;
   stats.maxSupportHeightError=Math.max(stats.maxSupportHeightError,Math.abs(support.ankle[1]-.13));
  }
  stats.samples++;
  // Do not apply a second blind crossfade over the physics contact frame:
  // that would move the boot off the ball at the very moment of release.
  return result;
 }
 function reset(){
  contact.reset();travel=0;lastPoint=null;selected=null;stats.samples=0;stats.blenderSamples=0;
  stats.contactFrames=0;stats.maxSupportHeightError=0;stats.maxContactGap=0;stats.contactReleaseSamples=0;
 }
 function info(){return {...stats,status,reason,playerId,clips:clips?[...clips.keys()]:[],
  ...contact.state(),visual:undefined};}
 return {observe,paletteForPlayer,reset,info,ready};
}
window.TribunLiveClipPilot={create};
