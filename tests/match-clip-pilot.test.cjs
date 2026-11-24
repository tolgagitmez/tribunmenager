'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFile}=require('node:fs/promises');
const {registerHooks}=require('node:module');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const Rig=require('../humanoid-rig.js');
const Assets=require('../assets/player/player-model-data.js');
const Renderer=require('../player-renderer.js');
const ContactPilot=require('../match-contact-pilot.js');
const AnimationBridge=require('../match-animation-bridge.js');

test('the real Blender pilot keeps physical skill poses on the licensed match renderer',async t=>{
 const vendor=path.resolve(__dirname,'../vendor/three'),addons='three/addons/';
 const hooks=registerHooks({resolve(name,context,next){
  if(name==='three')return next(pathToFileURL(path.join(vendor,'build/three.module.min.js')).href,context);
  if(name.startsWith(addons))return next(pathToFileURL(path.join(vendor,'examples/jsm',name.slice(addons.length))).href,context);
  return next(name,context);
 }});
 t.after(()=>hooks.deregister());
 const bytes=await readFile(path.resolve(__dirname,'../assets/interchange/footballer.blender.glb'));
 const browser={TribunHumanoidRig:Rig,TribunPlayerRenderer:Renderer,TribunContactPilot:ContactPilot,TribunMatchAnimationBridge:AnimationBridge};
 const restore=[];
 for(const [key,value] of Object.entries({window:browser,self:globalThis,createImageBitmap:async blob=>{
  // The palette uses the parsed geometry and skeleton. Supply the PNG
  // dimensions so Node can load the same embedded maps without a canvas.
  const png=new DataView(await blob.arrayBuffer());
  assert.equal(png.getUint32(0),0x89504e47);
  return {width:png.getUint32(16),height:png.getUint32(20),close(){}};
 }})){
  const descriptor=Object.getOwnPropertyDescriptor(globalThis,key);
  Object.defineProperty(globalThis,key,{configurable:true,writable:true,value});
  restore.push(()=>descriptor?Object.defineProperty(globalThis,key,descriptor):delete globalThis[key]);
 }
 t.after(()=>restore.forEach(reset=>reset()));
 const fetch=globalThis.fetch;
 t.mock.method(globalThis,'fetch',(url,...args)=>{
  if(url==='http://localhost/assets/interchange/footballer.blender.glb')return Promise.resolve(new Response(bytes));
  if(String(url).startsWith('blob:'))return fetch(url,...args);
  throw new Error(`Unexpected pilot asset URL ${url}`);
 });
 await import('../match-clip-pilot.mjs');
 const pilot=browser.TribunLiveClipPilot.create({playerId:1});
 assert.equal(await pilot.ready,true,pilot.info().reason);

 const actor={id:1,role:'ATT',active:true,x:4,z:2,face:.1,vx:3,vz:0,speed:3,
  action:'run',actionClock:0,actionElapsed:0,kickFoot:1,dribbleFoot:1};
 const draw=fields=>{
  pilot.reset();
  const p={...actor,...fields},match={time:1,players:[p]},original=structuredClone(match);
  const step=pilot.observe(match,1/60);
  const pose=Rig.getPose(step.visual);
  const expected=Renderer.palette(step.visual,Assets,pose);
  const result=pilot.paletteForPlayer(p,1/60,null,Assets);
  assert.deepEqual(match,original,'drawing cannot mutate match state');
  return {expected,result};
 };
 draw({});
 assert.equal(pilot.info().clip,'run');
 assert.equal(pilot.info().blenderSamples,1,'ordinary running still samples the imported clip');
 for(const fields of [
  {feintClock:.175,feintSign:1},
  {brainRole:'shield'},
  {feintResponseClock:.16,feintResponseSign:-1},
  {action:'pass',actionClock:.12,actionElapsed:.16,actionDuration:.28,contactTime:.24,wallPassClock:.12,wallPassFoot:1}
 ]){
  const {expected,result}=draw(fields);
  assert.equal(pilot.info().blenderSamples,0,'the generic clip cannot overwrite a physical skill cue');
  assert.deepEqual(result,expected,'the skinned joints must retain the same skill pose as the ordinary match renderer');
 }
});
