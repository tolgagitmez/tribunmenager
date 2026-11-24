'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {Match}=require('../football-sim'),D=require('../attack-diagnostics'),T=require('../tactics');
const starters=[8,9,10,7,5,6,4,2,3,1,0],dt=1/60;
const roster=()=>Array.from({length:11},(_,id)=>({id,name:'Synthetic '+id,rating:82,passing:82,shooting:82,tackling:82,vision:82,composure:82,dribbling:82,pace:82,agility:82,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:70}));
const preset=id=>T.presets.find(p=>p.id===id).tactics;
const scenarios=[{id:'balanced21',seed:21},{id:'press42',seed:42,away:'press'},{id:'narrow21',seed:21,change:{width:'narrow'}},{id:'wide21',seed:21,change:{width:'wide'}}];
const category=(p,team)=>{const x=p.x*(team===0?1:-1);return x<0?'own-half':x<17?'progress':x<35?'final-third':x<49?'box-approach':'deep';};
function run(s){
 const cfg={seed:s.seed,starters,formation:'4-3-3',awayFormation:'4-2-3-1',matchMinutes:5,players:roster(),tactics:{...preset('balanced'),...s.change},awayTactics:preset(s.away||'counter')};
 const m=new Match(cfg),o=D.attach(m,{maxEpisodes:20000}),samples={late:0,lateSupported:0,lateRunners:0,lateUnsupported:0,receiver:0,receiverFacingAway:0,receiverSupported:0,receiverRunners:0},losses={},gains=[];
 let turnovers=m.telemetry.turnovers,previous=m.owner?.id;
 for(let i=0;i<7200&&!m.done;i++){
   o.step(dt);
   const p=m.owner;
   if(p){
     const zone=category(p,p.team);
     const support=[...m.targets].filter(([q,t])=>q.active&&q!==p&&q.team===p.team&&['support','receive-run','return-support','between-lines','cutback-support'].includes(t.state)&&Math.hypot(q.x-p.x,q.z-p.z)<23);
     const runs=[...m.targets].filter(([q,t])=>q.active&&q!==p&&q.team===p.team&&['box-run','channel-run','penetration'].includes(t.state));
     if(['final-third','box-approach'].includes(zone)){samples.late++;if(support.length)samples.lateSupported++;else samples.lateUnsupported++;if(runs.length)samples.lateRunners++;}
     if(p.id!==previous&&p.receiveMode){samples.receiver++;if(Math.cos(p.face)*m.direction(p.team)<-.15)samples.receiverFacingAway++;if(support.length)samples.receiverSupported++;if(runs.length)samples.receiverRunners++;}
   }
   if(m.telemetry.turnovers>turnovers){const e=m.lastGain||{},q=m.players.find(x=>x.id===e.player),zone=q?category(q,q.team):'unknown';losses[zone]=(losses[zone]||0)+1;gains.push({time:Math.round(m.time*10)/10,team:q?.team,zone,player:q?.id,x:q?.x,z:q?.z});turnovers=m.telemetry.turnovers;}
   previous=p?.id;
 }
 const d=o.report();assert(d.valid,JSON.stringify(d.errors));o.detach();
 const territorial={
  finalThird:d.teams.reduce((n,t)=>n+(t.stageCounts.finalThird||0),0),
  box:d.teams.reduce((n,t)=>n+(t.stageCounts.box||0),0),
  shot:d.teams.reduce((n,t)=>n+(t.stageCounts.shot||0),0)
 };
 // Count losses from the attacking team's actual ball position, not from
 // the winning opponent's position (which mirrors the territorial label).
 const lossZones={};
 const ended=d.episodes.filter(e=>['duel-loss','pass-interception','opponent-control'].includes(e.endReason)&&e.endPosition);
 for(const e of ended){const zone=category(e.endPosition,e.team);lossZones[zone]=(lossZones[zone]||0)+1;}
 const locationBuckets={};
 for(const e of ended){const p=e.endPosition,side=e.team===0?1:-1,cell=Math.floor((p.x*side+52)/8)+'/'+Math.floor((p.z+34)/8);locationBuckets[cell]=(locationBuckets[cell]||0)+1;}
 const repeatedZoneLosses=Object.values(locationBuckets).reduce((n,count)=>n+Math.max(0,count-1),0);
 const eligible=d.episodes.filter(e=>e.origin==='gain'&&e.confirmedControl&&!e.startedBeyond?.finalThird&&!e.startedBeyond?.box);
 const cohorts={},endReasons={};
 for(const e of eligible){const key=(e.pressureRequired?'pressed':'unpressed')+'-'+(e.eligibility?.lineBreak?'screen':'no-screen');const group=cohorts[key]??={count:0,escape:0,line:0,finalThird:0,box:0,shot:0};group.count++;for(const [from,to]of [['pressureEscape','escape'],['lineBreak','line'],['finalThird','finalThird'],['box','box'],['shot','shot']])if(e.stages?.[from])group[to]++;const reason=e.endReason||e.status;endReasons[reason]=(endReasons[reason]||0)+1;}
 return {id:s.id,seed:s.seed,elapsed:m.time,inPlay:d.clock.inPlaySeconds,score:m.score,shots:m.shots,passes:m.passes,completed:m.completed,turnovers:m.telemetry.turnovers,telemetry:m.telemetry,samples,losses,gains,territorial,lossZones,repeatedZoneLosses,cohorts,endReasons,episodes:eligible.map(e=>({id:e.id,team:e.team,reason:e.endReason,status:e.status,pressure:e.pressureRequired,stages:e.stages,last:e.lastStage,endPosition:e.endPosition,startPosition:e.startPosition,evidence:e.evidence,observations:e.observations}))};
}
const results=scenarios.map(s=>{process.stderr.write('SCENARIO '+s.id+'\n');return run(s);});
const overall={inPlay:0,shots:0,cohort:0,cohorts:{},losses:{},lossZones:{},territorial:{finalThird:0,box:0,shot:0},repeatedZoneLosses:0,endReasons:{}};
for(const r of results){overall.inPlay+=r.inPlay;overall.shots+=r.shots[0]+r.shots[1];for(const [k,n]of Object.entries(r.territorial))overall.territorial[k]+=n;overall.repeatedZoneLosses+=r.repeatedZoneLosses;for(const [k,n]of Object.entries(r.lossZones))overall.lossZones[k]=(overall.lossZones[k]||0)+n;for(const [k,g]of Object.entries(r.cohorts)){const n=overall.cohorts[k]??={count:0,escape:0,line:0,finalThird:0,box:0,shot:0};for(const [key,val]of Object.entries(g))n[key]+=val;overall.cohort+=g.count;}for(const [k,n]of Object.entries(r.losses))overall.losses[k]=(overall.losses[k]||0)+n;for(const [k,n]of Object.entries(r.endReasons))overall.endReasons[k]=(overall.endReasons[k]||0)+n;}
const report={engineSHA256:crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname,'../football-sim.js'))).digest('hex'),method:'Four deterministic natural 120s games, original decision loop with actual passive episode observer',overall,results};
const filename=path.resolve('docs/validation/current-attack-120s.json');fs.mkdirSync(path.dirname(filename),{recursive:true});fs.writeFileSync(filename,JSON.stringify(report,null,2)+'\n');
console.log('ATTACK_AUDIT '+JSON.stringify({engine:report.engineSHA256,overall,scenarios:results.map(r=>({id:r.id,inPlay:r.inPlay,shots:r.shots,samples:r.samples,cohorts:r.cohorts,losses:r.losses,lossZones:r.lossZones,territorial:r.territorial,repeatedZoneLosses:r.repeatedZoneLosses,safeForwardBeforeHold:r.telemetry.safeForwardBeforeHold||0,openShotReleases:r.telemetry.openShotReleases||0,endReasons:r.endReasons}))}));
