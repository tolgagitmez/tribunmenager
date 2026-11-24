'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Renderer=require('../player-renderer.js'),Rig=require('../humanoid-rig.js');
const Bridge=require('../match-animation-bridge.js'),Assets=require('../assets/player/player-model-data.js');
const actors=()=>Array.from({length:22},(_,i)=>({id:i,index:i,active:true,team:i<11?0:1,role:i%11===0?'GK':'MID',x:i%11*1.5-8,z:i<11?-5:5,face:0,speed:0,action:'idle',actionClock:0,kickFoot:1,dribbleFoot:1,footTouch:0,feintClock:0}));
function renderer(){
 let captures=[],uniforms={},calls={binds:0,draws:0};
 const gl={ARRAY_BUFFER:1,ELEMENT_ARRAY_BUFFER:2,FLOAT:3,TRIANGLES:4,TEXTURE0:5,TEXTURE1:6,TEXTURE_2D:7,
 useProgram(){},uniformMatrix4fv(){},uniform3fv(){},uniform1f(){},uniform1i(){},activeTexture(){},bindTexture(){},
 uniform4fv(loc,data){uniforms[loc]=Array.from(data);},bindBuffer(){calls.binds++;},enableVertexAttribArray(){},vertexAttribPointer(){},
 disableVertexAttribArray(){},drawElements(){calls.draws++;captures.push({real:uniforms.real,dual:uniforms.dual});}};
 const r=Object.assign(Object.create(Renderer.prototype),{gl,assets:Assets,options:{},studio:false,visualQuality:'fast',
  loc:{'uBoneReal[0]':'real','uBoneDual[0]':'dual'},textures:{},program:{},
  poseCache:new WeakMap(),attributes:[{location:0,size:3,off:0}],
  lods:[0,1,2].map(i=>({vertex:{i},index:{i},count:3000-i*300,type:0}))});
 const draw=(players,dt=0,bridge=null,opts={})=>{
  calls={binds:0,draws:0};captures=[];r.draw(players,new Float32Array(16),[0,0,60],'tv',dt,bridge,opts);
  return {stats:r.lastRenderStats,calls:{...calls},captures};
 };
 return {r,draw};
}
test('22-player broadcast draws reuse one LOD binding and cache exact repeated pose and dual quaternion data',()=>{
 const players=actors(),{draw}=renderer();
 for(const p of players)Rig.update(p,1/60);
 const bridge=Bridge.create(),first=draw(players,0,bridge),second=draw(players,0,bridge);
 assert.equal(first.stats.players,22);assert.equal(first.calls.draws,22);assert.equal(first.stats.lodBinds,1);assert.equal(first.calls.binds,2);
 assert.equal(first.stats.paletteBuilds,22);assert.equal(first.stats.dualBuilds,22);
 assert.equal(second.stats.paletteBuilds,0);assert.equal(second.stats.dualBuilds,0);
 assert.equal(second.stats.paletteHits,22);assert.equal(second.stats.dualHits,22);
 assert.deepEqual(second.captures,first.captures,'cache must upload byte-equivalent matrices for all actors');
});
test('fresh physical skill poses invalidate cache only for changed actors, preserving all other 21',()=>{
 const players=actors(),{draw}=renderer();
 for(const p of players)Rig.update(p,1/60);
 const first=draw(players);
 Object.assign(players[4],{feintClock:.175,feintSign:1});
 Rig.update(players[4],1/60);
 const second=draw(players);
 assert.equal(second.stats.paletteBuilds,1);assert.equal(second.stats.dualBuilds,1);
 assert.equal(second.stats.paletteHits,21);
 assert.notDeepEqual(second.captures[4],first.captures[4],'new skill pose must actually reach GPU');
 for(let i=0;i<22;i++)if(i!==4)assert.deepEqual(second.captures[i],first.captures[i]);
});
test('mutable animation transition/pilot palettes are never reused as immutable cached dual quaternions',()=>{
 const players=actors(),{draw}=renderer();
 const bridge=Bridge.create({duration:.28});
 draw(players,1/60,bridge);
 Object.assign(players[5],{action:'pass',actionClock:.3,actionDuration:.4,actionElapsed:.1,contactTime:.2});
 Rig.update(players[5],1/60);
 const first=draw(players,.05,bridge),second=draw(players,.05,bridge);
 assert(first.stats.dualBuilds>=1&&second.stats.dualBuilds>=1,'mutable transition must convert every sampled frame');
 assert.notDeepEqual(first.captures[5],second.captures[5]);
 const p=players[3],pose=Rig.getPose(p),custom=Renderer.palette(p,Assets,pose);
 const options={paletteForPlayer:player=>player===p?custom:null};
 const a=draw(players,0,null,options);
 custom[12]+=.1;const b=draw(players,0,null,options);
 assert.notDeepEqual(a.captures[3],b.captures[3],'custom palette mutated in place must be recomputed');
});
test('quality changes keep identical 22 draw calls while binding the appropriate LOD',()=>{
 const players=actors(),{r,draw}=renderer();const low=draw(players);
 r.visualQuality='detailed';const high=draw(players);
 assert.equal(high.stats.players,22);assert.equal(high.stats.detailed,22);assert.equal(high.stats.lodBinds,1);
 assert(high.stats.triangles>low.stats.triangles);assert.deepEqual(high.captures,low.captures);
});
