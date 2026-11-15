'use strict';
/* Shared scenarios for the inspection screen and motion regression tests. */
(function(root){
const TAU=Math.PI*2,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function create(mode='run'){
 const p={active:true,index:0,team:0,role:mode.startsWith('dive')?'GK':'MID',x:0,z:0,face:0,speed:0,vx:0,vz:0,anim:0,action:'idle',actionClock:0,kickFoot:1,stamina:100,skin:[.69,.48,.33],hair:[.12,.09,.07]};
 return {mode,p,ball:{x:.88,y:.11,z:.18,vx:0,vy:0,vz:0},time:0};
}
function sample(s,t,rig){
 const p=s.p;let prevX=p.x,prevZ=p.z;s.time=t;p.x=p.z=0;p.face=0;p.actionClock=0;p.action='idle';p.actionElapsed=0;
 if(['walk','jog','run','sprint'].includes(s.mode)){
  // Constant-speed circular locomotion preserves continuity when the
  // inspection loop restarts. Distinct modes expose walk/jog/sprint stride.
  const speed=s.mode==='walk'?1.25:s.mode==='sprint'?6.4:2.8;
  const radius=s.mode==='sprint'?8:4,omega=speed/radius,yaw=t*omega;
  p.x=Math.sin(yaw)*radius;p.z=(1-Math.cos(yaw))*radius;p.face=yaw;p.speed=speed;
  p.vx=Math.cos(yaw)*speed;p.vz=Math.sin(yaw)*speed;
  p.action=s.mode==='walk'?'walk':s.mode==='sprint'?'sprint':'run';
 }else if(s.mode==='turn'){
  const u=t%8;
  if(u<2){p.x=2*u;p.face=0;p.speed=2;}
  else if(u<2.5){const d=u-2;p.x=4+2*d-2*d*d;p.face=0;p.speed=2-4*d;}
  else if(u<3.5){p.x=4.5;p.face=(u-2.5)*Math.PI;p.speed=0;}
  else if(u<4){const d=u-3.5;p.x=4.5-2*d*d;p.face=Math.PI;p.speed=4*d;}
  else if(u<5.75){p.x=4-2*(u-4);p.face=Math.PI;p.speed=2;}
  else if(u<6.25){const d=u-5.75;p.x=.5-2*d+2*d*d;p.face=Math.PI;p.speed=2-4*d;}
  else {p.x=0;p.face=Math.PI+(u-6.25)*Math.PI/1.75;p.speed=0;}
  p.action=p.speed>.2?'jog':'idle';
 }else if(s.mode==='run-pass'||s.mode==='run-shoot'){
  // Full locomotion -> planted strike -> follow-through -> locomotion,
  // including exactly timed contact so GLB baking uses the same rig state.
  const start=.75,kind=s.mode==='run-pass'?'pass':'shoot',contact=kind==='pass'?.31:.38;
  const duration=contact+.30,elapsed=t-start,speed=3.3;
  p.x=t*speed;p.z=0;p.face=0;p.speed=speed;p.vx=speed;p.vz=0;p.kickFoot=1;
  p.kickMoving=true;p.contactTime=contact;p.actionDuration=duration;
  p.action=t>=start&&elapsed<duration?kind:'run';
  p.actionElapsed=Math.max(0,elapsed);
  p.actionClock=p.action===kind?Math.max(.001,duration-elapsed):0;
  const point=rig.kickContact(p),flight=Math.max(0,elapsed-contact);
  const contactOrigin=start*speed+contact*speed+.88;
  s.ball.x=elapsed<contact?point[0]:contactOrigin+flight*(kind==='shoot'?18:9);
  s.ball.z=point[2];
  s.ball.y=elapsed<contact?.11:Math.max(.11,.11+flight*1.4-.4*flight*flight);
  return s;
 }else if(s.mode==='pass'||s.mode==='shoot'){
  const u=t%2.5,contact=s.mode==='shoot'?.38:.31;
  p.action=u<contact+.30?s.mode:'idle';p.actionElapsed=u;p.contactTime=contact;p.actionDuration=contact+.30;p.actionClock=Math.max(0,p.actionDuration-u);
  const point=rig.kickContact(p),flight=Math.max(0,u-contact),v=s.mode==='shoot'?18:9;
  s.ball.x=point[0]+flight*v;s.ball.z=point[2];s.ball.y=Math.max(.11,point[1]+flight*1.4-.4*flight*flight);return s;
 }else if(s.mode.startsWith('dive')){
  const u=t%2.5;p.diveSide=s.mode==='dive-left'?-1:1;p.diveContactTime=.34;p.actionDuration=.95;
  p.action=u<.95?'dive':'idle';p.actionElapsed=u;p.actionClock=Math.max(0,.95-u);p.saveTarget={x:0,y:1.05,z:p.diveSide*1.65};
  s.ball.x=u<.34?5*(1-u/.34):0;s.ball.y=1.05;s.ball.z=p.diveSide*1.65;
  if(u>.95){s.ball.x=6;s.ball.y=.11;}return s;
 }
 p.anim=t*p.speed*2.3;s.ball.x=p.x+1.6;s.ball.z=p.z+1.6;s.ball.y=.11;
 return s;
}
const api={create,sample};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.TribunAnimationScenarios=api;
})(typeof window!=='undefined'?window:globalThis);
