#!/usr/bin/env node
'use strict';
// Controlled event-boundary checks for the passive reception observer.
// Real Match.acquire/setRestart run in both observed and unobserved fixtures;
// fixture timestamps are selected explicitly to test inclusive window limits.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),{Match,BallPhysics}=require('../football-sim');
const file=path.join(root,'tools/profile-reception-facing.cjs'),source=fs.readFileSync(file,'utf8'),hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const start=source.indexOf('function observe(m,physics,detailed){'),end=source.indexOf('\nfunction run(',start);
assert(start>=0&&end>start,'observer source boundaries must be present');
const helperNames=['distance','gaps','pose','copyCommand'];
const helperSource=source.split('\n').filter(line=>helperNames.some(name=>line.startsWith('const '+name+'='))).join('\n');
assert.equal(helperSource.split('\n').length,helperNames.length,'all exact observer helpers must be extracted');
const observerSource=source.slice(start,end);
const observe=vm.runInNewContext(helperSource+'\n'+observerSource+'\nobserve',{structuredClone,passKinds:new Set(['pass','through','cutback','cross','long-pass'])},{filename:file});
function fixture(){
 const m=new Match({seed:21});m.players.forEach(p=>p.active=false);m.restart=null;m.owner=null;m.kick=null;m.time=10;
 const q=m.players[5],from=m.players[3],rival=m.players[14];
 for(const [p,x,z] of [[q,0,0],[from,-10,0],[rival,1,0]])Object.assign(p,{active:true,x,z,vx:0,vz:0,speed:0,face:0,touchClock:0,receiveClock:0,duelRecovery:0});
 m.ball={x:.2,y:BallPhysics.radius,z:0,vx:5,vy:0,vz:0};m.flight={id:7,kind:'pass',from,target:q,age:0,point:{x:0,z:0},offsidePlayers:[]};m.lastTouch=from;m.lastTeam=0;
 q.reception={flightId:7,fromId:from.id,at:10,refreshAt:10.2,mode:'open',point:{x:4,z:0},face:0,next:null};
 return {m,q,rival};
}
const cases=[
 {name:'opponent restart at exactly 1s is in both windows',event:'restart',at:11,expected:{restart1:1,restart2:1,acquire1:0,acquire2:0,elapsed1:1,elapsed2:0,pending2:1}},
 {name:'opponent restart at exactly 2s is in the 2s window',event:'restart',at:12,intermediate:11,expected:{restart1:0,restart2:1,acquire1:0,acquire2:0,elapsed1:1,elapsed2:1,pending2:0}},
 {name:'opponent acquisition at exactly 1s is in both windows',event:'acquire',at:11,expected:{restart1:0,restart2:0,acquire1:1,acquire2:1,elapsed1:1,elapsed2:0,pending2:1}},
 {name:'opponent acquisition at exactly 2s is in the 2s window',event:'acquire',at:12,intermediate:11,expected:{restart1:0,restart2:0,acquire1:0,acquire2:1,elapsed1:1,elapsed2:1,pending2:0}},
 {name:'1.5s opponent acquisition is absent from 1s and present in 2s',event:'acquire',at:11.5,intermediate:11,expected:{restart1:0,restart2:0,acquire1:0,acquire2:1,elapsed1:1,elapsed2:0,pending2:1}},
 {name:'an event beyond 2s is outside both windows',event:'acquire',at:12+1/60,expected:{restart1:0,restart2:0,acquire1:0,acquire2:0,elapsed1:1,elapsed2:1,pending2:0}},
 {name:'a 1.5s observation leaves the 2s window pending',event:null,at:11.5,expected:{restart1:0,restart2:0,acquire1:0,acquire2:0,elapsed1:1,elapsed2:0,pending2:1}}
];
const results=[];
for(const c of cases){
 const observed=fixture(),plain=fixture(),observer=observe(observed.m,BallPhysics,true);
 assert.equal(observed.m.acquire(observed.q),true);assert.equal(plain.m.acquire(plain.q),true);
 if(c.intermediate){observed.m.time=plain.m.time=c.intermediate;observer.sample();}
 observed.m.time=plain.m.time=c.at;
 if(c.event==='restart')for(const f of [observed,plain])f.m.setRestart('throw',1,{x:0,z:34});
 if(c.event==='acquire')for(const f of [observed,plain]){assert.equal(f.m.acquire(f.rival),true);assert.equal(f.m.acquire(f.rival),false,'a failed duplicate acquisition must not create a second event');}
 observer.sample();const data=observer.results(),summary=data.receptionSummary[0],s=summary.allWindows;
 assert.equal(s.count,1);assert.equal(summary.groundFacing.actualAcquisitions,1);
 const actual={restart1:s.opponentRestartWithin1s,restart2:s.opponentRestartWithin2s,acquire1:s.opponentAcquiredWithin1s,acquire2:s.opponentAcquiredWithin2s,elapsed1:s.elapsedWindows,elapsed2:s.elapsedWindows2s,pending2:s.pendingAtWindowEnd2s};
 assert.deepEqual(actual,c.expected,c.name);
 assert.equal(s.elapsedWithoutOpponentAcquisition2s,c.expected.elapsed2&&c.expected.acquire2===0?1:0);
 assert.equal(data.receptions[0].windowStatus2s,c.expected.pending2?'pending-at-window-end':'elapsed');
 for(const hook of ['acquire','release','setRestart'])delete observed.m[hook];
 assert.deepEqual(structuredClone(observed.m),structuredClone(plain.m),c.name+': observer changed real match state');
 results.push({name:c.name,actual,expected:c.expected,passiveStateEquality:true,passed:true});
}
const report={generatedAt:new Date().toISOString(),sources:{engine:hash(fs.readFileSync(path.join(root,'football-sim.js'))),observer:hash(source),extractedObserver:hash(observerSource),check:hash(fs.readFileSync(__filename))},method:'Extract the exact observe() and its exact data helpers from profile-reception-facing.cjs into a VM. Run real unchanged Match.acquire and Match.setRestart methods in paired observed/plain controlled fixtures. Select timestamps explicitly; these event-boundary fixtures do not claim a naturally simulated physical reception.',tests:results,total:results.length,verified:true};
const arg=process.argv.indexOf('--output'),output=arg<0?path.join(root,'docs/validation/reception-facing-observer-check.json'):path.resolve(process.argv[arg+1]);
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({output,total:results.length,verified:true}));
