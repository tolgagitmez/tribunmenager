'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Skinning=require('../player-skinning.js');
const Renderer=require('../player-renderer.js');
const Rig=require('../humanoid-rig.js');
const Assets=require('../assets/player/player-model-data.js');
const Bridge=require('../match-animation-bridge.js');
const Scenarios=require('../animation-scenarios.js');

const close=(a,b,tolerance=3e-6)=>assert(Math.abs(a-b)<tolerance,`${a} differs from ${b}`);
const vectorClose=(a,b,tolerance)=>a.forEach((v,i)=>close(v,b[i],tolerance));
// Rodrigues' formula is an independent oracle for the quaternion implementation.
function matrix(axis=[0,1,0],angle=0,translation=[0,0,0]){
 const n=Math.hypot(...axis),[x,y,z]=axis.map(v=>v/n),c=Math.cos(angle),s=Math.sin(angle),t=1-c;
 return new Float32Array([
  t*x*x+c,t*x*y+s*z,t*x*z-s*y,0,
  t*x*y-s*z,t*y*y+c,t*y*z+s*x,0,
  t*x*z+s*y,t*y*z-s*x,t*z*z+c,0,...translation,1
 ]);
}
const apply=(m,p)=>[0,1,2].map(r=>m[r]*p[0]+m[r+4]*p[1]+m[r+8]*p[2]+m[r+12]);
const join=matrices=>new Float32Array(matrices.flatMap(m=>Array.from(m)));
const lbs=(matrices,joints,weights,p)=>weights.reduce((out,w,i)=>{
 const v=apply(matrices.slice(joints[i]*16,joints[i]*16+16),p);
 return out.map((x,k)=>x+w*v[k]);
},[0,0,0]);
const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const subtract=(a,b)=>a.map((v,i)=>v-b[i]);
const unit=a=>a.map(v=>v/Math.hypot(...a));
function renderedGeometry(matrices){
 return Assets.bones.map((bone,i)=>{
  const m=matrices.subarray(i*16,i*16+16);return {head:apply(m,bone.head),tail:apply(m,bone.tail)};
 });
}
function angleWithin(angle,minimum,maximum,label){
 assert(angle>=minimum-1e-4&&angle<=maximum+1e-4,`${label}: rendered ${(angle*180/Math.PI).toFixed(4)} degrees outside ${minimum*180/Math.PI}..${maximum*180/Math.PI}`);
}
function checkRenderedJoints(matrices,label){
 const world=renderedGeometry(matrices),direction=i=>unit(subtract(world[i].tail,world[i].head));
 for(let i=0;i<Assets.bones.length;i++){
  const bone=Assets.bones[i];
  if(bone.parent>=0){
   const parent=apply(matrices.subarray(bone.parent*16,bone.parent*16+16),bone.head);
   assert(Math.hypot(...subtract(parent,world[i].head))<2e-5,`${label} ${bone.name}: disconnected parent joint`);
  }
 }
 for(const [name,a,b,limit] of [['elbow.L',6,7,Rig.LIMITS.elbow],['elbow.R',13,14,Rig.LIMITS.elbow],['knee.L',9,10,Rig.LIMITS.knee],['knee.R',16,17,Rig.LIMITS.knee]])
  angleWithin(Math.acos(Math.max(-1,Math.min(1,dot(direction(a),direction(b))))),limit.min,limit.max,label+' '+name);
 // Torso axes come from rendered attachment positions, independently of the
 // rig's cached flex/abduction values. This catches invalid midfade poses.
 const up=direction(2),right=unit(subtract(world[13].head,world[6].head)),forward=unit(cross(up,right));
 for(const [name,index,side,limit] of [['shoulder.L',6,-1,Rig.LIMITS.shoulder],['shoulder.R',13,1,Rig.LIMITS.shoulder],['hip.L',9,-1,Rig.LIMITS.hip],['hip.R',16,1,Rig.LIMITS.hip]]){
  const v=direction(index),flex=Math.atan2(dot(v,forward),-dot(v,up)),abduct=Math.atan2(dot(v,right)*side,Math.hypot(dot(v,forward),dot(v,up)));
  angleWithin(flex,limit.flexMin,limit.flexMax,label+' '+name+' flex');
  angleWithin(abduct,limit.abductMin,limit.abductMax,label+' '+name+' abduction');
 }
}

