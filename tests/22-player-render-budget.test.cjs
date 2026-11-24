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

test('broadcast quality uniform is sent once per frame, but close camera transitions still update it',()=>{
 const players=actors(),{r,draw}=renderer(),fast=[];
 r.loc.uFast='fast';r.gl.uniform1f=(location,value)=>{if(location==='fast')fast.push(value);};
 draw(players);assert.deepEqual(fast,[1]);
 fast.length=0;r.visualQuality='detailed';draw(players);assert.deepEqual(fast,[0]);
 fast.length=0;r.visualQuality='auto';
 for(let i=0;i<players.length;i++){players[i].x=i%2?30:0;players[i].z=0;}
 r.draw(players,new Float32Array(16),[0,0,0],'close',0,null,{});
 assert.equal(r.lastRenderStats.players,22);assert.equal(r.lastRenderStats.detailed,11);
 assert.deepEqual(fast,Array.from({length:22},(_,i)=>i%2));
});


test('conservative frustum culling keeps edge actors, selected players and live blend state',()=>{
 const players=actors(),{r}=renderer(),bridge=Bridge.create();
 const vp=new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
 for(const p of players){p.x=30;p.z=0;Rig.update(p,1/60);}
 Object.assign(players[0],{x:0,z:0});Object.assign(players[1],{x:3.8,z:0});
 players[2].selected=true;
 assert(Renderer.playerInView(players[0],vp));assert(Renderer.playerInView(players[1],vp));
 assert(!Renderer.playerInView(players[3],vp));
 assert(Renderer.playerInView(players[3],new Float32Array(16)));
 assert(Renderer.playerInView(players[3],Array(16).fill(NaN)));
 r.draw(players,vp,[0,0,0],'close',1/60,bridge,{cull:true});
 assert.equal(r.lastRenderStats.active,22);assert.equal(r.lastRenderStats.players,3);assert.equal(r.lastRenderStats.culled,19);
 assert.equal(r.lastRenderStats.dualBuilds,3);assert.equal(bridge.stats().players,22);
 players[3].x=0;Rig.update(players[3],1/60);
 r.draw(players,vp,[0,0,0],'close',1/60,bridge,{cull:true});
 assert.equal(r.lastRenderStats.players,4);assert.equal(bridge.stats().players,22);
 r.draw(players,vp,[0,0,60],'tv',0,bridge,{});
 assert.equal(r.lastRenderStats.players,22);assert.equal(r.lastRenderStats.culled,0);
});


test('instanced broadcast packs distinct footballer poses and appearances into one draw',()=>{
 const players=actors(),{r,draw}=renderer(),bridge=Bridge.create();
 for(const p of players)Rig.update(p,1/60);
 const baseline=draw(players,0,bridge),batch={data:new Float32Array(45*32*4)};
 r.initBatch=()=>batch;let calls=0;
 r.drawBatch=(b,lod,count)=>{calls++;assert.equal(b,batch);assert.equal(count,22);};
 const result=draw(players,0,bridge,{instancing:true});
 assert.equal(calls,1);assert.equal(result.stats.drawCalls,1);assert.equal(result.stats.instanced,22);
 assert.equal(result.calls.draws,0);assert.equal(result.stats.triangles,baseline.stats.triangles);
 for(let i=0;i<22;i++){
  const row=i*45*4;
  assert.deepEqual(Array.from(batch.data.slice(row,row+76)),baseline.captures[i].real);
  assert.deepEqual(Array.from(batch.data.slice(row+76,row+152)),baseline.captures[i].dual);
 }
 assert.notDeepEqual(batch.data.slice(39*4,39*4+3),batch.data.slice(11*45*4+39*4,11*45*4+39*4+3));
 assert.equal(batch.data[44*4+3],1);
 assert.equal(batch.data[45*4+44*4+3],0);
 r.initBatch=()=>null;
 const fallback=draw(players,0,bridge,{instancing:true});
 assert.equal(fallback.stats.drawCalls,22);assert.equal(fallback.stats.instanced,0);
 assert.deepEqual(fallback.captures,baseline.captures);
});
test('batch shader uses per-instance texture rows rather than shared uniform bone arrays',()=>{
 const {vertex,fragment,width,rows}=Renderer.batchShaders;
 assert.equal(width,45);assert.equal(rows,32);
 assert(!vertex.includes('uBoneReal[')&&!vertex.includes('uBoneDual['));
 assert(vertex.includes('instanceData(19.+aJoints.w)'));assert(fragment.includes('vInstance'));
 const {r}=renderer();r.gl.getExtension=()=>null;
 assert.equal(r.initBatch(),null);
});
