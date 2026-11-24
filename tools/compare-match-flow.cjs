'use strict';
// Same harness for both revisions; read only, no injected possessions or shots.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {performance}=require('node:perf_hooks');
const [baseline,candidate]=process.argv.slice(2);
assert(baseline&&candidate,'usage: node tools/compare-match-flow.cjs BASE_DIR CANDIDATE_DIR');
const scenarios=[
 {id:'balanced21',seed:21},{id:'press42',seed:42,away:'press'},
 {id:'narrow21',seed:21,change:{width:'narrow'}},{id:'wide21',seed:21,change:{width:'wide'}}
];
if(process.argv.includes('--technical'))scenarios.push({id:'technical-press73',seed:73,away:'press',technical:true},{id:'technical-wing42',seed:42,change:{playstyle:'wing',width:'wide',fullbacks:'overlap'},technical:true},{id:'technical-narrow114',seed:114,change:{width:'narrow',passing:'short'},technical:true},{id:'technical-press206',seed:206,away:'press',technical:true});
if(process.argv.includes('--take-on'))scenarios.push({id:'takeon-press73',seed:73,away:'press',technical:true},{id:'takeon-wing42',seed:42,change:{playstyle:'wing',width:'wide'},technical:true},{id:'takeon-narrow114',seed:114,change:{width:'narrow',passing:'short'},technical:true},{id:'takeon-press206',seed:206,away:'press',technical:true});
const sum=a=>a.reduce((n,x)=>n+x,0),round=x=>Math.round(x*1000)/1000;
const roster=technical=>Array.from({length:11},(_,id)=>({id,name:'Synthetic '+id,rating:82,passing:82,shooting:82,tackling:82,vision:82,composure:technical?(id%2?92:70):82,dribbling:technical?(id%2?95:69):82,pace:82,agility:technical?(id%2?93:71):82,...(technical?{balance:id%2?91:70}:{}),fitness:92,preferredFoot:id%2?'right':'left',weakFoot:technical?(id%2?85:55):70}));
function run(root,s){
 const {Match}=require(path.resolve(root,'football-sim.js')),D=require(path.resolve(root,'attack-diagnostics.js')),T=require(path.resolve(root,'tactics.js'));
 const preset=id=>T.presets.find(p=>p.id===id).tactics;
 const m=new Match({takeOnCalibration:process.argv.includes('--take-on'),technicalTouchExperiment:process.argv.includes('--technical'),seed:s.seed,starters:[8,9,10,7,5,6,4,2,3,1,0],formation:'4-3-3',awayFormation:'4-2-3-1',matchMinutes:5,players:roster(s.technical),tactics:{...preset('balanced'),...s.change},awayTactics:preset(s.away||'counter')});
 const observer=D.attach(m,{maxEpisodes:20000}),timings=[],decisionAudit={reads:0,nearDefender:0,eligibleSkill:0,reachableFoot:0,feint:0,carry:0,pass:0,shot:0,other:0};
 if(process.argv.includes('--take-on')){
  const choose=m.choose,Brain=require(path.resolve(root,'player-brain.js'));
  m.choose=function(p){
   decisionAudit.reads++;
   const rivals=this.rivals(p);let defender=null,gap=Infinity;
   for(const q of rivals){const d=Math.hypot(q.x-p.x,q.z-p.z);if(d<gap){defender=q;gap=d;}}
   if(gap>=1.25&&gap<=3.35){
    decisionAudit.nearDefender++;
    if(Brain.canFeint(p,defender,{pressure:gap})){
     decisionAudit.eligibleSkill++;if(this.touchContact(p).ready&&this.ball.y<.25)decisionAudit.reachableFoot++;
    }
   }
   const result=choose.call(this,p),kind=result.kind;
   const key=['feint','carry','shot'].includes(kind)?kind:['pass','through','cross','cutback','long-pass'].includes(kind)?'pass':'other';decisionAudit[key]++;
   return result;
  };
 }
 let serial=m.releaseSerial,aimedPasses=0,backwardPassAims=0,forwardPassAims=0;
 for(let i=0;i<7200&&!m.done;i++){
  const start=performance.now();observer.step(1/60);timings.push(performance.now()-start);
  const f=m.flight;
  if(m.releaseSerial!==serial){
   serial=m.releaseSerial;
   if(f?.from&&f.point&&['pass','through','long-pass','cutback','cross'].includes(f.kind)){
    const gain=(f.point.x-f.from.x)*m.direction(f.from.team);aimedPasses++;
    if(gain< -3)backwardPassAims++;if(gain>3)forwardPassAims++;
   }
  }
  assert(Number.isFinite(m.ball.x)&&Number.isFinite(m.ball.z)&&Number.isFinite(m.ball.y),'non-finite ball');
 }
 const d=observer.report();assert(d.valid,JSON.stringify(d.errors));observer.detach();
 const counts=k=>sum(d.teams.map(t=>t.stageCounts[k]||0));
 timings.sort((a,b)=>a-b);
 return {id:s.id,elapsed:m.time,inPlay:d.clock.inPlaySeconds,goals:sum(m.score),shots:sum(m.shots),onTarget:sum(m.onTarget),passes:sum(m.passes),completed:sum(m.completed),turnovers:m.telemetry.turnovers,calibratedTakeOnAttempts:m.telemetry.calibratedTakeOnAttempts||0,calibratedTakeOnSuccesses:m.telemetry.calibratedTakeOnSuccesses||0,feints:m.telemetry.feints||0,beatenDefenders:m.telemetry.beatenDefenders||0,decisionAudit,takeOnGates:Object.fromEntries(Object.entries(m.telemetry).filter(([key])=>key.startsWith('takeOnGate_'))),technicalCutTouches:m.telemetry.technicalCutTouches||0,technicalProtectedReceives:m.telemetry.technicalProtectedReceives||0,dribbleTouches:m.telemetry.dribbleTouches||0,touchDeferrals:m.telemetry.touchDeferrals||0,directedTouches:m.telemetry.directedTouches||0,box:counts('box'),finalThird:counts('finalThird'),aimedPasses,backwardPassAims,forwardPassAims,stepMeanMs:round(sum(timings)/timings.length),stepP95Ms:round(timings[Math.floor((timings.length-1)*.95)]),steps:timings.length};
}
const pairs=[];
for(const s of scenarios){
 console.log('Scenario '+s.id);
 const base=run(baseline,s),head=run(candidate,s);
 pairs.push({id:s.id,base,head});
}
const keys=['elapsed','inPlay','goals','shots','onTarget','passes','completed','turnovers','calibratedTakeOnAttempts','calibratedTakeOnSuccesses','feints','beatenDefenders','technicalCutTouches','technicalProtectedReceives','dribbleTouches','touchDeferrals','directedTouches','box','finalThird','aimedPasses','backwardPassAims','forwardPassAims'];
function aggregate(side){
 const rows=pairs.map(p=>p[side]),r={};
 for(const key of keys)r[key]=round(sum(rows.map(x=>x[key])));
 r.passCompletionPct=r.passes?round(r.completed/r.passes*100):null;
 r.backwardAimPct=r.aimedPasses?round(r.backwardPassAims/r.aimedPasses*100):null;
 r.shotsPer120InPlay=r.inPlay?round(r.shots/r.inPlay*120):null;
 r.turnoversPer120InPlay=r.inPlay?round(r.turnovers/r.inPlay*120):null;
 r.boxPer120InPlay=r.inPlay?round(r.box/r.inPlay*120):null;
 r.stepMeanMs=round(sum(rows.map(x=>x.stepMeanMs*x.steps))/sum(rows.map(x=>x.steps)));
 r.maxScenarioP95Ms=Math.max(...rows.map(x=>x.stepP95Ms));
 return r;
}
const base=aggregate('base'),head=aggregate('head'),delta={};
for(const k of Object.keys(base))delta[k]=base[k]===null||head[k]===null?null:round(head[k]-base[k]);
const audit=side=>{const decisionAudit={},takeOnGates={};for(const pair of pairs){for(const [k,v] of Object.entries(pair[side].decisionAudit))decisionAudit[k]=(decisionAudit[k]||0)+v;for(const [k,v] of Object.entries(pair[side].takeOnGates))takeOnGates[k]=(takeOnGates[k]||0)+v;}return {decisionAudit,takeOnGates};};
const report={decisionAudit:{base:audit('base'),head:audit('head')},method:scenarios.length+' paired natural 120s simulations, same roster/seeds/tactics; passive observer. Pass aims are intended destinations at release, not actual completed direction. Step time includes observer and is not browser FPS. Small sample; differences are descriptive, not statistical proof.',base,head,delta,pairs};
fs.mkdirSync('docs/validation',{recursive:true});fs.writeFileSync('docs/validation/match-flow-comparison.json',JSON.stringify(report,null,2)+'\n');
if(process.argv.includes('--take-on'))console.log('TAKE_ON_DECISION_AUDIT '+JSON.stringify(report.decisionAudit));
console.log('MATCH_FLOW_COMPARISON '+JSON.stringify({base,head,delta,pairs:pairs.map(({id,base,head})=>({id,base:{shots:base.shots,box:base.box,turnovers:base.turnovers,touchDeferrals:base.touchDeferrals},head:{shots:head.shots,box:head.box,turnovers:head.turnovers,touchDeferrals:head.touchDeferrals,technicalCutTouches:head.technicalCutTouches,technicalProtectedReceives:head.technicalProtectedReceives}}))}));
