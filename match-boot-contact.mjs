// Diagnostic geometry from the canonical licensed LOD0 boot mesh.
// The submitted palette is used with the same rigid DQ blend as WebGL.
const STRIDE=20;
const BOOT_MATERIAL=4;

function readBoots(assets,decode){
 const lod=assets.lods[0];
 const vertices=new Float32Array(decode(lod.vertices));
 const Indices=lod.indexType==='H'?Uint16Array:Uint32Array;
 const indices=new Indices(decode(lod.indices));
 const footJoints=['foot.L','foot.R'].map(name=>assets.bones.findIndex(bone=>bone.name===name));
 if(footJoints.some(joint=>joint<0))throw Error('Licensed boot joints are missing.');

 const boots=footJoints.map(()=>({vertices:[],triangles:[],lookup:new Map()}));
 const side=new Int8Array(vertices.length/STRIDE).fill(-1);
 for(let vertex=0;vertex<side.length;vertex++){
  const first=vertex*STRIDE;
  if(Math.round(vertices[first+16])!==BOOT_MATERIAL)continue;
  const joints=vertices.subarray(first+8,first+12);
  const weights=vertices.subarray(first+12,first+16);
  const hasLeft=joints.some((joint,i)=>joint===footJoints[0]&&weights[i]>0);
  const hasRight=joints.some((joint,i)=>joint===footJoints[1]&&weights[i]>0);
  if(hasLeft!==hasRight)side[vertex]=hasLeft?0:1;
 }

 for(let i=0;i<indices.length;i+=3){
  const a=indices[i],b=indices[i+1],c=indices[i+2];
  const boot=boots[side[a]];
  if(!boot||side[a]!==side[b]||side[a]!==side[c])continue;
  const triangle=[a,b,c].map(vertex=>{
   if(!boot.lookup.has(vertex)){
    const first=vertex*STRIDE;
    boot.lookup.set(vertex,boot.vertices.length);
    boot.vertices.push({
     point:Array.from(vertices.subarray(first,first+3)),
     joints:Array.from(vertices.subarray(first+8,first+12)),
     weights:Array.from(vertices.subarray(first+12,first+16))
    });
   }
   return boot.lookup.get(vertex);
  });
  boot.triangles.push(triangle);
 }
 if(boots.some(boot=>!boot.triangles.length))throw Error('Licensed boot geometry is missing.');
 return boots.map(({vertices,triangles})=>({vertices,triangles}));
}

export function createBootContactMeter({assets,decode,Skinning,THREE}){
 let boots;
 return {
  // Signed clearance from the boot to the ball: positive is a gap, negative
  // is overlap. LOD0 is a stable reference even when the broadcast uses a
  // simplified runtime mesh.
  measure({palette,foot,ball,radius=.11}){
   if((foot!==0&&foot!==1)||!ball||![ball.x,ball.y,ball.z,radius].every(Number.isFinite)||radius<=0){
    throw new TypeError('Boot side and physical ball position are required.');
   }
   boots??=readBoots(assets,decode);
   const {vertices,triangles}=boots[foot];
   const dual=Skinning.fromMatrices(palette);
   const points=vertices.map(({joints,weights,point})=>
    new THREE.Vector3().fromArray(Skinning.deform(dual,joints,weights,point)));
   const centre=new THREE.Vector3(ball.x,ball.y,ball.z);
   const nearest=new THREE.Vector3();
   const closestPoint=new THREE.Vector3();
   const triangle=new THREE.Triangle();
   let minSquared=Infinity;
   for(const [a,b,c] of triangles){
    triangle.set(points[a],points[b],points[c]);
    triangle.closestPointToPoint(centre,nearest);
    const squared=nearest.distanceToSquared(centre);
    if(squared>=minSquared)continue;
    minSquared=squared;
    closestPoint.copy(nearest);
   }
   const {x,y,z}=closestPoint;
   return {gapMetres:Math.sqrt(minSquared)-radius,closestPoint:{x,y,z},triangleCount:triangles.length,lod:0};
  }
 };
}
