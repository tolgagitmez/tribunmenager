'use strict';
// Presentation only. No Match constructor, AI, inferred score or fixture persistence.
(function(root){
 const requireValue=(v,m)=>{if(!v)throw Error(m);};
 const finite=Number.isFinite, nonneg=n=>Number.isSafeInteger(n)&&n>=0;
 const vec=v=>Array.isArray(v)&&v.length===3&&v.every(finite);
 const pair=v=>Array.isArray(v)&&v.length===2&&v.every(nonneg);
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 const lerp=(a,b,t)=>a+(b-a)*t;
 const yaw=(a,b,t)=>a+Math.atan2(Math.sin(b-a),Math.cos(b-a))*t;
 const keys=['shots','onTarget','passes','completed','fouls','possessionMs'];
 const coord=v=>({x:v[0],y:v[2],z:-v[1]});
 const velocity=v=>({vx:v[0],vy:v[2],vz:-v[1]});
 function parse(text){
  requireValue(typeof text==='string'&&text.trim(),'Boş maç kaydı.');
  const frames=text.trim().split(/\r?\n/).map(JSON.parse);
  let prior;
  for(const f of frames){
   requireValue(f?.schema===1&&f.engine==='league-soccer'&&nonneg(f.elapsedMs)&&nonneg(f.matchMs)&&typeof f.done==='boolean'&&pair(f.score)&&vec(f.ball)&&vec(f.ballVelocity),'Geçersiz motor karesi.');
   requireValue(Array.isArray(f.players)&&f.players.length>=2&&f.players.length<=22,'Geçersiz oyuncu sayısı.');
   const seen=new Set(),teams=[0,0];
   for(const p of f.players){
    requireValue(p&&[0,1].includes(p.team)&&nonneg(p.id)&&!seen.has(p.id)&&vec(p.position)&&vec(p.velocity)&&vec(p.direction),'Geçersiz oyuncu verisi.');
    requireValue(p.databaseId===undefined||nonneg(p.databaseId),'Geçersiz kadro kimliği.');
    requireValue(p.goalkeeper===undefined||typeof p.goalkeeper==='boolean','Geçersiz kaleci bilgisi.');
    seen.add(p.id);teams[p.team]++;
   }
   requireValue(teams.every(n=>n>=1&&n<=11),'Geçersiz takım sayısı.');
   if(f.stats!==undefined)requireValue(f.stats&&keys.every(k=>pair(f.stats[k])),'Geçersiz maç istatistiği.');
   if(prior)requireValue(!prior.done&&f.elapsedMs>=prior.elapsedMs&&f.score.every((v,i)=>v>=prior.score[i]),'Maç kaydı sırası geçersiz.');
   prior=f;
  }
  return frames;
 }
 function rosterMap(manifest){
  if(!manifest)return new Map();
  requireValue(manifest.schema===1&&Array.isArray(manifest.teams)&&manifest.teams.length===2,'Geçersiz kadro dosyası.');
  const map=new Map(),teams=new Set();
  for(const t of manifest.teams){
   requireValue([0,1].includes(t.team)&&!teams.has(t.team)&&Array.isArray(t.players)&&t.players.length===11,'Geçersiz kadro takımı.');
   teams.add(t.team);
   for(const p of [...t.players,...(t.bench||[])]){
    requireValue(nonneg(p.nativeId)&&!map.has(p.nativeId)&&typeof p.name==='string'&&typeof p.role==='string'&&Number.isInteger(p.slot)&&p.slot>=0&&p.slot<18,'Geçersiz kadro oyuncusu.');
    map.set(p.nativeId,{...p,team:t.team});
   }
  }
  return map;
 }
 // Trace-derived presentation cues. Never infer contacts or modify positions.
 function balanceCue(a,b,source,target){
  const span=b.elapsedMs-a.elapsedMs;
  if(a.done||a.inPlay===false||b.inPlay===false||a.setPiece||b.setPiece||
     !target||target.team!==source.team||target.databaseId!==source.databaseId||
     span<50||span>200)return {ax:0,az:0,valid:false};
  const dt=span/1000,p=coord(source.position),q=coord(target.position);
  if(Math.hypot(q.x-p.x,q.z-p.z)>2||source.goalkeeper)return {ax:0,az:0,valid:false};
  const v=velocity(source.velocity),w=velocity(target.velocity);
  let ax=(w.vx-v.vx)/dt,az=(w.vz-v.vz)/dt;
  // Clamp the visual input rather than smoothing or rewriting engine velocity.
  const magnitude=Math.hypot(ax,az),scale=magnitude>15?15/magnitude:1;
  return {ax:ax*scale,az:az*scale,valid:true};
 }
 function create(frames,manifest=null,{bodyBalance=false,footPlant=false}={}){
  requireValue(Array.isArray(frames)&&frames.length,'Kayıt yok.');
  const roster=rosterMap(manifest),actors=new Map();
  if(roster.size)for(const f of frames)for(const p of f.players)requireValue(roster.get(p.databaseId)?.team===p.team,'Kadro dosyası maçla uyuşmuyor.');
  const start=frames[0].elapsedMs,end=frames.at(-1).elapsedMs,duration=end-start;
  let previousTime=null;
  function reset(rig){for(const p of actors.values())rig?.reset(p);actors.clear();previousTime=null;}
  function sample(ms,rig,dt=0){
   const time=start+clamp(ms,0,duration);
   if(previousTime!==null&&(time<previousTime||time-previousTime>500))reset(rig);
   const step=previousTime===null?0:clamp((time-previousTime)/1000,0,.1);
   previousTime=time;
   let lo=0,hi=frames.length;
   while(lo<hi){const mid=(lo+hi)>>1;if(frames[mid].elapsedMs<=time)lo=mid+1;else hi=mid;}
   const a=frames[Math.max(0,lo-1)],b=frames[lo]||a,span=b.elapsedMs-a.elapsedMs;
   const u=span>0&&span<=500?clamp((time-a.elapsedMs)/span,0,1):0;
   const next=new Map(b.players.map(p=>[p.id,p]));
   const active=new Set();
   const players=a.players.map((source,i)=>{
    const target=next.get(source.id);
    const p2=target?.team===source.team&&target.databaseId===source.databaseId?target:source;
    const metadata=roster.get(source.databaseId);
    const pos=coord(source.position),dest=coord(p2.position),v=velocity(source.velocity),v2=velocity(p2.velocity);
    const blend=Math.hypot(dest.x-pos.x,dest.z-pos.z)<=5?u:0;
    const face=Math.atan2(-source.direction[1],source.direction[0]),nextFace=Math.atan2(-p2.direction[1],p2.direction[0]);
    let actor=actors.get(source.id);
    if(!actor||actor.team!==source.team||actor.databaseId!==source.databaseId){
     if(actor)rig?.reset(actor);
     actor={id:source.id,team:source.team,databaseId:source.databaseId};actors.set(source.id,actor);
    }
    const vx=lerp(v.vx,v2.vx,blend),vz=lerp(v.vz,v2.vz,blend),speed=Math.hypot(vx,vz);
    Object.assign(actor,{active:true,index:metadata?.slot??i%11,name:metadata?.name??('Oyuncu '+source.id),rosterId:metadata?.rosterId,
     role:metadata?.role==='GK'||source.goalkeeper===true?'GK':'FIELD',num:(metadata?.slot??i%11)+1,
     x:lerp(pos.x,dest.x,blend),z:lerp(pos.z,dest.z,blend),face:yaw(face,nextFace,blend),vx,vz,speed,action:speed>.25?'run':'idle',actionClock:0,selected:false});
    if(bodyBalance||footPlant){
     const cue=balanceCue(a,b,source,target);
     if(bodyBalance)actor.nativeBodyBalance=cue;
     if(footPlant){
      const active=cue.valid&&actor.role!=='GK';
      if(actor.nativeFootPlant!==undefined&&actor.nativeFootPlant!==active)rig?.reset(actor);
      actor.nativeFootPlant=active;
     }
     // Hysteresis avoids flickering around gait boundaries. All moving
     // categories remain compatible with the existing animation bridge.
     const prior=actor.nativeGait||'idle';
     const gait= speed<(prior==='idle'?.35:.20)?'idle':
       speed>(prior==='sprint'?5.3:5.8)?'sprint':
       speed>(['run','sprint'].includes(prior)?2.4:2.8)?'run':
       speed>(['jog','run','sprint'].includes(prior)?1.1:1.4)?'jog':'walk';
     actor.nativeGait=gait;actor.action=gait;
    }
    active.add(source.id);rig?.update(actor,bodyBalance||footPlant?step:clamp(dt,0,.1));return actor;
   });
   for(const [id,p] of actors)if(!active.has(id)){rig?.reset(p);actors.delete(id);}
   const p=coord(a.ball),q=coord(b.ball),v=velocity(a.ballVelocity),w=velocity(b.ballVelocity);
   const ballU=Math.hypot(q.x-p.x,q.y-p.y,q.z-p.z)<=12?u:0;
   const ball={x:lerp(p.x,q.x,ballU),y:lerp(p.y,q.y,ballU),z:lerp(p.z,q.z,ballU),vx:lerp(v.vx,w.vx,ballU),vy:lerp(v.vy,w.vy,ballU),vz:lerp(v.vz,w.vz,ballU)};
   return {players,ball,score:a.score.slice(),matchMs:a.matchMs,elapsedMs:time-start,done:a.done,stats:a.stats||null};
  }
  return {sample,reset,duration,complete:frames.at(-1).done,frames:frames.length};
 }
 const api={parse,create,coord,velocity};root.TribunNativeReplay=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
