'use strict';
// Read-only decision support. Never changes a fixture, runs a simulation, or reads future frames.
(function(root){
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),finite=Number.isFinite;
 const pair=a=>Array.isArray(a)&&a.length===2&&a.every(v=>Number.isSafeInteger(v)&&v>=0);
 const group=p=>({GK:'GK',CB:'DEF',LB:'DEF',RB:'DEF',LWB:'DEF',RWB:'DEF',DEF:'DEF',DM:'MID',CM:'MID',AM:'MID',LM:'MID',RM:'MID',MID:'MID',LW:'ATT',RW:'ATT',ST:'ATT',CF:'ATT',ATT:'ATT'}[p]||null);
 const minutes=ms=>Math.floor(ms/60000);
 function shape(frame,team){
  const field=(frame.players||[]).filter(p=>p.team===team&&!p.goalkeeper);
  if(field.length!==10||field.some(p=>!Array.isArray(p.formationTarget)||!finite(p.formationTarget[0])))return null;
  const lines=[0,0,0];
  for(const p of field){const x=p.formationTarget[0];lines[x<-.30?0:x>.32?2:1]++;}
  return lines.join('-');
 }
 function create(){
  let history=[],latest=null,lastSequence=-1;
  function reset(){history=[];latest=null;lastSequence=-1;}
  function ingest(packet){
   const f=packet?.frame;
   if(packet?.engine!=='league-soccer'||packet.authoritative!==false||!Number.isSafeInteger(packet.sequence)||packet.sequence<=lastSequence||!f||f.engine!=='league-soccer'||!pair(f.score)||!Number.isSafeInteger(f.matchMs)||f.matchMs<0||typeof f.done!=='boolean'||!Array.isArray(f.players))return false;
   if(latest&&(f.matchMs<latest.frame.matchMs||f.elapsedMs<latest.frame.elapsedMs))history=[];
   latest=packet;lastSequence=packet.sequence;
   const s=f.stats;
   if(s&&['shots','onTarget','passes','completed','possessionMs'].every(k=>pair(s[k]))){
    const prev=history.at(-1);
    if(prev&&['shots','onTarget','passes','completed','possessionMs'].some(k=>s[k].some((v,t)=>v<prev.stats[k][t])))history=[];
    // One sample per simulated minute, with an exact current sample separately.
    if(!history.length||f.matchMs-history.at(-1).ms>=60000){
     history.push({ms:f.matchMs,stats:Object.fromEntries(['shots','onTarget','passes','completed','possessionMs'].map(k=>[k,s[k].slice()]))});
    }
    history=history.filter(x=>f.matchMs-x.ms<=15*60000);
   }
   return true;
  }
  function advice(team){
   if(team!==0&&team!==1)throw Error('Invalid team');
   if(!latest||latest.phase!=='playing'||latest.frame.done)return null;
   const f=latest.frame,t=team,o=1-t,minute=minutes(f.matchMs);
   if(minute>=90)return null;
   const diff=f.score[t]-f.score[o];
   const active=f.players.filter(p=>p.team===t);
   const rivalShape=shape(f,o),ownShape=shape(f,t);
   const raw=latest.players||[],meta=new Map(raw.filter(p=>p.team===t).map(p=>[p.nativeId,p]));
   const fatigue=Array.isArray(f.participation)?f.participation.filter(p=>p.team===t):[];
   const info=new Map(fatigue.map(p=>[p.databaseId,p]));
   const acks=f.managerTactics?.find(x=>x.team===t&&x.revision>0);
   const values={press:acks?.press??55,counter:acks?.counter??50,support:acks?.support??50,width:acks?.width??50,tempo:acks?.tempo??50,formation:0};
   const baselineKnown=!!acks;
   let mode='balanced',reasons=[];
   if(active.length<11){
    mode='short-handed';Object.assign(values,{press:45,counter:70,support:35,width:45,tempo:50});
    reasons.push('Eksik oyuncuyla alanları kapat; diziliş komutu önerilmez.');
   }else if(diff<0&&minute>=65){
    mode='chase';Object.assign(values,{press:76,counter:70,support:55,width:65,tempo:80,formation:433});
    reasons.push('Skor geride ve süre azalıyor; daha hızlı hücum kararları değerlendir.');
   }else if(diff>0&&minute>=70){
    mode='protect';Object.assign(values,{press:45,counter:65,support:35,width:45,tempo:38,formation:4231});
    reasons.push('Skor avantajını korumak için daha kompakt ve sabırlı oyun değerlendir.');
   }
   let window=null;
   const old=history.find(x=>f.matchMs-x.ms>=8*60000),s=f.stats;
   if(old&&s&&['shots','onTarget','passes','completed','possessionMs'].every(k=>pair(s[k]))){
    const delta=k=>s[k].map((v,i)=>v-old.stats[k][i]);
    const shots=delta('shots'),onTarget=delta('onTarget'),passes=delta('passes'),completed=delta('completed');
    if([...shots,...onTarget,...passes,...completed].every(v=>v>=0)&&onTarget.every((v,i)=>v<=shots[i])&&completed.every((v,i)=>v<=passes[i])){
     window={minutes:(f.matchMs-old.ms)/60000,shots,onTarget,passes,completed};
     if(mode==='balanced'&&minute>=20&&diff<=0&&shots[t]===0&&passes[t]>=8){
      mode='attack-stall';Object.assign(values,{press:65,counter:68,support:55,width:65,tempo:70});
      reasons.push('Son gözlem aralığında en az 8 pas denemesi var, ancak şut yok.');
     }else if(mode==='balanced'&&shots[o]>=3&&shots[o]>=shots[t]+3){
      mode='under-pressure';Object.assign(values,{press:48,counter:65,support:40,width:48,tempo:50});
      reasons.push('Rakip son gözlem aralığında belirgin şekilde daha çok şut üretiyor.');
     }
    }
   }
   if(mode==='balanced')reasons.push('Mevcut veriler belirgin bir taktik değişikliği gerektirmiyor.');
   if(active.length!==11)values.formation=0;
   if(acks?.formation===values.formation)values.formation=0;
   // Fatigue factor is native relative fatigue, not a measured fitness percentage.
   const changes=[];
   if(minute>=45&&minute<85&&fatigue.length&&active.length===11){
    const used=fatigue.filter(p=>meta.get(p.databaseId)?.reserve&&p.nominalMs>0).length;
    const bench=raw.filter(p=>p.team===t&&p.reserve&&info.has(p.nativeId)&&info.get(p.nativeId).active===false&&info.get(p.nativeId).nominalMs===0&&info.get(p.nativeId).cardCode===0);
    const tired=active.map(p=>({p,row:info.get(p.databaseId),m:meta.get(p.databaseId)})).filter(x=>!x.p.goalkeeper&&x.row&&x.m&&finite(x.row.fatigueFactor)&&x.row.fatigueFactor<=.72&&x.row.cardCode<2&&x.row.nominalMs>=30*60000).sort((a,b)=>a.row.fatigueFactor-b.row.fatigueFactor);
    const chosen=new Set();
    for(const x of tired){
     if(changes.length>=Math.min(2,Math.max(0,5-used)))break;
     const pos=group(x.m.position);if(!pos)continue;
     const options=bench.filter(b=>!chosen.has(b.nativeId)&&group(b.position)===pos&&finite(b.startFitness)&&b.startFitness>=75&&finite(b.rating)&&(!finite(x.m.rating)||b.rating>=x.m.rating-15)).sort((a,b)=>Number(b.position===x.m.position)-Number(a.position===x.m.position)||b.rating-a.rating||b.startFitness-a.startFitness||a.nativeId-b.nativeId);
     if(options.length){const b=options[0];chosen.add(b.nativeId);changes.push({out:x.m.name,in:b.name,outId:x.m.nativeId,inId:b.nativeId,nativeFatigueFactor:x.row.fatigueFactor,reason:'Yorgunluk ve mevki uyumu'});}
    }
   }
   return {team,minute,mode,score:f.score.slice(),ownShape,rivalShape,window,values,reasons,changes,baselineKnown,advisoryOnly:true};
  }
  return {ingest,advice,reset};
 }
 const api={create,shape};root.TribunNativeAdvisor=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
