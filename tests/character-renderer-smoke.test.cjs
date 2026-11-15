'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Rig=require('../humanoid-rig');
const Assets=require('../assets/player/procedural-player-model-data.js');
const Renderer=require('../player-renderer-procedural');
const Scenarios=require('../animation-scenarios');
function mockWebGL(){
 const calls=[],uniforms={};
 const gl={
  calls,uniforms,
  VERTEX_SHADER:35633,FRAGMENT_SHADER:35632,COMPILE_STATUS:35713,LINK_STATUS:35714,
  ARRAY_BUFFER:34962,ELEMENT_ARRAY_BUFFER:34963,STATIC_DRAW:35044,
  DEPTH_TEST:2929,TRIANGLES:4,FLOAT:5126,UNSIGNED_SHORT:5123,UNSIGNED_INT:5125,
  createShader:()=>({}),shaderSource:()=>{},compileShader:()=>{},getShaderParameter:()=>true,getShaderInfoLog:()=>'',createProgram:()=>({}),attachShader:()=>{},linkProgram:()=>{},getProgramParameter:()=>true,getProgramInfoLog:()=>'',
  getUniformLocation:(_,name)=>name,getAttribLocation:(_,name)=>['aPosition','aNormal','aUV','aJoints','aWeights','aMaterial','aColor'].indexOf(name),
  createBuffer:()=>({}),bindBuffer:()=>{},bufferData:(_,data)=>{assert(data.byteLength>0);},
  getExtension:()=>({}),useProgram:()=>{},
  uniformMatrix4fv:(name,transpose,data)=>{assert.equal(transpose,false);uniforms[name]=data;},
  uniform3fv:(name,data)=>{uniforms[name]=data;},
  uniform4fv:(name,data)=>{uniforms[name]=data;},
  uniform2fv:(name,data)=>{uniforms[name]=data;},
  uniform1f:(name,data)=>{uniforms[name]=data;},
  enableVertexAttribArray:()=>{},disableVertexAttribArray:()=>{},vertexAttribPointer:()=>{},
  drawElements:(mode,count,type,offset)=>{calls.push({mode,count,type,offset});}
 };
 return gl;
}
test('complete character draw pipeline uploads skin matrices for still and moving poses',()=>{
 const gl=mockWebGL(),renderer=new Renderer(gl,Assets);
 const vp=new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
 for(const mode of ['idle','walk','sprint','turn','pass','shoot','dive-left']){
  const state=Scenarios.create(mode==='idle'?'run':mode);
  if(mode!=='idle')Scenarios.sample(state,.24,Rig);
  Rig.update(state.p,1/60);
  state.p.visual={presentation:mode==='idle'};
  renderer.draw([state.p],vp,[0,3,6],'portrait');
  assert.equal(gl.calls.length,mode==='idle'?1:['idle','walk','sprint','turn','pass','shoot','dive-left'].indexOf(mode)+1);
  assert.equal(gl.calls.at(-1).count,Assets.lods[0].indexCount);
  assert.equal(gl.uniforms['uBones[0]'].length,19*16);
  assert.equal(gl.uniforms['uJointRest[0]'].length,4*3);
  assert.equal(gl.uniforms['uHipRest[0]'].length,2*3);
  assert.equal(gl.uniforms['uHipFlex'].length,2);
  for(const x of gl.uniforms['uHipFlex'])assert(x>=0&&x<=1);
  assert.equal(gl.uniforms['uJointFlex'].length,4);
  for(const x of gl.uniforms['uJointFlex'])assert(x>=0&&x<=1);
 }
});
