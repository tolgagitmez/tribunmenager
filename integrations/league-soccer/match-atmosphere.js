'use strict';
(function(root){
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 const profiles=Object.freeze({
  classic:{tone:[1,1,1],sky:[.025,.05,.095],shadow:{offset:[0,0],stretch:.37,color:[.025,.11,.065]}},
  day:{tone:[1.06,1.08,1.01],sky:[.29,.44,.56],shadow:{offset:[.40,-.28],stretch:.72,color:[.05,.16,.085]}},
  evening:{tone:[1.10,.94,.81],sky:[.22,.14,.20],shadow:{offset:[.76,-.50],stretch:1.17,color:[.04,.13,.07]}},
  night:{tone:[.83,.94,1.09],sky:[.019,.029,.065],shadow:{offset:[.15,.08],stretch:.48,color:[.03,.10,.06]}}
 });
 function cameraFrame(focus,ball,aspect=16/9){
  const x=Number.isFinite(focus?.[0])?focus[0]:0,z=Number.isFinite(focus?.[1])?focus[1]:0;
  const vx=Number.isFinite(ball?.vx)?ball.vx:0,vz=Number.isFinite(ball?.vz)?ball.vz:0;
  const speed=clamp(Math.hypot(vx,vz),0,25),wide=clamp((speed-3)/15,0,1),edge=clamp((Math.abs(x)-25)/24,0,1);
  const narrow=Number.isFinite(aspect)?clamp((1.6-aspect)*7,0,7):0;
  const target=[clamp(x*.76+clamp(vx*.25,-4,4),-39,39),.3,clamp(z*.40+clamp(vz*.16,-2,2),-15,15)];
  return {target,eye:[target[0]*.92,31+wide*5+edge*2,56+wide*5],fov:clamp(49+wide*5+edge*3+narrow,49,64)};
 }
 const api={profiles,cameraFrame};root.TribunMatchAtmosphere=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
