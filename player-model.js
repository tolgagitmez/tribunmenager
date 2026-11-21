'use strict';
/* One roster-to-pitch contract. Inputs stay raw; effective values are derived once. */
(function(root){
const profiles=typeof module!=='undefined'&&module.exports?require('./player-model-profiles.json'):root.TribunPlayerProfiles;
if(!profiles)throw Error('Oyuncu profil verileri yüklenemedi.');
const deliverySkills={
 freeKick:p=>.40*p.shooting+.35*p.passing+.25*p.composure,
 corner:p=>.75*p.crossing+.15*p.passing+.10*p.composure,
 penalty:p=>.65*p.shooting+.35*p.composure
};
const attributes=Object.freeze([...Object.keys(profiles.playmaker),...Object.keys(deliverySkills)]);
const groups={GK:['GK'],DEF:['CB','LB','RB','LWB','RWB'],MID:['DM','CM','AM','LM','RM'],ATT:['ST','CF','LW','RW']};
const slots={
 '4-3-3':['LW','ST','RW','CM','DM','CM','LB','CB','CB','RB','GK'],
 '4-2-3-1':['ST','LM','AM','RM','DM','DM','LB','CB','CB','RB','GK'],
 '4-4-2':['ST','ST','LM','CM','CM','RM','LB','CB','CB','RB','GK'],
 '3-5-2':['ST','ST','LM','CM','AM','CM','RM','CB','CB','CB','GK'],
 '5-3-2':['ST','ST','CM','DM','CM','LWB','CB','CB','CB','RWB','GK'],
 '4-5-1':['ST','LM','CM','AM','CM','RM','LB','CB','CB','RB','GK']
};
const number=(value,fallback,lo=1,hi=99)=>typeof value==='number'&&Number.isFinite(value)?Math.max(lo,Math.min(hi,value)):fallback;
function group(position){return Object.keys(groups).find(k=>k===position||groups[k].includes(position));}
function slotFor(formation,index){const position=(slots[formation]||slots['4-3-3'])[index]||'CM';return {role:group(position),position};}
function archetypeFor(p){
 if(Object.hasOwn(profiles,p.archetype))return p.archetype;
 const pos=p.subposition;
 if(p.pos==='GK')return 'goalkeeper';
 if(p.pos==='DEF')return ['LB','RB','LWB','RWB'].includes(pos)?'fullback':'stopper';
 if(p.pos==='ATT')return ['LW','RW'].includes(pos)?'winger':'poacher';
 return pos==='DM'?'ballWinner':'playmaker';
}
function normalize(raw={}){
 const source=raw&&typeof raw==='object'&&!Array.isArray(raw)?raw:{};
 const pos=group(source.pos)||group(source.subposition)||'MID';
 const p={...source,pos,rating:number(source.rating,80),fitness:number(source.fitness,95,0,100),form:number(source.form,80,0,100)};
 p.subposition=groups[pos].includes(source.subposition)?source.subposition:null;
 p.positions=Array.isArray(source.positions)?[...new Set(source.positions.filter(s=>group(s)))]:p.subposition?[p.subposition]:[];
 p.archetype=archetypeFor(p);const inferred=[],prior=source.profileProvenance,priorInferred=new Set(Array.isArray(prior?.inferredAttributes)?prior.inferredAttributes:[]);
 for(const key of attributes){
  const fallback=deliverySkills[key]?Math.round(deliverySkills[key](p)):profiles[p.archetype][key];
  p[key]=number(source[key],fallback);
  if(typeof source[key]!=='number'||!Number.isFinite(source[key])||priorInferred.has(key)&&source[key]===(key==='weakFoot'&&source.preferredFoot==='both'?99:fallback))inferred.push(key);
 }
 p.preferredFoot=['left','right','both'].includes(source.preferredFoot)?source.preferredFoot:'unknown';
 if(p.preferredFoot==='both')p.weakFoot=99;
 p.profileProvenance={inferredAttributes:inferred,preferredFootSource:p.preferredFoot==='unknown'?'unknown':'provided',archetypeSource:Object.hasOwn(profiles,source.archetype)&&!(prior?.archetypeSource==='position-default'&&source.archetype===archetypeFor({...p,archetype:undefined}))?'provided':'position-default'};
 return p;
}
const adjacent={
 CB:['RB','LB','DM'],LB:['LWB','RB','CB','LM'],RB:['RWB','LB','CB','RM'],
 LWB:['LB','LW','LM','RWB'],RWB:['RB','RW','RM','LWB'],
 DM:['CM','CB','AM'],CM:['DM','AM','LM','RM'],AM:['CM','DM','CF','ST'],
 LM:['LW','LWB','CM','RM'],RM:['RW','RWB','CM','LM'],
 ST:['CF','AM'],CF:['ST','AM'],LW:['LM','RW','ST'],RW:['RM','LW','ST']
};
const habits={
 CB:{hold:.98,overlap:0,intercept:.92,press:.74,forward:.22,shortPass:.65},
 LB:{hold:.74,overlap:.90,intercept:.76,press:.94,forward:.68,shortPass:.84},
 RB:{hold:.74,overlap:.90,intercept:.76,press:.94,forward:.68,shortPass:.84},
 LWB:{hold:.58,overlap:1.13,intercept:.7,press:1,forward:.96,shortPass:.86},
 RWB:{hold:.58,overlap:1.13,intercept:.7,press:1,forward:.96,shortPass:.86},
 DM:{hold:1.1,overlap:.08,intercept:1.2,press:.88,forward:.35,shortPass:1.17},
 CM:{hold:.76,overlap:.22,intercept:.90,press:.95,forward:.64,shortPass:1},
 AM:{hold:.34,overlap:.3,intercept:.54,press:1.03,forward:1.18,shortPass:.78},
 LM:{hold:.43,overlap:.65,intercept:.57,press:1,forward:.97,shortPass:.83},
 RM:{hold:.43,overlap:.65,intercept:.57,press:1,forward:.97,shortPass:.83}
};
function habitsFor(raw,slot){
 const position=typeof slot==='object'?slot.position:slot;
 const baseline=habits[position]||{hold:.45,overlap:.3,intercept:.66,press:1,forward:1,shortPass:1};
 const p=normalize(raw);
 const mentality=p.archetype==='ballWinner'?1.06:p.archetype==='playmaker'?.97:1;
 return {...baseline,intercept:baseline.intercept*mentality,
  footLane:typeof position==='string'&&/^(L[WBMR]|R[WBMR])/.test(position)?
    position.startsWith('L')?'left':'right':'central'};
}
function fit(raw,slot){
 const p=normalize(raw),position=typeof slot==='object'?slot.position:slot,role=group(typeof slot==='object'?slot.role||position:position)||p.pos;
 let base;
 if(p.pos===role)base=1;
 else if(p.pos==='GK'||role==='GK')base=.45;
 else if(p.pos==='MID'&&role==='ATT'||p.pos==='ATT'&&role==='MID')base=.87;
 else if(p.pos==='DEF'&&role==='MID'||p.pos==='MID'&&role==='DEF')base=.82;
 else base=.66;
 if(typeof position!=='string'||!groups[role]?.includes(position))return base;
 const declared=p.positions.length?p.positions:p.subposition?[p.subposition]:[];
 if(declared.length){
  const positionSkill=declared.some(source=>source===position)?1:
    declared.some(source=>adjacent[source]?.includes(position))?.91:.77;
  base*=positionSkill;
 }
 // Real preferred foot matters on the flank; unknown feet stay unknown.
 const lane=habitsFor(p,position).footLane;
 if((lane==='left'||lane==='right')&&p.preferredFoot!=='unknown'&&p.preferredFoot!=='both'&&p.preferredFoot!==lane)base*=.94;
 return Math.round(base*10000)/10000;
}
function forSlot(raw,slot){
 const p=normalize(raw),position=fit(p,slot),form=.91+.09*p.form/100,condition=.83+.17*p.fitness/100;
 const effective={};
 for(const key of attributes){
  const factor=['strength','endurance'].includes(key)?1:['pace','acceleration','agility','balance'].includes(key)?condition:position*form;
  effective[key]=p[key]*factor;
 }
 const skill=Math.round(p.rating*position*condition*form);
 const roleHabits=habitsFor(p,slot);
 const detailedRole=p.dataKind!=='demo'&&p.dataKind!=='league-demo'&&!!(p.subposition||p.positions.length);
 return {...effective,baseRating:p.rating,skill,fitness:p.fitness,stamina:p.fitness,form:p.form,roleFit:position,roleHabits,detailedRole,
  preferredFoot:p.preferredFoot==='left'?0:1,footPreference:p.preferredFoot,archetype:p.archetype,
  model:{version:1,slot:typeof slot==='object'?{...slot}:{role:group(slot)||p.pos},baseRating:p.rating,effectiveRating:skill,factors:{position,form,condition},...p.profileProvenance}};
}
const quality=(p,slot)=>forSlot(p,slot).skill;
function demoTeam(team=1,formation='4-3-3'){
 return (slots[formation]||slots['4-3-3']).map((position,i)=>{
  const role=group(position),side=['LB','LWB','LW','LM'].includes(position)?'left':'right';
  const p=normalize({id:i,name:`Deneme ${team+1} / ${i+1}`,number:i+1,pos:role,subposition:position,rating:80,fitness:95,form:80,preferredFoot:side,dataKind:'demo'});
  // Materialize fictional profiles. These are never represented as provider observations.
  delete p.profileProvenance;return p;
 });
}
const labels={goalkeeper:'Kaleci',stopper:'Güçlü stoper',fullback:'Hücumcu bek',playmaker:'Oyun kurucu',ballWinner:'Top kazanan',winger:'Süratli kanat',poacher:'Hızlı bitirici',targetForward:'Hedef santrfor'};
const footLabel=p=>({left:'Sol',right:'Sağ',both:'İki ayak',unknown:'Ayak bilgisi yok'})[normalize(p).preferredFoot];
const api={version:2,profiles,attributes,groups,slots,slotFor,normalize,forSlot,quality,fit,habitsFor,demoTeam,labels,footLabel};
root.TribunPlayerModel=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
