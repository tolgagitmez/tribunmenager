'use strict';
/* Appearance-only GPU skinning. Reads cached poses; never advances simulation. */
(function(root){
const Skinning=typeof module!=='undefined'&&module.exports?require('./player-skinning'):root.TribunPlayerSkinning;
const Rig=typeof module!=='undefined'&&module.exports?require('./humanoid-rig'):root.TribunHumanoidRig;
const Constraints=typeof module!=='undefined'&&module.exports?require('./character-palette-constraints'):root.TribunCharacterConstraints;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]),mul=(a,s)=>a.map(v=>v*s),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),len=a=>Math.hypot(...a),unit=a=>mul(a,1/(len(a)||1)),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],mix=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
const matmul=(a,b)=>{const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)out[c*4+r]=a[r]*b[c*4]+a[4+r]*b[c*4+1]+a[8+r]*b[c*4+2]+a[12+r]*b[c*4+3];return out;};
const decode=s=>{const b=atob(s),a=new Uint8Array(b.length);for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return a.buffer;};
const VS=`precision highp float;
attribute vec3 aPosition;attribute vec3 aNormal;attribute vec2 aUV;attribute vec4 aJoints;attribute vec4 aWeights;attribute float aMaterial;attribute vec3 aColor;
uniform mat4 uVP;uniform vec4 uBoneReal[19];uniform vec4 uBoneDual[19];uniform vec3 uVariant;uniform float uGoalie;uniform float uStandardAsset;
varying vec3 vWorld;varying vec3 vNormal;varying vec3 vBind;varying vec3 vColor;varying vec2 vUV;varying float vMaterial;varying float vHand;
vec3 rotateUnit(vec4 q,vec3 p){return p+2.*cross(q.xyz,cross(q.xyz,p)+q.w*p);}
void main(){vec3 p=aPosition;float head=smoothstep(1.59,1.68,p.y);if(uStandardAsset<.5){p.z*=mix(1.,uVariant.x,head);p.x+=head*max(0.,p.x-.035)*uVariant.y;}
vec4 hands=1.-step(vec4(.1),min(abs(aJoints-vec4(8.)),abs(aJoints-vec4(15.))));vHand=dot(aWeights,hands);if(aMaterial<.5&&uStandardAsset<.5){p.z+=sign(p.z)*.005*uGoalie*vHand;p.x+=.003*uGoalie*vHand;}
vec4 r0=uBoneReal[int(aJoints.x)],r1=uBoneReal[int(aJoints.y)],r2=uBoneReal[int(aJoints.z)],r3=uBoneReal[int(aJoints.w)];
vec4 reference=r0;float largest=aWeights.x;
if(aWeights.y>largest){reference=r1;largest=aWeights.y;}if(aWeights.z>largest){reference=r2;largest=aWeights.z;}if(aWeights.w>largest)reference=r3;
vec4 weights=aWeights*vec4(dot(reference,r0)<0.?-1.:1.,dot(reference,r1)<0.?-1.:1.,dot(reference,r2)<0.?-1.:1.,dot(reference,r3)<0.?-1.:1.);
vec4 r=r0*weights.x+r1*weights.y+r2*weights.z+r3*weights.w;
vec4 d=uBoneDual[int(aJoints.x)]*weights.x+uBoneDual[int(aJoints.y)]*weights.y+uBoneDual[int(aJoints.z)]*weights.z+uBoneDual[int(aJoints.w)]*weights.w;
float magnitude=max(length(r),.000001);r/=magnitude;d/=magnitude;d-=r*dot(r,d);
vec3 translation=2.*(r.w*d.xyz-d.w*r.xyz+cross(r.xyz,d.xyz));
vec4 w=vec4(rotateUnit(r,p)+translation,1.);vWorld=w.xyz;vNormal=normalize(rotateUnit(r,aNormal));vBind=p;vUV=aUV;vMaterial=aMaterial;vColor=aColor;gl_Position=uVP*w;}`;
const FS=`precision highp float;
varying vec3 vWorld;varying vec3 vNormal;varying vec3 vBind;varying vec3 vColor;varying vec2 vUV;varying float vMaterial;varying float vHand;
uniform sampler2D uSkinTexture;uniform sampler2D uFabricTexture;
uniform float uStandardAsset;
#ifdef STANDARD_ASSET
uniform vec3 uMaterialBase[10];uniform float uMaterialRoughness[10];
#endif
uniform vec3 uEye;uniform vec3 uSkin;uniform vec3 uShirt;uniform vec3 uShorts;uniform vec3 uHair;uniform vec3 uBoots;uniform vec3 uIris;uniform float uNumber;uniform float uBeard;uniform float uStudio;uniform float uGoalie;uniform float uFast;
const float PI=3.14159265359;
float hash(vec3 p){return fract(sin(dot(p,vec3(12.9898,78.233,37.719)))*43758.5453);}
float rect(vec2 p,vec2 c,vec2 r){vec2 d=abs(p-c)-r;return 1.-smoothstep(0.,.025,max(d.x,d.y));}
float digit(float n,vec2 p){float a=0.,b=0.,c=0.,d=0.,e=0.,f=0.,g=0.;if(n<.5){a=1.;b=1.;c=1.;d=1.;e=1.;f=1.;}else if(n<1.5){b=1.;c=1.;}else if(n<2.5){a=1.;b=1.;g=1.;e=1.;d=1.;}else if(n<3.5){a=1.;b=1.;c=1.;d=1.;g=1.;}else if(n<4.5){b=1.;c=1.;f=1.;g=1.;}else if(n<5.5){a=1.;f=1.;g=1.;c=1.;d=1.;}else if(n<6.5){a=1.;f=1.;g=1.;e=1.;c=1.;d=1.;}else if(n<7.5){a=1.;b=1.;c=1.;}else if(n<8.5){a=1.;b=1.;c=1.;d=1.;e=1.;f=1.;g=1.;}else{a=1.;b=1.;c=1.;d=1.;f=1.;g=1.;}
return min(1.,a*rect(p,vec2(0.,.82),vec2(.34,.055))+g*rect(p,vec2(0.,0.),vec2(.34,.055))+d*rect(p,vec2(0.,-.82),vec2(.34,.055))+b*rect(p,vec2(.34,.41),vec2(.055,.40))+c*rect(p,vec2(.34,-.41),vec2(.055,.40))+f*rect(p,vec2(-.34,.41),vec2(.055,.40))+e*rect(p,vec2(-.34,-.41),vec2(.055,.40)));}
float ggx(float nh,float rough){float a=rough*rough,a2=a*a,d=nh*nh*(a2-1.)+1.;return a2/max(.0001,PI*d*d);}
float smith(float nv,float rough){float k=rough+1.;k=k*k/8.;return nv/(nv*(1.-k)+k);}
vec3 lightPBR(vec3 N,vec3 V,vec3 L,vec3 radiance,vec3 base,float rough,float wrap,float f0){vec3 H=normalize(V+L);float nl=max(0.,dot(N,L)),nv=max(.001,dot(N,V)),nh=max(0.,dot(N,H)),vh=max(0.,dot(V,H));vec3 F=vec3(f0)+(1.-f0)*pow(1.-vh,5.);vec3 spec=ggx(nh,rough)*smith(nv,rough)*smith(max(.001,nl),rough)*F/max(.004,4.*nv*max(.001,nl));return ((1.-F)*base/PI*max(0.,(nl+wrap)/(1.+wrap))+spec*nl)*radiance;}
vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
#ifdef STANDARD_ASSET
vec4 standardMaterial(float id){
 if(id<.5)return vec4(uMaterialBase[0],uMaterialRoughness[0]);if(id<1.5)return vec4(uMaterialBase[1],uMaterialRoughness[1]);
 if(id<2.5)return vec4(uMaterialBase[2],uMaterialRoughness[2]);if(id<3.5)return vec4(uMaterialBase[3],uMaterialRoughness[3]);
 if(id<4.5)return vec4(uMaterialBase[4],uMaterialRoughness[4]);if(id<5.5)return vec4(uMaterialBase[5],uMaterialRoughness[5]);
 if(id<6.5)return vec4(uMaterialBase[6],uMaterialRoughness[6]);if(id<7.5)return vec4(uMaterialBase[7],uMaterialRoughness[7]);
 if(id<8.5)return vec4(uMaterialBase[8],uMaterialRoughness[8]);return vec4(uMaterialBase[9],uMaterialRoughness[9]);
}
#endif
void main(){float id=floor(vMaterial+.5),rough=.72,wrap=0.,f0=.035;vec3 base=vec3(.5),N=normalize(vNormal),V=normalize(uEye-vWorld),p=vBind;
#ifdef STANDARD_ASSET
 if(uStandardAsset>.5){
  vec4 material=standardMaterial(id);base=material.rgb*vColor;rough=material.a;
  vec3 texel=id<.5?texture2D(uSkinTexture,vUV).rgb:texture2D(uFabricTexture,vUV).rgb;
  vec3 linearTexel=mix(texel/12.92,pow((texel+.055)/1.055,vec3(2.4)),step(vec3(.04045),texel));base*=linearTexel;
  vec3 color=base*vec3(.72,.81,1.)*(.12+.22*(N.y*.5+.5));
  color+=lightPBR(N,V,normalize(vec3(3.5,5.,4.)),vec3(3.2,3.05,2.85),base,rough,0.,.04);
  color+=lightPBR(N,V,normalize(vec3(-4.,2.,2.)),vec3(.65,.82,1.10),base,rough,0.,.04);
  color+=lightPBR(N,V,normalize(vec3(-2.,3.,-4.)),vec3(.70,.82,1.05),base,rough,0.,.04);
  gl_FragColor=vec4(pow(aces(color),vec3(1./2.2)),1.);return;
 }
#endif
 // Match broadcast mode skips three expensive GGX/Smith lights, hash and procedural digits.
 // Full licensed material remains available for studio/portrait and explicit detailed mode.
 if(uFast>.5){
  vec3 diffuse=id<.5?uSkin:id<1.5?uShirt:id<2.5?uShorts:id<3.5?uShirt*.82:id<4.5?uBoots:id<5.5?uHair:id<6.5?vec3(.7):id<7.5?uIris:vec3(.06);
  if(id<.5)diffuse*=texture2D(uSkinTexture,vUV*4.).rgb;
  else if(id<3.5)diffuse*=texture2D(uFabricTexture,vUV*8.).rgb;
  diffuse*=vColor;
  float lit=max(0.,dot(N,normalize(vec3(.35,.85,.45))));
  float fill=max(0.,dot(N,normalize(vec3(-.7,.35,-.2))));
  vec3 color=diffuse*(.36+.68*lit+.16*fill);
  gl_FragColor=vec4(pow(clamp(color,0.,1.),vec3(.454545)),1.);
  return;
 }
if(id<.5){base=pow(uSkin,vec3(2.2))*vColor;rough=.60;wrap=.10;f0=.025;
 base*=texture2D(uSkinTexture,vUV*4.).rgb;
 float beard=(1.-smoothstep(1.68,1.735,p.y))*smoothstep(1.625,1.65,p.y)*smoothstep(.10,.135,p.x);float stubble=hash(floor(p*1700.));base=mix(base,pow(uHair,vec3(2.2))*.8,beard*uBeard*(.14+.14*stubble));
 float pore=hash(floor(p*1400.))-.5;base*=1.+pore*.035;rough+=pore*.045;
}else if(id<1.5){base=pow(uShirt,vec3(2.2));rough=.84;base*=.97+.025*sin(p.z*180.);
 base*=texture2D(uFabricTexture,vUV*10.).rgb;
 if(p.x>.075&&p.y>1.15&&p.y<1.52){float piping=smoothstep(.155,.158,abs(p.z))*(1.-smoothstep(.163,.167,abs(p.z)));base=mix(base,vec3(.78),piping*.85);
 vec2 q=vec2((p.z+.085)/.021,(p.y-1.41)/.028);float crest=step(abs(q.x)+abs(q.y)*.6,.95);base=mix(base,vec3(.72,.58,.24),crest*.9);}
 if(p.x<-.065&&p.y>1.17&&p.y<1.45&&abs(p.z)<.115){float num=0.;vec2 q=vec2(-p.z/.085,(p.y-1.31)/.12);if(uNumber<9.5)num=digit(uNumber,q);else{q.x*=1.7;num=max(digit(floor(uNumber/10.),q+vec2(.47,0.)),digit(mod(uNumber,10.),q-vec2(.47,0.)));}base=mix(base,vec3(.85),num);}
 base*=1.+sin(p.y*1800.)*sin(p.z*1800.)*.018;
}else if(id<2.5){base=pow(uShorts,vec3(2.2))*texture2D(uFabricTexture,vUV*10.).rgb;rough=.86;float seam=smoothstep(.135,.139,abs(p.z))*(1.-smoothstep(.145,.148,abs(p.z)));base=mix(base,pow(uShirt,vec3(2.2)),seam*.7);
}else if(id<3.5){base=pow(uShirt,vec3(2.2))*.88;rough=.86;if(p.y>.390)base=vec3(.8);base*=.96+.04*sin(p.y*1900.);
}else if(id<4.5){base=pow(uBoots,vec3(2.2));rough=.42;
}else if(id<5.5){base=pow(uHair,vec3(2.2));rough=.85;f0=.018;float strand=.91+.09*sin(p.z*2100.+sin(p.x*115.)*2.);base*=strand;
}else if(id<6.5){base=vec3(.65,.68,.63);rough=.23;wrap=.05;
}else if(id<7.5){base=pow(uIris,vec3(2.2));rough=.18;
}else if(id<8.5){base=vec3(.001,.002,.003);rough=.09;
}else if(id<9.5){base=vec3(.05,.06,.07);rough=.47;
}else{base=vec3(.85);rough=.73;}
if(id<.5&&uGoalie>.5&&vHand>.65){base=mix(vec3(.82,.84,.78),pow(uShirt,vec3(2.2))*.5,smoothstep(.65,.85,vHand)*step(.1,sin(p.y*240.))*.18);rough=.56;wrap=0.;}
float hemi=.12+.22*(N.y*.5+.5);vec3 color=base*vec3(.72,.81,1.0)*hemi;
color+=lightPBR(N,V,normalize(vec3(3.5,5.,4.)),vec3(3.2,3.05,2.85),base,rough,wrap,f0);
color+=lightPBR(N,V,normalize(vec3(-4.,2.,2.)),vec3(.65,.82,1.10),base,rough,wrap,f0);
color+=lightPBR(N,V,normalize(vec3(-2.,3.,-4.)),vec3(.70,.82,1.05),base,rough,wrap,f0);
color+=base*.08*pow(1.-max(0.,dot(N,V)),3.)*(id>.5&&id<3.5?1.:.3);
color=aces(color*(uStudio>.5?1.03:.95));gl_FragColor=vec4(pow(color,vec3(1./2.2)),1.);}`;
function quatAlign(a,b,v){const c=cross(a,b),d=clamp(dot(a,b),-1,1);if(d<-.9999){let axis=unit(cross(a,Math.abs(a[0])<.8?[1,0,0]:[0,1,0]));return sub(mul(axis,2*dot(axis,v)),v);}return add(add(v,cross(c,v)),mul(cross(c,cross(c,v)),1/(1+d)));}
function presentationPalette(p,assets){const a=new Float32Array(assets.bones.length*16),c=Math.cos(p.face||0),s=Math.sin(p.face||0),M=[c,0,s,0,0,1,0,0,-s,0,c,0,p.x,0,p.z,1];for(let i=0;i<assets.bones.length;i++)a.set(M,i*16);return a;}
function renderPalette(raw,mixed,assets){return mixed===raw?raw:Constraints.constrain(mixed,assets.bones,Rig.LIMITS);}
function palette(p,assets,pose){
 const f=[Math.cos(p.face||0),0,Math.sin(p.face||0)],side=[-f[2],0,f[0]],yaw=v=>[v[0]*f[0]+v[2]*side[0],v[1],v[0]*f[2]+v[2]*side[2]],frames=Rig.boneFrames(pose);
 const all=new Float32Array(assets.bones.length*16),headYaw=Number.isFinite(pose.headYaw)?clamp(pose.headYaw,-.8,.8):0;
 assets.bones.forEach((bone,i)=>{const scan=bone.name==='head'?headYaw:bone.name==='neck'?headYaw*.25:0,cs=Math.cos(scan),sn=Math.sin(scan),boneYaw=v=>{const u=yaw(v);return scan?[u[0]*cs-u[2]*sn,u[1],u[0]*sn+u[2]*cs]:u;};const [a,b]=frames[bone.name],rest=unit(sub(bone.tail,bone.head)),start=boneYaw(rest),target=unit(sub(b,a)),M=new Float32Array(16);
  for(let col=0;col<3;col++){const v=quatAlign(start,target,boneYaw(bone.matrix.slice(col*4,col*4+3)));for(let j=0;j<3;j++)M[col*4+j]=v[j];}M[12]=a[0];M[13]=a[1];M[14]=a[2];M[15]=1;all.set(matmul(M,bone.inverseBind),i*16);
 });return all;
}
// Runtime mesh LOD for the licensed, single-LOD MakeHuman asset.
// It never rewrites the verified source / manifest / original full-resolution GLB.
// Cluster only vertices with identical skin joint sets and material/normal sides.
function simplifyLOD(sourceVertices,sourceIndices,cell){
 const stride=20,lookup=new Map(),counts=[],merged=[],remap=new Uint16Array(sourceVertices.length/stride);
 const round=(x,step)=>Math.round(x/step);
 for(let i=0;i<remap.length;i++){
  const p=i*stride,v=sourceVertices;
  const key=[
   round(v[p],cell),round(v[p+1],cell),round(v[p+2],cell),
   Math.round(v[p+16]),Math.sign(v[p+3]),Math.sign(v[p+4]),Math.sign(v[p+5]),
   v[p+8],v[p+9],v[p+10],v[p+11]
  ].join(',');
  let item=lookup.get(key);
  if(item===undefined){
   item=counts.length;lookup.set(key,item);counts.push(0);
   for(let k=0;k<stride;k++)merged.push(0);
  }
  remap[i]=item;counts[item]++;
  for(let k=0;k<stride;k++){
   // Joint indices and material IDs cannot be averaged as they are discrete.
   if((k>=8&&k<12)||k===16){merged[item*stride+k]=v[p+k];}
   else merged[item*stride+k]+=v[p+k];
  }
 }
 const vertices=new Float32Array(merged.length);
 for(let i=0;i<counts.length;i++){
  const off=i*stride,n=counts[i],nv=vertices;
  for(let j=0;j<stride;j++)nv[off+j]=((j>=8&&j<12)||j===16)?merged[off+j]:merged[off+j]/n;
  const length=Math.hypot(nv[off+3],nv[off+4],nv[off+5])||1;
  for(let j=3;j<=5;j++)nv[off+j]/=length;
  const sum=nv[off+12]+nv[off+13]+nv[off+14]+nv[off+15];
  if(sum>0)for(let j=12;j<=15;j++)nv[off+j]/=sum;
 }
 const indices=[],seen=new Set();
 for(let i=0;i<sourceIndices.length;i+=3){
  let a=remap[sourceIndices[i]],b=remap[sourceIndices[i+1]],c=remap[sourceIndices[i+2]];
  if(a===b||a===c||b===c)continue;
  const o=a*stride,p=b*stride,q=c*stride;
  const ux=vertices[p]-vertices[o],uy=vertices[p+1]-vertices[o+1],uz=vertices[p+2]-vertices[o+2];
  const vx=vertices[q]-vertices[o],vy=vertices[q+1]-vertices[o+1],vz=vertices[q+2]-vertices[o+2];
  const nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx;
  if(nx*nx+ny*ny+nz*nz<1e-13)continue;
  const key=[a,b,c].sort((x,y)=>x-y).join(':');
  if(seen.has(key))continue;seen.add(key);
  // Prevent inverted triangles caused by local vertex clustering.
  if(nx*(vertices[o+3]+vertices[p+3]+vertices[q+3])+
     ny*(vertices[o+4]+vertices[p+4]+vertices[q+4])+
     nz*(vertices[o+5]+vertices[p+5]+vertices[q+5])<0){const t=b;b=c;c=t;}
  indices.push(a,b,c);
 }
 return {vertices,indices:new Uint16Array(indices),indexType:'H',vertexCount:vertices.length/stride,indexCount:indices.length,cell};
}
// Conservative world-space sphere covers standing, diving and extended limbs.
// Invalid matrices fail open; never clip a player merely at the screen edge.
function playerInView(p,vp,radius=3){
 if(!vp||vp.length!==16||!Number.isFinite(p?.x)||!Number.isFinite(p?.z))return true;
 for(const v of vp)if(!Number.isFinite(v))return true;
 const x=p.x,y=1,z=p.z;
 for(let row=0;row<3;row++)for(const sign of [-1,1]){
  const a=vp[3]+sign*vp[row],b=vp[7]+sign*vp[4+row],c=vp[11]+sign*vp[8+row],d=vp[15]+sign*vp[12+row],n=Math.hypot(a,b,c);
  if(n>1e-9&&a*x+b*y+c*z+d< -radius*n)return false;
 }
 return true;
}
class PlayerRenderer{
 constructor(gl,assets=root.TribunPlayerAssets,options={}){
  if(!assets)throw Error('Oyuncu modeli yüklenmedi');
  if(!Skinning)throw Error('Oyuncu deri çizim modülü yüklenemedi: player-skinning.js');
  if(!Constraints)throw Error('Oyuncu eklem sınırı modülü yüklenemedi: character-palette-constraints.js');
  this.validation=root.TribunPlayerAssetStatus?.validate(assets);if(this.validation&&!this.validation.ok){const error=Error(this.validation.errors.map(e=>e.code+' '+e.path+': '+e.message).join('; '));error.validation=this.validation;throw error;}
  this.gl=gl;this.assets=assets;this.options=options;this.studio=false;this.visualQuality='auto';this.lastRenderStats={players:0,fast:0,detailed:0,triangles:0,paletteBuilds:0,paletteHits:0,dualBuilds:0,dualHits:0,lodBinds:0};this.poseCache=new WeakMap();
  const shader=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
  const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,VS));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,options.standardMaterials?'#define STANDARD_ASSET\n'+FS:FS));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));this.program=program;
  this.loc={};for(const n of ['uVP','uBoneReal[0]','uBoneDual[0]','uEye','uSkin','uShirt','uShorts','uHair','uBoots','uIris','uVariant','uNumber','uBeard','uStudio','uGoalie','uFast','uSkinTexture','uFabricTexture','uStandardAsset','uMaterialBase[0]','uMaterialRoughness[0]'])this.loc[n]=gl.getUniformLocation(program,n);
  this.attributes=[['aPosition',3,0],['aNormal',3,3],['aUV',2,6],['aJoints',4,8],['aWeights',4,12],['aMaterial',1,16],['aColor',3,17]].map(([n,size,off])=>({location:gl.getAttribLocation(program,n),size,off}));
  const uint32=assets.lods.some(a=>a.indexType==='I')?gl.getExtension('OES_element_index_uint'):true;
  const original=assets.lods.map(a=>({vertices:new Float32Array(decode(a.vertices)),
   indices:a.indexType==='H'?new Uint16Array(decode(a.indices)):new Uint32Array(decode(a.indices)),
   indexType:a.indexType}));
  // MakeHuman package intentionally keeps one checked, full-resolution LOD.
  // Derive lower-detail mesh buffers *in memory*, without invalidating its SHA.
  const levels=original.length===1&&original[0].indexType==='H'?
   [original[0],simplifyLOD(original[0].vertices,original[0].indices,.075),
    simplifyLOD(original[0].vertices,original[0].indices,.155)]:original;
  this.lods=levels.map(a=>{if(a.indexType==='I'&&!uint32)return null;
   const vertex=gl.createBuffer(),index=gl.createBuffer();
   gl.bindBuffer(gl.ARRAY_BUFFER,vertex);gl.bufferData(gl.ARRAY_BUFFER,a.vertices,gl.STATIC_DRAW);
   gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,index);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,a.indices,gl.STATIC_DRAW);
   return {vertex,index,count:a.indices.length,vertices:a.vertices.length/20,type:a.indexType==='H'?gl.UNSIGNED_SHORT:gl.UNSIGNED_INT};
  });
  if(!this.lods.some(Boolean))throw Error('Bu tarayıcı modelin üçgen indis türünü desteklemiyor.');
  this.textures={};this.textureState={state:'loading',loaded:[],error:null};
  for(const name of ['skin','fabric'])if(typeof assets.textures?.[name]!=='string'||!assets.textures[name])throw Error('Doku dosyası kaydı eksik: '+name);
  const upload=(name,unit,texture,img)=>{
   const width=img.naturalWidth||img.width,height=img.naturalHeight||img.height,file=assets.textures[name];
   if(!width||!height)throw Error('Doku görüntüsü boş: '+file);if(Math.max(width,height)>gl.getParameter(gl.MAX_TEXTURE_SIZE))throw Error('Doku boyutu grafik sınırını aşıyor: '+file);
   gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,options.textureFlipY??true);
   if(img.data)gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,width,height,0,gl.RGBA,gl.UNSIGNED_BYTE,img.data);
   else gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);
   const pot=n=>(n&(n-1))===0,isPOT=pot(width)&&pot(height),settings=options.textureSettings?.[name],wrap={1000:gl.REPEAT,1001:gl.CLAMP_TO_EDGE,1002:gl.MIRRORED_REPEAT},filter={1003:gl.NEAREST,1004:gl.NEAREST_MIPMAP_NEAREST,1005:gl.NEAREST_MIPMAP_LINEAR,1006:gl.LINEAR,1007:gl.LINEAR_MIPMAP_NEAREST,1008:gl.LINEAR_MIPMAP_LINEAR};
   if(settings){
    if(!(settings.wrapS in wrap)||!(settings.wrapT in wrap)||!(settings.minFilter in filter)||![1003,1006].includes(settings.magFilter))throw Error('Desteklenmeyen doku örnekleyicisi: '+file);
    const mip=![1003,1006].includes(settings.minFilter);if(!isPOT&&(mip||settings.wrapS!==1001||settings.wrapT!==1001))throw Error('Bu doku örnekleyicisi WebGL1 boyut sınırına uymuyor: '+file);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,wrap[settings.wrapS]);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,wrap[settings.wrapT]);if(mip)gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,filter[settings.minFilter]);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,filter[settings.magFilter]);
   }else{if(isPOT){gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.REPEAT);gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);}else{gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);}gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);}
   this.textureState.loaded.push(file);
  };
  const jobs=['skin','fabric'].map((name,unit)=>{
   const file=assets.textures?.[name];if(typeof file!=='string'||!file)throw Error('Doku dosyası kaydı eksik: '+name);
   const texture=gl.createTexture();this.textures[name]=texture;gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([255,255,255,255]));gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
   if(options.textureImages?.[name]){try{upload(name,unit,texture,options.textureImages[name]);return Promise.resolve();}catch(error){return Promise.reject(error);}}
   return new Promise((resolve,reject)=>{const img=new root.Image();let settled=false;
    const finish=error=>{if(settled)return;settled=true;root.clearTimeout(timer);if(error)reject(error);else resolve();};
    const timer=root.setTimeout(()=>finish(Error('Doku yükleme zaman aşımı: '+file)),12000);
    img.onload=()=>{try{upload(name,unit,texture,img);finish();}catch(error){finish(error);}};img.onerror=()=>finish(Error('Doku dosyası açılamadı: '+file));img.src=file;
   });
  });
  this.ready=Promise.all(jobs).then(()=>{this.textureState.state='ready';return this;}).catch(error=>{this.textureState.state='error';this.textureState.error=error.message;throw error;});
 }
 draw(players,vp,eye,camera='tv',dt=1/60,matchBridge=null,frameOptions={}){
  const gl=this.gl;gl.useProgram(this.program);gl.uniformMatrix4fv(this.loc.uVP,false,vp instanceof Float32Array?vp:new Float32Array(vp));gl.uniform3fv(this.loc.uEye,eye);gl.uniform1f(this.loc.uStudio,this.studio?1:0);
  const standard=this.options.standardMaterials;gl.uniform1f(this.loc.uStandardAsset,standard?1:0);if(standard){gl.uniform3fv(this.loc['uMaterialBase[0]'],standard.baseColors);gl.uniform1fv(this.loc['uMaterialRoughness[0]'],standard.roughness);}
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.textures.skin);gl.uniform1i(this.loc.uSkinTexture,0);gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,this.textures.fabric);gl.uniform1i(this.loc.uFabricTexture,1);
  const renderStats={players:0,fast:0,detailed:0,triangles:0,paletteBuilds:0,paletteHits:0,dualBuilds:0,dualHits:0,lodBinds:0,culled:0,active:0};let boundLOD=null,boundFast=null;
  const full=this.visualQuality==='detailed'||this.studio||camera==='portrait',close=camera==='close',auto=this.visualQuality==='auto';
  for(const p of players){if(!p.active)continue;const dx=close?p.x-eye[0]:0,dz=close?p.z-eye[2]:0,d2=close?dx*dx+dz*dz:Infinity,lod=this.lods[full?0:close&&d2<484?1:2]||this.lods[1]||this.lods[2]||this.lods[0],v=p.visual||{},n=p.index||0,role=v.role||p.role,isGK=role==='GK',ref=p.referee;
   const detailed=this.visualQuality==='detailed'||(auto&&(this.studio||camera==='portrait'||(close&&d2<324)));
   const fast=detailed?0:1;
   renderStats.active++;
   const hidden=frameOptions.cull===true&&!this.studio&&!p.selected&&!p.referee&&!playerInView(p,vp);
   if(hidden){renderStats.culled++;if(!matchBridge&&!frameOptions.paletteForPlayer)continue;}
   // Keep the bridge and pilot sampled while offscreen, but skip all GL work.
   if(!hidden){if(boundFast!==fast){gl.uniform1f(this.loc.uFast,fast);boundFast=fast;}
   renderStats.players++;renderStats[detailed?'detailed':'fast']++;renderStats.triangles+=lod.count/3;
   const shirt=v.shirt||(ref?[.94,.76,.16]:isGK?(p.team===0?[.42,.23,.67]:[.91,.59,.12]):p.team===0?[.075,.29,.68]:[.65,.075,.13]),shorts=v.shorts||(ref?[.10,.12,.14]:p.team===0?[.88,.90,.93]:[.09,.12,.16]);
   const set=(name,value)=>gl.uniform3fv(this.loc[name],value);set('uSkin',v.skin||p.skin||[.69,.48,.34]);set('uShirt',shirt);set('uShorts',shorts);set('uHair',v.hair||p.hair||[.10,.065,.043]);set('uBoots',v.boots||[[.055,.065,.08],[.91,.42,.09],[.07,.56,.45]][n%3]);set('uIris',v.iris||[[.15,.25,.18],[.30,.18,.09],[.13,.28,.36]][n%3]);set('uVariant',v.variant||[.94+(n%4)*.035,(n%3-1)*.06,0]);
   gl.uniform1f(this.loc.uGoalie,isGK?1:0);gl.uniform1f(this.loc.uNumber,p.num||n+1);gl.uniform1f(this.loc.uBeard,v.beard??(n%4===2?.85:0));}let connected;
   if(frameOptions.paletteForPlayer)connected=frameOptions.paletteForPlayer(p);
   let dual;
   if(!connected){
    // A Rig.update returns a new immutable pose; getPose is a read-only query.
    // Reuse exact pose matrices on repeated/paused draws, without ever
    // reusing a mutable transition palette or a custom pilot's result.
    const pose=Rig.getPose(p);
    let entry=!v.presentation?this.poseCache.get(p):null;
    if(!entry||entry.pose!==pose||entry.face!==p.face||entry.assets!==this.assets){
     entry={pose,face:p.face,assets:this.assets,raw:v.presentation?presentationPalette(p,this.assets):palette(p,this.assets,pose),dual:null};
     if(!v.presentation)this.poseCache.set(p,entry);
     renderStats.paletteBuilds++;
    }else renderStats.paletteHits++;
    const rawPalette=entry.raw,skinPalette=matchBridge?matchBridge.sample(p,rawPalette,dt,pose.action):rawPalette;
    connected=renderPalette(rawPalette,skinPalette,this.assets);
    if(!hidden&&connected===rawPalette){
     if(entry.dual){dual=entry.dual;renderStats.dualHits++;}
     else{dual=entry.dual=Skinning.fromMatrices(connected);renderStats.dualBuilds++;}
    }
   }
   if(hidden)continue;
   if(!dual){dual=Skinning.fromMatrices(connected);renderStats.dualBuilds++;}
   gl.uniform4fv(this.loc['uBoneReal[0]'],dual.real);gl.uniform4fv(this.loc['uBoneDual[0]'],dual.dual);
   // Preserve draw order and all individual uniforms. Bind vertex attributes
   // only when LOD actually changes, rather than 23 times per broadcast frame.
   if(boundLOD!==lod){
    gl.bindBuffer(gl.ARRAY_BUFFER,lod.vertex);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,lod.index);
    for(const a of this.attributes){if(a.location<0)continue;gl.enableVertexAttribArray(a.location);gl.vertexAttribPointer(a.location,a.size,gl.FLOAT,false,80,a.off*4);}
    boundLOD=lod;renderStats.lodBinds++;
   }
   gl.drawElements(gl.TRIANGLES,lod.count,lod.type,0);
  }
  if(boundLOD)for(const a of this.attributes)if(a.location>=0)gl.disableVertexAttribArray(a.location);
  this.lastRenderStats=renderStats;
 }
 dispose(){if(this.disposed)return;this.disposed=true;this.poseCache=new WeakMap();const gl=this.gl;for(const lod of this.lods||[])if(lod){gl.deleteBuffer(lod.vertex);gl.deleteBuffer(lod.index);}for(const texture of Object.values(this.textures||{}))gl.deleteTexture(texture);if(this.program){for(const shader of gl.getAttachedShaders(this.program)||[])gl.deleteShader(shader);gl.deleteProgram(this.program);}}
}
PlayerRenderer.playerInView=playerInView;PlayerRenderer.renderPalette=renderPalette;PlayerRenderer.skinning=Skinning;PlayerRenderer.simplifyLOD=simplifyLOD;PlayerRenderer.presentationPalette=presentationPalette;PlayerRenderer.vertexShader=VS;PlayerRenderer.fragmentShader=FS;PlayerRenderer.palette=palette;PlayerRenderer.decode=decode;root.TribunPlayerRenderer=PlayerRenderer;if(typeof module!=='undefined'&&module.exports)module.exports=PlayerRenderer;
})(typeof window!=='undefined'?window:globalThis);
