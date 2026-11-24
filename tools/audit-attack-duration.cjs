'use strict';
// Compare physical playing time, not displayed or wall-clock minutes.
// No engine changes or synthetic goal/chance injection.
const fs=require('node:fs'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),D=require('../attack-diagnostics'),T=require('../tactics');
const presets=id=>T.presets.find(p=>p.id===id).tactics;
const fixtures=[{seed:42,away:'press'},{seed:527,away:'press'},{seed:301,away:'balanced'},{seed:607,away:'counter'}];
const roster=()=>Array.from({length:11},(_,id)=>({id,name:'Synthetic '+id,rating:82,passing:82,shooting:82,tackling:82,vision:82,composure:82,dribbling:82,pace:82,agility:82,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:70}));
function run(f,minutes){
 const m=new Match({seed:f.seed,individualAI:true,territorialProgression:true,managerKicks:false,matchMinutes:minutes,formation:'4-3-3',awayFormation:'4-2-3-1',players:roster(),awayPlayers:roster(),tactics:presets('balanced'),awayTactics:presets(f.away)});
 const o=D.attach(m,{maxEpisodes:20000}),depths=[{},{}],shotReads=[{},{}],choose=m.choose;
 m.choose=function(p){
  const result=choose.call(this,p),side=this.direction(p.team),depth=p.x*side,band=depth<0?'own-half':depth<52/3?'middle':depth<35.5?'final-third':'box-depth';
  const key=band+'/'+result.kind;depths[p.team][key]=(depths[p.team][key]||0)+1;
  if(depth>=52/3&&p.role!=='GK'){
   const s=this.shotWindow(p),zone=Math.abs(p.z)<19?'central':'wide';
   const reason=s.distance>29?'distance':s.open<.4?'blocked':s.execution<=.68?'execution':s.pressure>=.65?'pressure':s.quality<=.13?'quality':'geometric-window';
   const k=zone+'/'+reason+'/'+result.kind;shotReads[p.team][k]=(shotReads[p.team][k]||0)+1;
  }
  return result;
 };
 for(let i=0;i<minutes*60*60*2&&!m.done;i++)o.step(1/60);
 const d=o.report();assert(d.valid,JSON.stringify(d.errors));o.detach();
 const row={...f,minutes,finished:m.done,time:m.time,inPlay:d.clock.inPlaySeconds,clock:m.clockState(),phase:m.phase,restart:m.restart?.kind??null,teams:d.teams.map(t=>({team:t.team,shots:m.shots[t.team],goals:m.score[t.team],box:t.stageCounts.box,finalThird:t.stageCounts.finalThird,attacks:t.attacks,decisionZones:depths[t.team],shotReads:shotReads[t.team],endReasons:t.endReasons,endedByStage:t.endedByStage}))};
 console.log('DURATION_FIXTURE '+JSON.stringify(row));return row;
}
const pairs=fixtures.map(f=>({short:run(f,5),long:run(f,15)}));
const valid=pairs.filter(p=>p.short.finished&&p.long.finished);
const summaries=Object.fromEntries(['short','long'].map(k=>{const rows=valid.map(p=>p[k]),s=fn=>rows.reduce((a,r)=>a+fn(r),0),inPlay=s(r=>r.inPlay);return [k,{fixtures:rows.length,inPlay,teams:[0,1].map(team=>{const shots=s(r=>r.teams[team].shots),box=s(r=>r.teams[team].box);return {team,shots,box,shotsPer90Physical:inPlay?shots*5400/inPlay:null,boxPer90Physical:inPlay?box*5400/inPlay:null,finalThird:s(r=>r.teams[team].finalThird)};})}];}));
console.log('DURATION_SUMMARY '+JSON.stringify(summaries));
fs.mkdirSync('docs/validation',{recursive:true});fs.writeFileSync('docs/validation/attack-duration.json',JSON.stringify({method:'Four matched 5 vs 15 physical minute fixtures. Rates normalized to active time (not observed 90-minute totals). Decision read counts are not shots; geometry read is descriptive, not a guarantee or cause. Incomplete pairs excluded.',summaries,pairs},null,2)+'\n');
assert(valid.length===pairs.length,'Incomplete fixture: inspect diagnostic report');
