'use strict';
/* Pure visual angular integration. Never writes to football-sim's ball or RNG. */
(function(root){
const norm=v=>{const d=Math.hypot(...v)||1;return v.map(x=>x/d)};
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const rotate=(v,axis,theta)=>{
 const c=Math.cos(theta),s=Math.sin(theta),n=norm(axis),k=v.reduce((t,x,i)=>t+x*n[i],0);
 const w=cross(n,v);return v.map((x,i)=>x*c+w[i]*s+n[i]*k*(1-c));
};
function create(){
 let marks=[norm([.45,.76,.46]),norm([-.79,.24,.57])],last=null;
 const reset=()=>{marks=[norm([.45,.76,.46]),norm([-.79,.24,.57])];last=null;};
 function sample(ball,dt=1/60){
  if(!ball||!Number.isFinite(ball.x)||!Number.isFinite(ball.z)||!Number.isFinite(ball.y))return marks;
  // A paused/inspection render must be read-only, including repeated gl.finish().
  if(!Number.isFinite(dt)||dt<=0)return marks;
  dt=Math.min(dt,.075);
  const speed=Math.hypot(ball.vx||0,ball.vz||0),ground=ball.y<=.16;
  // Spin is the *same scalar* written by Match.release() and used by ball
  // aerodynamics. Side spin rotates the visible seams about the vertical.
  const curl=Number.isFinite(ball.spin)?ball.spin:0;
  const yaw=curl*Math.PI*2*dt;
  if(Math.abs(yaw)>0)marks=marks.map(v=>rotate(v,[0,1,0],yaw));
  // Rolling rotation must not treat a stationary lofted football as rolling.
  if(ground&&speed>.05){
   const angle=Math.min(24,speed/.11)*dt;
   marks=marks.map(v=>rotate(v,[-ball.vz,0,ball.vx],angle));
  }else if(!ground&&speed>.05){
   const tumble=Math.min(8,speed*.1)*dt;
   marks=marks.map(v=>rotate(v,[-ball.vz,0,ball.vx],tumble));
  }
  last={x:ball.x,z:ball.z,y:ball.y};
  return marks;
 }
 return {sample,reset,orientation:()=>marks.map(v=>v.slice())};
}
const api={create,rotate};root.TribunBallVisual=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
