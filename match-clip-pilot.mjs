/* Pilot: Blender-validated glTF clips supply upper-body animation for ONE
 * actual footballer. Lower-body IK and the planted boot remain the licensed
 * match rig: the clip never drives the ball or player coordinates. */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { createStandardAssetLoader } from './gltf-asset-loader.mjs';
import { createCustomRuntimeAdapter } from './gltf-runtime-adapter.mjs';
import { createBootContactMeter } from './match-boot-contact.mjs';

const keepProcedural=name=>name==='pelvis'||/^(thigh|shin|foot)\./.test(name);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const maxContactLag=1/30,followThrough=.10,maxBootCorrection=.14;
const freshStats=()=>({samples:0,blenderSamples:0,contactFrames:0,maxSupportHeightError:0,
 maxContactGap:0,contactReleaseSamples:0,bootContactSamples:0,lastBootContact:null,clip:null,source:'Blender GLB'});

function towardContact(Rig,pose,foot,delta){
 const leg=pose.legs[foot];
 const target=leg.ankle.map((value,i)=>value+delta[i]);
 target[1]=Math.max(Math.min(leg.ankle[1],.13),target[1]);
 const pole=leg.knee.map((value,i)=>value-leg.hip[i]);
 const {thigh,shin}=Rig.ANATOMY,{knee,hip}=Rig.LIMITS;
 const ik=Rig.solveLimb(leg.hip,target,thigh,shin,pole,knee.max,knee.min);
 const up=new THREE.Vector3().fromArray(pose.torsoBase).sub(new THREE.Vector3().fromArray(pose.pelvis)).normalize();
 const forward=new THREE.Vector3(Math.cos(pose.face),0,Math.sin(pose.face)).projectOnPlane(up).normalize();
 const right=new THREE.Vector3().crossVectors(forward,up);
 const upper=new THREE.Vector3().fromArray(ik.joint).sub(new THREE.Vector3().fromArray(leg.hip));
 const along=upper.dot(forward),vertical=-upper.dot(up);
 const flex=Math.atan2(along,vertical),abduct=Math.atan2(upper.dot(right)*(foot?1:-1),Math.hypot(along,vertical));
 if(flex<hip.flexMin||flex>hip.flexMax||abduct<hip.abductMin||abduct>hip.abductMax||ik.end[1]<target[1]-.015)return pose;
 const toe=leg.toe.map((value,i)=>value+ik.end[i]-leg.ankle[i]);
 const legs=pose.legs.slice();
 legs[foot]={...leg,knee:ik.joint,ankle:ik.end,toe};
 return {...pose,legs};
}

