#!/usr/bin/env node
'use strict';
/* Source-bound, reproducible surface-deformation measurements. This is not a
   tissue-volume estimator: the footballer is an open, material-split surface. */
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const Skinning=require('../player-skinning.js');
const Scenarios=require('../animation-scenarios.js');
const BASELINE='6ddd4f1';
const FILES=['humanoid-rig.js','player-renderer.js','player-skinning.js','character-palette-constraints.js','match-animation-bridge.js','animation-scenarios.js','assets/player/player-model-data.js','assets/player/manifest.json'];
const add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]),mul=(a,n)=>a.map(v=>v*n);
const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const length=a=>Math.hypot(...a),unit=a=>mul(a,1/(length(a)||1));
const hash=buffer=>crypto.createHash('sha256').update(buffer).digest('hex');
const quantile=(values,p)=>values.length?values.slice().sort((a,b)=>a-b)[Math.floor((values.length-1)*p)]:null;
const summary=values=>({samples:values.length,min:quantile(values,0),p01:quantile(values,.01),p05:quantile(values,.05),median:quantile(values,.5),max:quantile(values,1)});
const determinant=m=>dot(m.slice(0,3),cross(m.slice(3,6),m.slice(6,9)));
const apply=(m,p)=>[0,1,2].map(r=>m[r]*p[0]+m[r+4]*p[1]+m[r+8]*p[2]+m[r+12]);
const rotate=(m,p)=>[0,1,2].map(r=>m[r]*p[0]+m[r+4]*p[1]+m[r+8]*p[2]);
function linear(matrices,joints,weights,point){
 const out=[0,0,0];for(let i=0;i<4;i++)if(weights[i]){
  const m=matrices.subarray(joints[i]*16,joints[i]*16+16),p=apply(m,point);
  for(let k=0;k<3;k++)out[k]+=p[k]*weights[i];
 }return out;
}
function linearRotation(matrices,joints,weights,normal){
 const out=[0,0,0];for(let i=0;i<joints.length;i++)if(weights[i]){
  const p=rotate(matrices.subarray(joints[i]*16,joints[i]*16+16),normal);
  for(let k=0;k<3;k++)out[k]+=p[k]*weights[i];
 }return unit(out);
}
function frozenLinearDeterminant(matrices,joints,weights){
 const m=new Array(9).fill(0);
 for(let i=0;i<4;i++)for(let c=0;c<3;c++)for(let r=0;r<3;r++)m[c*3+r]+=weights[i]*matrices[joints[i]*16+c*4+r];
 return determinant(m);
}
function loadAtRef(ref,file){
 const source=execFileSync('git',['show',ref+':'+file],{cwd:ROOT,maxBuffer:8*1024*1024});
 const module={exports:{}};vm.runInNewContext(source.toString(),{module,exports:module.exports,atob:global.atob},{filename:ref+':'+file});
 return {api:module.exports,sha256:hash(source)};
}
function unpack(assets){
 const raw=Buffer.from(assets.lods[0].vertices,'base64'),ib=Buffer.from(assets.lods[0].indices,'base64');
 const data=new Float32Array(raw.buffer,raw.byteOffset,raw.byteLength/4),Index=assets.lods[0].indexType==='H'?Uint16Array:Uint32Array;
 const indices=new Index(ib.buffer,ib.byteOffset,ib.byteLength/Index.BYTES_PER_ELEMENT),vertices=[];
 for(let o=0;o<data.length;o+=20)vertices.push({point:Array.from(data.subarray(o,o+3)),joints:Array.from(data.subarray(o+8,o+12)),weights:Array.from(data.subarray(o+12,o+16))});
 const triangles=[];for(let i=0;i<indices.length;i+=3)triangles.push(Array.from(indices.subarray(i,i+3)));
 return {vertices,triangles};
}
function hullArea(points){
 const sorted=points.slice().sort((a,b)=>a[0]-b[0]||a[1]-b[1]),unique=[];
 for(const p of sorted)if(!unique.length||length(sub(p,unique[unique.length-1]))>1e-7)unique.push(p);
 if(unique.length<3)return null;
 const turn=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 const lower=[],upper=[];
 for(const p of unique){while(lower.length>1&&turn(lower[lower.length-2],lower[lower.length-1],p)<=0)lower.pop();lower.push(p);}
 for(const p of unique.slice().reverse()){while(upper.length>1&&turn(upper[upper.length-2],upper[upper.length-1],p)<=0)upper.pop();upper.push(p);}
 const hull=lower.slice(0,-1).concat(upper.slice(0,-1));
 return Math.abs(hull.reduce((sum,p,i)=>{const q=hull[(i+1)%hull.length];return sum+p[0]*q[1]-q[0]*p[1];},0))*.5;
}
function section(mesh,positions,region,center,normal){
 const tangent=unit(cross(normal,Math.abs(normal[0])<.8?[1,0,0]:[0,1,0])),bitangent=cross(normal,tangent),points=[];
 for(const index of region.triangles){
  const tri=mesh.triangles[index],p=tri.map(i=>positions[i]),d=p.map(v=>dot(sub(v,center),normal));
  for(let j=0;j<3;j++){
   const k=(j+1)%3;if(d[j]*d[k]>=0)continue;
   const t=d[j]/(d[j]-d[k]),point=sub(add(p[j],mul(sub(p[k],p[j]),t)),center);
   points.push([dot(point,tangent),dot(point,bitangent)]);
  }
 }
 return {intersectionPoints:points.length,outerConvexArea:hullArea(points)};
}
// Strict transverse interior intersections. Coplanar surfaces, shared topology,
// coincident material/UV splits and boundary-only contact are excluded. This is
// an independently measured lower bound, not a robust collision solver.
function segmentTriangleInterior(a,b,triangle){
 const direction=sub(b,a),edge1=sub(triangle[1],triangle[0]),edge2=sub(triangle[2],triangle[0]),h=cross(direction,edge2),det=dot(edge1,h);
 if(Math.abs(det)<1e-12)return false;
 const inverse=1/det,s=sub(a,triangle[0]),u=inverse*dot(s,h);if(u<=1e-7||u>=1-1e-7)return false;
 const q=cross(s,edge1),v=inverse*dot(direction,q);if(v<=1e-7||u+v>=1-1e-7)return false;
 const t=inverse*dot(edge2,q);return t>1e-7&&t<1-1e-7;
}
function strictIntersectionStats(mesh,positions,region){
 const triangles=region.triangles.map(index=>({index,vertices:mesh.triangles[index],points:mesh.triangles[index].map(i=>positions[i])}));
 for(const tri of triangles){tri.minimum=[0,1,2].map(k=>Math.min(...tri.points.map(p=>p[k])));tri.maximum=[0,1,2].map(k=>Math.max(...tri.points.map(p=>p[k])));}
 const pairs=[],involved=new Set();let candidatePairs=0;
 for(let i=0;i<triangles.length;i++)for(let j=i+1;j<triangles.length;j++){
  const a=triangles[i],b=triangles[j];
  if(a.vertices.some(v=>b.vertices.includes(v)))continue;
  if([0,1,2].some(k=>a.minimum[k]>b.maximum[k]-1e-8||a.maximum[k]<b.minimum[k]+1e-8))continue;
  if(a.vertices.some(x=>b.vertices.some(y=>length(sub(mesh.vertices[x].point,mesh.vertices[y].point))<1e-6)))continue;
  candidatePairs++;let intersects=false;
  for(let k=0;k<3&&!intersects;k++)intersects=segmentTriangleInterior(a.points[k],a.points[(k+1)%3],b.points)||segmentTriangleInterior(b.points[k],b.points[(k+1)%3],a.points);
  if(intersects){pairs.push([a.index,b.index]);involved.add(a.index);involved.add(b.index);}
 }
 const restArea=ti=>{const p=mesh.triangles[ti].map(i=>mesh.vertices[i].point);return length(cross(sub(p[1],p[0]),sub(p[2],p[0])))*.5;};
 const totalRestArea=region.triangles.reduce((sum,i)=>sum+restArea(i),0),involvedRestArea=[...involved].reduce((sum,i)=>sum+restArea(i),0);
 return {candidatePairs,intersectingPairs:pairs.length,involvedTriangles:involved.size,regionTriangles:region.triangles.length,involvedRestAreaFraction:totalRestArea?involvedRestArea/totalRestArea:0,examplePairs:pairs.slice(0,4)};
}
function regionsFor(mesh,assets){
 const out=[];
 for(const side of ['L','R'])for(const [kind,parent,child,radius] of [
  ['shoulder','clavicle','upper_arm',.18],['elbow','upper_arm','forearm',.12],['knee','thigh','shin',.15]
 ]){
  const a=assets.bones.findIndex(b=>b.name===parent+'.'+side),b=assets.bones.findIndex(b=>b.name===child+'.'+side),bone=assets.bones[b],pa=assets.bones[a],center=bone.head;
  const normal=unit(add(unit(sub(pa.tail,pa.head)),unit(sub(bone.tail,bone.head))));
  const member=mesh.vertices.map(v=>length(sub(v.point,center))<radius&&v.weights.reduce((sum,w,i)=>sum+([a,b].includes(v.joints[i])?w:0),0)>.35);
  const vertices=member.flatMap((valid,i)=>valid?[i]:[]),triangles=[];
  mesh.triangles.forEach((tri,i)=>{if(tri.every(j=>member[j]))triangles.push(i);});
  const region={name:kind+'.'+side,a,b,center,normal,radius,vertices,triangles};
  region.restSection=section(mesh,mesh.vertices.map(v=>v.point),region,center,normal);
  region.restIntersections=strictIntersectionStats(mesh,mesh.vertices.map(v=>v.point),region);
  out.push(region);
 }
 return out;
}
function analyze(mesh,regions,matrices,method){
 const dq=method==='dual-quaternion'?Skinning.fromMatrices(matrices):null;
 const positions=mesh.vertices.map(v=>dq?Skinning.deform(dq,v.joints,v.weights,v.point):linear(matrices,v.joints,v.weights,v.point));
 if(positions.some(p=>!p.every(Number.isFinite)))throw Error('Nonfinite deformed mesh');
 return regions.map(region=>{
  const areaRatios=[],frozenDet=[],normals=new Map(),restNormals=new Map();
  for(const i of region.vertices){
   const v=mesh.vertices[i];
   if(dq){
    // Differentiate only point coordinates while holding this vertex's skin
    // weights fixed. It proves a local rigid map, not anatomical tissue volume.
    const e=1e-4,q=Skinning.blend(dq,v.joints,v.weights),columns=[];
    for(let axis=0;axis<3;axis++){
     const delta=[0,0,0];delta[axis]=e;
     columns.push(...mul(sub(Skinning.transform(q,add(v.point,delta)),Skinning.transform(q,sub(v.point,delta))),1/(2*e)));
    }
    frozenDet.push(determinant(columns));
   }else frozenDet.push(frozenLinearDeterminant(matrices,v.joints,v.weights));
  }
  let reversedRelativeToTransportedNormal=0;const edgeNormals=new Map();let foldbackEdges=0,eligibleEdges=0;
  for(const ti of region.triangles){
   const tri=mesh.triangles[ti],rest=tri.map(i=>mesh.vertices[i].point),p=tri.map(i=>positions[i]),rn=cross(sub(rest[1],rest[0]),sub(rest[2],rest[0])),n=cross(sub(p[1],p[0]),sub(p[2],p[0]));
   if(length(rn)<1e-10)continue;
   areaRatios.push(length(n)/length(rn));normals.set(ti,unit(n));restNormals.set(ti,unit(rn));
   const transported=tri.map(i=>{const v=mesh.vertices[i];return dq?Skinning.rotate(Skinning.blend(dq,v.joints,v.weights).real,unit(rn)):linearRotation(matrices,v.joints,v.weights,unit(rn));}).reduce(add,[0,0,0]);
   if(dot(n,transported)<0)reversedRelativeToTransportedNormal++;
   for(let e=0;e<3;e++){
    const key=[tri[e],tri[(e+1)%3]].sort((a,b)=>a-b).join(':');
    if(edgeNormals.has(key)){
     const other=edgeNormals.get(key);
     if(dot(restNormals.get(other),unit(rn))>.5){eligibleEdges++;if(dot(normals.get(other),unit(n))<0)foldbackEdges++;}
    }else edgeNormals.set(key,ti);
   }
  }
  const center=dq?Skinning.deform(dq,[region.a,region.b],[.5,.5],region.center):linear(matrices,[region.a,region.b,0,0],[.5,.5,0,0],region.center);
  const normal=dq?Skinning.rotate(Skinning.blend(dq,[region.a,region.b],[.5,.5]).real,region.normal):linearRotation(matrices,[region.a,region.b],[.5,.5],region.normal);
  const slice=section(mesh,positions,region,center,unit(normal));
  return {region:region.name,vertices:region.vertices.length,triangles:region.triangles.length,
   frozenWeightFiniteDifferenceJacobianDeterminant:summary(frozenDet),
   actualSurfaceTriangleAreaRatio:summary(areaRatios),
   strictTransverseSurfaceIntersections:strictIntersectionStats(mesh,positions,region),
   reversedRelativeToTransportedNormal,adjacentSurfaceFoldback:{eligibleEdges,foldbackEdges},
   jointSection:{...slice,restOuterConvexArea:region.restSection.outerConvexArea,outerConvexAreaRatio:region.restSection.outerConvexArea&&slice.outerConvexArea?slice.outerConvexArea/region.restSection.outerConvexArea:null}};
 });
}
function attachmentGaps(assets,matrices){
 return assets.bones.flatMap((bone,i)=>{
  if(bone.parent<0)return [];
  const parent=apply(matrices.subarray(bone.parent*16,bone.parent*16+16),bone.head),child=apply(matrices.subarray(i*16,i*16+16),bone.head);
  return [{bone:bone.name,gapMetres:length(sub(parent,child))}];
 });
}
function anatomicalAngles(assets,matrices,limits){
 const world=assets.bones.map((bone,i)=>{const m=matrices.subarray(i*16,i*16+16);return [apply(m,bone.head),apply(m,bone.tail)];});
 const direction=i=>unit(sub(world[i][1],world[i][0])),up=direction(2),right=unit(sub(world[13][0],world[6][0])),forward=unit(cross(up,right)),out=[];
 const record=(joint,axis,value,min,max)=>out.push({joint,axis,radians:value,degrees:value*180/Math.PI,minimumRadians:min,maximumRadians:max,excessRadians:Math.max(0,min-value,value-max)});
 for(const [name,a,b,limit] of [['elbow.L',6,7,limits.elbow],['elbow.R',13,14,limits.elbow],['knee.L',9,10,limits.knee],['knee.R',16,17,limits.knee]])
  record(name,'hinge',Math.acos(Math.max(-1,Math.min(1,dot(direction(a),direction(b))))),limit.min,limit.max);
 for(const [name,index,side,limit] of [['shoulder.L',6,-1,limits.shoulder],['shoulder.R',13,1,limits.shoulder],['hip.L',9,-1,limits.hip],['hip.R',16,1,limits.hip]]){
  const v=direction(index);record(name,'flex',Math.atan2(dot(v,forward),-dot(v,up)),limit.flexMin,limit.flexMax);
  record(name,'abduction',Math.atan2(dot(v,right)*side,Math.hypot(dot(v,forward),dot(v,up))),limit.abductMin,limit.abductMax);
 }
 return out;
}
const CASES=[
 ['idle',[0]],['walk',[.33,.67]],['sprint',[.23,.61,.91]],['turn',[2.75,3.25]],
 ['pass',[.15,.31,.5]],['shoot',[.17,.38,.6]],['run-shoot',[.75,.9,1.13,1.45]],
 ['dive-left',[.12,.23,.34,.65,2.6833,2.7,2.75]],['dive-right',[.12,.23,.34,.65,2.6833,2.7,2.75]],
 ['throw',[.25,.5]],['celebrate',[.25]],['catch',[.25]],['tackle',[.25]],['receive',[.15]],['header',[.2]]
];
function* poses(rig,renderer,assets,bridgeAPI){
 for(const [mode,times] of CASES){
  const state=Scenarios.create(mode),bridge=bridgeAPI.create({duration:.28}),wanted=new Set(times.map(t=>Math.round(t*60)));
  for(let frame=0;frame<=Math.max(...wanted);frame++){
   const t=frame/60;Scenarios.sample(state,t,rig);
   if(['throw','celebrate','catch','tackle','receive','header'].includes(mode)){
    Object.assign(state.p,{action:mode,actionClock:1,actionDuration:1,actionElapsed:t,contactTime:.55});
   }
   const pose=rig.update(state.p,1/60),raw=renderer.palette(state.p,assets,pose),mixed=bridge.sample(state.p,raw,1/60,pose.action);
   const rendered=renderer.renderPalette?renderer.renderPalette(raw,mixed,assets):mixed;
   if(wanted.has(frame))yield {mode,time:t,palette:rendered,bridgeActive:mixed!==raw};
  }
 }
}
function run({baselineRef=BASELINE}={}){
 const sourceFiles=[...FILES,'tools/check-character-deformation.cjs','tests/player-skinning.test.cjs'];
 const sourceSHA256=Object.fromEntries(sourceFiles.map(file=>[file,hash(fs.readFileSync(path.join(ROOT,file)))]));
 const current={rig:require('../humanoid-rig.js'),renderer:require('../player-renderer.js'),assets:require('../assets/player/player-model-data.js'),bridge:require('../match-animation-bridge.js')};
 const parent={rig:loadAtRef(baselineRef,'humanoid-rig.js'),renderer:loadAtRef(baselineRef,'player-renderer.js'),assets:loadAtRef(baselineRef,'assets/player/player-model-data.js'),bridge:loadAtRef(baselineRef,'match-animation-bridge.js')};
 const mesh=unpack(current.assets),regions=regionsFor(mesh,current.assets),oldMesh=unpack(parent.assets.api),oldRegions=regionsFor(oldMesh,parent.assets.api),frames=[];
 for(const frame of poses(current.rig,current.renderer,current.assets,current.bridge))frames.push({scenario:frame.mode,time:frame.time,matchBridgeActive:frame.bridgeActive,
  currentHierarchyAttachmentGaps:attachmentGaps(current.assets,frame.palette),
  currentAnatomicalAngles:anatomicalAngles(current.assets,frame.palette,current.rig.LIMITS),
  currentDualQuaternion:analyze(mesh,regions,frame.palette,'dual-quaternion'),currentLinearBlendControl:analyze(mesh,regions,frame.palette,'linear')});
 const oldFrames=Array.from(poses(parent.rig.api,parent.renderer.api,parent.assets.api,parent.bridge.api));
 for(let i=0;i<frames.length;i++){
  const old=oldFrames[i];if(old.mode!==frames[i].scenario||old.time!==frames[i].time)throw Error('Baseline scenario alignment differs');
  frames[i].baselineLinearBlend=analyze(oldMesh,oldRegions,old.palette,'linear');
  frames[i].baselineHierarchyAttachmentGaps=attachmentGaps(parent.assets.api,old.palette);
 }
 const methods=['currentDualQuaternion','currentLinearBlendControl','baselineLinearBlend'],aggregate={};
 for(const method of methods){aggregate[method]={};for(const name of regions.map(r=>r.name)){
  const values=frames.map(f=>f[method].find(r=>r.region===name));
  aggregate[method][name]={
   minimumFrozenWeightJacobianDeterminant:Math.min(...values.map(v=>v.frozenWeightFiniteDifferenceJacobianDeterminant.min)),
   minimumSurfaceTriangleAreaRatioP05:Math.min(...values.map(v=>v.actualSurfaceTriangleAreaRatio.p05)),
   jointSectionOuterAreaRatio:summary(values.map(v=>v.jointSection.outerConvexAreaRatio).filter(Number.isFinite)),
   reversedRelativeToTransportedNormal:values.reduce((sum,v)=>sum+v.reversedRelativeToTransportedNormal,0),
   adjacentFoldbackEdges:values.reduce((sum,v)=>sum+v.adjacentSurfaceFoldback.foldbackEdges,0),
   strictIntersectionPairsAcrossSampledFrames:values.reduce((sum,v)=>sum+v.strictTransverseSurfaceIntersections.intersectingPairs,0),
   maximumIntersectingBindAreaFraction:Math.max(...values.map(v=>v.strictTransverseSurfaceIntersections.involvedRestAreaFraction))
  };
 }}
 for(const file of sourceFiles)if(hash(fs.readFileSync(path.join(ROOT,file)))!==sourceSHA256[file])throw Error('Source changed during measurement: '+file+'; freeze and rerun');
 return {schemaVersion:1,baselineRef,sourceSHA256,
  baselineSourceSHA256:Object.fromEntries(Object.entries(parent).map(([name,value])=>[name,value.sha256])),
  model:{id:current.assets.metadata.id,vertices:mesh.vertices.length,triangles:mesh.triangles.length,bones:current.assets.bones.length},
  bindRegionIntersections:{current:Object.fromEntries(regions.map(r=>[r.name,r.restIntersections])),baseline:Object.fromEntries(oldRegions.map(r=>[r.name,r.restIntersections]))},
  method:{
   comparison:'Same deterministic scenarios through the production match crossfade. Current LBS isolates skinning changes; baseline LBS includes the original proportions, rig and skinning.',
   frozenWeightJacobian:'Central finite differences in XYZ with epsilon 0.1 mm for DQ, exact affine derivative for LBS. Skin weights are held fixed, so determinant 1 is not an anatomical tissue-volume measurement.',
   surfaceArea:'Actual deformed indexed triangles divided by their bind triangle areas; a two-dimensional surface Jacobian that includes spatially changing vertex weights.',
   sections:'Actual triangle-plane intersections near each bind joint, cut perpendicular to its transported average bone axis. The convex hull area measures the outer section silhouette and may bridge concavities; it is not enclosed tissue volume.',
   orientation:'A reversed triangle is measured against its locally transported bind normal. Adjacent foldback counts smooth bind-neighbor triangles whose deformed normals oppose each other; it is a surface diagnostic, not a full self-intersection test.',
   intersections:'Strict interior segment/triangle tests on nonadjacent joint-region triangles after an AABB rejection. Shared/coincident bind vertices, coplanar and boundary-only contact are excluded. Counts are a lower bound on transverse self-penetration, and include any already present in the bind-region reference.',
   limitations:'The material-split human surface is open. Whole human tissue volume, robust watertight collision checking, anatomical artist review, and actual device performance are not established by this report.'
  },hierarchyAttachmentGapMetres:{current:summary(frames.flatMap(f=>f.currentHierarchyAttachmentGaps.map(v=>v.gapMetres))),baseline:summary(frames.flatMap(f=>f.baselineHierarchyAttachmentGaps.map(v=>v.gapMetres)))},
  anatomicalLimitExcessRadians:summary(frames.flatMap(f=>f.currentAnatomicalAngles.map(v=>v.excessRadians))),aggregate,frames};
}
if(require.main===module){
 const args=process.argv.slice(2),outputIndex=args.indexOf('--output'),baselineIndex=args.indexOf('--baseline-ref');
 if(args.includes('--help')){process.stdout.write('Usage: node tools/check-character-deformation.cjs [--output FILE] [--baseline-ref REF]\n');process.exit(0);}
 for(let i=0;i<args.length;i++){
  if(!['--output','--baseline-ref'].includes(args[i])||!args[i+1]||args[i+1].startsWith('--'))throw Error('Unknown or incomplete argument: '+args[i]);
  i++;
 }
 const report=run({baselineRef:baselineIndex<0?BASELINE:args[baselineIndex+1]});
 const output=outputIndex<0?path.join(ROOT,'docs/validation/character-deformation.json'):path.resolve(args[outputIndex+1]);
 fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
 process.stdout.write(JSON.stringify({output,model:report.model,frames:report.frames.length,hierarchyAttachmentGapMetres:report.hierarchyAttachmentGapMetres,anatomicalLimitExcessRadians:report.anatomicalLimitExcessRadians,aggregate:report.aggregate},null,2)+'\n');
}
module.exports={run,unpack,regionsFor,analyze,hullArea,attachmentGaps,anatomicalAngles,segmentTriangleInterior,strictIntersectionStats};
