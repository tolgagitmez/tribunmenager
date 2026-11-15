'use strict';
/* Tribun Manager: self-contained athletic base footballer, metres / Y up.
   This is a procedural, rigged game prototype. Not a scanned or sculpted human.
   Asset geometry is generated once at startup; match drawing is unchanged. */
(function(root){
const Rig=root.TribunHumanoidRig;
if(!Rig)throw Error('Load humanoid-rig.js before player-model-data.js');
const blend=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const sum=(a,b)=>a.map((v,i)=>v+b[i]);
const scale=(a,k)=>a.map(v=>v*k);
const dot=(a,b)=>a.reduce((s,n,i)=>s+n*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2]];
const norm=a=>{const l=Math.hypot(...a)||1;return a.map(v=>v/l);};
const rgba=[1,1,1];
const rest=Rig.update({x:0,z:0,face:0,speed:0,action:'idle',actionClock:0,kickFoot:1},1/60);
const waist=sum(rest.pelvis,[0,.08,0]),chest=sum(rest.torsoUpper,[0,.02,0]),mid=blend(waist,chest,.56),neck=sum(rest.neck,[0,.04,0]);
const defs=[['pelvis',rest.pelvis,waist],['spine',waist,mid],['chest',mid,chest],['neck',chest,neck],['head',neck,sum(rest.head,[0,.11,0])]];
for(let i=0;i<2;i++){
 const L=i===0?'L':'R',a=rest.arms[i],l=rest.legs[i];
 const shoulder=blend(sum(rest.torsoUpper,[0,-.01,0]),a.shoulder,.84);
 const handEnd=sum(a.wrist,scale(norm(sub(a.wrist,a.elbow)),.125));
 defs.push(['clavicle.'+L,sum(rest.torsoUpper,[0,-.01,0]),shoulder],
 ['upper_arm.'+L,shoulder,a.elbow],['forearm.'+L,a.elbow,a.wrist],['hand.'+L,a.wrist,handEnd],
 ['thigh.'+L,l.hip,l.knee],['shin.'+L,l.knee,l.ankle],['foot.'+L,l.ankle,sum(l.toe,[0,-.075,0])]);
}
const bones=defs.map(([name,head,tail])=>({
 name,head,tail,
 matrix:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
 inverseBind:[1,0,0,0,0,1,0,0,0,0,1,0,-head[0],-head[1],-head[2],1]
}));
const id=Object.fromEntries(bones.map((b,i)=>[b.name,i]));
const skin=(...pairs)=>pairs.map(([name,weight])=>[id[name],weight]);
function encode(bytes){
 const abc='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/',parts=[];
 for(let i=0;i<bytes.length;i+=3){
  const a=bytes[i],hasB=i+1<bytes.length,hasC=i+2<bytes.length;
  const b=hasB?bytes[i+1]:0,c=hasC?bytes[i+2]:0;
  parts.push(abc[a>>2],abc[((a&3)<<4)|(b>>4)],hasB?abc[((b&15)<<2)|(c>>6)]:'=',hasC?abc[c&63]:'=');
 }
 return parts.join('');
}
function mesh(lod){
 const v=[],tri=[],sides=[20,14,10][lod];
 function vertex(p,n,uv,weights,material,tint=rgba){
  const bindings=weights.slice(0,4),total=bindings.reduce((s,b)=>s+b[1],0)||1;
  const joints=bindings.map(b=>b[0]),values=bindings.map(b=>b[1]/total);
  while(joints.length<4){joints.push(0);values.push(0);}
  v.push(...p,...norm(n),...uv,...joints,...values,material,...tint);
  return v.length/20-1;
 }
 function rings(points,material,mode='XZ',segments=sides){
  const positions=[];for(let j=0;j<points.length;j++){
   const r=points[j],row=[];
   for(let k=0;k<segments;k++){
    const t=k*Math.PI*2/segments,co=Math.cos(t),si=Math.sin(t);
    let position,normal;
    if(mode==='XZ'){
     position=[r.p[0]+r.rx*co,r.p[1],r.p[2]+r.rz*si];
     normal=[co/Math.max(r.rx,.002),0,si/Math.max(r.rz,.002)];
    }else{
     position=[r.p[0],r.p[1]+r.rx*co,r.p[2]+r.rz*si];
     normal=[0,co/Math.max(r.rx,.002),si/Math.max(r.rz,.002)];
    }
    row.push(vertex(position,normal,[k/segments,j/(points.length-1)],r.w,r.m??material,r.color||rgba));
   }positions.push(row);
  }
  for(let j=0;j<positions.length-1;j++)for(let k=0;k<segments;k++){
   const a=positions[j][k],b=positions[j][(k+1)%segments],c=positions[j+1][(k+1)%segments],d=positions[j+1][k];
   tri.push(a,b,c,a,c,d);
  }
 }
 function sweep(nodes,material,segments=sides){
  const rows=[];
  for(let j=0;j<nodes.length;j++){
   const r=nodes[j],prev=nodes[Math.max(j-1,0)].p,next=nodes[Math.min(j+1,nodes.length-1)].p;
   const tangent=norm(sub(next,prev)),ref=Math.abs(tangent[1])>.9?[1,0,0]:[0,1,0];
   const u=norm(cross(tangent,ref)),w=norm(cross(tangent,u)),row=[];
   for(let k=0;k<segments;k++){
    const t=k*2*Math.PI/segments,co=Math.cos(t),si=Math.sin(t);
    const normal=norm(sum(scale(u,co/Math.max(r.rx,.005)),scale(w,si/Math.max(r.rz,.005))));
    const position=sum(r.p,sum(scale(u,co*r.rx),scale(w,si*r.rz)));
    row.push(vertex(position,normal,[k/segments,j/(nodes.length-1)],r.w,r.m??material));
   }rows.push(row);
  }
  for(let j=0;j<rows.length-1;j++)for(let k=0;k<segments;k++){
   const a=rows[j][k],b=rows[j][(k+1)%segments],c=rows[j+1][(k+1)%segments],d=rows[j+1][k];
   tri.push(a,b,c,a,c,d);
  }
 }
 function ellipsoid(center,rx,ry,rz,weights,material,ringCount=[12,8,6][lod]){
  const ringset=[];
  for(let i=0;i<=ringCount;i++){
   const a=-Math.PI/2+i*Math.PI/ringCount,rr=Math.max(.001,Math.cos(a));
   ringset.push({p:[center[0],center[1]+ry*Math.sin(a),center[2]],rx:rx*rr,rz:rz*rr,w:weights,m:material});
  }rings(ringset,material);
 }
 const torso=[
  [rest.pelvis[1]-.09,-.04,.148,.165,2],[rest.pelvis[1]+.00,-.04,.152,.181,2],
  [1.065,-.045,.127,.160,2],[1.095,-.043,.124,.163,1],
  [1.17,-.035,.124,.196,1],[1.245,-.01,.145,.244,1],
  [1.33,.005,.154,.264,1],[1.40,.01,.151,.265,1],
  [1.46,.013,.141,.247,1],[1.505,.02,.120,.137,1],[1.555,.021,.066,.082,0]
 ].map(([y,x,rx,rz,m])=>({p:[x,y,0],rx,rz,m,w:y<1.05?skin(['pelvis',1]):y<1.2?skin(['pelvis',.15],['spine',.85]):y<1.4?skin(['spine',.30],['chest',.70]):skin(['chest',.9],['neck',.1])}));
 rings(torso,1);
 // Neck and adult-proportioned cranium. Facial features face +X.
 rings([
  [1.505,.057,.071],[1.56,.065,.072],[1.615,.067,.075],[1.64,.077,.082]
 ].map(([y,rx,rz])=>({p:[.022,y,0],rx,rz,w:skin(['neck',.76],['head',.24]),m:0})),0);
 const skull=[
 [1.607,.005,.009,.010],[1.629,.023,.065,.065],[1.656,.03,.086,.082],
 [1.69,.035,.099,.091],[1.74,.035,.102,.093],[1.79,.03,.105,.096],
 [1.832,.025,.105,.094],[1.875,.017,.091,.082],[1.911,.016,.054,.053],
 [1.934,.016,.001,.001]
 ].map(([y,x,rx,rz])=>({p:[x,y,0],rx,rz,w:skin(['head',1]),m:0}));
 rings(skull,0);
 // Ears and anatomically legible facial landmarks.
 for(const side of [-1,1]){
  ellipsoid([.016,1.747,side*.101],.023,.038,.019,skin(['head',1]),0,8);
  ellipsoid([.119,1.782,side*.049],.0085,.013,.024,skin(['head',1]),6,8);
  ellipsoid([.128,1.782,side*.048],.007,.009,.012,skin(['head',1]),7,8);
  ellipsoid([.134,1.782,side*.048],.004,.007,.006,skin(['head',1]),8,7);
  ellipsoid([.125,1.812,side*.048],.009,.008,.031,skin(['head',1]),9,6);
 }
 ellipsoid([.144,1.724,0],.030,.045,.023,skin(['head',1]),0,8);
 ellipsoid([.120,1.668,0],.006,.004,.036,skin(['head',1]),9,7);
 // Hair cap with a natural crown height and shorter sideburns.
 rings([[1.835,.025,.094,.095],[1.86,.021,.104,.096],[1.898,.017,.084,.075],[1.935,.015,.043,.044],[1.947,.014,.001,.001]]
  .map(([y,x,rx,rz])=>({p:[x,y,0],rx,rz,w:skin(['head',1]),m:5})),5);
 for(const i of [0,1]){
  const side=i===0?'L':'R',a=rest.arms[i],l=rest.legs[i];
  const shoulder=bones[id['upper_arm.'+side]].head,elbow=a.elbow,wrist=a.wrist;
  const up='upper_arm.'+side,fore='forearm.'+side,hand='hand.'+side;
  const armNodes=[
   [shoulder,.113,.112,skin(['clavicle.'+side,.30],[up,.70]),1],
   [blend(shoulder,elbow,.15),.115,.110,skin([up,1]),1],
   [blend(shoulder,elbow,.36),.111,.105,skin([up,1]),1],
   [blend(shoulder,elbow,.52),.102,.096,skin([up,1]),1],
   [blend(shoulder,elbow,.67),.092,.087,skin([up,1]),0],
   [blend(shoulder,elbow,.88),.081,.079,skin([up,.78],[fore,.22]),0],
   [elbow,.079,.078,skin([up,.48],[fore,.52]),0],
   [blend(elbow,wrist,.12),.079,.077,skin([up,.22],[fore,.78]),0],
   [blend(elbow,wrist,.33),.090,.086,skin([fore,1]),0],
   [blend(elbow,wrist,.64),.082,.079,skin([fore,1]),0],
   [blend(elbow,wrist,.88),.066,.064,skin([fore,.80],[hand,.20]),0],
   [wrist,.057,.057,skin([fore,.22],[hand,.78]),0]
  ].map(([p,rx,rz,w,m])=>({p,rx,rz,w,m}));
  sweep(armNodes,0);
  const handCenter=sum(wrist,scale(norm(sub(wrist,elbow)),.055));
  ellipsoid(handCenter,.056,.081,.059,skin([hand,1]),0,8);
  const thigh='thigh.'+side,shin='shin.'+side,foot='foot.'+side;
  const legNodes=[
   [l.hip,.133,.139,skin(['pelvis',.28],[thigh,.72]),2],
   [blend(l.hip,l.knee,.14),.142,.144,skin([thigh,1]),2],
   [blend(l.hip,l.knee,.34),.137,.141,skin([thigh,1]),2],
   [blend(l.hip,l.knee,.49),.129,.131,skin([thigh,1]),2],
   [blend(l.hip,l.knee,.66),.115,.116,skin([thigh,1]),0],
   [blend(l.hip,l.knee,.86),.099,.100,skin([thigh,.83],[shin,.17]),0],
   [l.knee,.095,.097,skin([thigh,.48],[shin,.52]),0],
   [blend(l.knee,l.ankle,.12),.098,.099,skin([thigh,.18],[shin,.82]),3],
   [blend(l.knee,l.ankle,.34),.101,.101,skin([shin,1]),3],
   [blend(l.knee,l.ankle,.64),.081,.088,skin([shin,1]),3],
   [blend(l.knee,l.ankle,.87),.064,.075,skin([shin,.83],[foot,.17]),3],
   [l.ankle,.065,.070,skin([shin,.22],[foot,.78]),4]
  ].map(([p,rx,rz,w,m])=>({p,rx,rz,w,m}));
  sweep(legNodes,2);
  // X-forward low-cut football boot with rounded toe and heel (local X/Y/Z).
  const ank=l.ankle;const shoe=[
   [-.105,.109,.038,.047],[-.052,.107,.068,.074],
   [.01,.102,.074,.091],[.092,.096,.066,.093],
   [.185,.091,.050,.088],[.278,.087,.025,.054],
   [.303,.085,.003,.006]
  ].map(([dx,y,rx,rz])=>({p:[ank[0]+dx,y,ank[2]],rx,rz,w:skin([foot,1]),m:4}));
  rings(shoe,4,'YZ');
 }
 if(v.length/20>65535)throw Error('Base footballer exceeds WebGL1 index limit');
 const vertices=new Float32Array(v),indices=new Uint16Array(tri);
 return {vertices:encode(new Uint8Array(vertices.buffer)),indices:encode(new Uint8Array(indices.buffer)),indexType:'H',
  vertexCount:vertices.length/20,indexCount:indices.length};
}
const assets={version:'base-footballer-procedural-1',units:'metres',up:'Y',boneCount:bones.length,bones,
 lods:[mesh(0),mesh(1),mesh(2)]};
root.TribunPlayerAssets=assets;
if(typeof module!=='undefined'&&module.exports)module.exports=assets;
})(typeof window!=='undefined'?window:globalThis);
