'use strict';

(function(){
const ground=.045;
const radians=Math.PI/180;
const clamp=(value,min,max)=>Math.min(max,Math.max(min,value));

function project(matrix,x,z,width,height){
 const depth=matrix[3]*x+matrix[7]*ground+matrix[11]*z+matrix[15];
 if(depth<=.2)return null;
 return [
  (.5+.5*(matrix[0]*x+matrix[4]*ground+matrix[8]*z+matrix[12])/depth)*width,
  (.5-.5*(matrix[1]*x+matrix[5]*ground+matrix[9]*z+matrix[13])/depth)*height
 ];
}

// Solve the two projection equations for x/z on the same grass plane as the arrow.
function unproject(matrix,u,v){
 const a=matrix[0]-u*matrix[3],b=matrix[8]-u*matrix[11];
 const c=matrix[1]-v*matrix[3],d=matrix[9]-v*matrix[11];
 const x=u*(matrix[7]*ground+matrix[15])-matrix[4]*ground-matrix[12];
 const z=v*(matrix[7]*ground+matrix[15])-matrix[5]*ground-matrix[13];
 const determinant=a*d-b*c;
 if(Math.abs(determinant)<1e-8)return null;
 const point={x:(x*d-b*z)/determinant,z:(a*z-x*c)/determinant};
 return matrix[3]*point.x+matrix[7]*ground+matrix[11]*point.z+matrix[15]>.2?point:null;
}

class KickAim{
 constructor(canvas,scene,onAim){
  this.canvas=canvas;
  this.scene=scene;
  this.onAim=onAim;
  this.context=canvas.getContext('2d');
  canvas.addEventListener('pointerdown',event=>{
   if(event.button!==0||this.pointer!==undefined)return;
   this.pointer=event.pointerId;
   canvas.setPointerCapture(event.pointerId);
   this.aim(event);
  });
  canvas.addEventListener('pointermove',event=>{
   if(this.pointer===event.pointerId)this.aim(event);
  });
  canvas.addEventListener('lostpointercapture',event=>{
   if(this.pointer===event.pointerId)this.pointer=undefined;
  });
 }
 show(opportunity,input,stage){
  this.opportunity=opportunity;
  this.input=input;
  this.scene.managerKickView=opportunity;
  this.canvas.hidden=stage!==1;
  if(this.canvas.hidden)this.releasePointer();
  else this.draw();
 }
 releasePointer(){
  if(this.pointer!==undefined&&this.canvas.hasPointerCapture(this.pointer))this.canvas.releasePointerCapture(this.pointer);
  this.pointer=undefined;
 }
 hide(){
  this.releasePointer();
  this.opportunity=null;
  this.canvas.hidden=true;
 }
 length(power){
  const range=clamp(this.opportunity.range||22,10,42);
  return range*(.22+.98*power);
 }
 aim(event){
  if(!this.opportunity||this.canvas.hidden)return;
  const rect=this.canvas.getBoundingClientRect();
  if(!rect.width||!rect.height)return;
  const {matrix}=this.scene.managerKickCamera(rect.width/rect.height);
  const point=unproject(matrix,2*(event.clientX-rect.left)/rect.width-1,1-2*(event.clientY-rect.top)/rect.height);
  if(!point)return;
  const {origin,angle}=this.opportunity,dx=point.x-origin.x,dz=point.z-origin.z;
  const distance=Math.hypot(dx,dz);
  if(distance<.9)return;
  const delta=Math.atan2(dz,dx)-angle;
  const direction=Math.atan2(Math.sin(delta),Math.cos(delta))/radians;
  const power=100*clamp((distance-this.length(0))/(this.length(1)-this.length(0)),0,1);
  this.onAim(Math.round(direction),Math.round(power));
 }
 draw(){
  if(!this.context||this.canvas.hidden||!this.opportunity)return;
  const {width,height}=this.canvas.getBoundingClientRect();
  if(!width||!height)return;
  const density=Math.min(window.devicePixelRatio||1,2);
  const w=Math.round(width*density),h=Math.round(height*density);
  if(this.canvas.width!==w||this.canvas.height!==h){
   this.canvas.width=w;
   this.canvas.height=h;
  }
  const {matrix}=this.scene.managerKickCamera(width/height);
  const {origin,angle}=this.opportunity,ctx=this.context;
  const start=project(matrix,origin.x,origin.z,width,height);
  ctx.setTransform(w/width,0,0,h/height,0,0);
  ctx.clearRect(0,0,width,height);
  if(!start)return;
  const heading=angle+this.input.direction*radians;
  const power=clamp(this.input.power/100,0,1);
  const endAt=(a,d)=>project(matrix,origin.x+Math.cos(a)*d,origin.z+Math.sin(a)*d,width,height);
  let length=this.length(power),end=endAt(heading,length);
  while(length>1.1&&(!end||end[0]<14||end[0]>width-14||end[1]<14||end[1]>height-14)){
   length*=.82;
   end=endAt(heading,length);
  }
  if(!end)return;
  const line=(a,b)=>{ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();};
  ctx.lineCap='round';
  ctx.strokeStyle='#ebffbfaa';
  ctx.lineWidth=1.2;
  ctx.setLineDash([4,5]);
  for(const side of [-1,1]){
   const edge=endAt(heading+side*.16,length);
   if(edge)line(start,edge);
  }
  ctx.setLineDash([]);
  const dir=Math.atan2(end[1]-start[1],end[0]-start[0]);
  const arrowHead=[-.55,.55].map(a=>[end[0]-15*Math.cos(dir+a),end[1]-15*Math.sin(dir+a)]);
  ctx.strokeStyle='#14200c';
  ctx.lineWidth=9;
  line(start,end);
  ctx.strokeStyle='#d8ff65';
  ctx.lineWidth=5;
  line(start,end);
  for(const wing of arrowHead)line(end,wing);
  ctx.beginPath();
  ctx.arc(...start,5,0,2*Math.PI);
  ctx.fillStyle='#f2ffe0';
  ctx.fill();
 }
}
window.TribunManagerKickAim=KickAim;
})();
