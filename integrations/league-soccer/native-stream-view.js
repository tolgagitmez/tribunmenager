'use strict';
// Read-only rendering of due native frames. Never runs football AI.
(function(root){
const Replay=typeof module!=='undefined'&&module.exports?require('./native-replay.js'):root.TribunNativeReplay;
const clamp=(x,a,b)=>Math.min(b,Math.max(a,x)),mix=(a,b,t)=>a+(b-a)*t;
const yaw=(a,b,t)=>a+Math.atan2(Math.sin(b-a),Math.cos(b-a))*t;
const point=v=>({x:v[0]*52/55,y:v[2],z:-v[1]*34/36});
const velocity=v=>({vx:v[0]*52/55,vy:v[2],vz:-v[1]*34/36});
function applyPresentation(actor,source,priorFrame,frame,priorTarget,target,enabled,rig){
 const span=priorFrame?frame.elapsedMs-priorFrame.elapsedMs:0;
 const valid=!!(enabled&&priorFrame&&priorTarget&&span>=50&&span<=250&&
  !priorFrame.done&&!frame.done&&priorFrame.inPlay===true&&frame.inPlay===true&&!priorFrame.setPiece&&!frame.setPiece&&
  source.goalkeeper!==true&&Math.hypot(target.x-priorTarget.x,target.z-priorTarget.z)<=2);
 const height=source.heightMetres,hasHeight=Number.isFinite(height)&&height>=1.45&&height<=2.15;
 const oldScale=actor.nativeAnatomy?.scale??1,scale=enabled&&hasHeight?height/1.88:1;
 if(oldScale!==scale||(actor.nativeFootPlant===true)!==valid)rig?.reset(actor);
 if(!enabled){
  for(const key of ['nativeAnatomy','nativeBodyBalance','nativeFootPlant','nativeMotionMatch','nativeMotionIdentity','nativeGait','nativeBlend'])delete actor[key];
  return;
 }
 actor.nativeAnatomy={height:hasHeight?height:null,scale,preferredFoot:'unknown'};
 let ax=0,az=0;
 if(valid){ax=(target.vx-priorTarget.vx)/(span/1000);az=(target.vz-priorTarget.vz)/(span/1000);const mag=Math.hypot(ax,az),factor=mag>15?15/mag:1;ax*=factor;az*=factor;}
 actor.nativeBodyBalance={ax,az,valid};actor.nativeFootPlant=valid;actor.nativeMotionMatch=valid;actor.nativeBlend=valid;
 const c=source.motionIdentity;
 actor.nativeMotionIdentity=valid&&c?{agility:clamp(c.agility,0,1),velocity:clamp(c.velocity,0,1),
  acceleration:clamp(c.acceleration,0,1),balance:clamp(c.balance,0,1),dribble:clamp(c.dribble,0,1),
  control:clamp(c.control,0,1),freshness:clamp(c.fatigueFactor,0,1)}:null;
 const speed=actor.speed,prior=actor.nativeGait||'idle';
 actor.nativeGait=speed<(prior==='idle'?.35:.20)?'idle':speed>(prior==='sprint'?5.3:5.8)?'sprint':
  speed>(['run','sprint'].includes(prior)?2.4:2.8)?'run':speed>(['jog','run','sprint'].includes(prior)?1.1:1.4)?'jog':'walk';
 if(valid)actor.action=actor.nativeGait;
}
function create(rig,{advancedPresentation=false}={}){
 let actors=new Map(),players=[],ball=null,ballFrom=null,ballTo=null,received=0,sequence=-1,metadata=null,blendMs=0,lastFrame=null;
 function reset(){for(const a of actors.values())rig?.reset(a.actor);actors.clear();players=[];ball=null;ballFrom=null;ballTo=null;sequence=-1;metadata=null;lastFrame=null;}
 function ingest(data,now){
  if(data?.engine!=='league-soccer'||data.authoritative!==false||!data.frame||!Number.isSafeInteger(data.sequence)||data.sequence<0)return false;
  if(data.sequence<sequence)return false;
  if(data.sequence===sequence){metadata=data;return true;}
  const f=Replay.parse(JSON.stringify(data.frame))[0];
  if(f.done&&data.phase!=='finished')throw Error('Erken maç sonucu');
  const names=new Map((data.players||[]).map(p=>[p.nativeId,p]));
  const gap=sequence<0?Infinity:now-received;
  blendMs=gap>1000||f.done?0:clamp(gap,80,200);
  received=now;sequence=data.sequence;metadata=data;
  const next=new Set();
  players=f.players.map((p,i)=>{
   let a=actors.get(p.id);
   if(!a||a.actor.team!==p.team||a.actor.databaseId!==p.databaseId){
    if(a)rig?.reset(a.actor);
    a={actor:{id:p.id,team:p.team,databaseId:p.databaseId},target:null};actors.set(p.id,a);
   }
   const name=names.get(p.databaseId),v=velocity(p.velocity),pos=point(p.position),face=Math.atan2(-p.direction[1],p.direction[0]);
   const target={...pos,...v,face};
   const prior=a.target?{x:a.actor.x,z:a.actor.z,face:a.actor.face}:target;
   a.from=Math.hypot(prior.x-target.x,prior.z-target.z)<=5?prior:target;
   const previousTarget=a.target;
   a.target=target;
   Object.assign(a.actor,{active:true,index:name?.slot??i%11,num:name?.number??i%11+1,name:name?.name||'Oyuncu '+p.id,role:p.goalkeeper?'GK':'FIELD',speed:Math.hypot(v.vx,v.vz),action:Math.hypot(v.vx,v.vz)>.25?'run':'idle',actionClock:0,selected:p.uniquePossession===true});
   a.source=p;
   applyPresentation(a.actor,p,lastFrame,f,previousTarget,target,advancedPresentation,rig);
   next.add(p.id);return a.actor;
  });
  for(const [id,a] of actors)if(!next.has(id)){rig?.reset(a.actor);actors.delete(id);}
  ballTo={...point(f.ball),...velocity(f.ballVelocity)};
  ballFrom=ball&&Math.hypot(ball.x-ballTo.x,ball.y-ballTo.y,ball.z-ballTo.z)<=12?{...ball}:ballTo;
  lastFrame=f;ball=ball||{...ballTo};sample(now,0);return true;
 }
 function sample(now,dt){
  if(!metadata)return null;
  const t=blendMs?clamp((now-received)/blendMs,0,1):1;
  for(const a of actors.values()){
   const p=a.actor,q=a.target;
   p.x=mix(a.from.x,q.x,t);p.z=mix(a.from.z,q.z,t);p.face=yaw(a.from.face,q.face,t);p.vx=q.vx;p.vz=q.vz;
   rig?.update(p,clamp(dt,0,.1));
  }
  for(const k of ['x','y','z'])ball[k]=mix(ballFrom[k],ballTo[k],t);
  for(const k of ['vx','vy','vz'])ball[k]=ballTo[k];
  return {players,ball,score:metadata.frame.score.slice(),matchMs:metadata.frame.matchMs,done:metadata.frame.done,stats:metadata.frame.stats||null,sequence};
 }
 function setPresentation(enabled){
  if(advancedPresentation===!!enabled)return;
  advancedPresentation=!!enabled;
  for(const a of actors.values()){
   rig?.reset(a.actor);
   applyPresentation(a.actor,a.source,null,lastFrame,null,a.target,advancedPresentation,rig);
  }
 }
 return {ingest,sample,reset,setPresentation};
}
// Only render at the chosen budget. Polling and authoritative frames are independent.
function createRenderBudget(){
 let last=null;
 return {reset(){last=null;},next(now,{hidden=false,playing=false,mode='balanced'}={}){
  if(hidden){last=null;return null;}
  if(!Number.isFinite(now))return null;
  const interval=playing?(mode==='performance'?1000/30:0):1000/15;
  if(last!==null&&now-last+0.5<interval)return null;
  const dt=last===null?0:Math.max(0,(now-last)/1000);
  last=now;return {dt:Math.min(.1,dt),measuredDt:dt};
 }};
}
const api={create,point,createRenderBudget};root.TribunNativeStreamView=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
