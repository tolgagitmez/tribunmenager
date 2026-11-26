'use strict';
(function(root){
 const validPair=v=>Array.isArray(v)&&v.length===2&&v.every(n=>Number.isFinite(n)&&n>=0);
 const labels=[['shots','Şut'],['onTarget','İsabetli şut'],['completed','Başarılı pas'],['fouls','Faul'],['possessionMs','Topa sahip olma']];
 function metrics(stats){
  if(!stats)return [];
  return labels.flatMap(([key,label])=>{
   const pair=stats[key];if(!validPair(pair))return [];
   const total=pair[0]+pair[1];
   if(key==='possessionMs'&&!total)return [];
   const homeShare=total?pair[0]/total:0;
   const values=key==='possessionMs'?[Math.round(homeShare*100)+'%',(100-Math.round(homeShare*100))+'%']:pair.map(String);
   return [{key,label,values,homeShare,awayShare:total?1-homeShare:0,empty:!total}];
  });
 }
 function create(doc){
  const $=id=>doc.getElementById(id);
  let last='',phaseValue='';
  function set(id,value){const e=$(id);if(e.textContent!==value)e.textContent=value;}
  function phase(value){if(value!==phaseValue){phaseValue=value;set('tvPhase',value);}}
  function update(frame,{home='Ev sahibi',away='Deplasman',phase:label}={}){
   set('tvHome',typeof home==='string'&&home.trim()?home:'Ev sahibi');set('tvAway',typeof away==='string'&&away.trim()?away:'Deplasman');
   set('tvResult',validPair(frame?.score)?frame.score.join(' : '):'– : –');
   set('tvMinute',Number.isFinite(frame?.matchMs)?Math.min(90,Math.floor(frame.matchMs/60000))+'′':"--′");
   phase(label||(frame?.done?'MAÇ SONU':frame?'KAYIT':'BEKLENİYOR'));
   const rows=metrics(frame?.stats),key=JSON.stringify(rows);
   if(last===key)return;last=key;
   const host=$('tvMetrics');host.replaceChildren();
   if(!rows.length){const p=doc.createElement('p');p.className='tm-muted';p.textContent='Bu maç için istatistik verisi henüz yok.';host.append(p);return;}
   for(const r of rows){
    const div=doc.createElement('div');div.className='tm-metric';
    const title=doc.createElement('div');title.className='tm-metric-label';
    for(const [tag,value] of [['b',r.values[0]],['span',r.label],['b',r.values[1]]]){const e=doc.createElement(tag);e.textContent=value;title.append(e);}
    const meter=doc.createElement('div');meter.className='tm-meter';meter.dataset.empty=String(r.empty);meter.setAttribute('aria-hidden','true');
    for(const share of [r.homeShare,r.awayShare]){const e=doc.createElement('span');e.style.flexGrow=String(share);meter.append(e);}
    div.append(title,meter);host.append(div);
   }
  }
  update(null);return {update,phase};
 }
 const api={create,metrics};root.TribunBroadcastDesign=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
