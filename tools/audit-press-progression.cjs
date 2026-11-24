'use strict';
// Diagnostic only: same engine, same inputs, correction on/off.
// No injected possession, shot, opponent movement or random draws.
const fs=require('node:fs'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),D=require('../attack-diagnostics'),T=require('../tactics');
const seeds=[42,73,206,311,527,881],presets=id=>T.presets.find(p=>p.id===id).tactics;
const roster=()=>Array.from({length:11},(_,id)=>({id,name:'Synthetic '+id,rating:82,passing:82,shooting:82,tackling:82,vision:82,composure:82,dribbling:82,pace:82,agility:82,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:70}));
const bump=(o,k)=>{o[k]=(o[k]||0)+1;};
const stageKeys=['pressureEscape','lineBreak','finalThird','box','shot'];
function run(seed,enabled){
 const m=new Match({seed,individualAI:true,territorialProgression:enabled,managerKicks:false,matchMinutes:5,formation:'4-3-3',awayFormation:'4-2-3-1',players:roster(),awayPlayers:roster(),tactics:presets('balanced'),awayTactics:presets('press')});
 const obs=D.attach(m,{maxEpisodes:20000}),decisions=[{},{}],losses=[{},{}],releases=[{},{}],passes=new Map(),choose=m.choose;
 m.choose=function(p){
  const choice=choose.call(this,p),depth=p.x*this.direction(p.team),zone=depth<0?'own-half':depth<52/3?'middle':depth<35.5?'final-third':'box-depth';
  const pressure=Math.min(20,...this.rivals(p).map(q=>Math.hypot(q.x-p.x,q.z-p.z))),band=pressure<4?'pressed':pressure<7?'closing':'space';
  const gain=choice.point?(choice.point.x-p.x)*this.direction(p.team):0;
  const key=[zone,band,choice.territorialPass?'corrected-pass':choice.territorialCarry?'corrected-carry':choice.hold?'hold':choice.kind,gain>3?'forward':gain< -3?'backward':'other'].join('/');
  bump(decisions[p.team],key);return choice;
 };
 let previous=m.releaseSerial;
 for(let i=0;i<36000&&!m.done;i++){
  const before=m.owner,prior=m.flight;
  obs.step(1/60);
  if(m.releaseSerial!==previous){
   previous=m.releaseSerial;const f=m.flight;
   if(f?.from&&f.point&&['pass','through','long-pass','cutback','cross'].includes(f.kind)){
    const team=f.from.team,key=f.territorialPass?'corrected':'ordinary';
    passes.set(f.id,{team,key});bump(releases[team],key+'/released');
   }
  }
  if(prior&&!m.flight&&m.owner&&passes.has(prior.id)){
   const rec=passes.get(prior.id);bump(releases[rec.team],rec.key+(m.owner.team===rec.team?'/own-control':'/opponent-control'));passes.delete(prior.id);
  }
  if(before&&!m.owner&&!m.kick&&!m.flight&&!m.restart){const depth=before.x*m.direction(before.team);bump(losses[before.team],depth<0?'own-half':depth<52/3?'middle':'advanced');}
 }
 assert(m.done,'full match did not finish: '+seed);
 const report=obs.report();assert(report.valid,JSON.stringify(report.errors));obs.detach();
 const teams=report.teams.map(t=>({team:t.team,attacks:t.attacks,shots:m.shots[t.team],goals:m.score[t.team],box:t.stageCounts.box,finalThird:t.stageCounts.finalThird,eligible:t.stageEligibility,reached:t.eligibleReached,endReasons:t.endReasons,endedByStage:t.endedByStage,decisions:decisions[t.team],releaseOutcomes:releases[t.team],looseControl:losses[t.team]}));
 const cohorts=[0,1].map(team=>{const rows=report.episodes.filter(e=>e.team===team&&e.pressureRequired&&e.confirmedControl),endReasons={};for(const e of rows)bump(endReasons,e.endReason||'pending');return {team,count:rows.length,stages:Object.fromEntries(stageKeys.map(k=>[k,rows.filter(e=>e.stages[k]).length])),endReasons};});
 return {seed,enabled,inPlay:report.clock.inPlaySeconds,teams,cohorts};
}
const pairs=seeds.map(seed=>{const off=run(seed,false),on=run(seed,true);console.log('PRESS_PAIR '+JSON.stringify({seed,off:off.teams.map(t=>({team:t.team,box:t.box,shots:t.shots})),on:on.teams.map(t=>({team:t.team,box:t.box,shots:t.shots})),offCohorts:off.cohorts,onCohorts:on.cohorts}));return {seed,off,on};});
fs.mkdirSync('docs/validation',{recursive:true});fs.writeFileSync('docs/validation/press-progression-audit.json',JSON.stringify({method:'Six matched complete fixtures, three prior seeds and three unseen; current engine correction off/on; actual decisions, release/control outcomes and attack-stage failures split by team. Pressure cohorts use passive geometric proxy, not AI knowledge. No guaranteed improvement.',pairs},null,2)+'\n');
