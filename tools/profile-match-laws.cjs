#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),v8=require('node:v8'),assert=require('node:assert/strict'),path=require('node:path');
const {Match}=require('../football-sim'),C=require('../club-data'),D=require('../attack-diagnostics');
const root=path.resolve(__dirname,'..'),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const paths=['football-sim.js','match-rules.js','referee-laws.js','pitch-laws.js','player-model.js','player-model-profiles.json','player-perception.js','team-intent.js','attack-diagnostics.js','club-data.js','tools/profile-match-laws.cjs'];
const sources=Object.fromEntries(paths.map(p=>[p,hash(fs.readFileSync(path.join(root,p)))]));
const cfg={seed:21,formation:'4-3-3',players:C.createRoster(),starters:C.starters.slice(),matchMinutes:5};
const snapshot=m=>v8.deserialize(v8.serialize({...m,motion:null}));
function run(observed){
 const m=new Match(structuredClone(cfg)),observer=observed?D.attach(m):null;let steps=0;
 for(;!m.done&&steps<1200*60;steps++){
  if(observer)observer.step();else m.step();
  assert(Number.isFinite(m.ball.x)&&Number.isFinite(m.ball.y)&&Number.isFinite(m.ball.z));
  assert(m.players.every(p=>[p.x,p.z,p.vx,p.vz].every(Number.isFinite)));
 }
 assert(m.done,'default match must terminate');assert.equal(m.finishReason,'full-time');assert.equal(m.period,2);
 assert(m.matchClock.periodLengths.every(n=>n>=150-1e-8));
 const state=snapshot(m),report=observer?.report();
 if(report){assert.deepEqual(snapshot(m),state,'report reads preserve state');assert(report.valid);assert(Math.abs(report.clock.observedSeconds-m.time)<1e-6);const c=report.clock;assert(Math.abs(c.deadBallSeconds-c.restartSeconds-c.goalPauseSeconds-c.halftimeSeconds)<1e-6);observer.detach();}
 return {state,summary:{elapsedSeconds:m.time,periodLengths:m.matchClock.periodLengths,addedAnnounced:m.matchClock.announcedAdded,halftimeSeconds:m.matchClock.breakElapsed,score:m.score,shots:m.shots,fouls:m.fouls,redCards:m.reds,passes:m.passes,completed:m.completed,frameHits:m.telemetry.frameHits||0,offsides:m.telemetry.offsides,penaltyDecisions:m.referee.decisions.filter(d=>d.restart==='penalty').length,advantageDecisions:m.referee.decisions.filter(d=>d.status!=='stopped').length,finishReason:m.finishReason,finalSeed:m.seed,steps},clock:report?.clock};
}
const first=run(true);process.stderr.write('observed match complete\n');const plain=run(false);assert.deepEqual(first.state,plain.state);process.stderr.write('plain match equal\n');const replay=run(true);assert.deepEqual(first.state,replay.state);assert.deepEqual(first.clock,replay.clock);
for(const p of paths)assert.equal(hash(fs.readFileSync(path.join(root,p))),sources[p],p+' changed');
const report={sources,method:'One natural five-minute nominal scenario, seed21, with default competition rules. Observed/plain/observed replay must terminate and produce identical complete serializable state. This is lifecycle/replay coverage; event frequencies are not a balance estimate.',naturalScenarios:1,executions:3,nominalSeconds:300,summary:first.summary,clock:first.clock,verification:{fullTime:true,twoPeriods:true,finite:true,observerEqual:true,replayEqual:true,reportReadOnly:true,clockPartitions:true,sourcesStable:true},verified:true};
fs.writeFileSync(path.join(root,'docs/validation/match-laws-natural.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify({verified:true,...first.summary})+'\n');
