'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {scenarios,runScenario,buildCoverageReport}=require('../tools/check-attacking-coverage.cjs');
for(const s of scenarios)test(`controlled live coverage: ${s.id}`,()=>{
 const {result:r,match:m}=runScenario(s);assert.equal(r.outcome,s.expected);assert(r.frames.flight>0);assert(m.time>10);
 if(r.launchMode==='actual-windup-release'){assert.equal(r.opportunities.actualFootReleases,1);assert(r.frames.windup>0);assert(r.launch.flight);}
 if(s.kind==='header'){assert.equal(r.counts.headers,1);assert.equal(r.opportunities.eligibleAerialContacts,1);assert.equal(m.flight.kind,'shot');assert(m.shots[m.lastTouch.team]>0);}
 if(s.kind==='headed-pass'){assert.equal(r.counts.headedPasses,1);assert.equal(r.counts.headers,0);assert.equal(m.flight.kind,'pass');assert.equal(r.opportunities.eligibleAerialContacts,1);}
 if(s.kind==='aerial-clearance'){assert.equal(r.opportunities.eligibleAerialContacts,1);assert.equal(m.flight,null);assert.equal(m.lastTouch.team,1);}
 if(s.kind==='aerial-miss'){assert.equal(r.opportunities.crossReleases,1);assert(r.opportunities.descendingCrossWindows>0);assert.equal(r.opportunities.eligibleAerialContacts,0);assert.equal(r.counts.headers+r.counts.headedPasses,0);}
 if(s.kind==='cutback'){assert.equal(r.counts.cutbacks,1);assert.equal(r.counts.completedPasses,1);assert.equal(m.owner.id,1+(s.side<0?11:0));}
 if(s.kind==='cutback-intercept'){assert.equal(r.counts.cutbacks,1);assert.equal(r.counts.completedPasses,0);assert.equal(m.owner.team,1);}
 if(s.kind==='cutback-loose'){assert.equal(r.counts.cutbacks,1);assert.equal(r.counts.looseBalls,1);assert.equal(m.owner,null);assert.equal(m.ball.vy,1.3);}
 if(s.kind==='shot-block'){assert.equal(r.counts.shotEvents,1);assert.equal(m.owner,null);assert.equal(m.flight,null);assert(r.events.some(e=>e.type==='block'));}
 if(s.kind==='offside'){assert.equal(r.opportunities.flaggedOffsideFlights,1);assert.equal(r.counts.offsides,1);assert.equal(m.restart.kind,'free-kick');assert.equal(m.restart.team,1);assert.equal(r.counts.completedPasses,0);}
 if(s.kind==='onside'){assert.equal(r.opportunities.flaggedOffsideFlights,0);assert.equal(r.counts.offsides,0);assert.equal(r.counts.completedPasses,1);}
 if(s.kind==='keeper-catch'){assert.equal(r.counts.keeperCatches,1);assert.equal(m.owner.holdingBall,true);assert(m.owner.holdClock>0);assert.deepEqual([m.ball.vx,m.ball.vy,m.ball.vz],[0,0,0]);}
 if(s.kind==='keeper-parry'){assert.equal(r.counts.keeperCatches,0);assert.equal(r.counts.saveEvents,1);assert.equal(r.counts.looseBalls,1);assert.equal(m.owner,null);assert(m.ball.vx<0);}
 if(s.kind==='keeper-fast-catch'){assert.equal(r.motion,'real-rig-two-hands');assert.equal(r.counts.keeperCatches,1);assert.equal(r.counts.fastCatches,1);assert.equal(m.owner.holdingBall,true);}
 if(s.kind==='keeper-skill-low'){assert.equal(r.motion,'real-rig-two-hands');assert.equal(r.counts.keeperCatches,0);assert.equal(r.counts.saveEvents,1);assert.equal(m.owner,null);}
 if(s.kind==='keeper-skill-high'){assert.equal(r.motion,'real-rig-two-hands');assert.equal(r.counts.keeperCatches,1);assert.equal(r.counts.fastCatches,1);assert.equal(m.owner.holdingBall,true);}
 if(s.kind==='keeper-backpass'){assert.equal(r.opportunities.keeperOwnBackpassFlights,1);assert.equal(r.opportunities.keeperOpponentShotFlights,0);assert.equal(r.counts.keeperCatches,0);assert.equal(r.counts.saveEvents,0);assert.equal(m.owner.holdingBall,false);}
 if(s.kind==='keeper-late'){assert.equal(r.opportunities.keeperOpponentShotFlights,1);assert.equal(r.counts.goalEvents,1);assert.equal(r.counts.saveEvents,0);assert.equal(r.counts.keeperCatches,0);}
 if(s.kind==='keeper-screened'){assert(r.counts.screenedReads>0);assert.equal(r.counts.goalEvents,1);assert.equal(r.counts.saveEvents,0);}
});
test('all selected fixtures repeat complete Match state and keep controlled denominators separate',()=>{
 const r=buildCoverageReport();assert.equal(r.verified,true);assert.equal(r.naturalSample,false);assert.equal(r.fixtureCount,21);assert(r.runs.every(x=>x.deterministicReplay));
 assert.equal(r.opportunities.crossReleases,5);assert.equal(r.opportunities.eligibleAerialContacts,4);assert.equal(r.opportunities.cutbackReleases,4);assert.equal(r.opportunities.flaggedOffsideFlights,1);
 assert.equal(r.opportunities.keeperOpponentShotFlights,8);assert.equal(r.opportunities.keeperOwnBackpassFlights,1);assert.equal(r.outcomes['held-catch'],4);assert.equal(r.outcomes.parry,2);assert.equal(r.outcomes['goal-before-contact'],2);
});
test('the keeper skill examples use the same incoming flight and ordinary two-hand model',()=>{
 const low=runScenario('keeper-skill60-matched-flight').result,high=runScenario('keeper-skill94-matched-flight').result;
 assert.equal(low.rng.before,high.rng.before);assert.deepEqual(low.start.ball,high.start.ball);assert.equal(low.motion,high.motion);
 const input=r=>r.start.activePlayers.map(p=>({...p,skill:p.role==='GK'?null:p.skill}));assert.deepEqual(input(low),input(high));
 assert.equal(low.start.activePlayers.find(p=>p.role==='GK').skill,60);assert.equal(high.start.activePlayers.find(p=>p.role==='GK').skill,94);
 assert.equal(low.outcome,'parry');assert.equal(high.outcome,'held-catch');
});
