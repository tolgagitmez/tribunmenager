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
 const strikeProfiles=Object.freeze({
  'short-pass':Object.freeze({pre:180,post:180,back:.18,follow:.25,lift:.10,turn:.40,lean:.05,arm:.13}),
  'long-pass':Object.freeze({pre:230,post:260,back:.32,follow:.40,lift:.18,turn:.15,lean:.09,arm:.23}),
  'high-pass':Object.freeze({pre:240,post:280,back:.34,follow:.42,lift:.23,turn:.12,lean:-.04,arm:.25}),
  'shot':Object.freeze({pre:260,post:300,back:.43,follow:.51,lift:.27,turn:.03,lean:.13,arm:.29}),
  'pass':Object.freeze({pre:190,post:190,back:.22,follow:.27,lift:.12,turn:.15,lean:.06,arm:.15})
 });
 function strikeProfile(e){
  if(e.kind==='shot')return 'shot';
  if(e.kind!=='pass')return null;
  return ['short-pass','long-pass','high-pass'].includes(e.technique)?e.technique:'pass';
 }
 // All labels describe presentation profiles, not proven dribble outcomes.
 const controlProfiles=Object.freeze({
  'cushion':Object.freeze({pre:170,post:160,reach:.12,recover:.14,lift:.035,turn:.22,drop:.055,arm:.12}),
  'close-control':Object.freeze({pre:125,post:120,reach:.07,recover:.09,lift:.035,turn:.20,drop:.025,arm:.10}),
  'running-control':Object.freeze({pre:105,post:115,reach:.10,recover:.18,lift:.07,turn:.12,drop:.02,arm:.15}),
  'turn-control':Object.freeze({pre:140,post:155,reach:.10,recover:.12,lift:.06,turn:.32,drop:.045,arm:.18}),
  'knock-on':Object.freeze({pre:145,post:165,reach:.12,recover:.25,lift:.09,turn:.10,drop:.035,arm:.19})
 });
 function controlProfile(e){
  if(e.kind!=='trap'&&e.kind!=='control')return null;
  const c=e.controlContext;
  if(e.kind==='trap')return 'cushion';
  if(!c)return 'close-control';
  if(c.knockOn)return 'knock-on';
  const m=Math.hypot(c.playerVelocity[0],c.playerVelocity[1]),v=Math.hypot(e.impulseVelocity[0],e.impulseVelocity[1]);
  if(m>1.2&&v>1.2&&(c.playerVelocity[0]*e.impulseVelocity[0]+c.playerVelocity[1]*e.impulseVelocity[1])/(m*v)<.70)return 'turn-control';
  return m>=4.2?'running-control':'close-control';
 }
 function validControl(c){
  return c&&['incomingVelocity','playerVelocity','direction'].every(k=>vec(c[k]))&&
   finite(c.opponentDistance)&&c.opponentDistance>=0&&finite(c.dribbleSkill)&&finite(c.controlSkill)&&
   typeof c.knockOn==='boolean'&&typeof c.uniquePossession==='boolean';
 }
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
    if(p.heightMetres!==undefined)requireValue(finite(p.heightMetres)&&p.heightMetres>0,'Geçersiz motor boyu.');
    if(p.motionIdentity!==undefined)requireValue(p.motionIdentity&&
     ['agility','velocity','acceleration','balance','dribble','control','fatigueFactor'].every(k=>finite(p.motionIdentity[k])),'Geçersiz hareket karakteri.');
    requireValue(p.goalkeeper===undefined||typeof p.goalkeeper==='boolean','Geçersiz kaleci bilgisi.');
    seen.add(p.id);teams[p.team]++;
   }
   requireValue(teams.every(n=>n>=1&&n<=11),'Geçersiz takım sayısı.');
   if(f.nativeContacts!==undefined){
    requireValue(Array.isArray(f.nativeContacts),'Geçersiz temas listesi.');
    let lastContact=prior?.elapsedMs??0;
    for(const e of f.nativeContacts){
     requireValue(e&&nonneg(e.timeMs)&&e.timeMs>=lastContact&&e.timeMs<=f.elapsedMs&&
      nonneg(e.playerId)&&nonneg(e.databaseId)&&[0,1].includes(e.team)&&[-1,0,1].includes(e.foot)&&
      ['trap','control','pass','shot','standing-tackle','sliding-tackle'].includes(e.kind)&&
      (e.technique===undefined||['none','short-pass','long-pass','high-pass','shot'].includes(e.technique))&&(e.headContact===undefined||typeof e.headContact==='boolean')&&vec(e.ball)&&vec(e.impulseVelocity)&&
      (e.controlContext===undefined||validControl(e.controlContext)),'Geçersiz motor teması.');
     lastContact=e.timeMs;
    }
   }
   if(f.nativeDuels!==undefined){
    requireValue(Array.isArray(f.nativeDuels),'Geçersiz mücadele listesi.');
    let lastDuel=prior?.elapsedMs??0;
    for(const d of f.nativeDuels){
     requireValue(d&&nonneg(d.timeMs)&&d.timeMs>=lastDuel&&d.timeMs<=f.elapsedMs&&
      nonneg(d.playerId)&&nonneg(d.databaseId)&&[0,1].includes(d.team)&&nonneg(d.opponentId)&&d.opponentId!==d.playerId&&
      ['bump','trip','tackle-trip'].includes(d.kind)&&[0,1,2,3].includes(d.tripType)&&vec(d.direction)&&
      finite(d.displacement)&&d.displacement>=0&&finite(d.relativeSpeed)&&d.relativeSpeed>=0&&
      finite(d.balance)&&typeof d.possession==='boolean','Geçersiz motor mücadelesi.');
     lastDuel=d.timeMs;
    }
   }
   if(f.nativeFouls!==undefined){
    requireValue(Array.isArray(f.nativeFouls),'Geçersiz faul listesi.');
    let last=prior?.elapsedMs??0;
    for(const e of f.nativeFouls){
     requireValue(e&&nonneg(e.timeMs)&&e.timeMs>=last&&e.timeMs<=f.elapsedMs&&nonneg(e.playerId)&&
      nonneg(e.victimId)&&e.playerId!==e.victimId&&[0,1].includes(e.team)&&[2,3].includes(e.tackleType),'Geçersiz hakem olayı.');
     last=e.timeMs;
    }
   }
   if(f.ballRetainerId!==undefined)requireValue(f.ballRetainerId===null||nonneg(f.ballRetainerId),'Geçersiz top tutan oyuncu.');
   if(f.nativeKeeperEvents!==undefined){
    requireValue(Array.isArray(f.nativeKeeperEvents),'Geçersiz kaleci olayları.');
    let last=prior?.elapsedMs??0;
    for(const k of f.nativeKeeperEvents){
     requireValue(k&&nonneg(k.timeMs)&&k.timeMs>=last&&k.timeMs<=f.elapsedMs&&nonneg(k.playerId)&&nonneg(k.databaseId)&&
      [0,1].includes(k.team)&&['catch','parry'].includes(k.kind)&&[-1,0,1].includes(k.hand)&&vec(k.ball)&&vec(k.incomingVelocity),'Geçersiz kaleci teması.');
     last=k.timeMs;
    }
   }
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
 function create(frames,manifest=null,{bodyBalance=false,footPlant=false,contactSync=false,strikeMotion=false,controlMotion=false,duelMotion=false,tackleMotion=false,keeperMotion=false,aerialMotion=false,animationBlend=false,motionMatching=false,playerMotionIdentity=false,playerAnatomy=false,clipLibrary=null}={}){
  requireValue(Array.isArray(frames)&&frames.length,'Kayıt yok.');
  // The combined profile enables all prior opt-in layers, but remains a
  // presentation experiment; the recorded match is still authoritative.
  if(clipLibrary)playerAnatomy=true;
  if(playerAnatomy)playerMotionIdentity=true;
  if(playerMotionIdentity)motionMatching=true;
  if(motionMatching)animationBlend=true;
  if(animationBlend)bodyBalance=footPlant=contactSync=strikeMotion=controlMotion=duelMotion=tackleMotion=keeperMotion=aerialMotion=true;
  const roster=rosterMap(manifest),actors=new Map();
  if(roster.size)for(const f of frames)for(const p of f.players)requireValue(roster.get(p.databaseId)?.team===p.team,'Kadro dosyası maçla uyuşmuyor.');
  const start=frames[0].elapsedMs,end=frames.at(-1).elapsedMs,duration=end-start;
  const contacts=new Map();
  if(contactSync||strikeMotion||controlMotion||tackleMotion)for(const frame of frames)for(const e of frame.nativeContacts||[]){
   if(e.foot<0||e.ball[2]>.35)continue;
   const key=e.team+':'+e.playerId+':'+e.databaseId;
   if(!contacts.has(key))contacts.set(key,[]);
   contacts.get(key).push(e);
  }
  function contactAt(source,time){
   const events=contacts.get(source.team+':'+source.id+':'+source.databaseId)||[];
   let lo=0,hi=events.length;
   while(lo<hi){const mid=(lo+hi)>>1;if(events[mid].timeMs<time)lo=mid+1;else hi=mid;}
   let best=null;
   for(const e of [events[lo-1],events[lo]]){
    if(!e)continue;
    const d=time-e.timeMs;
    const profile=strikeMotion&&strikeProfile(e),control=controlMotion&&controlProfile(e);
    const tackle=tackleMotion&&['standing-tackle','sliding-tackle'].includes(e.kind);
    const shape=profile?strikeProfiles[profile]:control?controlProfiles[control]:tackle?{pre:150,post:180}:null;
    if(!shape&&!contactSync)continue;
    if(d< -(shape?.pre??100)||d>(shape?.post??90))continue;
    if(!best||Math.abs(d)<Math.abs(time-best.timeMs))best=e;
   }
   if(!best)return null;
   const delta=time-best.timeMs,profile=strikeMotion&&strikeProfile(best),control=controlMotion&&controlProfile(best);
   const tackle=tackleMotion&&['standing-tackle','sliding-tackle'].includes(best.kind);
   const shape=profile?strikeProfiles[profile]:control?controlProfiles[control]:tackle?{pre:150,post:180}:null;
   const weight=clamp(1-Math.abs(delta)/(delta<0?(shape?.pre??100):(shape?.post??90)),0,1);
   const cue={kind:best.kind,foot:best.foot,timeMs:best.timeMs,deltaMs:delta,weight:weight*weight*(3-2*weight),ball:coord(best.ball),impulse:velocity(best.impulseVelocity)};
   if(tackle)cue.tackle={sliding:best.kind==='sliding-tackle'};
   if(profile)cue.strike={profile,shape,power:clamp(Math.hypot(...best.impulseVelocity)/30,0,1)};
   if(control){
    const c=best.controlContext,skill=c?clamp(control==='cushion'?c.controlSkill:c.dribbleSkill,0,1):.5;
    const pressure=c&&c.uniquePossession&&control!=='knock-on'?clamp((1.8-c.opponentDistance)/1.4,0,1):0;
    const speed=c?Math.hypot(c.playerVelocity[0],c.playerVelocity[1]):0;
    const direction=c?coord(c.direction):null;
    const lateral=direction?(-direction.z*cue.impulse.vx+direction.x*cue.impulse.vz):0;
    cue.control={profile:control,shape,skill,pressure,speed,
     lateral:clamp(lateral/5,-1,1),incoming:c?velocity(c.incomingVelocity):null,
     contextRecorded:!!c};
   }
   return cue;
  }
  const duels=new Map();
  if(duelMotion||tackleMotion)for(const frame of frames)for(const d of frame.nativeDuels||[]){
   const key=d.team+':'+d.playerId+':'+d.databaseId;
   if(!duels.has(key))duels.set(key,[]);
   duels.get(key).push(d);
  }
  function duelAt(source,time){
   const events=duels.get(source.team+':'+source.id+':'+source.databaseId)||[];
   let lo=0,hi=events.length;
   while(lo<hi){const mid=(lo+hi)>>1;if(events[mid].timeMs<=time)lo=mid+1;else hi=mid;}
   let best=null;
   for(let i=lo-1;i>=0;i--){
    const d=events[i],age=time-d.timeMs;
    if(age>(tackleMotion?900:420))break;
    const duration=d.kind==='bump'?180:tackleMotion&&d.tripType>=2?900:420;
    if(age>=duration)continue;
    const strength=d.kind==='bump'?clamp(d.displacement/.065,0,1)*(.45+.55*clamp(d.relativeSpeed/7,0,1)):
     clamp(.48+.15*d.tripType,0,1);
    if(!duelMotion&&d.kind==='bump')continue;
    const recovery=1-age/duration,weight=strength*recovery*recovery;
    if(!best||weight>best.weight)best={kind:d.kind,timeMs:d.timeMs,age,weight,direction:coord(d.direction),
     balance:clamp(d.balance,0,1),possession:d.possession,opponentId:d.opponentId,tripType:d.tripType,fall:tackleMotion&&d.kind!=='bump'&&d.tripType>=2};
   }
   return best;
  }
  const keepers=new Map();
  if(keeperMotion)for(const frame of frames)for(const k of frame.nativeKeeperEvents||[]){
   const key=k.team+':'+k.playerId+':'+k.databaseId;
   if(!keepers.has(key))keepers.set(key,[]);
   keepers.get(key).push(k);
  }
  function keeperAt(source,time,a,b,actor,u){
   const events=keepers.get(source.team+':'+source.id+':'+source.databaseId)||[];
   let lo=0,hi=events.length;
   while(lo<hi){const mid=(lo+hi)>>1;if(events[mid].timeMs<time)lo=mid+1;else hi=mid;}
   let best=null;
   for(const e of [events[lo-1],events[lo]]){
    if(!e)continue;
    const delta=time-e.timeMs;
    if(delta< -220||delta>420)continue;
    if(!best||Math.abs(delta)<Math.abs(time-best.timeMs))best=e;
   }
   const held=a.ballRetainerId===source.id&&b.ballRetainerId===source.id;
   const point=held&&(!best||time-best.timeMs>80)?a.ball.map((v,i)=>lerp(v,b.ball[i],u)):best?.ball;
   if(!point)return null;
   const ball=coord(point),dx=ball.x-actor.x,dz=ball.z-actor.z;
   if(Math.hypot(dx,dz)>2.35||ball.y<0||ball.y>2.8)return null;
   const lateral=-Math.sin(actor.face)*dx+Math.cos(actor.face)*dz;
   const forward=Math.cos(actor.face)*dx+Math.sin(actor.face)*dz;
   const delta=best?time-best.timeMs:0;
   const raw=held?1:clamp(1-Math.abs(delta)/(delta<0?220:420),0,1);
   const profile=held?'hold':ball.y<.55?'low':ball.y>1.65?'high':Math.abs(lateral)>.7?'side':'central';
   return {kind:held?'hold':best.kind,profile,hand:best?.hand??-1,ball,lateral,forward,deltaMs:delta,
    weight:raw*raw*(3-2*raw),timeMs:best?.timeMs??null,held};
  }
  const aerial=new Map();
  if(aerialMotion)for(const frame of frames)for(const e of frame.nativeContacts||[]){
   if(e.headContact!==true||e.foot!==-1||e.ball[2]<.65||e.ball[2]>2.8)continue;
   const key=e.team+':'+e.playerId+':'+e.databaseId;
   if(!aerial.has(key))aerial.set(key,[]);
   aerial.get(key).push(e);
  }
  function aerialAt(source,time,actor){
   const events=aerial.get(source.team+':'+source.id+':'+source.databaseId)||[];
   let lo=0,hi=events.length;
   while(lo<hi){const mid=(lo+hi)>>1;if(events[mid].timeMs<time)lo=mid+1;else hi=mid;}
   let best=null;
   for(const e of [events[lo-1],events[lo]]){
    if(!e)continue;
    const delta=time-e.timeMs;
    if(delta< -300||delta>360)continue;
    if(!best||Math.abs(delta)<Math.abs(time-best.timeMs))best=e;
   }
   if(!best)return null;
   const ball=coord(best.ball),dx=ball.x-actor.x,dz=ball.z-actor.z;
   if(Math.hypot(dx,dz)>1.2)return null;
   const delta=time-best.timeMs,raw=clamp(1-Math.abs(delta)/(delta<0?300:360),0,1);
   const weight=raw*raw*(3-2*raw);
   const movement=best.controlContext?.playerVelocity;
   const speed=movement?Math.hypot(movement[0],movement[1]):null;
   const contested=best.controlContext?best.controlContext.opponentDistance<1.1:false;
   const profile=ball.y<1.55?'stoop':ball.y>1.95?'jump':speed!==null&&speed>2.5?'running':'standing';
   return {timeMs:best.timeMs,kind:best.kind,profile,ball,deltaMs:delta,weight,
    contested,speed,forward:Math.cos(actor.face)*dx+Math.sin(actor.face)*dz,
    lateral:-Math.sin(actor.face)*dx+Math.cos(actor.face)*dz};
  }
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
    if(contactSync||strikeMotion||controlMotion||tackleMotion){
     const cue=actor.role==='GK'||a.setPiece||b.setPiece||a.inPlay===false||b.inPlay===false||span>200?null:contactAt(source,time);
     actor.nativeContact=cue&&Math.hypot(cue.ball.x-actor.x,cue.ball.z-actor.z)<=1.15?cue:null;
    }
    if(duelMotion||tackleMotion){
     actor.nativeDuel=actor.role==='GK'||a.setPiece||a.inPlay===false||span>200||Math.hypot(dest.x-pos.x,dest.z-pos.z)>2?null:duelAt(source,time);
    }
    if(keeperMotion){
     actor.nativeKeeper=actor.role==='GK'&&!a.done&&!a.setPiece&&a.inPlay!==false&&span>0&&span<=200&&
      Math.hypot(dest.x-pos.x,dest.z-pos.z)<=2?keeperAt(source,time,a,b,actor,u):null;
    }
    if(aerialMotion){
     actor.nativeAerial=actor.role!=='GK'&&!a.done&&!a.setPiece&&!b.setPiece&&a.inPlay!==false&&b.inPlay!==false&&
      span>0&&span<=200&&Math.hypot(dest.x-pos.x,dest.z-pos.z)<=2?aerialAt(source,time,actor):null;
    }
    if(animationBlend){
     const valid=!a.done&&!a.setPiece&&!b.setPiece&&a.inPlay!==false&&b.inPlay!==false&&span>0&&span<=200&&
      target&&target.team===source.team&&target.databaseId===source.databaseId&&Math.hypot(dest.x-pos.x,dest.z-pos.z)<=2;
     actor.nativeBlend=!!valid;
     if(!valid){actor.nativeContact=actor.nativeAerial=actor.nativeKeeper=actor.nativeDuel=null;}
     else{
      // Head and foot contacts cannot own the same pose. Nearest actual
      // event wins; exact contact never loses to another event's tail.
      if(actor.nativeContact&&actor.nativeAerial){
       if(Math.abs(actor.nativeAerial.deltaMs)<Math.abs(actor.nativeContact.deltaMs))actor.nativeContact=null;
       else actor.nativeAerial=null;
      }
      const primary=actor.nativeContact||actor.nativeAerial||actor.nativeKeeper;
      if(primary&&actor.nativeDuel){
       const scale=1-.85*clamp(primary.weight,0,1);
       actor.nativeDuel={...actor.nativeDuel,weight:actor.nativeDuel.weight*scale,fall:actor.nativeDuel.fall&&primary.weight<.35};
      }
     }
    }
    if(motionMatching)actor.nativeMotionMatch=actor.nativeBlend&&actor.nativeFootPlant===true&&actor.role!=='GK';
    if(playerAnatomy){
     const height=source.heightMetres,foot=metadata?.preferredFoot;
     // Only explicit data, not identity-derived body shape or preferred foot.
     actor.nativeAnatomy={height:finite(height)&&height>=1.45&&height<=2.15?height:null,
      scale:finite(height)&&height>=1.45&&height<=2.15?height/1.88:1,
      preferredFoot:['left','right','both'].includes(foot)?foot:'unknown'};
    }
    if(playerMotionIdentity){
     // Never infer missing traits from name, identity or overall rating.
     const c=source.motionIdentity,d=p2.motionIdentity;
     actor.nativeMotionIdentity=actor.nativeMotionMatch&&c?{
      agility:clamp(c.agility,0,1),velocity:clamp(c.velocity,0,1),acceleration:clamp(c.acceleration,0,1),
      balance:clamp(c.balance,0,1),dribble:clamp(c.dribble,0,1),control:clamp(c.control,0,1),
      freshness:clamp(d?lerp(c.fatigueFactor,d.fatigueFactor,blend):c.fatigueFactor,0,1)
     }:null;
    }
    if(clipLibrary)actor.nativeClipLibrary=actor.nativeBlend?clipLibrary:null;
    active.add(source.id);rig?.update(actor,bodyBalance||footPlant||contactSync||strikeMotion||controlMotion||duelMotion||tackleMotion||keeperMotion||aerialMotion?step:clamp(dt,0,.1));return actor;
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