test('production renderer exposes the same rigid skinning implementation',()=>{
 assert.equal(Renderer.skinning,Skinning);
 assert.equal(Skinning.mode,'dual-quaternion-rigid-v1');
 assert.match(Renderer.vertexShader,/uBoneReal/);
 assert.match(Renderer.vertexShader,/uBoneDual/);
});

test('dual quaternions reproduce independent rigid matrix rotations and translations',()=>{
 for(const axis of [[1,0,0],[0,1,0],[0,0,1],[1,-2,3]]){
  for(const angle of [0,.37,-1.1,Math.PI/2,Math.PI,-Math.PI,Math.PI-1e-7,Math.PI+1e-7]){
   const m=matrix(axis,angle,[2.1,-.73,4.2]),palette=Skinning.fromMatrices(m);
   for(const point of [[0,0,0],[1,0,0],[-.41,1.23,2.77]])
    vectorClose(Skinning.deform(palette,[0],[1],point),apply(m,point),4e-6);
   const q=Skinning.blend(palette,[0],[1]);
   close(Math.hypot(...q.real),1);close(dot(q.real,q.dual),0);
  }
 }
 const identity=Skinning.fromMatrices(matrix());
 vectorClose(Skinning.deform(identity,[0],[1],[.2,-.4,.8]),[.2,-.4,.8]);
});

test('antipodal signs and rotations crossing 180 degrees do not cancel the blend',()=>{
 const palette=Skinning.fromMatrices(join([matrix([1,2,3],Math.PI-.0001,[.4,.5,-.6]),matrix([1,2,3],-Math.PI+.0001,[.4,.5,-.6])])),point=[.3,.8,-.5];
 const original=Skinning.deform(palette,[0,1],[.5,.5],point);
 const antipodal={real:palette.real.slice(),dual:palette.dual.slice(),count:2};
 for(let k=4;k<8;k++){antipodal.real[k]*=-1;antipodal.dual[k]*=-1;}
 vectorClose(Skinning.deform(antipodal,[0,1],[.5,.5],point),original,3e-6);
 vectorClose(original,apply(matrix([1,2,3],Math.PI,[.4,.5,-.6]),point),4e-6);
 // The sign of both halves changes together, including nonzero translation.
 for(let k=0;k<8;k++){antipodal.real[k]*=-1;antipodal.dual[k]*=-1;}
 vectorClose(Skinning.deform(antipodal,[0,1],[.25,.75],point),Skinning.deform(palette,[0,1],[.25,.75],point),3e-6);
});

test('nonrigid, reflected and projective palettes are rejected before GPU upload',()=>{
 for(const mutate of [m=>m[0]=1.05,m=>m[4]=.02,m=>m[0]=-1,m=>m[3]=.01,m=>m[15]=.9,m=>m[12]=NaN]){
  const m=matrix();mutate(m);assert.throws(()=>Skinning.fromMatrices(m),/rigid|scaled|stretched/);
 }
 assert.throws(()=>Skinning.fromMatrices(new Float32Array(15)),/complete/);
 const palette=Skinning.fromMatrices(matrix());
 for(const [joints,weights] of [[[0],[0]],[[0],[-1]],[[0],[NaN]],[[1],[1]],[[.5],[1]],[[],[]]])
  assert.throws(()=>Skinning.deform(palette,joints,weights,[0,0,0]));
});

