'use strict';
/* Appearance-only GPU skinning. Reads cached poses; never advances simulation. */
(function(root){
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]),mul=(a,s)=>a.map(v=>v*s),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),len=a=>Math.hypot(...a),unit=a=>mul(a,1/(len(a)||1)),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],mix=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
const matmul=(a,b)=>{const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)out[c*4+r]=a[r]*b[c*4]+a[4+r]*b[c*4+1]+a[8+r]*b[c*4+2]+a[12+r]*b[c*4+3];return out;};
const decode=s=>{const b=atob(s),a=new Uint8Array(b.length);for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return a.buffer;};
const VS=`precision highp float;
attribute vec3 aPosition;attribute vec3 aNormal;attribute vec2 aUV;attribute vec4 aJoints;attribute vec4 aWeights;attribute float aMaterial;attribute vec3 aColor;
uniform mat4 uVP;uniform mat4 uBones[19];uniform vec3 uVariant;uniform float uGoalie;
varying vec3 vWorld;varying vec3 vNormal;varying vec3 vBind;varying vec3 vColor;varying float vMaterial;varying float vHand;
void main(){vec3 p=aPosition;float head=smoothstep(1.59,1.68,p.y);p.z*=mix(1.,uVariant.x,head);p.x+=head*max(0.,p.x-.035)*uVariant.y;
vec4 hands=1.-step(vec4(.1),min(abs(aJoints-vec4(8.)),abs(aJoints-vec4(15.))));vHand=dot(aWeights,hands);if(aMaterial<.5){p.z+=sign(p.z)*.005*uGoalie*vHand;p.x+=.003*uGoalie*vHand;}
mat4 skin=aWeights.x*uBones[int(aJoints.x)]+aWeights.y*uBones[int(aJoints.y)]+aWeights.z*uBones[int(aJoints.z)]+aWeights.w*uBones[int(aJoints.w)];
vec4 w=skin*vec4(p,1.);vWorld=w.xyz;vNormal=normalize(mat3(skin)*aNormal);vBind=p;vMaterial=aMaterial;vColor=aColor;gl_Position=uVP*w;}`;
const FS=`precision highp float;
varying vec3 vWorld;varying vec3 vNormal;varying vec3 vBind;varying vec3 vColor;varying float vMaterial;varying float vHand;
uniform vec3 uEye;uniform vec3 uSkin;uniform vec3 uShirt;uniform vec3 uShorts;uniform vec3 uHair;uniform vec3 uBoots;uniform vec3 uIris;uniform float uNumber;uniform float uBeard;uniform float uStudio;uniform float uGoalie;
const float PI=3.14159265359;
float hash(vec3 p){return fract(sin(dot(p,vec3(12.9898,78.233,37.719)))*43758.5453);}
float rect(vec2 p,vec2 c,vec2 r){vec2 d=abs(p-c)-r;return 1.-smoothstep(0.,.025,max(d.x,d.y));}
float digit(float n,vec2 p){float a=0.,b=0.,c=0.,d=0.,e=0.,f=0.,g=0.;if(n<.5){a=1.;b=1.;c=1.;d=1.;e=1.;f=1.;}else if(n<1.5){b=1.;c=1.;}else if(n<2.5){a=1.;b=1.;g=1.;e=1.;d=1.;}else if(n<3.5){a=1.;b=1.;c=1.;d=1.;g=1.;}else if(n<4.5){b=1.;c=1.;f=1.;g=1.;}else if(n<5.5){a=1.;f=1.;g=1.;c=1.;d=1.;}else if(n<6.5){a=1.;f=1.;g=1.;e=1.;c=1.;d=1.;}else if(n<7.5){a=1.;b=1.;c=1.;}else if(n<8.5){a=1.;b=1.;c=1.;d=1.;e=1.;f=1.;g=1.;}else{a=1.;b=1.;c=1.;d=1.;f=1.;g=1.;}
return min(1.,a*rect(p,vec2(0.,.82),vec2(.34,.055))+g*rect(p,vec2(0.,0.),vec2(.34,.055))+d*rect(p,vec2(0.,-.82),vec2(.34,.055))+b*rect(p,vec2(.34,.41),vec2(.055,.40))+c*rect(p,vec2(.34,-.41),vec2(.055,.40))+f*rect(p,vec2(-.34,.41),vec2(.055,.40))+e*rect(p,vec2(-.34,-.41),vec2(.055,.40)));}
float ggx(float nh,float rough){float a=rough*rough,a2=a*a,d=nh*nh*(a2-1.)+1.;return a2/max(.0001,PI*d*d);}
float smith(float nv,float rough){float k=rough+1.;k=k*k/8.;return nv/(nv*(1.-k)+k);}
vec3 lightPBR(vec3 N,vec3 V,vec3 L,vec3 radiance,vec3 base,float rough,float wrap,float f0){vec3 H=normalize(V+L);float nl=max(0.,dot(N,L)),nv=max(.001,dot(N,V)),nh=max(0.,dot(N,H)),vh=max(0.,dot(V,H));vec3 F=vec3(f0)+(1.-f0)*pow(1.-vh,5.);vec3 spec=ggx(nh,rough)*smith(nv,rough)*smith(max(.001,nl),rough)*F/max(.004,4.*nv*max(.001,nl));return ((1.-F)*base/PI*max(0.,(nl+wrap)/(1.+wrap))+spec*nl)*radiance;}
vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
void main(){float id=floor(vMaterial+.5),rough=.72,wrap=0.,f0=.035;vec3 base=vec3(.5),N=normalize(vNormal),V=normalize(uEye-vWorld),p=vBind;
if(id<.5){base=pow(uSkin,vec3(2.2))*vColor;rough=.60;wrap=.10;f0=.025;
 float beard=(1.-smoothstep(1.68,1.735,p.y))*smoothstep(1.625,1.65,p.y)*smoothstep(.10,.135,p.x);float stubble=hash(floor(p*1700.));base=mix(base,pow(uHair,vec3(2.2))*.8,beard*uBeard*(.14+.14*stubble));
 float pore=hash(floor(p*1400.))-.5;base*=1.+pore*.035;rough+=pore*.045;
}else if(id<1.5){base=pow(uShirt,vec3(2.2));rough=.84;base*=.97+.025*sin(p.z*180.);
 if(p.x>.075&&p.y>1.15&&p.y<1.52){float piping=smoothstep(.155,.158,abs(p.z))*(1.-smoothstep(.163,.167,abs(p.z)));base=mix(base,vec3(.78),piping*.85);
 vec2 q=vec2((p.z+.085)/.021,(p.y-1.41)/.028);float crest=step(abs(q.x)+abs(q.y)*.6,.95);base=mix(base,vec3(.72,.58,.24),crest*.9);}
 if(p.x<-.065&&p.y>1.17&&p.y<1.45&&abs(p.z)<.115){float num=0.;vec2 q=vec2(-p.z/.085,(p.y-1.31)/.12);if(uNumber<9.5)num=digit(uNumber,q);else{q.x*=1.7;num=max(digit(floor(uNumber/10.),q+vec2(.47,0.)),digit(mod(uNumber,10.),q-vec2(.47,0.)));}base=mix(base,vec3(.85),num);}
 base*=1.+sin(p.y*1800.)*sin(p.z*1800.)*.018;
}else if(id<2.5){base=pow(uShorts,vec3(2.2));rough=.86;float seam=smoothstep(.135,.139,abs(p.z))*(1.-smoothstep(.145,.148,abs(p.z)));base=mix(base,pow(uShirt,vec3(2.2)),seam*.7);
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
function palette(p,assets,pose){
 const f=[Math.cos(p.face||0),0,Math.sin(p.face||0)],side=[-f[2],0,f[0]],yaw=v=>[v[0]*f[0]+v[2]*side[0],v[1],v[0]*f[2]+v[2]*side[2]],shift=(v,y)=>[v[0],v[1]+y,v[2]];
 const hip=pose.pelvis,chest=shift(pose.torsoUpper,.02),waist=shift(hip,.08),mid=mix(waist,chest,.56),neck=shift(pose.neck,.04),headTop=shift(pose.head,.11),frames={pelvis:[hip,waist],spine:[waist,mid],chest:[mid,chest],neck:[chest,neck],head:[neck,headTop]};
 for(let i=0;i<2;i++){
  const s=i===0?'L':'R',a=pose.arms[i],l=pose.legs[i],shoulder=mix(shift(pose.torsoUpper,-.01),a.shoulder,.84),handEnd=add(a.wrist,mul(unit(sub(a.wrist,a.elbow)),.125));frames['clavicle.'+s]=[shift(pose.torsoUpper,-.01),shoulder];frames['upper_arm.'+s]=[shoulder,a.elbow];frames['forearm.'+s]=[a.elbow,a.wrist];frames['hand.'+s]=[a.wrist,handEnd];frames['thigh.'+s]=[l.hip,l.knee];frames['shin.'+s]=[l.knee,l.ankle];frames['foot.'+s]=[l.ankle,shift(l.toe,-.075)];
 }
 const all=new Float32Array(assets.bones.length*16),headYaw=Number.isFinite(pose.headYaw)?clamp(pose.headYaw,-.8,.8):0;
 assets.bones.forEach((bone,i)=>{const scan=bone.name==='head'?headYaw:bone.name==='neck'?headYaw*.25:0,cs=Math.cos(scan),sn=Math.sin(scan),boneYaw=v=>{const u=yaw(v);return scan?[u[0]*cs-u[2]*sn,u[1],u[0]*sn+u[2]*cs]:u;};const [a,b]=frames[bone.name],rest=unit(sub(bone.tail,bone.head)),start=boneYaw(rest),target=unit(sub(b,a)),ratio=clamp(len(sub(b,a))/len(sub(bone.tail,bone.head)),.5,1.7),M=new Float32Array(16);
  for(let col=0;col<3;col++){let v=quatAlign(start,target,boneYaw(bone.matrix.slice(col*4,col*4+3)));if(col===1)v=mul(v,ratio);for(let j=0;j<3;j++)M[col*4+j]=v[j];}M[12]=a[0];M[13]=a[1];M[14]=a[2];M[15]=1;all.set(matmul(M,bone.inverseBind),i*16);
 });return all;
}
class PlayerRenderer{
 constructor(gl,assets=root.TribunPlayerAssets){
  if(!assets)throw Error('Oyuncu modeli yüklenmedi');this.gl=gl;this.assets=assets;this.studio=false;
  const shader=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
  const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,VS));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,FS));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));this.program=program;
  this.loc={};for(const n of ['uVP','uBones[0]','uEye','uSkin','uShirt','uShorts','uHair','uBoots','uIris','uVariant','uNumber','uBeard','uStudio','uGoalie'])this.loc[n]=gl.getUniformLocation(program,n);
  this.attributes=[['aPosition',3,0],['aNormal',3,3],['aUV',2,6],['aJoints',4,8],['aWeights',4,12],['aMaterial',1,16],['aColor',3,17]].map(([n,size,off])=>({location:gl.getAttribLocation(program,n),size,off}));
  const uint32=assets.lods.some(a=>a.indexType==='I')?gl.getExtension('OES_element_index_uint'):true;
  this.lods=assets.lods.map(a=>{if(a.indexType==='I'&&!uint32)return null;const vertices=new Float32Array(decode(a.vertices)),indices=a.indexType==='H'?new Uint16Array(decode(a.indices)):new Uint32Array(decode(a.indices));const vertex=gl.createBuffer(),index=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vertex);gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,index);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);return {vertex,index,count:indices.length,type:a.indexType==='H'?gl.UNSIGNED_SHORT:gl.UNSIGNED_INT};});
 }
 draw(players,vp,eye,camera='tv'){
  const gl=this.gl;gl.useProgram(this.program);gl.uniformMatrix4fv(this.loc.uVP,false,new Float32Array(vp));gl.uniform3fv(this.loc.uEye,eye);gl.uniform1f(this.loc.uStudio,this.studio?1:0);
  for(const p of players){if(!p.active)continue;const d=Math.hypot(p.x-eye[0],p.z-eye[2]),lod=this.lods[camera==='portrait'?0:camera==='close'&&d<22?1:2]||this.lods[1]||this.lods[2],v=p.visual||{},n=p.index||0,role=v.role||p.role,isGK=role==='GK',ref=p.referee;
   const shirt=v.shirt||(ref?[.94,.76,.16]:isGK?(p.team===0?[.42,.23,.67]:[.91,.59,.12]):p.team===0?[.075,.29,.68]:[.65,.075,.13]),shorts=v.shorts||(ref?[.10,.12,.14]:p.team===0?[.88,.90,.93]:[.09,.12,.16]);
   const set=(name,value)=>gl.uniform3fv(this.loc[name],value);set('uSkin',v.skin||p.skin||[.69,.48,.34]);set('uShirt',shirt);set('uShorts',shorts);set('uHair',v.hair||p.hair||[.10,.065,.043]);set('uBoots',v.boots||[[.055,.065,.08],[.91,.42,.09],[.07,.56,.45]][n%3]);set('uIris',v.iris||[[.15,.25,.18],[.30,.18,.09],[.13,.28,.36]][n%3]);set('uVariant',v.variant||[.94+(n%4)*.035,(n%3-1)*.06,0]);
   gl.uniform1f(this.loc.uGoalie,isGK?1:0);gl.uniform1f(this.loc.uNumber,p.num||n+1);gl.uniform1f(this.loc.uBeard,v.beard??(n%4===2?.85:0));const pose=root.TribunHumanoidRig.getPose(p);gl.uniformMatrix4fv(this.loc['uBones[0]'],false,(v.presentation?presentationPalette(p,this.assets):palette(p,this.assets,pose)));
   gl.bindBuffer(gl.ARRAY_BUFFER,lod.vertex);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,lod.index);for(const a of this.attributes){if(a.location<0)continue;gl.enableVertexAttribArray(a.location);gl.vertexAttribPointer(a.location,a.size,gl.FLOAT,false,80,a.off*4);}gl.drawElements(gl.TRIANGLES,lod.count,lod.type,0);for(const a of this.attributes)if(a.location>=0)gl.disableVertexAttribArray(a.location);
  }
 }
}
PlayerRenderer.presentationPalette=presentationPalette;PlayerRenderer.vertexShader=VS;PlayerRenderer.fragmentShader=FS;PlayerRenderer.palette=palette;PlayerRenderer.decode=decode;root.TribunPlayerRenderer=PlayerRenderer;if(typeof module!=='undefined'&&module.exports)module.exports=PlayerRenderer;
})(typeof window!=='undefined'?window:globalThis);
