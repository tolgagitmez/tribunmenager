'use strict';
// Diagnostic only: same engine, same inputs, correction on/off.
// No injected possession, shot, opponent movement or random draws.
const fs=require('node:fs'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),D=require('../attack-diagnostics'),T=require('../tactics');
const seeds=[42,73,206,311,527,881],presets=id=>T.presets.find(p=>p.id===id).tactics;
const roster=()=>Array.from({length:11},(_,id)=>({id,name:'Synthetic '+id,rating:82,passing:82,shooting:82,tackling:82,vision:82,composure:82,dribbling:82,pace:82,agility:82,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:70}));
const bump=(o,k)=>{o[k]=(o[k]||0)+1;};
const stageKeys=['pressureEscape','lineBreak','finalThird','box','shot'];
function run(seed,enabled,safety=false){
 const m=new Match({seed,individualAI:true,territorialProgression:enabled,acceleratingRunReceivers:safety,managerKicks:false,matchMinutes:5,formation:'4-3-3',awayFormation:'4-2-3-1',players:roster(),awayPlayers:roster(),tactics:presets('balanced'),awayTactics:presets('press')});
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
    const team=f.from.team,key=f.acceleratingRun?'accelerating-run':f.territorialPass?'corrected':'ordinary';
    passes.set(f.id,{team,key});bump(releases[team],key+'/released');
   }
  }
  if(prior&&!m.flight&&m.owner&&passes.has(prior.id)){
   const rec=passes.get(prior.id);bump(releases[rec.team],rec.key+(m.owner.team===rec.team?'/own-control':'/opponent-control'));passes.delete(prior.id);
  }
  if(before&&!m.owner&&!m.kick&&!m.flight&&!m.restart){const depth=before.x*m.direction(before.team);bump(losses[before.team],depth<0?'own-half':depth<52/3?'middle':'advanced');}
 }
 // A stalled fixture is evidence, not a missing row or a completed match.
 const r=m.restart||m.kick?.restartContext;
 const terminal={finished:m.done,time:m.time,clock:m.clockState(),phase:m.phase,pendingManagerKick:!!m.pendingManagerKick,penaltyState:m.penaltyAttempt?.state??null,restart:r?{kind:r.kind,team:r.team,spot:r.spot,clock:r.clock,setupPoint:r.setupPoint??null,taker:r.taker?.id,takerPosition:r.taker?{x:r.taker.x,z:r.taker.z,face:r.taker.face}:null,ready:m.restartReady(r),wall:r.layout?[...r.layout.wall].map(([id,point])=>({id,point,actual:{x:m.players[id].x,z:m.players[id].z}})):[],opponents:m.team(1-r.team).map(p=>({id:p.id,x:p.x,z:p.z,target:m.targets.get(p)??null}))}:null,kick:m.kick?{kind:m.kick.kind,clock:m.kick.clock,duration:m.kick.duration,point:m.kick.point,foot:m.contactPoint(m.kick.p,m.kick.kind)}:null,ball:{...m.ball},recentEvents:m.events.slice(-8).map(e=>({type:e.type,time:e.time,title:e.title}))};
 if(!m.done)console.log('PRESS_STALL '+JSON.stringify({seed,enabled,safety,terminal}));
 const report=obs.report();assert(report.valid,JSON.stringify(report.errors));obs.detach();
 const teams=report.teams.map(t=>({team:t.team,attacks:t.attacks,shots:m.shots[t.team],goals:m.score[t.team],box:t.stageCounts.box,finalThird:t.stageCounts.finalThird,eligible:t.stageEligibility,reached:t.eligibleReached,endReasons:t.endReasons,endedByStage:t.endedByStage,decisions:decisions[t.team],releaseOutcomes:releases[t.team],looseControl:losses[t.team]}));
 const cohorts=[0,1].map(team=>{const rows=report.episodes.filter(e=>e.team===team&&e.pressureRequired&&e.confirmedControl),endReasons={};for(const e of rows)bump(endReasons,e.endReason||'pending');return {team,count:rows.length,stages:Object.fromEntries(stageKeys.map(k=>[k,rows.filter(e=>e.stages[k]).length])),endReasons};});
 return {seed,enabled,safety,terminal,inPlay:report.clock.inPlaySeconds,teams,cohorts,turnovers:m.telemetry.turnovers,acceleratingRunReleases:m.telemetry.acceleratingRunReleases||0,acceleratingRunCompletions:m.telemetry.acceleratingRunCompletions||0,forwardReleases:m.telemetry.territorialPassReleases||0,forwardCompletions:m.telemetry.territorialPassCompletions||0};
}
const brief=r=>({finished:r.terminal.finished,inPlay:r.inPlay,turnovers:r.turnovers,acceleratingRunReleases:r.acceleratingRunReleases,acceleratingRunCompletions:r.acceleratingRunCompletions,forwardReleases:r.forwardReleases,forwardCompletions:r.forwardCompletions,teams:r.teams.map(t=>({team:t.team,box:t.box,shots:t.shots,finalThird:t.finalThird})),cohorts:r.cohorts});
const pairs=seeds.map(seed=>{const off=run(seed,false),on=run(seed,true),safe=run(seed,true,true);console.log('PRESS_PAIR '+JSON.stringify({seed,off:brief(off),on:brief(on),safe:brief(safe)}));return {seed,off,on,safe};});
const aggregates=Object.fromEntries(['off','on','safe'].map(mode=>{const comparable=pairs.filter(p=>['off','on','safe'].every(k=>p[k].terminal.finished)),rows=comparable.map(p=>p[mode]),sum=f=>rows.reduce((n,r)=>n+f(r),0),inPlay=sum(r=>r.inPlay);return [mode,{comparableFixtures:rows.length,incompleteFixtures:pairs.length-rows.length,inPlay,turnovers:sum(r=>r.turnovers),acceleratingRunReleases:sum(r=>r.acceleratingRunReleases),acceleratingRunCompletions:sum(r=>r.acceleratingRunCompletions),forwardReleases:sum(r=>r.forwardReleases),forwardCompletions:sum(r=>r.forwardCompletions),teams:[0,1].map(team=>{const box=sum(r=>r.teams[team].box),shots=sum(r=>r.teams[team].shots);return {team,box,shots,finalThird:sum(r=>r.teams[team].finalThird),boxPer120InPlay:inPlay?box*120/inPlay:null,shotsPer120InPlay:inPlay?shots*120/inPlay:null};})}];}));
console.log('PRESS_AGGREGATE '+JSON.stringify(aggregates));
fs.mkdirSync('docs/validation',{recursive:true});fs.writeFileSync('docs/validation/accelerating-run-audit.json',JSON.stringify({method:'Six matched complete fixtures, three prior seeds and three unseen; territorial off/current/on with accelerating run receivers. Actual decisions, release/control outcomes and attack-stage failures split by team. Pressure cohorts use passive geometric proxy, not AI knowledge. Incomplete fixtures are explicitly recorded and excluded from all three matched outcome aggregates; any stall fails the audit after writing evidence. No guaranteed improvement.',aggregates,pairs},null,2)+'\n');
assert(pairs.every(p=>['off','on','safe'].every(k=>p[k].terminal.finished)),'At least one fixture stalled; see PRESS_STALL and uploaded diagnostic report');