test('hierarchy reconnection retains rigid rotations and root motion even with unordered parents',()=>{
 const bones=[{name:'child',parent:2,head:[0,1,0]},{name:'root',parent:-1,head:[0,0,0]},{name:'middle',parent:1,head:[0,.5,0]}];
 const matrices=join([matrix([1,0,0],.6,[.1,.7,.2]),matrix([0,1,0],.3,[2,.5,1]),matrix([0,0,1],-.4,[.2,1,-.1])]),before=matrices.slice();
 const connected=Skinning.connectHierarchy(matrices,bones);
 assert.deepEqual(matrices,before,'source palettes belong to the crossfader');
 assert.deepEqual(connected.slice(16,32),matrices.slice(16,32),'root owns world motion');
 for(let i=0;i<bones.length;i++){
  for(let k=0;k<12;k++)close(connected[i*16+k],matrices[i*16+k]);
  if(bones[i].parent>=0)vectorClose(apply(connected.slice(i*16,i*16+16),bones[i].head),apply(connected.slice(bones[i].parent*16,bones[i].parent*16+16),bones[i].head));
 }
 Skinning.fromMatrices(connected);
 assert.throws(()=>Skinning.connectHierarchy(matrices,[{...bones[0],parent:0},bones[1],bones[2]]),/cycle/);
});

function closedTube(rings=33,sides=64){
 const vertices=[],faces=[],radius=.07,height=1.4;
 for(let j=0;j<rings;j++)for(let k=0;k<sides;k++){
  const theta=k*2*Math.PI/sides;vertices.push([radius*Math.cos(theta),height*j/(rings-1),radius*Math.sin(theta)]);
 }
 for(let j=0;j<rings-1;j++)for(let k=0;k<sides;k++){
  const a=j*sides+k,b=j*sides+(k+1)%sides,c=a+sides,d=b+sides;
  faces.push([a,c,b],[b,c,d]);
 }
 for(let k=1;k<sides-1;k++){faces.push([0,k,k+1]);const o=(rings-1)*sides;faces.push([o,o+k+1,o+k]);}
 return {vertices,faces,radius,height};
}
const signedVolume=(vertices,faces)=>Math.abs(faces.reduce((sum,[a,b,c])=>sum+dot(vertices[a],cross(vertices[b],vertices[c]))/6,0));
test('a spatially varying 180 degree tube twist retains radius and actual closed-mesh volume',()=>{
 const tube=closedTube(),matrices=join([matrix([0,1,0],-Math.PI/2),matrix([0,1,0],Math.PI/2)]),palette=Skinning.fromMatrices(matrices);
 const deform=fn=>tube.vertices.map(p=>fn([0,1],[1-p[1]/tube.height,p[1]/tube.height],p));
 const dual=deform((j,w,p)=>Skinning.deform(palette,j,w,p)),linear=deform((j,w,p)=>lbs(matrices,j,w,p));
 for(const p of dual)close(Math.hypot(p[0],p[2]),tube.radius,2e-6);
 assert(Math.hypot(linear[16*64][0],linear[16*64][2])<1e-8,'the equal-weight LBS ring collapses');
 const restVolume=signedVolume(tube.vertices,tube.faces),dualRatio=signedVolume(dual,tube.faces)/restVolume,linearRatio=signedVolume(linear,tube.faces)/restVolume;
 assert(dualRatio>.985&&dualRatio<1.015,`closed DQ mesh volume ratio ${dualRatio}`);
 assert(linearRatio<.35,`closed LBS mesh volume ratio ${linearRatio}`);
});

test('surface penetration diagnostic distinguishes strict crossing from boundary and coplanar contact',()=>{
 const {segmentTriangleInterior}=require('../tools/check-character-deformation.cjs'),triangle=[[0,0,0],[0,1,0],[0,0,1]];
 assert(segmentTriangleInterior([-1,.3,.3],[1,.3,.3],triangle));
 assert(!segmentTriangleInterior([-1,0,.3],[1,0,.3],triangle),'triangle edge contact is excluded');
 assert(!segmentTriangleInterior([0,.2,.2],[0,.4,.4],triangle),'coplanar contact is excluded');
 assert(!segmentTriangleInterior([-1,.3,.3],[0,.3,.3],triangle),'segment endpoint contact is excluded');
});

