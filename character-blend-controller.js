'use strict';
/* Standalone glTF action crossfader. The football simulation never calls this:
   only model presentation controls blend duration and clip transitions. */
(function(root){
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x)};
function rootStart(clip){
 const track=(clip?.tracks||[]).find(t=>/(\.|^)pelvis\.position$/.test(t.name));
 const a=track?.values;
 return a&&a.length>=3?[a[0],a[1],a[2]]:[0,0,0];
}
function create({mixer,clips,model=null,pelvis=null,fadeSeconds=.28}){
 if(!mixer||!Array.isArray(clips))throw Error('AnimationMixer and glTF clips required');
 const all=new Map(clips.map(c=>[c.name,c])),actions=new Map();
 let active=null,transition=null;
 function get(name){if(!all.has(name))return null;if(!actions.has(name))actions.set(name,mixer.clipAction(all.get(name)));return actions.get(name);}
 function select(name,{immediate=false}={}){
  const target=get(name);if(!target)return false;
  if(active===name&&!transition)return true;
  const from=active?get(active):null;
  if(transition){
   if(transition.from)transition.from.stop();
   if(transition.to&&transition.to!==from)transition.to.stop();
   transition=null;
   if(from)from.reset().play();
  }
  target.reset();target.enabled=true;target.setEffectiveTimeScale(1);target.setEffectiveWeight((from&&!immediate)?0:1);target.play();
  if(from&&from!==target&&!immediate&&fadeSeconds>0){
   from.enabled=true;from.setEffectiveWeight(1);from.play();
   const source=[pelvis?.position.x||0,pelvis?.position.y||0,pelvis?.position.z||0];
   const dest=rootStart(all.get(name));
   transition={from,to:target,sourceName:active,targetName:name,elapsed:0,duration:fadeSeconds,ease:0,
    offset:[source[0]-dest[0],0,source[2]-dest[2]]};
  }else if(from&&from!==target)from.stop();
  active=name;return true;
 }
 function update(dt){
  if(!Number.isFinite(dt)||dt<0)throw Error('Animation delta must be finite and nonnegative');
  mixer.update(Math.min(dt,.10));
  if(!transition)return;
  const tr=transition;tr.elapsed=Math.min(tr.duration,tr.elapsed+dt);
  const easing=smooth(tr.elapsed/tr.duration),increment=easing-tr.ease;
  if(model&&model.position){model.position.x+=tr.offset[0]*increment;model.position.z+=tr.offset[2]*increment;}
  tr.ease=easing;
  tr.from.setEffectiveWeight(1-easing);tr.to.setEffectiveWeight(easing);
  if(tr.elapsed>=tr.duration){
   tr.from.stop();tr.to.setEffectiveWeight(1);transition=null;
  }
 }
 function seek(time){
  const selected=get(active);if(!selected)return false;
  if(transition){transition.from.stop();transition.to.setEffectiveWeight(1);transition=null;}
  // Deterministic scrubbing of the chosen clip, not mixed wall-clock state.
  mixer.setTime(clamp(Number(time)||0,0,all.get(active).duration-.0001));
  return true;
 }
 function info(){
  const t=transition;
  return {active,transition:!!t,from:t?.sourceName||null,to:t?.targetName||null,
   progress:t?clamp(t.elapsed/t.duration,0,1):1,
   fromWeight:t?t.from.getEffectiveWeight():0,toWeight:get(active)?.getEffectiveWeight()??0,
   rootOffset:model?.position?[model.position.x,model.position.z]:[0,0]};
 }
 function reset(){for(const a of actions.values())a.stop();active=null;transition=null;}
 return {select,update,seek,info,reset,clipName:()=>active};
}
const API={create,rootStart};
if(typeof module!=='undefined'&&module.exports)module.exports=API;
root.TribunCharacterBlending=API;
})(typeof window!=='undefined'?window:globalThis);
