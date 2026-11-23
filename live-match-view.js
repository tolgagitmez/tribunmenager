'use strict';

(function(){
const clamp=(value,min,max)=>Math.min(max,Math.max(min,value));
const mix=(from,to,weight)=>from+(to-from)*weight;
const yaw=(from,to,weight)=>from+Math.atan2(Math.sin(to-from),Math.cos(to-from))*weight;
const epsilon=1e-6;
const poseFields=window.TribunContactEvents?.poseFields??[
 'face','vx','vz','speed','action','actionClock','actionDuration','actionElapsed',
 'kickFoot','kickMoving','contactTime','diveSide','diveContactTime','saveTarget','catchPoint'
];

function bracket(frames,time){
 for(let i=1;i<frames.length;i++){
  const later=frames[i];
  if(later.time>time+epsilon){
   const earlier=frames[i-1];
   return {earlier,later,u:clamp((time-earlier.time)/(later.time-earlier.time),0,1)};
  }
 }
 const last=frames.at(-1);
 return {earlier:last,later:last,u:1};
}

function blend(earlier,later,u,key){
 const a=earlier[key],b=later[key];
 return Number.isFinite(a)&&Number.isFinite(b)?mix(a,b,u):b;
}

function applyPose(display,frames,time){
 const {earlier,later,u}=bracket(frames,time),a=earlier.value,b=later.value;
 // Untagged movements can still change action between two packets. The
 // target actor's elapsed time tells us when its current action began.
 const began=later.time-(b.actionElapsed||0);
 const atContact=earlier.kind&&time<=earlier.time+epsilon;
 const state=!atContact&&a.action!==b.action&&b.actionClock>0&&time>=began-epsilon?later:earlier;
 const p=state.value,age=time-state.time;
 for(const field of poseFields){
  if(p[field]===undefined)delete display[field];
  else display[field]=p[field];
 }
 for(const key of ['x','z','speed','vx','vz'])display[key]=blend(a,b,u,key);
 display.face=yaw(a.face,b.face,u);
 if(p.actionClock>0){
  display.actionElapsed=Math.max(0,(p.actionElapsed||0)+age);
  display.actionClock=Math.max(0,p.actionClock-age);
  if(display.actionClock===0)display.action='idle';
 }
 if(p.receiveClock>0)display.receiveClock=Math.max(0,p.receiveClock-age);
 if(p.footTouch>0)display.footTouch=Math.max(0,p.footTouch-age);
 if(p.holdClock>0)display.holdClock=Math.max(0,p.holdClock-age);
}

// Only presentation is buffered; rules, scores and the kick chooser use
// authoritative snapshots immediately. Both pose and ball are drawn on the
// same clock, with real contact keyframes between network packets.
class LiveMatchView {
 constructor(){
  this.actors=new Map();
  this.queue=[];
  this.eventSerial=0;
  this.visualBall={};
  this.presentation={};
 }
 ingest(snapshot,now){
  if(this.time!==undefined&&(snapshot.time+epsilon<this.time||snapshot.eventSerial<this.eventSerial))return;
  const {players,ball,ownerId,direction,tactics,contacts=[],...state}=snapshot;
  const first=this.time===undefined;
  const sameTime=this.time===snapshot.time;
  const priorPeriod=this.period;
  const priorKickId=this.pendingManagerKick?.id;
  const wasDone=this.done;
  if(!first)this.sample(now,0);
  const eventCount=Math.max(0,snapshot.eventSerial-this.eventSerial);
  if(eventCount)this.queue.push(...snapshot.events.slice(-eventCount));
  Object.assign(this,state);
  this.t=tactics;
  this.attackDirections=direction;
  this.ball=ball;
  this.owner=players.find(p=>p.id===ownerId)??null;
  this.contacts=contacts;
  const changedPeriod=this.period!==priorPeriod;
  const changedKick=this.pendingManagerKick?.id!==priorKickId;
  if(sameTime&&!changedPeriod&&!changedKick&&this.done===wasDone)return;
  const from=first?this.time:this.presentationTime;
  const jumped=first||changedPeriod||this.pendingManagerKick||this.done||this.time-from>.8;
  this.blendMs=jumped?0:clamp((this.time-from)*1000,0,230);
  this.arrived=now;
  this.startTime=this.blendMs?from:this.time;

  const inSegment=this.segmentContacts=contacts.filter(cue=>cue.time>this.startTime+epsilon&&cue.time<=this.time+epsilon);
  const endpoint=(value,kind)=>({time:this.time,value,kind});
  const frames=(initial,points,key,final,kind)=>[
   ...(this.blendMs?[{time:this.startTime,value:initial},...points.map(point=>({time:point.time,value:point[key],kind:point.kind}))]:[]),
   endpoint(final,kind)
  ];
  const replacedBall=this.restart&&this.priorRestartId!==this.restart.id&&
   Math.hypot(ball.x-this.visualBall.x,ball.z-this.visualBall.z)>5;
  this.priorRestartId=this.restart?.id;
  this.ballFrames=replacedBall&&!inSegment.length?[endpoint(ball)]:
   frames({...this.visualBall},inSegment,'ball',ball,replacedBall?'placement':undefined);

  this.players=players.map(row=>{
   let actor=this.actors.get(row.id);
   if(!actor){
    actor={display:{},target:{}};
    this.actors.set(row.id,actor);
   }
   const display=actor.display;
   actor.frames=Object.hasOwn(display,'x')
    ?frames({...display},inSegment.filter(cue=>cue.playerId===row.id),'actor',row)
    :[endpoint(row)];
   for(const field of Object.keys(actor.target))if(!Object.hasOwn(row,field))delete display[field];
   Object.assign(display,row);
   actor.target=row;
   return display;
  });
  // A frozen prompt or final whistle still needs one fresh skeletal pose.
  // The rig otherwise reuses its last pose when sampled with a zero delta.
  this.sample(now,!first&&(jumped||sameTime)?1/60:0);
 }
 sample(now,dt){
  if(!this.ballFrames)return;
  const u=this.blendMs?clamp((now-this.arrived)/this.blendMs,0,1):1;
  const previous=this.presentationTime??this.startTime;
  const target=Math.max(previous,mix(this.startTime,this.time,u));
  // A slow frame still draws one exact contact before catching up. Ingest
  // samples with dt=0 cannot consume a contact before a frame can display it.
  const contact=this.segmentContacts.find(c=>c.time>previous+epsilon&&c.time<=target+epsilon);
  const time=this.presentationTime=contact?(dt>0?contact.time:previous):target;
  for(const {display,frames} of this.actors.values()){
   applyPose(display,frames,time);
   if(display.active)window.TribunHumanoidRig.update(display,dt);
  }
  const {earlier,later,u:weight}=bracket(this.ballFrames,time);
  const a=earlier.value,b=later.value;
  const ballWeight=later.kind==='placement'?0:weight;
  for(const key of ['x','y','z'])this.visualBall[key]=blend(a,b,ballWeight,key);
  const impact=later.kind==='release'||later.kind==='receive'||later.kind==='keeper-contact';
  for(const key of ['vx','vy','vz'])this.visualBall[key]=blend(a,b,impact?0:ballWeight,key);
  if(a.spin===undefined&&(b.spin===undefined||impact))delete this.visualBall.spin;
  else this.visualBall.spin=mix(a.spin||0,b.spin||0,impact?0:ballWeight);
  const activeFlight=this.flight&&time>=this.time-(this.flight.age??0)-epsilon;
  Object.assign(this.presentation,{
   time,players:this.players,ball:this.visualBall,
   flight:activeFlight?{...this.flight,age:Math.max(0,(this.flight.age??0)-(this.time-time))}:null,
   releaseSerial:this.releaseSerial,contacts:this.contacts.filter(cue=>cue.time<=time+epsilon)
  });
 }
 clockState(){return this.clock;}
 direction(team){return this.attackDirections[team];}
 drain(){
  const pending=this.queue.findIndex(event=>event.time>this.presentationTime+epsilon);
  return this.queue.splice(0,pending<0?this.queue.length:pending);
 }
}
window.TribunLiveMatchView=LiveMatchView;
})();
