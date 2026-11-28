'use strict';
(function(root){
 // Read-only display of explicitly saved web manager decisions.
 // Never convert to native values, fill missing players, or modify storage.
 const formations=new Set(['4-3-3','4-2-3-1','4-4-2','3-5-2','5-3-2','4-5-1']);
 const enums={
  mentality:{defensive:'Temkinli',balanced:'Dengeli',attacking:'Hücumcu'},
  playstyle:{possession:'Pas oyunu',direct:'Dikine oyun',wing:'Kanat oyunu',counter:'Kontra atak'},
  marking:{zone:'Alan',man:'Adam adama'},
  offside:{off:'Kapalı',on:'Açık'},
  line:{low:'Geride',normal:'Orta blok',high:'Önde'},
  passing:{short:'Kısa',mixed:'Karma',direct:'Uzun / dikine'},
  width:{narrow:'Dar',balanced:'Dengeli',wide:'Geniş'},
  onLoss:{regroup:'Yerleş',counterpress:'Karşı pres'},
  onWin:{retain:'Kontrolü koru',counter:'Hızlı çık'},
  fullbacks:{hold:'Geride kal',support:'Destekle',overlap:'Bindir'},
  crossing:{mixed:'Duruma göre',low:'Yerden',early:'Erken orta'},
  shooting:{patient:'Sabırlı',balanced:'Uygun fırsat',early:'Erken şut'}
 };
 const labels={mentality:'Oyun anlayışı',playstyle:'Oyun tarzı',marking:'Markaj',offside:'Ofsayt tuzağı',
  line:'Savunma hattı',passing:'Pas',width:'Genişlik',onLoss:'Top kaybı',onWin:'Top kazanımı',
  fullbacks:'Bekler',crossing:'Orta',shooting:'Şut',press:'Baskı',tempo:'Tempo',aggression:'Agresiflik'};
 function inspect(raw){
  if(!raw||typeof raw!=='object'||Array.isArray(raw))return null;
  const formation=formations.has(raw.formation)?raw.formation:null;
  const tactics=[];
  for(const [key,label] of Object.entries(labels)){
   const value=raw.tactics?.[key];
   if(enums[key]){
    if(typeof value==='string'&&Object.prototype.hasOwnProperty.call(enums[key],value))
     tactics.push({key,label,value:enums[key][value]});
   }else if(typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100)
    tactics.push({key,label,value});
  }
  let lineup=null;
  if(Array.isArray(raw.starters)&&raw.starters.length===11&&
     new Set(raw.starters).size===11&&Array.isArray(raw.players)&&raw.players.length<=1000){
   const selected=raw.starters.map(i=>Number.isInteger(i)&&i>=0?raw.players[i]:null);
   if(selected.every(p=>p&&p.owned!==false&&typeof p.name==='string'&&p.name.trim()&&p.name.length<=160))
    lineup=selected.map((p,i)=>({slot:i+1,name:p.name,position:typeof p.subposition==='string'&&p.subposition.length<=12?p.subposition:''}));
  }
  if(!formation&&!tactics.length&&!lineup)return null;
  return {formation,tactics,lineup,readOnly:true,nativeApplied:false,
   source:'saved-web-manager-plan'};
 }
 function read(storage){
  try{return inspect(JSON.parse(storage.getItem('tribun-manager-pro09')||'null'));}
  catch{return null;}
 }
 // Preflight only: project the actual stored roster; never infer a native
 // skill value or treat array indices as cross-account player identities.
 const nativeRoles=new Set(['GK','CB','LB','RB','DM','CM','LM','RM','AM','CF']);
 const webRoles=new Set([...nativeRoles,'ST','LW','RW','LWB','RWB']);
 const skills=['rating','fitness','form','passing','shooting','tackling','dribbling','pace','agility','heading','crossing','vision','composure','strength','balance','acceleration','endurance','weakFoot','goalkeeping','reactions','handling','freeKick','corner','penalty'];
 function rosterPreflight(raw){
  const plan=inspect(raw);
  if(!plan?.formation||!plan.lineup||raw.players.length>128)return null;
  const players=[];
  for(const [index,p] of raw.players.entries()){
   if(!p||p.owned===false)continue;
   if(typeof p.name!=='string'||!p.name.trim()||p.name.length>160)return null;
   const role=webRoles.has(p.subposition)?p.subposition:null;
   const nativeRole=nativeRoles.has(role)?role:role==='ST'?'CF':null;
   const values={};
   for(const key of skills)if(typeof p[key]==='number'&&Number.isFinite(p[key])&&p[key]>=0&&p[key]<=100)values[key]=p[key];
   players.push({localIndex:index,name:p.name,webRole:role,nativeRole,
    roleStatus:nativeRole===null?'requires-explicit-mapping':role===nativeRole?'exact-code':'native-striker-code',
    starterSlot:raw.starters.includes(index)?raw.starters.indexOf(index)+1:null,
    preferredFoot:['left','right','both'].includes(p.preferredFoot)?p.preferredFoot:null,
    dataKind:typeof p.dataKind==='string'&&p.dataKind.length<=40?p.dataKind:null,
    webValues:values,inferredAttributes:skills.filter(k=>p.profileProvenance?.inferredAttributes?.includes?.(k)),
    nativeSkillValues:null});
  }
  return {schema:1,source:'saved-web-roster',formation:plan.formation,players,
   nativeApplied:false,skillConversionVerified:false,
   unresolvedRoles:players.filter(p=>!p.nativeRole).length};
 }
 const api={inspect,read,rosterPreflight};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.TribunOriginalManagerPlan=api;
})(typeof window!=='undefined'?window:globalThis);
