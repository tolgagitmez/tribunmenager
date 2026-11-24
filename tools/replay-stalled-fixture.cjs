'use strict';
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const [base,head]=process.argv.slice(2);
assert(base&&head,'Provide baseline and candidate directories');
const roster=()=>Array.from({length:11},(_,id)=>({id,name:'Synthetic '+id,rating:82,passing:82,shooting:82,tackling:82,vision:82,composure:82,dribbling:82,pace:82,agility:82,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:70}));
function run(root,seed,enabled){
 const {Match}=require(path.resolve(root,'football-sim.js')),T=require(path.resolve(root,'tactics.js')),D=require(path.resolve(root,'attack-diagnostics.js'));
 const preset=id=>T.presets.find(p=>p.id===id).tactics;
 const m=new Match({seed,individualAI:true,territorialProgression:enabled,managerKicks:false,matchMinutes:5,formation:'4-3-3',awayFormation:'4-2-3-1',players:roster(),awayPlayers:roster(),tactics:preset('balanced'),awayTactics:preset('press')});
 const obs=D.attach(m,{maxEpisodes:20000}),longest={};let key=null,start=0;
 for(let i=0;i<36000&&!m.done;i++){
  obs.step(1/60);
  const r=m.restart||m.kick?.restartContext,k=r?String(r.id)+':'+r.kind:null;
  if(k!==key){key=k;start=m.time;}
  if(r)longest[r.kind]=Math.max(longest[r.kind]||0,m.time-start);
 }
 const r=m.restart||m.kick?.restartContext,d=obs.report();assert(d.valid,JSON.stringify(d.errors));obs.detach();
 return {seed,enabled,finished:m.done,time:m.time,inPlay:d.clock.inPlaySeconds,clock:m.clockState(),phase:m.phase,longest,shots:m.shots,box:d.teams.map(t=>t.stageCounts.box),restart:r?{kind:r.kind,spot:r.spot,setupPoint:r.setupPoint,ready:m.restartReady(r),taker:r.taker?.id,takerPosition:r.taker?{x:r.taker.x,z:r.taker.z}:null,opponents:m.team(1-r.team).map(p=>({id:p.id,x:p.x,z:p.z,target:m.targets.get(p)}))}:null,kick:m.kick?{kind:m.kick.kind,clock:m.kick.clock,duration:m.kick.duration}:null,events:m.events.slice(-6).map(e=>({time:e.time,type:e.type,title:e.title}))};
}
const pairs=[];
for(const seed of [311,42])for(const enabled of [false,true]){const row={base:run(base,seed,enabled),head:run(head,seed,enabled)};pairs.push(row);console.log('RESTART_REPLAY '+JSON.stringify(row));}
fs.mkdirSync('docs/validation',{recursive:true});fs.writeFileSync('docs/validation/restart-replay.json',JSON.stringify(pairs,null,2)+'\n');
assert(pairs.every(p=>p.head.finished),'Candidate fixture did not finish; inspect saved terminal state');
