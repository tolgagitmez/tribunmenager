'use strict';
/* TRIBUN 3D: tiny zero-dependency WebGL renderer. Real 3D geometry, perspective and depth. */
(function(){
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const add=(a,b)=>a.map((v,i)=>v+b[i]);const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const norm=a=>{let d=Math.hypot(...a)||1;return a.map(v=>v/d)};
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function lookAt(eye,target){let f=norm(sub(target,eye)),s=norm(cross(f,[0,1,0])),u=cross(s,f);
return [s[0],u[0],-f[0],0,s[1],u[1],-f[1],0,s[2],u[2],-f[2],0,-s.reduce((v,n,i)=>v+n*eye[i],0),-u.reduce((v,n,i)=>v+n*eye[i],0),f.reduce((v,n,i)=>v+n*eye[i],0),1]}
function perspective(fov,aspect,near,far){const f=1/Math.tan(fov/2),nf=1/(near-far);return [f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*nf,-1,0,0,2*far*near*nf,0]}
function matmul(a,b){let o=Array(16).fill(0);for(let col=0;col<4;col++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)o[col*4+row]+=a[k*4+row]*b[col*4+k];return o}
class Mesh{
constructor(){this.v=[];this.ct=0}
shade(normal,color){const n=norm(normal),sun=Math.max(0,n[0]*-.35+n[1]*.85+n[2]*.34),fill=Math.max(0,n[0]*.5+n[2]*-.45);const light=clamp(.57+.43*sun+.10*fill,.48,1.1);return color.map(v=>clamp(v*light,0,1));}
tri(a,b,c,color,normals=null){const flat=norm(cross(sub(b,a),sub(c,a)));for(let i=0;i<3;i++)this.v.push(...[a,b,c][i],...this.shade(normals?normals[i]:flat,color));this.ct+=3;}
quad(a,b,c,d,color,normals=null){this.tri(a,b,c,color,normals?[normals[0],normals[1],normals[2]]:null);this.tri(a,c,d,color,normals?[normals[0],normals[2],normals[3]]:null);}
// Smooth, variable-radius body sections; colours remain compatible with the small shader.
profile(a,b,sections,color,sides=10){
 const axis=norm(sub(b,a)),L=Math.hypot(...sub(b,a))||1,ref=Math.abs(axis[1])>.9?[1,0,0]:[0,1,0],u=norm(cross(axis,ref)),v=cross(axis,u);
 const ring=(j,theta)=>{const [t,r]=sections[j],rad=add(u.map(n=>n*Math.cos(theta)),v.map(n=>n*Math.sin(theta))),pos=add(add(a,axis.map(n=>n*t*L)),rad.map(n=>n*r));const lo=sections[Math.max(0,j-1)],hi=sections[Math.min(sections.length-1,j+1)],slope=(hi[1]-lo[1])/(Math.max(.01,(hi[0]-lo[0])*L));return {p:pos,n:sub(rad,axis.map(n=>n*slope))};};
 for(let j=0;j<sections.length-1;j++)for(let i=0;i<sides;i++){const t=i*Math.PI*2/sides,n=(i+1)*Math.PI*2/sides,A=ring(j,t),B=ring(j,n),C=ring(j+1,n),D=ring(j+1,t);this.quad(A.p,B.p,C.p,D.p,color,[A.n,B.n,C.n,D.n]);}
}
loft(rings,forward,side,color,sides=12){
 const point=(j,t)=>{const r=rings[j],rad=add(forward.map(n=>n*Math.cos(t)*r.depth),side.map(n=>n*Math.sin(t)*r.width));return {p:add(r.p,rad),n:add(forward.map(n=>n*Math.cos(t)/r.depth),side.map(n=>n*Math.sin(t)/r.width))};};
 for(let j=0;j<rings.length-1;j++)for(let i=0;i<sides;i++){const t=i*Math.PI*2/sides,n=(i+1)*Math.PI*2/sides,A=point(j,t),B=point(j,n),C=point(j+1,n),D=point(j+1,t);this.quad(A.p,B.p,C.p,D.p,color,[A.n,B.n,C.n,D.n]);}
}
box(x,y,z,w,h,d,color,angle=0){let co=Math.cos(angle),si=Math.sin(angle),r=(u,v,t)=>[x+u*co-t*si,y+v,z+u*si+t*co];let X=w/2,Y=h/2,Z=d/2;let p=[r(-X,-Y,-Z),r(X,-Y,-Z),r(X,Y,-Z),r(-X,Y,-Z),r(-X,-Y,Z),r(X,-Y,Z),r(X,Y,Z),r(-X,Y,Z)];for(let q of [[0,1,2,3],[5,4,7,6],[4,0,3,7],[1,5,6,2],[3,2,6,7],[4,5,1,0]])this.quad(...q.map(i=>p[i]),color)}
sphere(x,y,z,rx,ry,rz,color,nlat=6,nlon=9){for(let j=0;j<nlat;j++){const a=-Math.PI/2+j*Math.PI/nlat,b=-Math.PI/2+(j+1)*Math.PI/nlat;for(let i=0;i<nlon;i++){const c=2*Math.PI*i/nlon,d=2*Math.PI*(i+1)/nlon,pt=(l,t)=>[x+rx*Math.cos(l)*Math.cos(t),y+ry*Math.sin(l),z+rz*Math.cos(l)*Math.sin(t)],N=(l,t)=>[Math.cos(l)*Math.cos(t)/Math.max(rx,.001),Math.sin(l)/Math.max(ry,.001),Math.cos(l)*Math.sin(t)/Math.max(rz,.001)];this.quad(pt(a,c),pt(a,d),pt(b,d),pt(b,c),color,[N(a,c),N(a,d),N(b,d),N(b,c)]);}}}
line(x1,y1,z1,x2,y2,z2,w,color){const dx=x2-x1,dz=z2-z1;this.box((x1+x2)/2,(y1+y2)/2,(z1+z2)/2,Math.hypot(dx,dz),.07,w,color,Math.atan2(dz,dx))}
tapered(a,b,ra,rb,color,sides=7){let d=norm(sub(b,a)),ref=Math.abs(d[1])>.92?[1,0,0]:[0,1,0],u=norm(cross(d,ref)),v=cross(d,u);const pt=(base,r,theta)=>add(base,[r*(u[0]*Math.cos(theta)+v[0]*Math.sin(theta)),r*(u[1]*Math.cos(theta)+v[1]*Math.sin(theta)),r*(u[2]*Math.cos(theta)+v[2]*Math.sin(theta))]);for(let i=0;i<sides;i++){let t=i/sides*2*Math.PI,n=(i+1)/sides*2*Math.PI;this.quad(pt(a,ra,t),pt(a,ra,n),pt(b,rb,n),pt(b,rb,t),color)}}
segment(ax,ay,az,bx,by,bz,r,color){let a=[ax,ay,az],b=[bx,by,bz],dir=sub(b,a),L=Math.hypot(...dir);let d=norm(dir),ref=Math.abs(d[1])>.94?[1,0,0]:[0,1,0],u=norm(cross(d,ref)),v=cross(d,u);const sides=5;for(let i=0;i<sides;i++){let t=i/sides*2*Math.PI,t2=(i+1)/sides*2*Math.PI,ring=(base,t)=>add(base,[r*(u[0]*Math.cos(t)+v[0]*Math.sin(t)),r*(u[1]*Math.cos(t)+v[1]*Math.sin(t)),r*(u[2]*Math.cos(t)+v[2]*Math.sin(t))]);this.quad(ring(a,t),ring(a,t2),ring(b,t2),ring(b,t),color)}}
}
class Stadium3D{
constructor(canvas){this.canvas=canvas;this.gl=canvas.getContext('webgl',{antialias:true,alpha:false});if(!this.gl){this.ctx=canvas.getContext('2d');this.camera='tv';this.cameraSmoothing=[0,35,60];this.cameraTarget=[0,0,0];this.debugRig=false;return;}const gl=this.gl;const vs=`attribute vec3 p;attribute vec3 c;uniform mat4 vp;varying vec3 col;void main(){gl_Position=vp*vec4(p,1.);col=c;}`;
const fs=`precision mediump float;varying vec3 col;void main(){gl_FragColor=vec4(col,1.);}`;
let make=(type,src)=>{let sh=gl.createShader(type);gl.shaderSource(sh,src);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(sh));return sh};let prog=gl.createProgram();gl.attachShader(prog,make(gl.VERTEX_SHADER,vs));gl.attachShader(prog,make(gl.FRAGMENT_SHADER,fs));gl.linkProgram(prog);gl.useProgram(prog);this.program=prog;this.aPos=gl.getAttribLocation(prog,'p');this.aColor=gl.getAttribLocation(prog,'c');this.mvp=gl.getUniformLocation(prog,'vp');this.staticBuffer=gl.createBuffer();this.dynamicBuffer=gl.createBuffer();gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.clearColor(.025,.05,.095,1);this.camera='tv';this.cameraSmoothing=[0,35,60];this.cameraTarget=[0,0,0];this.debugRig=false;this.playerRenderer=null;this.playerAppearanceError=null;if(window.TribunPlayerRenderer&&window.TribunPlayerAssets){try{this.playerRenderer=new window.TribunPlayerRenderer(gl);}catch(error){this.playerAppearanceError=error.message;console.warn('Oyuncu modeli açılamadı:',error.message);}}if(typeof document!=='undefined'){const badge=document.querySelector('[data-player-quality]');if(badge)badge.textContent=this.playerRenderer?'YENİ OYUNCU MODELİ':'YEDEK OYUNCU MODELİ';}this.makeStatic();}
makeStatic(){let m=new Mesh(),green=[.09,.34,.16],white=[.72,.83,.75],seat=[.055,.12,.20],ad=[.09,.33,.52],stripe=[.11,.39,.19];m.box(0,-.4,0,137,.6,98,[.035,.075,.09]);for(let i=0;i<12;i++)m.box(-47.66+i*8.67,-.035,0,8.67,.07,68,i%2?green:stripe);
// proper field boundary and areas
const line=(x,z,X,Z,w=.18)=>m.line(x,.055,z,X,.055,Z,w,white);line(-52,-34,52,-34);line(-52,34,52,34);line(-52,-34,-52,34);line(52,-34,52,34);line(0,-34,0,34);
for(let a=-1;a<=1;a+=2){let x=52*a,inner=35*a;line(x,-20,inner,-20);line(inner,-20,inner,20);line(inner,20,x,20);let small=46*a;line(x,-9,small,-9);line(small,-9,small,9);line(small,9,x,9);m.sphere(41.5*a,.08,0,.2,.09,.2,white);}
for(let i=0;i<48;i++){let a=i*Math.PI/24,b=(i+1)*Math.PI/24;line(Math.cos(a)*9.15,Math.sin(a)*9.15,Math.cos(b)*9.15,Math.sin(b)*9.15,.16)}m.sphere(0,.08,0,.24,.08,.24,white);
// 3d goals and nets
for(let sign of [-1,1]){let x=52*sign,bx=x+sign*2.8;let pole=[.9,.94,.93],net=[.45,.65,.74];m.segment(x,0,-3.75,x,2.52,-3.75,.13,pole);m.segment(x,0,3.75,x,2.52,3.75,.13,pole);m.segment(x,2.52,-3.75,x,2.52,3.75,.13,pole);m.segment(x,2.52,-3.75,bx,2.22,-3.75,.06,pole);m.segment(x,2.52,3.75,bx,2.22,3.75,.06,pole);for(let zz=-3.75;zz<=3.76;zz+=.75){m.segment(x,0,zz,bx,0,zz,.018,net);m.segment(x,2.52,zz,bx,2.18,zz,.018,net)}for(let xx=0;xx<=2.8;xx+=.7){let p=x+sign*xx;for(let y of [0,1.05,2.15])m.segment(p,y,-3.75,p,y,3.75,.014,net)}}
// digital advertising and elevated stands
for(let z of [-1,1]){m.box(0,1,z*37.3,117,2,1.05,[.04,.17,.28]);m.box(0,2,z*38.05,115,.12,.27,[.10,.63,.94]);for(let row=0;row<11;row++)m.box(0,2.8+row*.96,z*(39.5+row*1.23),124,row===0?.5:.52,1.5,row%2?seat:[.075,.16,.24]);}
for(let x of [-1,1]){m.box(x*57,1,0,1.5,2,82,[.04,.17,.28]);for(let row=0;row<10;row++)m.box(x*(59+row*1.22),3+row*.94,0,1.6,.52,87,row%2?seat:[.08,.15,.22]);}
// low poly crowd colored seats, deterministic
let rs=1783;let rnd=()=>{rs=(Math.imul(rs,1664525)+1013904223)>>>0;return rs/4294967296};const crowdColors=[[.12,.38,.57],[.31,.38,.44],[.51,.55,.60],[.07,.21,.37],[.38,.22,.20],[.65,.54,.32]];for(let j=0;j<680;j++){let edge=rnd()>.5?'long':'short';let s=rnd()>.5?1:-1;let row=Math.floor(rnd()*8),x,z;if(edge==='long'){x=(rnd()-.5)*120;z=s*(40+row*1.3)}else{x=s*(60+row*1.3);z=(rnd()-.5)*85}let y=3.7+row*.96;let col=crowdColors[Math.floor(rnd()*crowdColors.length)];m.box(x,y,z,.32,.50,.32,col);m.sphere(x,y+.34,z,.17,.18,.17,[.55,.43,.36],3,5)}
// floodlights towers and glow fixtures
for(let x of [-65,65])for(let z of [-50,50]){m.box(x,17,z,.9,35,.9,[.13,.20,.28]);m.box(x,34,z,12,4,.5,[.65,.78,.86]);for(let k=0;k<7;k++)m.box(x-5+k*1.65,34.5,z-.35,.92,1.9,.14,[.84,.92,1])}
this.staticCount=m.ct;let gl=this.gl;gl.bindBuffer(gl.ARRAY_BUFFER,this.staticBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(m.v),gl.STATIC_DRAW);}
figure(mesh,p,dt){
 if(!p.active)return;const rig=window.TribunHumanoidRig;if(!rig)return;
 const pose=rig.getPose(p),skin=p.skin||[.72,.52,.38],hair=p.hair||[.12,.10,.08],isGK=p.role==='GK',ref=p.referee;
 const shirt=ref?[.94,.78,.16]:isGK?(p.team===0?[.48,.27,.69]:[.92,.62,.12]):p.team===0?[.06,.36,.82]:[.80,.07,.15];
 const shorts=ref?[.10,.13,.16]:p.team===0?[.94,.95,.96]:[.09,.12,.17],socks=p.team===0?[.055,.32,.75]:[.72,.06,.12],trim=p.team===0?[.91,.96,1]:[1,.85,.68];
 const boots=[[.07,.10,.13],[.94,.44,.08],[.18,.72,.68]][(p.index||0)%3],forward=[Math.cos(p.face),0,Math.sin(p.face)],side=[-Math.sin(p.face),0,Math.cos(p.face)];
 const shift=(a,f,s=0,y=0)=>[a[0]+forward[0]*f+side[0]*s,a[1]+y,a[2]+forward[2]*f+side[2]*s],mix=(a,b,t)=>a.map((n,i)=>n+(b[i]-n)*t);
 const detailed=this.camera==='portrait'||this.camera==='close',segments=detailed?12:8;
 mesh.sphere(p.x,.035,p.z,.37,.018,.27,[.025,.11,.065],3,8);
 if(p.selected)mesh.sphere(p.x,.025,p.z,.48,.012,.44,p.team===0?[.12,.42,.60]:[.55,.16,.12],3,12);
 for(let i=0;i<2;i++){
  const l=pose.legs[i],a=pose.arms[i],thighHem=mix(l.hip,l.knee,.47),sockTop=mix(l.knee,l.ankle,.28);
  mesh.profile(l.hip,thighHem,[[0,.128],[.35,.137],[1,.117]],shorts,segments);
  mesh.profile(thighHem,l.knee,[[0,.099],[.5,.095],[1,.076]],skin,segments);
  mesh.sphere(...l.knee,.077,.075,.076,skin,4,segments);
  mesh.profile(l.knee,sockTop,[[0,.074],[1,.088]],skin,segments);
  mesh.profile(sockTop,l.ankle,[[0,.090],[.3,.083],[.65,.067],[1,.052]],socks,segments);
  mesh.profile(mix(sockTop,l.ankle,.02),mix(sockTop,l.ankle,.11),[[0,.093],[1,.091]],trim,segments);
  const boot=norm(sub(l.toe,l.ankle)),heel=add(l.ankle,[-boot[0]*.045,-.045,-boot[2]*.045]),tip=add(l.toe,[boot[0]*.055,-.035,boot[2]*.055]);
  mesh.profile(heel,tip,[[0,.057],[.25,.069],[.7,.060],[1,.045]],boots,segments);
  if(detailed){for(const u of [.35,.49,.63]){const loc=mix(heel,tip,u);mesh.segment(loc[0]-side[0]*.037,loc[1]+.052,loc[2]-side[2]*.037,loc[0]+side[0]*.037,loc[1]+.052,loc[2]+side[2]*.037,.008,trim);}}
  const sleeveEnd=mix(a.shoulder,a.elbow,.48);
  mesh.profile(shift(pose.torsoUpper,0,(i?1:-1)*.205,-.01),a.shoulder,[[0,.085],[1,.098]],shirt,segments);
  mesh.sphere(...a.shoulder,.102,.099,.102,shirt,5,segments);
  mesh.profile(a.shoulder,sleeveEnd,[[0,.105],[.5,.106],[1,.09]],shirt,segments);
  mesh.profile(mix(a.shoulder,a.elbow,.43),sleeveEnd,[[0,.094],[1,.093]],trim,segments);
  mesh.profile(sleeveEnd,a.elbow,[[0,.077],[1,.061]],skin,segments);
  mesh.sphere(...a.elbow,.062,.063,.062,skin,4,segments);
  mesh.profile(a.elbow,a.wrist,[[0,.062],[.35,.064],[1,.043]],skin,segments);
  mesh.sphere(...a.wrist,isGK?.101:.049,isGK?.085:.068,isGK?.09:.044,isGK?[.94,.94,.80]:skin,5,segments);
 }
 const waist=shift(pose.pelvis,0,0,.08),chest=pose.torsoUpper;
 mesh.loft([{p:shift(pose.pelvis,0,0,-.04),width:.205,depth:.135},{p:waist,width:.215,depth:.14},{p:shift(waist,0,0,.06),width:.20,depth:.135}],forward,side,shorts,segments);
 mesh.loft([{p:shift(waist,0,0,.02),width:.208,depth:.145},{p:mix(waist,chest,.35),width:.193,depth:.138},{p:mix(waist,chest,.72),width:.246,depth:.16},{p:chest,width:.277,depth:.15},{p:shift(chest,-.012,0,.07),width:.20,depth:.125}],forward,side,shirt,segments);
 mesh.profile(shift(chest,0,0,.055),shift(pose.neck,0,0,.065),[[0,.067],[1,.061]],skin,segments);
 // A smaller adult head, jaw, ears and a hair cap replace the old large sphere.
 const h=pose.head,headW=.106+(p.index||0)%3*.004;
 mesh.sphere(...h,headW,.142,.108,skin,detailed?10:6,detailed?16:10);
 mesh.sphere(...shift(h,.009,0,-.082),headW*.83,.064,.09,skin,5,segments);
 mesh.sphere(...shift(h,-.015,0,.105),headW*1.02,.063,.109,hair,5,segments);
 if(detailed){
  for(const sign of [-1,1]){
   mesh.sphere(...shift(h,-.009,sign*(headW-.002),-.006),.020,.036,.020,skin,5,8);
   mesh.sphere(...shift(h,.100,sign*.041,.022),.010,.010,.016,[.86,.88,.88],4,7);
   mesh.sphere(...shift(h,.108,sign*.041,.022),.006,.007,.009,[.09,.10,.095],4,6);
   mesh.segment(...shift(h,.103,sign*.060,.045),...shift(h,.108,sign*.024,.049),.009,hair);
  }
  mesh.tapered(shift(h,.105,0,-.002),shift(h,.142,0,-.023),.021,.012,skin,8);
  mesh.segment(...shift(h,.105,-.028,-.060),...shift(h,.105,.028,-.060),.006,skin.map(c=>c*.65));
  if((p.index||0)%4===2)mesh.sphere(...shift(h,.041,0,-.100),.076,.029,.067,hair.map(c=>c*1.2),4,9);
  const collar=shift(chest,.115,0,.056);mesh.segment(...shift(collar,0,-.052,.018),...shift(collar,.012,0,-.027),.013,trim);mesh.segment(...shift(collar,.012,0,-.027),...shift(collar,0,.052,.018),.013,trim);
  mesh.sphere(...shift(chest,.148,-.115,-.035),.013,.032,.023,trim,4,6);
  // Geometry-based jersey numbers; no downloaded faces or texture dependencies.
  const digits=String(p.num||p.index+1||1),patterns={0:[0,1,2,3,4,5],1:[1,2],2:[0,1,6,4,3],3:[0,1,2,3,6],4:[5,6,1,2],5:[0,5,6,2,3],6:[0,5,4,3,2,6],7:[0,1,2],8:[0,1,2,3,4,5,6],9:[0,1,2,3,5,6]},lines=[[-.025,.07,.025,.07],[.025,.07,.025,0],[.025,0,.025,-.07],[-.025,-.07,.025,-.07],[-.025,0,-.025,-.07],[-.025,.07,-.025,0],[-.025,0,.025,0]];
  for(let n=0;n<digits.length;n++)for(const i of patterns[digits[n]]||[]){const [x,y,X,Y]=lines[i],off=(n-(digits.length-1)/2)*.072;mesh.segment(...shift(chest,-.157,x+off,y-.10),...shift(chest,-.157,X+off,Y-.10),.007,trim);}
 }
 if(p.yellow)mesh.sphere(...shift(chest,.16,.15,-.07),.016,.025,.025,[1,.86,.15],3,5);
 if(this.debugRig){const gold=[1,.72,.15];for(const l of pose.legs){mesh.segment(...l.hip,...l.knee,.014,gold);mesh.segment(...l.knee,...l.ankle,.014,gold);mesh.sphere(...l.knee,.029,.029,.029,gold,4,6);}for(const a of pose.arms){mesh.segment(...a.shoulder,...a.elbow,.012,gold);mesh.segment(...a.elbow,...a.wrist,.012,gold);}}
}
renderFallback(players,ball,focus,dt){
const c=this.canvas,ctx=this.ctx,rect=c.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,1.5),w=Math.floor(rect.width*dpr),h=Math.floor(rect.height*dpr);if(c.width!==w||c.height!==h){c.width=w;c.height=h}ctx.clearRect(0,0,w,h);let target=this.camera==='close'?[Math.max(-26,Math.min(26,focus[0])),0,Math.max(-18,Math.min(18,focus[1]))]:[0,0,0];let eye=this.camera==='portrait'?[target[0]+4.4,3.5,target[2]+5.5]:this.camera==='tactical'?[4,116,18]:this.camera==='close'?[target[0]+16,18,target[2]+20]:[target[0]*.65,35,60];let vp=matmul(perspective(.95,w/h,.2,400),lookAt(eye,target));let project=(x,y,z)=>{let clip=[vp[0]*x+vp[4]*y+vp[8]*z+vp[12],vp[1]*x+vp[5]*y+vp[9]*z+vp[13],vp[3]*x+vp[7]*y+vp[11]*z+vp[15]];return [w/2+clip[0]/clip[2]*w/2,h/2-clip[1]/clip[2]*h/2,clip[2]]};
let polygon=(pts,color)=>{let q=pts.map(p=>project(...p));ctx.beginPath();ctx.moveTo(q[0][0],q[0][1]);for(let i=1;i<q.length;i++)ctx.lineTo(q[i][0],q[i][1]);ctx.closePath();ctx.fillStyle=color;ctx.fill()};const stroke=(a,b,color,width=1)=>{let x=project(...a),y=project(...b);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x[0],x[1]);ctx.lineTo(y[0],y[1]);ctx.stroke()};
ctx.fillStyle='#061a2c';ctx.fillRect(0,0,w,h);polygon([[-74,-.45,-54],[74,-.45,-54],[74,-.45,54],[-74,-.45,54]],'#162e43');
for(let i=0;i<12;i++){let x=-52+i*104/12,xx=-52+(i+1)*104/12;polygon([[x,0,-34],[xx,0,-34],[xx,0,34],[x,0,34]],i%2?'#195b2d':'#206c35')}
for(let side of [-1,1]){for(let tier=0;tier<9;tier++){let z=side*(38+tier*1.6);polygon([[-61,tier*.8+2,z], [61,tier*.8+2,z],[61,tier*.8+2,z+side*1.8],[-61,tier*.8+2,z+side*1.8]],tier%2?'#20435d':'#17354c')}}
let white='#e4f5e6',y=.05;for(let [a,b] of [[[-52,y,-34],[52,y,-34]],[[-52,y,34],[52,y,34]],[[-52,y,-34],[-52,y,34]],[[52,y,-34],[52,y,34]],[[0,y,-34],[0,y,34]],[[-52,y,-20],[-35,y,-20]],[[-35,y,-20],[-35,y,20]],[[-35,y,20],[-52,y,20]],[[52,y,-20],[35,y,-20]],[[35,y,-20],[35,y,20]],[[35,y,20],[52,y,20]],[[-52,y,-9],[-46,y,-9]],[[-46,y,-9],[-46,y,9]],[[-46,y,9],[-52,y,9]],[[52,y,-9],[46,y,-9]],[[46,y,-9],[46,y,9]],[[46,y,9],[52,y,9]]])stroke(a,b,white,Math.max(1,w/900));for(let j=0;j<48;j++){let a=j*2*Math.PI/48,b=(j+1)*2*Math.PI/48;stroke([9.2*Math.cos(a),y,9.2*Math.sin(a)],[9.2*Math.cos(b),y,9.2*Math.sin(b)],white,w/900)}
for(let sign of [-1,1]){stroke([sign*52,.1,-3.7],[sign*52,2.6,-3.7],'white',2);stroke([sign*52,.1,3.7],[sign*52,2.6,3.7],'white',2);stroke([sign*52,2.6,-3.7],[sign*52,2.6,3.7],'white',2)}
let sorted=players.filter(p=>p.active).map(p=>({p,xy:project(p.x,0,p.z)})).sort((a,b)=>b.xy[2]-a.xy[2]);for(let {p,xy} of sorted){let foot=project(p.x,0,p.z),head=project(p.x,1.8,p.z),size=Math.max(2,Math.hypot(foot[0]-head[0],foot[1]-head[1]));ctx.strokeStyle=p.referee?'#f5d63c':p.team===0?'#4fb5f3':'#f04455';ctx.lineWidth=Math.max(2,size*.25);ctx.lineCap='round';ctx.beginPath();ctx.moveTo((foot[0]+head[0])/2,foot[1]);ctx.lineTo(head[0],head[1]+size*.22);ctx.stroke();ctx.beginPath();ctx.fillStyle='#d9af86';ctx.arc(head[0],head[1],Math.max(2,size*.15),0,Math.PI*2);ctx.fill()}
let bp=project(ball.x,ball.y,ball.z);ctx.beginPath();ctx.fillStyle='white';ctx.arc(bp[0],bp[1],Math.max(3,w/310),0,Math.PI*2);ctx.fill();ctx.strokeStyle='#142a37';ctx.lineWidth=1.4;ctx.stroke();ctx.fillStyle='#acd6e7';ctx.font=`${Math.round(w/69)}px Arial`;ctx.fillText('2D yedek görünüm · WebGL devre dışı',15,h-18);
}
resize(){const c=this.canvas,rect=c.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,1.8);let w=Math.max(2,Math.floor(rect.width*dpr)),h=Math.max(2,Math.floor(rect.height*dpr));if(c.width!==w||c.height!==h){c.width=w;c.height=h}this.gl.viewport(0,0,w,h)}
render(players,ball,focus,events,dt){if(!this.gl){this.renderFallback(players,ball,focus,dt);return;}let gl=this.gl;this.resize();let target=this.camera==='portrait'?[focus[0],.9,focus[1]]:this.camera==='close'?[clamp(focus[0],-47,47),.8,clamp(focus[1],-27,27)]:this.camera==='tv'?[clamp(focus[0]*.65,-32,32),0,clamp(focus[1]*.3,-10,10)]:[0,0,0];let desire=this.camera==='portrait'?[target[0]+4.4,3.5,target[2]+5.5]:this.camera==='tactical'?[4,116,18]:this.camera==='close'?[target[0]+16,18,target[2]+20]:[target[0]*.65,35,60];let smoothing=clamp(dt*3,0,1);for(let i=0;i<3;i++){this.cameraSmoothing[i]+=(desire[i]-this.cameraSmoothing[i])*smoothing;this.cameraTarget[i]+=(target[i]-this.cameraTarget[i])*smoothing}
let vp=matmul(perspective((this.camera==='portrait'?43:this.camera==='close'?48:54)*Math.PI/180,this.canvas.width/this.canvas.height,.2,400),lookAt(this.cameraSmoothing,this.cameraTarget));gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(this.program);gl.uniformMatrix4fv(this.mvp,false,new Float32Array(vp));const draw=(buffer,count)=>{gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.enableVertexAttribArray(this.aPos);gl.vertexAttribPointer(this.aPos,3,gl.FLOAT,false,24,0);gl.enableVertexAttribArray(this.aColor);gl.vertexAttribPointer(this.aColor,3,gl.FLOAT,false,24,12);gl.drawArrays(gl.TRIANGLES,0,count)};draw(this.staticBuffer,this.staticCount);
let m=new Mesh();
if(this.playerRenderer){
 gl.disableVertexAttribArray(this.aPos);gl.disableVertexAttribArray(this.aColor);this.playerRenderer.draw(players,vp,this.cameraSmoothing,this.camera);gl.useProgram(this.program);gl.uniformMatrix4fv(this.mvp,false,new Float32Array(vp));
 for(const p of players){if(!p.active)continue;m.sphere(p.x,.035,p.z,.37,.018,.27,[.025,.11,.065],3,10);if(p.selected)m.sphere(p.x,.025,p.z,.48,.012,.44,p.team===0?[.12,.42,.60]:[.55,.16,.12],3,16);
 if(this.debugRig){const pose=window.TribunHumanoidRig.getPose(p),gold=[1,.72,.15];for(const l of pose.legs){m.segment(...l.hip,...l.knee,.014,gold);m.segment(...l.knee,...l.ankle,.014,gold);}for(const a of pose.arms){m.segment(...a.shoulder,...a.elbow,.012,gold);m.segment(...a.elbow,...a.wrist,.012,gold);}}}
}else for(const p of players)this.figure(m,p,dt);
if(ball){m.sphere(ball.x,.06,ball.z,.21,.015,.21,[.035,.18,.13],4,8);m.sphere(ball.x,ball.y,ball.z,.11,.11,.11,[.98,.98,.94],6,9);m.sphere(ball.x+.045,ball.y+.065,ball.z+.045,.030,.025,.030,[.07,.07,.08],4,6)}if(events?.flash){let pp=events.flash;m.sphere(pp.x,.07,pp.z,2.05,.027,2.05,[.58,.50,.09],3,12)}
gl.bindBuffer(gl.ARRAY_BUFFER,this.dynamicBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(m.v),gl.DYNAMIC_DRAW);draw(this.dynamicBuffer,m.ct)}
}
window.Stadium3D=Stadium3D;
})();