test('all nineteen production bones and match crossfades remain rigid without mutating poses or gameplay fields',()=>{
 for(const mode of ['idle','walk','jog','sprint','turn','pass','shoot','run-pass','run-shoot','dive-left','dive-right','throw','celebrate','catch','tackle','receive','header']){
  const state=Scenarios.create(mode),bridge=Bridge.create({duration:.28});
  for(let i=0;i<180;i++){
   Scenarios.sample(state,i/60,Rig);
   if(['throw','celebrate','catch','tackle','receive','header'].includes(mode))Object.assign(state.p,{action:mode,actionClock:1,actionDuration:3,actionElapsed:i/60,contactTime:.55});
   const pose=Rig.update(state.p,1/60);
   const before=structuredClone({player:state.p,ball:state.ball,pose});
   const raw=Renderer.palette(state.p,Assets,pose),mixed=bridge.sample(state.p,raw,1/60,pose.action);
   const rendered=Renderer.renderPalette(raw,mixed,Assets),dq=Skinning.fromMatrices(rendered);
   assert.equal(dq.count,19);
   checkRenderedJoints(rendered,mode+' '+(i/60).toFixed(3));
   const point=Skinning.deform(dq,[6,7,2],[.45,.4,.15],[.03,1.2,-.28]);
   assert(point.every(Number.isFinite));
   assert.deepEqual({player:state.p,ball:state.ball,pose},before);
  }
  if(['pass','shoot','run-pass','run-shoot','dive-left','dive-right'].includes(mode))assert(bridge.stats().transitions>0,mode+' must exercise an actual fade');
 }
});

test('actual human joint sections retain their silhouette through ordinary football poses and moving-shot fades',()=>{
 const Metrics=require('../tools/check-character-deformation.cjs'),mesh=Metrics.unpack(Assets),regions=Metrics.regionsFor(mesh,Assets);
 const cases=[['walk',.67],['sprint',.61],['turn',2.75],['pass',.31],['shoot',.38],['run-shoot',.9],['run-shoot',1.13],['tackle',.25],['receive',.15],['header',.2]];
 for(const [mode,time] of cases){
  const state=Scenarios.create(mode),bridge=Bridge.create({duration:.28});let rendered;
  for(let i=0;i<=Math.round(time*60);i++){
   Scenarios.sample(state,i/60,Rig);
   if(['tackle','receive','header'].includes(mode))Object.assign(state.p,{action:mode,actionClock:1,actionDuration:1,actionElapsed:i/60,contactTime:.55});
   const pose=Rig.update(state.p,1/60),raw=Renderer.palette(state.p,Assets,pose),mixed=bridge.sample(state.p,raw,1/60,pose.action);
   rendered=Renderer.renderPalette(raw,mixed,Assets);
  }
  for(const measured of Metrics.analyze(mesh,regions,rendered,'dual-quaternion')){
   const label=mode+' '+time+' '+measured.region;
   assert(measured.vertices>50&&measured.triangles>100,label+' must cover actual weighted joint geometry');
   assert(measured.jointSection.outerConvexAreaRatio>.93,label+' loses more than 7% of its outer section area');
   assert(measured.actualSurfaceTriangleAreaRatio.p05>.2,label+' collapses a substantial set of actual surface triangles');
   assert(measured.strictTransverseSurfaceIntersections.involvedRestAreaFraction<.04,label+' exceeds the bounded ordinary-pose surface penetration allowance');
  }
 }
 // The section is a convex outer silhouette and the intersections are a
 // strict lower bound. These assertions do not claim zero self penetration or
 // preservation of closed anatomical tissue volume in extreme overhead poses.
});
