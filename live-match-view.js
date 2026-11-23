'use strict';

(function(){
const clamp=(value,min,max)=>Math.min(max,Math.max(min,value));
const mix=(from,to,weight)=>from+(to-from)*weight;
const yaw=(from,to,weight)=>from+Math.atan2(Math.sin(to-from),Math.cos(to-from))*weight;
const position=(p)=>({x:p.x,y:p.y,z:p.z,face:p.face});

// The displayed positions blend between server samples. Rules, clocks, badges
// and the kick chooser always read the latest authoritative state.
class LiveMatchView {
 constructor(){
  this.actors=new Map();
  this.queue=[];
  this.eventSerial=0;
  this.visualBall={};
 }
 ingest(snapshot,now){
  const {players,ball,ownerId,direction,tactics,...state}=snapshot;
  const delta=this.time===undefined?0:snapshot.time-this.time;
  const eventCount=Math.max(0,snapshot.eventSerial-this.eventSerial);
  if(eventCount)this.queue.push(...snapshot.events.slice(-eventCount));
  Object.assign(this,state);
  this.t=tactics;
  this.attackDirections=direction;
  this.ball=ball;
  this.blendMs=this.pendingManagerKick||this.done?0:clamp(delta*1000,0,230);
  this.arrived=now;
  this.ballStart=position(this.visualBall);
  Object.assign(this.visualBall,ball);
  this.players=players.map(row=>{
   let actor=this.actors.get(row.id);
   if(!actor){
    actor={display:{},start:position(row),target:row};
    this.actors.set(row.id,actor);
   }else actor.start=position(actor.display);
   const display=actor.display;
   for(const field of Object.keys(actor.target))if(!Object.hasOwn(row,field))delete display[field];
   Object.assign(display,row);
   actor.target=row;
   return display;
  });
  this.owner=this.actors.get(ownerId)?.display??null;
  this.sample(now,0);
 }
 sample(now,dt){
  const weight=this.blendMs?clamp((now-this.arrived)/this.blendMs,0,1):1;
  const interpolate=(start,end,key)=>Number.isFinite(start[key])&&Math.abs(end[key]-start[key])<5?mix(start[key],end[key],weight):end[key];
  for(const {display,start,target} of this.actors.values()){
   display.x=interpolate(start,target,'x');
   display.z=interpolate(start,target,'z');
   display.face=yaw(start.face,target.face,weight);
   // Server skill clocks are sampled at network intervals. Extrapolate for
   // presentation only between packets; authoritative snapshot is unchanged.
   const age=clamp((now-this.arrived)/1000,0,.4);
   for(const clock of ['feintClock','footTouch','feintResponseClock','wallPassClock']){
    if(Number.isFinite(target[clock]))display[clock]=Math.max(0,target[clock]-age);
   }
   if(display.active)window.TribunHumanoidRig.update(display,dt);
  }
  for(const axis of ['x','y','z'])this.visualBall[axis]=interpolate(this.ballStart,this.ball,axis);
 }
 clockState(){return this.clock;}
 direction(team){return this.attackDirections[team];}
 drain(){return this.queue.splice(0);}
}
window.TribunLiveMatchView=LiveMatchView;
})();
