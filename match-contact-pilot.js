'use strict';
/* One live footballer pilot. Pure presentation state; Match retains sole
   authority over collision, kick release, rotation/spin and player motion. */
(function(root){
const clamp=(v,lo,hi)=>Math.min(hi,Math.max(lo,v));
const wrap=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
function create({playerId=0}={}){
 let proxy=null,tracked=null,releaseSerial=null,releaseAt=-Infinity,contactSerial=null;
 let previousTime=null,previousSpeed=0,previousFace=0,brake=0,turn=0,contactCount=0;
 function reset(){
  if(proxy&&root.TribunHumanoidRig)root.TribunHumanoidRig.reset(proxy);
  proxy=null;tracked=null;releaseSerial=null;releaseAt=-Infinity;contactSerial=null;
  previousTime=null;previousSpeed=0;previousFace=0;brake=0;turn=0;contactCount=0;
 }
 function observe(match,dt=1/60){
  if(!match?.players)return null;
  const p=match.players.find(x=>x.id===playerId&&x.active&&!x.referee);
  if(!p){tracked=null;return null;}
  const now=Number.isFinite(match.time)?match.time:0;
  if(previousTime!==null&&now<previousTime-.1)reset();
  if(!proxy){proxy={...p};previousTime=now;previousSpeed=p.speed||0;previousFace=p.face||0;}
  tracked=p;
  const step=previousTime===null?0:clamp(now-previousTime,0,.20);
  if(step>0){
   brake=clamp(brake*.80+Math.max(0,previousSpeed-(p.speed||0))/step*.025,0,1);
   turn=clamp(turn*.76+Math.abs(wrap(p.face||0,previousFace))/step*.09,0,1);
   previousSpeed=p.speed||0;previousFace=p.face||0;previousTime=now;
  }
  // Source may be a physics Match or the synchronized server snapshot.
  const flight=match.flight,fromId=flight?.from?.id??flight?.fromId;
  if(releaseSerial!==match.releaseSerial){
   releaseSerial=match.releaseSerial;
   if(flight&&(flight.kind==='shot'||flight.kind==='pass'||flight.kind==='cross'||flight.kind==='long-pass')&&fromId===playerId){
    releaseAt=now;contactSerial=releaseSerial;contactCount++;
   }
  }
  const shot=p.action==='shoot'||p.action==='pass',inRecovery=now>=releaseAt&&now-releaseAt<.30&&contactSerial!==null;
  // Reuse a stable visual-only actor so foot lock survives consecutive frames.
  const keys=Object.keys(proxy);for(const key of keys)if(!(key in p))delete proxy[key];
  Object.assign(proxy,p);
  proxy.pilotBrake=brake;proxy.pilotTurn=turn;
  if(inRecovery){
   const contact=Math.max(.1,p.contactTime||.38),follow=now-releaseAt;
   proxy.action=p.action==='pass'?'pass':'shoot';
   proxy.contactTime=contact;proxy.actionElapsed=contact+follow;
   proxy.actionDuration=contact+.30;proxy.actionClock=Math.max(.001,.30-follow);
   // The single pilot plants its opposite foot even for a running strike.
   proxy.kickMoving=false;
  }else if(shot&&p.actionClock>0){
   proxy.kickMoving=false;
  }
  const rig=root.TribunHumanoidRig;
  if(rig&&dt>0)rig.update(proxy,clamp(dt,0,.1));
  return {player:p,visual:proxy,release:inRecovery,releaseSerial:contactSerial,
   contactCount,brake,turn,clip:inRecovery||shot&&p.actionClock>0?'shoot':
    (p.speed||0)<.4?'idle':'run'};
 }
 function state(){return {playerId,ready:!!tracked,releaseSerial:contactSerial,contactCount,
  brake,turn,releaseAt,visual:proxy};}
 return {observe,reset,state,playerId};
}
const api={create};root.TribunContactPilot=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
