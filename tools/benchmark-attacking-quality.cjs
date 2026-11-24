'use strict';
// CPU-only natural matches. Run this identical file in separate checkouts
// to compare revisions: globals installed by the engine must not be shared.
const path=require('node:path'),{performance}=require('node:perf_hooks');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const seconds=Number(process.argv[3]||300);
if(!Number.isFinite(seconds)||seconds<20||seconds>300)throw Error('Use 20..300 nominal match seconds');
const {Match}=require(path.join(root,'football-sim.js'));
const Diagnostics=require(path.join(root,'attack-diagnostics.js'));
const scenarios=[
 {seed:113,tactics:{playstyle:'possession',passing:'short'},awayTactics:{playstyle:'counter',passing:'direct'}},
 {seed:271,tactics:{playstyle:'wing',passing:'mixed'},awayTactics:{playstyle:'possession',passing:'short'}},
 {seed:5291,tactics:{playstyle:'counter',passing:'direct'},awayTactics:{playstyle:'wing',passing:'mixed'}}
];
const dt=1/60;
function percentile(a,p){const b=a.slice().sort((x,y)=>x-y);return b[Math.floor((b.length-1)*p)]??null;}
function run(s){
 const m=new Match({...s,individualAI:true,rules:{periodSeconds:seconds/2,halftimeSeconds:8,addedTime:true,maxAddedSeconds:60}});
 const observer=Diagnostics.attach(m),samples=[];
 let steps=0,activeMin=22,activeMax=0;
 const maxSteps=Math.ceil((seconds+130)*60);
 while(!m.done&&steps<maxSteps){
  const before=performance.now();observer.step(dt);samples.push(performance.now()-before);
  const active=m.players.filter(p=>p.active&&!p.referee).length;
  activeMin=Math.min(activeMin,active);activeMax=Math.max(activeMax,active);
  steps++;
 }
 if(!m.done)throw Error('Match did not finish within bounded added-time window: '+s.seed);
 const report=observer.summary();observer.detach();
 return {seed:s.seed,tactics:s.tactics,awayTactics:s.awayTactics,score:m.score,steps,activeMin,activeMax,
  clock:report.clock,teams:report.teams.map((t,i)=>({team:i,attacks:t.attacks,stages:t.stageCounts,eligibleReached:t.eligibleReached,passes:t.passes,shots:t.shots,xg:m.xg[i],rates:t.rates,
   boxRunnerCommands:t.evidence.boxRunnerCommands,boxRunnerArrivals:t.evidence.boxRunnerArrivals})),
  telemetry:{throughBalls:m.telemetry.throughBalls,alignedThroughBalls:m.telemetry.alignedThroughBalls??0,thirdManCompletions:m.telemetry.thirdManCompletions??0,giveGoCompletions:m.telemetry.giveGoCompletions??0,placedShotReleases:m.telemetry.placedShotReleases??0,drivenShotReleases:m.telemetry.drivenShotReleases??0,curledShotReleases:m.telemetry.curledShotReleases??0,chipShotReleases:m.telemetry.chipShotReleases??0,firstTimeShotReleases:m.telemetry.firstTimeShotReleases??0,directionalCutTouches:m.telemetry.directionalCutTouches??0,accelerationBurstTouches:m.telemetry.accelerationBurstTouches??0,shoulderContests:m.telemetry.shoulderContests??0,pressuredControlDeferrals:m.telemetry.pressuredControlDeferrals??0,stepOverAttempts:m.telemetry.stepOverAttempts??0,progressiveCarryChoices:m.telemetry.progressiveCarryChoices??0,openFieldCarryChoices:m.telemetry.openFieldCarryChoices??0,finalThirdLinkChoices:m.telemetry.finalThirdLinkChoices??0,progressiveFirstTouches:m.telemetry.progressiveFirstTouches??0,diagonalRuns:m.telemetry.diagonalRuns??0,blindSideRuns:m.telemetry.blindSideRuns??0,decoyRuns:m.telemetry.decoyRuns??0,diagonalFeedChoices:m.telemetry.diagonalFeedChoices??0},
  cpuStepIncludingObserver:{medianMs:percentile(samples,.5),p95Ms:percentile(samples,.95),totalMs:samples.reduce((a,b)=>a+b,0)}};
}
const result={kind:'natural matches, CPU step including observer; not GPU or device FPS',node:process.version,nominalMatchSeconds:seconds,runs:scenarios.map(run)};
console.log(JSON.stringify(result,null,2));
