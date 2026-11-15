'use strict';
/* Match presentation only: action crossfade for 19-bone WebGL palette.
   Never mutates Match / tactics / ball / physics / cached Rig poses.
   Uses quaternion SLERP + translation interpolation: no rubber-bone scale. */
(function(root){
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const ease=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const normalize=q=>{const n=Math.hypot(...q)||1;return q.map(v=>v/n);};
const category=action=>{
 const a=String(action||'idle').toLowerCase();
 return ['run','jog','walk','sprint','stride','dribble','carry','move'].includes(a)?'locomotion':
  ['idle','stand','ready'].includes(a)?'idle':a;
};
function quat(m,o){
 const a=m[o],b=m[o+5],c=m[o+10],trace=a+b+c;
 let x,y,z,w,s;
 if(trace>0){
  s=2*Math.sqrt(Math.max(.00001,trace+1));w=.25*s;
  x=(m[o+6]-m[o+9])/s;y=(m[o+8]-m[o+2])/s;z=(m[o+1]-m[o+4])/s;
 }else if(a>b&&a>c){
  s=2*Math.sqrt(Math.max(.00001,1+a-b-c));
  w=(m[o+6]-m[o+9])/s;x=.25*s;y=(m[o+4]+m[o+1])/s;z=(m[o+8]+m[o+2])/s;
 }else if(b>c){
  s=2*Math.sqrt(Math.max(.00001,1+b-a-c));
  w=(m[o+8]-m[o+2])/s;x=(m[o+4]+m[o+1])/s;y=.25*s;z=(m[o+9]+m[o+6])/s;
 }else{
  s=2*Math.sqrt(Math.max(.00001,1+c-a-b));
  w=(m[o+1]-m[o+4])/s;x=(m[o+8]+m[o+2])/s;y=(m[o+9]+m[o+6])/s;z=.25*s;
 }
 return normalize([x,y,z,w]);
}
function slerp(a,b,u){
 let dot=a.reduce((s,v,i)=>s+v*b[i],0);
 if(dot<0){b=b.map(x=>-x);dot=-dot;}
 if(dot>.9995)return normalize(a.map((v,i)=>v+(b[i]-v)*u));
 const angle=Math.acos(clamp(dot,-1,1)),sin=Math.sin(angle);
 return a.map((v,i)=>(v*Math.sin((1-u)*angle)+b[i]*Math.sin(u*angle))/sin);
}
function writeRotation(out,o,q){
 const [x,y,z,w]=q,xx=x*x,yy=y*y,zz=z*z,xy=x*y,xz=x*z,yz=y*z,wx=w*x,wy=w*y,wz=w*z;
 out[o]=1-2*(yy+zz);out[o+1]=2*(xy+wz);out[o+2]=2*(xz-wy);out[o+3]=0;
 out[o+4]=2*(xy-wz);out[o+5]=1-2*(xx+zz);out[o+6]=2*(yz+wx);out[o+7]=0;
 out[o+8]=2*(xz+wy);out[o+9]=2*(yz-wx);out[o+10]=1-2*(xx+yy);out[o+11]=0;
}
function mixRigid(source,destination,out,t,deltaX=0,deltaZ=0){
 if(source.length!==destination.length||source.length%16)throw Error('Bone palette size mismatch');
 for(let o=0;o<source.length;o+=16){
  const q=slerp(quat(source,o),quat(destination,o),t);
  writeRotation(out,o,q);
  out[o+12]=(source[o+12]+deltaX)*(1-t)+destination[o+12]*t;
  out[o+13]=source[o+13]*(1-t)+destination[o+13]*t;
  out[o+14]=(source[o+14]+deltaZ)*(1-t)+destination[o+14]*t;
  out[o+15]=1;
 }
 return out;
}
function create({duration=.28,enabled=true}={}){
 if(!Number.isFinite(duration)||duration<0||duration>1.5)throw Error('Invalid blending duration');
 let cached=new WeakMap(),live=0,changes=0,frameBlends=0;
 function sample(player,palette,dt=1/60,rawAction=player?.action){
  if(!player||typeof player!=='object')throw Error('Player must be an object');
  if(!palette||palette.length%16)throw Error('Bone palette invalid');
  if(!Number.isFinite(dt)||dt<0)throw Error('Frame delta invalid');
  const action=category(rawAction);
  let c=cached.get(player);
  if(!c){c={action,display:new Float32Array(palette),from:null,fromX:0,fromZ:0,x:Number(player.x)||0,z:Number(player.z)||0,elapsed:duration};
    cached.set(player,c);live++;return palette;}
  if(!enabled||!duration){
   c.action=action;c.from=null;c.display.set(palette);c.elapsed=duration;c.x=Number(player.x)||0;c.z=Number(player.z)||0;return palette;
  }
  if(c.action!==action){
   c.from=c.display.slice();c.fromX=c.x;c.fromZ=c.z;c.elapsed=0;c.action=action;changes++;
  }
  if(c.from){
   c.elapsed=Math.min(duration,c.elapsed+Math.min(dt,.25));
   const t=ease(c.elapsed/duration);
   mixRigid(c.from,palette,c.display,t,(Number(player.x)||0)-c.fromX,(Number(player.z)||0)-c.fromZ);
   frameBlends++;
   if(c.elapsed>=duration){c.from=null;c.display.set(palette);}
   c.x=Number(player.x)||0;c.z=Number(player.z)||0;
   return c.display;
  }
  c.display.set(palette);c.x=Number(player.x)||0;c.z=Number(player.z)||0;
  return palette;
 }
 function reset(){cached=new WeakMap();live=0;changes=0;frameBlends=0;}
 function stats(){return {players:live,transitions:changes,blendedFrames:frameBlends,duration,enabled};}
 return {sample,reset,stats,setEnabled:v=>{enabled=!!v;},isEnabled:()=>enabled};
}
const API={create,mixRigid,quat,slerp,category};
root.TribunMatchAnimationBridge=API;
if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
