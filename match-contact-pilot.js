'use strict';
/* One live footballer pilot. Pure presentation state; Match retains sole
   authority over collision, kick release, rotation/spin and player motion. */
(function(root){
const clamp=(v,lo,hi)=>Math.min(hi,Math.max(lo,v));
const wrap=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
const supportHeight=.13,stepSeconds=.14,stepLift=.10;
const releaseKinds=new Set(['shot','pass','through','cutback','cross','long-pass']);
function supportPose(rig,pose,p,current,dt){
 const index=1-(p.kickFoot===0?0:1),leg=pose.legs[index],hip=leg.hip,face=p.face||0;
 const forward=[Math.cos(face),0,Math.sin(face)];
 const solve=target=>rig.solveLimb(hip,target,rig.ANATOMY.thigh,rig.ANATOMY.shin,forward,
  rig.LIMITS.knee.max,rig.LIMITS.knee.min);
 const canPlant=ik=>ik.error<1e-5;
 const candidate=[hip[0]+forward[0]*.08,supportHeight,hip[2]+forward[2]*.08];
 const previous=current?.index===index?current:null;
 let target,yaw,ik,plant;
 if(!previous){
  target=candidate;
  yaw=face;
  ik=solve(target);
  if(canPlant(ik))plant={index,phase:'planted',anchor:target,yaw};
 }
 if(previous?.phase==='planted'){
  target=previous.anchor;
  yaw=previous.yaw;
  ik=solve(target);
  if(canPlant(ik)&&Math.abs(wrap(face,yaw))<Math.PI/4)plant=previous;
 }
 if(!plant){
  // Keep the contact target fixed until reach or turning runs out, then
  // visibly lift the boot while transferring to a new support point.
  const step=previous?.phase==='step'?previous:{
   index,phase:'step',origin:(previous?.anchor||leg.ankle).slice(),
   yaw:previous?.yaw??face,elapsed:0
  };
  step.elapsed=Math.min(stepSeconds,step.elapsed+dt);
  const t=step.elapsed/stepSeconds,u=t*t*(3-2*t);
  target=step.origin.map((v,i)=>v+(candidate[i]-v)*u);
  target[1]+=Math.sin(Math.PI*t)*stepLift;
  yaw=step.yaw+wrap(face,step.yaw)*u;
  ik=solve(target);
  if(t===1){
   plant=canPlant(ik)?{index,phase:'planted',anchor:candidate,yaw:face}:
    {index,phase:'step',origin:ik.end.slice(),yaw,elapsed:0};
  }else plant=step;
 }
 leg.knee=ik.joint;
 leg.ankle=ik.end;
 leg.toe=[ik.end[0]+Math.cos(yaw)*.20,ik.end[1]-.075,ik.end[2]+Math.sin(yaw)*.20];
 leg.target=target;
 leg.bend=ik.bend;
 leg.stance=plant.phase==='planted';
 leg.targetError=ik.error;
 leg.footLift=ik.end[1]-supportHeight;
 return plant;
}
function create({playerId=0}={}){
 let proxy=null,tracked=null,releaseSerial=null,releaseAt=-Infinity,contactSerial=null;
 let cueSerial=0,releaseCue=null,releaseKind=null;
 let previousTime=null,previousSpeed=0,previousFace=0,brake=0,turn=0,contactCount=0;
 let support=null;
 function reset(){
  if(proxy&&root.TribunHumanoidRig)root.TribunHumanoidRig.reset(proxy);
  proxy=null;tracked=null;releaseSerial=null;releaseAt=-Infinity;contactSerial=null;
  cueSerial=0;releaseCue=null;releaseKind=null;
  previousTime=null;previousSpeed=0;previousFace=0;brake=0;turn=0;contactCount=0;
  support=null;
 }
 function observe(match,dt=1/60){
  if(!match?.players)return null;
  const p=match.players.find(x=>x.id===playerId&&x.active&&!x.referee);
  if(!p){tracked=null;support=null;return null;}
  const now=Number.isFinite(match.time)?match.time:0;
  if(previousTime!==null&&now<previousTime-.1)reset();
  if(!proxy){proxy={...p};previousTime=now;previousSpeed=p.speed||0;previousFace=p.face||0;}
  if(Math.hypot(p.x-proxy.x,p.z-proxy.z)>1.5)support=null;
  tracked=p;
  const step=previousTime===null?0:clamp(now-previousTime,0,.20);
  if(step>0){
   brake=clamp(brake*.80+Math.max(0,previousSpeed-(p.speed||0))/step*.025,0,1);
   turn=clamp(turn*.76+Math.abs(wrap(p.face||0,previousFace))/step*.09,0,1);
   previousSpeed=p.speed||0;previousFace=p.face||0;previousTime=now;
  }
  // Published cues reach the presentation clock at the same instant as the
  // ball. Keep the flight fallback for ordinary current-step Match callers.
  if(Array.isArray(match.contacts)){
   const cue=match.contacts.findLast(c=>c.id>cueSerial&&c.kind==='release'&&c.playerId===playerId&&
    c.actor?.action!=='header'&&releaseKinds.has(c.kickKind)&&Number.isFinite(c.time)&&c.time<=now+1e-8);
   if(cue){
    cueSerial=cue.id;
    if(now-cue.time<.30){
     releaseAt=cue.time;contactSerial=cue.flightId;releaseCue=cue;releaseKind=cue.kickKind;contactCount++;
    }
   }
  }else if(releaseSerial!==match.releaseSerial){
   const flight=match.flight,fromId=flight?.from?.id??flight?.fromId;
   releaseSerial=match.releaseSerial;
   if(p.action!=='header'&&flight&&releaseKinds.has(flight.kind)&&fromId===playerId){
    releaseAt=now;contactSerial=releaseSerial;releaseCue=null;releaseKind=flight.kind;contactCount++;
   }
  }
  const shot=p.action==='shoot'||p.action==='pass',inRecovery=now>=releaseAt&&now-releaseAt<.30&&contactSerial!==null;
  // Reuse a stable visual-only actor so foot lock survives consecutive frames.
  const keys=Object.keys(proxy);for(const key of keys)if(!(key in p))delete proxy[key];
  Object.assign(proxy,p);
  proxy.pilotBrake=brake;proxy.pilotTurn=turn;
  proxy.pilotPlant=inRecovery||shot&&p.actionClock>0;
  if(inRecovery){
   const contact=Math.max(.1,releaseCue?.actor?.contactTime||p.contactTime||.38),follow=now-releaseAt;
   proxy.action=releaseKind==='shot'?'shoot':'pass';
   proxy.contactTime=contact;proxy.actionElapsed=contact+follow;
   proxy.actionDuration=contact+.30;proxy.actionClock=Math.max(.001,.30-follow);
   // The single pilot plants its opposite foot even for a running strike.
   proxy.kickMoving=false;
  }else if(shot&&p.actionClock>0){
   proxy.kickMoving=false;
  }
  const rig=root.TribunHumanoidRig;
  if(rig&&(dt>0||step>0)){
   const elapsed=clamp(dt||step,0,.1),pose=rig.update(proxy,elapsed);
   // Only the visual proxy receives the constraint. Ball contacts and the
   // fixed-step actor keep using the ordinary rig and match state.
   support=proxy.pilotPlant&&pose?.legs&&rig.solveLimb?supportPose(rig,pose,proxy,support,elapsed):null;
  }
  return {player:p,visual:proxy,release:inRecovery,releaseSerial:contactSerial,releaseCue:inRecovery?releaseCue:null,
   contactCount,brake,turn,clip:inRecovery||shot&&p.actionClock>0?'shoot':
    (p.speed||0)<.4?'idle':'run'};
 }
 function state(){return {playerId,ready:!!tracked,releaseSerial:contactSerial,contactCount,
  brake,turn,releaseAt,visual:proxy,support:support&&{index:support.index,phase:support.phase,
   anchor:support.anchor?.slice()??null}};}
 return {observe,reset,state,playerId};
}
const api={create};root.TribunContactPilot=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
