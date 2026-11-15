'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Rig=require('../humanoid-rig.js');
const Scenarios=require('../animation-scenarios.js');
const Assets=require('../assets/player/procedural-player-model-data.js');
const Renderer=require('../player-renderer-procedural.js');
const distance=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));
const near=(a,b,epsilon=1e-5)=>assert(Math.abs(a-b)<=epsilon,String(a)+' != '+String(b));
const contact={'run-pass':1.06,'run-shoot':1.13};
const release={'run-pass':1.36,'run-shoot':1.43};
function simulate(mode){
 const scenario=Scenarios.create(mode),frames=[],dt=1/60;
 for(let tick=0;tick<=144;tick++){
  const t=tick*dt;Scenarios.sample(scenario,t,Rig);
  const pose=Rig.update(scenario.p,dt);
  frames.push({t,action:pose.action,kick:pose.kick,ankle:pose.legs[1].ankle.slice(),target:Rig.kickAnkle(scenario.p),pelvis:pose.pelvis.slice(),upper:pose.torsoUpper.slice(),legs:pose.legs.map(l=>({...l}))});
 }
 return frames;
}
test('run-to-pass and run-to-shoot maintain reachable ball contact and gentle kick recovery',()=>{
 for(const mode of ['run-pass','run-shoot']){
  const frames=simulate(mode),atContact=Math.round(contact[mode]*60),afterRelease=Math.ceil(release[mode]*60);
  const k=frames[atContact];
  assert(['pass','shoot'].includes(k.action));
  assert(distance(k.ankle,k.target)<.012,mode+' contact ankle must be near target');
  assert(frames[afterRelease].action==='run',mode+' must return to run');
  const exit=distance(frames[afterRelease].ankle,frames[afterRelease-1].ankle);
  assert(exit<.085,mode+' must not teleport kick leg at action release: '+exit);
  assert(frames[afterRelease].kick>0,'upper body follow-through must decay instead of snapping off');
  assert(frames[afterRelease+9].kick<frames[afterRelease].kick,'follow-through must finish smoothly');
  for(const frame of frames){
   for(const leg of frame.legs){
    near(distance(leg.hip,leg.knee),.5);
    near(distance(leg.knee,leg.ankle),.5);
   }
  }
 }
});
test('ground-contact boot outsole lies above, and within 1 cm of, the pitch in every LOD',()=>{
 for(let lod=0;lod<Assets.lods.length;lod++){
  const asset=Assets.lods[lod],encoded=Buffer.from(asset.vertices,'base64'),v=new Float32Array(encoded.buffer,encoded.byteOffset,encoded.byteLength/4);
  let min=Infinity,close=0,boots=0,hipGradient=0,shoulderGradient=0;
  for(let i=0;i<v.length;i+=20){
   if(Math.round(v[i+16])===4){
    boots++;
    const y=v[i+1];min=Math.min(min,y);
    if(y>=0&&y<=.009)close++;
   }
   const weights=new Map();
   for(let j=0;j<4;j++)if(v[i+12+j]>0)weights.set(v[i+8+j],v[i+12+j]);
   if((weights.get(0)||0)>.1&&((weights.get(9)||0)>.1||(weights.get(16)||0)>.1))hipGradient++;
   if(((weights.get(5)||0)>.1&&(weights.get(6)||0)>.1)||((weights.get(12)||0)>.1&&(weights.get(13)||0)>.1))shoulderGradient++;
  }
  assert(boots>50);
  assert(min>=-.001&&min<.009,'outsole must be almost grounded: '+min);
  assert(close>=4,'outsole has multiple ground-proximate samples');
  assert(hipGradient>0,'pelvis and upper thigh require blended weights');
  assert(shoulderGradient>0,'clavicle and upper arm require blended weights');
 }
});
test('WebGL rig exposes measured hip-deformation uniforms without modifying fixed bones',()=>{
 assert(Renderer.vertexShader.includes('uHipRest[2]'));
 assert(Renderer.vertexShader.includes('uHipFlex'));
 assert(Renderer.vertexShader.includes('hipL+='));
 assert(Renderer.vertexShader.includes('hipR+='));
 const p={x:0,z:0,face:0,speed:0,action:'idle',actionClock:0,kickFoot:1};
 const pose=Rig.update(p,1/60),matrices=Renderer.palette(p,Assets,pose);
 for(let i=0;i<19;i++)for(let j=0;j<3;j++){
  const i0=i*16+j*4;
  near(Math.hypot(matrices[i0],matrices[i0+1],matrices[i0+2]),1,2e-5);
 }
});
