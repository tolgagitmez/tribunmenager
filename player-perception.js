'use strict';
/* Local player observations. Queries never inspect the live opposition. */
(function(root){
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const angle=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
const number=(v,fallback=0)=>Number.isFinite(v)?v:fallback;
const live=p=>p&&p.active!==false&&!p.referee&&(p.team===0||p.team===1)&&Number.isFinite(p.id);
const key=p=>`${p.team}:${p.rosterId??p.id}`;
const skill=p=>clamp(number(p.vision,number(p.skill,75)),30,100);
const limits=p=>({range:clamp(43+(skill(p)-70)*.22,35,50),halfAngle:clamp(1.65+(skill(p)-70)*.003,1.53,1.74),ttl:clamp(1.05+(skill(p)-50)*.011,.9,1.6),period:clamp(1.35-(skill(p)-50)*.012,.75,1.55)});
const physical=['skill','pace','agility','stamina','energy','tackling','dribbling','heading','vision','composure','passing','shooting','weakFoot','preferredFoot'];
const clocks=['touchClock','duelRecovery','tackleClock','receiveClock'];
function clear(p,time=0,epoch=null){
 const t=number(time),id=Math.abs(number(p.id));
 p.perception={version:1,actorKey:key(p),epoch,lastUpdate:t,nextScanAt:t+.28+(id%7)*.083,scanUntil:t,scanSide:id%2?1:-1,headYaw:0,records:{}};
 return p.perception;
}
function reset(players,time=0,epoch=null){for(const p of players)if(live(p))clear(p,time,epoch);else if(p)p.perception=null;}
function snapshot(p,time,source){
 const out={id:p.id,team:p.team,role:p.role,rosterId:p.rosterId??p.id,active:true,x:p.x,z:p.z,vx:number(p.vx),vz:number(p.vz),face:number(p.face),speed:Math.hypot(number(p.vx),number(p.vz)),seenAt:time,source};
 for(const k of physical)if(Number.isFinite(p[k]))out[k]=p[k];
 for(const k of clocks)out[k]=Math.max(0,number(p[k]));
 return out;
}
function update(players,time,dt=1/60,options={}){
 if(!Number.isFinite(time))return;
 const active=players.filter(live),byId=new Map(active.map(p=>[p.id,p])),epoch=options.epoch??null;
 for(const p of players){
  if(!live(p)){if(p)p.perception=null;continue;}
  let state=p.perception;
  if(!state||state.version!==1||state.actorKey!==key(p)||state.epoch!==epoch||time<state.lastUpdate-1e-8)state=clear(p,time,epoch);
  const config=limits(p),advancing=number(dt)>0&&time>state.lastUpdate;
  // A head turn is an observation window, never a change to the body's pose.
  const occupied=p.duelRecovery>0||p.receiveClock>0||p.actionClock>0&&['pass','through','cross','cutback','long-pass','shot','shoot','clearance','tackle','dive','receive'].includes(p.action);
  const scanning=options.scanAllowed!==false&&!occupied;
  if(advancing&&time>=state.nextScanAt){
   if(scanning){state.scanSide*=-1;state.headYaw=state.scanSide*1.55;state.scanUntil=time+.16;state.nextScanAt=time+config.period;}
   else state.nextScanAt=time+.15;
  }
  if(!scanning||time>=state.scanUntil)state.headYaw=0;
  const facing=number(p.face),look=facing+state.headYaw;
  for(const id of Object.keys(state.records)){
   const q=byId.get(+id),record=state.records[id];
   // Identity/activity are lifecycle data. Do not read a hidden actor's position.
   if(!q||q.team===p.team||record.rosterId!==(q.rosterId??q.id)||time-record.seenAt>config.ttl)delete state.records[id];
  }
  for(const q of active){
   if(q.team===p.team||!Number.isFinite(q.x)||!Number.isFinite(q.z))continue;
   const dx=q.x-p.x,dz=q.z-p.z,distance=Math.hypot(dx,dz),heading=Math.atan2(dz,dx);
   const contact=distance<=1.65,front=distance<=config.range&&Math.abs(angle(heading,facing))<=config.halfAngle;
   const scanned=state.headYaw!==0&&distance<=config.range*.88&&Math.abs(angle(heading,look))<=config.halfAngle;
   if(contact||front||scanned)state.records[q.id]=snapshot(q,time,contact?'contact':front?'vision':'scan');
  }
  state.lastUpdate=time;
 }
}
function rivals(p,time){
 const state=p?.perception;if(!live(p)||!state||state.version!==1||state.actorKey!==key(p)||!Number.isFinite(time)||time<state.lastUpdate-1e-8)return [];
 const ttl=limits(p).ttl,result=[];
 for(const record of Object.values(state.records)){
  const age=time-record.seenAt;if(age<0||age>ttl)continue;
  // Stale velocity contributes a bounded displacement. It cannot track a
  // hidden change of direction or extrapolate indefinitely behind the player.
  const horizon=.4,decay=Math.exp(-age/horizon),travel=horizon*(1-decay);
  const out={...record,x:clamp(record.x+record.vx*travel,-53,53),z:clamp(record.z+record.vz*travel,-34.5,34.5),vx:record.vx*decay,vz:record.vz*decay,speed:Math.hypot(record.vx,record.vz)*decay,age,confidence:Math.max(0,1-age/ttl),uncertainty:.12+age*(.85+Math.hypot(record.vx,record.vz)*.1)};
  for(const k of clocks)out[k]=Math.max(0,number(record[k])-age);
  result.push(out);
 }
 return result.sort((a,b)=>a.id-b.id);
}
const api={update,rivals,clear,reset,limits,contactRadius:1.65};
if(typeof module!=='undefined'&&module.exports)module.exports=api;root.TribunPerception=api;
})(typeof window!=='undefined'?window:globalThis);