function create({playerId=0}={}){
 const contact=window.TribunContactPilot.create({playerId});
 let status='loading',reason=null,asset=null,adapter=null,actor=null,mixer=null;
 let bones=null,clips=null,boneIndex=null,selected=null,action=null,clipTime=0,travel=0,lastPoint=null;
 let meter=null,pendingContact=null,bootCorrection=null,seenRelease=null,sampledTime=0,stats=freshStats();
 const ready=(async()=>{
  try{
   const loader=createStandardAssetLoader({THREE,GLTFLoader});
   asset=await loader.load({url:'assets/interchange/footballer.blender.glb',timeoutMs:20000});
   adapter=createCustomRuntimeAdapter(asset,{THREE});
   if(!adapter.supported)throw Error(adapter.reasons.join('; '));
   boneIndex=new Map(adapter.boneNames.map((bone,index)=>[bone,index]));
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
  sampledTime=match.time;
  if(step?.release&&step.releaseSerial!==seenRelease){
   const exact=step.releaseCue||match.flight?.age<=1e-8&&{
    time:match.time,ball:match.ball,actor:step.player,kickKind:match.flight.kind
   };
   seenRelease=step.releaseSerial;
   bootCorrection=null;
   if(exact){
    const {ball,actor}=exact;
    const boot=window.TribunHumanoidRig.kickContact(actor);
    stats.maxContactGap=Math.max(stats.maxContactGap,Math.hypot(boot[0]-ball.x,boot[1]-ball.y,boot[2]-ball.z));
    stats.contactReleaseSamples++;
    pendingContact={time:exact.time,ball:{...ball},foot:actor.kickFoot,flightId:seenRelease,kind:exact.kickKind};
   }
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
  const pose=Rig.getPose(proxy);
  let raw=Renderer.palette(proxy,assets,pose);
  if(pendingContact){
   const {ball,foot,flightId,time,kind}=pendingContact;
   pendingContact=null;
   try{
    meter??=createBootContactMeter({assets,decode:Renderer.decode,Skinning:Renderer.skinning,THREE});
    const baseline=meter.measure({palette:raw,foot,ball});
    const lag=Math.max(0,sampledTime-time);
    let reading=baseline;
    // Reach toward the physical release from the licensed boot surface. A
    // delayed sample can be measured, but cannot move a foot back in time.
    if(lag<=maxContactLag+1e-8&&proxy.kickFoot===foot&&baseline.gapMetres>.005){
     const nearest=baseline.closestPoint;
     const direction=[ball.x-nearest.x,ball.y-nearest.y,ball.z-nearest.z];
     const distance=Math.hypot(...direction);
     const length=Math.min(maxBootCorrection,baseline.gapMetres-.003);
     for(const scale of [1,.5]){
      const delta=direction.map(value=>value/distance*length*scale);
      const candidate=towardContact(Rig,pose,foot,delta);
      if(candidate===pose)continue;
      const palette=Renderer.palette(proxy,assets,candidate);
      const adjusted=meter.measure({palette,foot,ball});
      if(adjusted.gapMetres>=-.005&&Math.abs(adjusted.gapMetres)<Math.abs(reading.gapMetres)){
       raw=palette;reading=adjusted;bootCorrection={foot,delta,time:sampledTime};
       if(Math.abs(reading.gapMetres)<=.005)break;
      }
     }
    }
    stats.bootContactSamples++;
    stats.lastBootContact={...reading,baselineGapMetres:baseline.gapMetres,foot,flightId,kind,contactTime:time,
     firstRenderedSampleMs:lag*1000};
   }catch(error){stats.bootMeasurementError=String(error.message||error);}
  }else if(bootCorrection){
   const {foot,delta,time}=bootCorrection;
   const phase=clamp((sampledTime-time)/followThrough,0,1);
   if(phase===1||proxy.kickFoot!==foot)bootCorrection=null;
   else {
    const weight=1-phase*phase*(3-2*phase);
    const candidate=towardContact(Rig,pose,foot,delta.map(value=>value*weight));
    if(candidate!==pose)raw=Renderer.palette(proxy,assets,candidate);
   }
  }
  let result=raw;
  // The Blender shot is right-footed. Receive, pass, left-foot strikes and
  // keeper actions use the contact rig's own pose.
  const activeAction=proxy.actionClock>0&&proxy.action!=='idle';
  const name=activeAction?(proxy.action==='shoot'&&proxy.kickFoot===1?'shoot':null):(proxy.speed||0)>.45?'run':'idle';
  stats.clip=name||proxy.action;
  if(status==='ready'&&name){
   try{
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
    const imported=adapter.getPalette(actor);
    const aligned=raw.slice(),weight=name==='shoot'?.65:
      clamp(.64*(proxy.speed||0)/4.5+.12*(1-c.brake),0,.62);
    for(let i=0;i<assets.bones.length;i++){
     const bone=assets.bones[i],j=boneIndex.get(bone.name);
     if(j===undefined||keepProcedural(bone.name))continue;
     aligned.set(imported.subarray(j*16,j*16+16),i*16);
    }
    // The shared rigid crossfader preserves calibrated joint lengths. The
    // lower-body palette is overwritten with the exact procedural IK again.
    let mixed=new Float32Array(raw.length);
    window.TribunMatchAnimationBridge.mixRigid(raw,aligned,mixed,weight*(1-.35*c.turn));
    mixed=Renderer.renderPalette(raw,mixed,assets);
    for(let i=0;i<assets.bones.length;i++)if(keepProcedural(assets.bones[i].name))
     mixed.set(raw.subarray(i*16,i*16+16),i*16);
    result=mixed;stats.blenderSamples++;stats.clip=name;
   }catch(error){status='fallback';reason=String(error.message||error);}
  }
  const foot=proxy.kickFoot===0?0:1,support=pose.legs[1-foot];
  if(proxy.actionClock>0&&['shoot','pass'].includes(proxy.action)){
   stats.contactFrames++;
   if(support.stance)stats.maxSupportHeightError=Math.max(stats.maxSupportHeightError,Math.abs(support.ankle[1]-.13));
  }
  stats.samples++;
  // Do not apply a second blind crossfade over the physics contact frame:
  // that would move the boot off the ball at the very moment of release.
  return result;
 }
 function reset(){
  contact.reset();travel=0;lastPoint=null;selected=null;seenRelease=null;pendingContact=null;bootCorrection=null;stats=freshStats();
 }
 function info(){return {...stats,status,reason,playerId,clips:clips?[...clips.keys()]:[],
  ...contact.state(),visual:undefined};}
 return {observe,paletteForPlayer,reset,info,ready};
}
window.TribunLiveClipPilot={create};
