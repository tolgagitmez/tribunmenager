'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const Renderer=require('../player-renderer.js');
const source=fs.readFileSync(path.join(__dirname,'../scene3d.js'),'utf8');
function stadium(){
 const env={
  devicePixelRatio:2,
  window:{TribunPitchLaws:{dimensions:{halfLength:52,halfWidth:34,goalHalfWidth:3.66,goalHeight:2.44,postRadius:.06}}},
  document:{querySelector:()=>null},
  Math,Float32Array,Array,console,
 };
 vm.runInNewContext(source,env,{filename:'scene3d.js'});
 const canvas={width:0,height:0,getContext:()=>null,getBoundingClientRect:()=>({width:1200,height:750})};
 const s=new env.window.Stadium3D(canvas);let calls=[];
 s.gl={viewport:(...args)=>calls.push(args)};
 return {s,canvas,calls};
}
test('balanced graphics reduce physical GPU pixels after sustained low FPS without making match rules change',()=>{
 const {s,canvas}=stadium();
 assert.equal(s.performance.mode,'performance','match should start in low-cost mode');
 s.setPerformanceMode('balanced');s.resize();const original=canvas.width*canvas.height;
 for(let i=0;i<30;i++)s.observeFrame(.042,false);
 assert(s.performance.scale<=.76,'adaptive DPR should drop after sustained <25 FPS');
 s.resize();assert(canvas.width*canvas.height<original*.6,'adaptive resolution must save GPU pixels');
 const reduced=s.performance.scale;
 for(let i=0;i<60;i++)s.observeFrame(.040,true);
 assert.equal(s.performance.scale,reduced,'paused game must not change graphics quality');
 for(let i=0;i<210;i++)s.observeFrame(.016,false);
 assert(s.performance.scale>reduced,'sustained fast frames may recover GPU quality');
 assert(s.performanceMode().fps>35);
});
test('Performance mode saves GPU fragments; Quality mode restores original shading and DPR',()=>{
 const {s,canvas}=stadium();
 s.playerRenderer={visualQuality:'auto',lastRenderStats:{players:23}};
 s.setPerformanceMode('quality');s.resize();const max=canvas.width*canvas.height;
 assert.equal(s.playerRenderer.visualQuality,'detailed');
 s.setPerformanceMode('performance');s.resize();const low=canvas.width*canvas.height;
 assert.equal(s.playerRenderer.visualQuality,'fast');
 assert(low<=max*.26,'low mode must use <=26% of premium screen fragments');
 s.setPerformanceMode('balanced');s.resize();const mid=canvas.width*canvas.height;
 assert(mid>low&&mid<max);
 assert.equal(s.playerRenderer.visualQuality,'auto');
 assert.throws(()=>s.setPerformanceMode('bad'));
});
test('TV and tactical camera can skip expensive multi-light PBR without changing licensed geometry',()=>{
 const shader=Renderer.fragmentShader;
 assert(shader.includes('uniform float uFast;'),'GPU fast branch uniform must exist');
 assert(shader.includes('if(uFast>.5)'),'fast shading early-exit path missing');
 assert(shader.includes('lightPBR('),'full-quality licensed shading must remain available');
 const file=fs.readFileSync(path.join(__dirname,'../match3d.js'),'utf8');
 assert(file.includes('simOverloadFrames++'),'fixed step debt budget must prevent render starvation');
 assert(file.includes('scene.observeFrame(dt,paused)'),'FPS regulator must be updated every frame');
 assert(file.includes("now-lastPauseDraw>=120"),'paused stadium must not render at 60+ FPS');
});
