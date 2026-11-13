'use strict';
/* One roster-to-pitch contract. Inputs stay raw; effective values are derived once. */
(function(root){
const profiles=typeof module!=='undefined'&&module.exports?require('./player-model-profiles.json'):root.TribunPlayerProfiles;
if(!profiles)throw Error('Oyuncu profil verileri yüklenemedi.');
const attributes=Object.freeze(Object.keys(profiles.playmaker));
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
 for(const key of attributes){p[key]=number(source[key],profiles[p.archetype][key]);if(typeof source[key]!=='number'||!Number.isFinite(source[key])||priorInferred.has(key)&&source[key]===(key==='weakFoot'&&source.preferredFoot==='both'?99:profiles[p.archetype][key]))inferred.push(key);}
 p.preferredFoot=['left','right','both'].includes(source.preferredFoot)?source.preferredFoot:'unknown';
 if(p.preferredFoot==='both')p.weakFoot=99;
 p.profileProvenance={inferredAttributes:inferred,preferredFootSource:p.preferredFoot==='unknown'?'unknown':'provided',archetypeSource:Object.hasOwn(profiles,source.archetype)&&!(prior?.archetypeSource==='position-default'&&source.archetype===archetypeFor({...p,archetype:undefined}))?'provided':'position-default'};
 return p;
}
function fit(raw,slot){
 const p=normalize(raw),role=group(typeof slot==='object'?slot.role||slot.position:slot)||p.pos;
 if(p.pos===role)return 1;if(p.pos==='GK'||role==='GK')return .45;
 if(p.pos==='MID'&&role==='ATT'||p.pos==='ATT'&&role==='MID')return .87;
 if(p.pos==='DEF'&&role==='MID'||p.pos==='MID'&&role==='DEF')return .82;return .66;
}
function forSlot(raw,slot){
 const p=normalize(raw),position=fit(p,slot),form=.91+.09*p.form/100,condition=.83+.17*p.fitness/100;
 const effective={};
 for(const key of attributes){
  const factor=['strength','endurance'].includes(key)?1:['pace','acceleration','agility','balance'].includes(key)?condition:position*form;
  effective[key]=p[key]*factor;
 }
 const skill=Math.round(p.rating*position*condition*form);
 return {...effective,baseRating:p.rating,skill,fitness:p.fitness,stamina:p.fitness,form:p.form,roleFit:position,
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
const api={version:1,profiles,attributes,groups,slots,slotFor,normalize,forSlot,quality,fit,demoTeam,labels,footLabel};
root.TribunPlayerModel=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
