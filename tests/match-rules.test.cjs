'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Rules=require('../match-rules');
const clock=rules=>Rules.createClock(Rules.normalize({rules:{periodSeconds:10,halftimeSeconds:2,...rules}}));
test('competition defaults and bounded explicit variants preserve compressed durations',()=>{
 assert.equal(Rules.normalize({matchMinutes:90}).periodSeconds,2700);assert.equal(Rules.normalize({matchMinutes:15}).periodSeconds,450);assert.equal(Rules.normalize({matchMinutes:5}).periodSeconds,150);
 const defaults=Rules.normalize({});assert.equal(defaults.maxSubstitutions,5);assert.equal(defaults.substitutionWindows,3);assert.equal(defaults.minPlayers,7);
 assert.equal(Rules.normalize({rules:{maxSubstitutions:3,halftimeSeconds:0}}).maxSubstitutions,3);assert.equal(Rules.normalize({rules:{halftimeSeconds:0}}).halftimeSeconds,0);
 assert.equal(Rules.normalize({rules:{periodSeconds:NaN,maxSubstitutions:-1,substitutionWindows:99}}).periodSeconds,150);
 assert.equal(Rules.normalize({rules:{maxSubstitutions:-1}}).maxSubstitutions,0);assert.equal(Rules.normalize({rules:{substitutionWindows:99}}).substitutionWindows,11);
});
test('halftime is a real separate clock and second half starts at its nominal display time',()=>{
 const c=clock();assert.equal(Rules.tick(c,10).transition,'halftime');assert.equal(c.phase,'halftime');const view=Rules.clockView(c);assert.equal(view.displaySeconds,10);
 assert.equal(Rules.tick(c,1).transition,null);assert.equal(c.periodElapsed,10);assert.equal(c.elapsed,11);assert.equal(c.breakElapsed,1);
 assert.equal(Rules.tick(c,1).transition,'second-half');assert.equal(c.period,2);assert.equal(c.periodElapsed,0);assert.equal(Rules.clockView(c).displaySeconds,10);
 assert.equal(Rules.tick(c,10).transition,'finished');assert.equal(c.phase,'finished');assert.deepEqual(c.periodLengths,[10,10]);
});
test('normal restart grace avoids treating every routine restart second as added time',()=>{
 const c=clock({restartGraceSeconds:3});Rules.tick(c,2,{stoppedReason:'restart',stoppageId:1});assert.equal(c.lostSeconds[0],0);
 Rules.tick(c,3,{stoppedReason:'restart',stoppageId:1});assert.equal(c.lostSeconds[0],2);
 Rules.tick(c,1,{stoppedReason:'restart',stoppageId:2});assert.equal(c.lostSeconds[0],2);
 const result=Rules.tick(c,4);assert.equal(result.announcedAdded,2);assert.equal(result.transition,null);assert.equal(Rules.formatClock(c),'00:10 +00:00');
 assert.equal(Rules.tick(c,2).transition,'halftime');
});
test('announcement rounds the minimum once and stoppages during added time extend it',()=>{
 const c=clock({roundSeconds:1});Rules.tick(c,1.2,{stoppedReason:'goal',stoppageId:1});Rules.tick(c,8.8);
 assert.equal(c.announcedAdded[0],2);assert.equal(Rules.tick(c,1,{stoppedReason:'substitution',stoppageId:2}).transition,null);
 assert.equal(c.announcedAdded[0],2);assert.equal(c.addedAfterAnnouncement[0],1);assert.equal(Rules.clockView(c).addedTargetSeconds,3);
 assert.equal(Rules.tick(c,1).transition,null);assert.equal(Rules.tick(c,1).transition,'halftime');assert.equal(c.periodLengths[0],13);
});
test('a tick straddling regulation announces only the loss before regulation ended',()=>{
 const c=clock({roundSeconds:1});Rules.tick(c,9.5);const r=Rules.tick(c,1,{stoppedReason:'injury',stoppageId:1});
 assert.equal(r.announcedAdded,1);assert.equal(c.lostSeconds[0],1);assert.equal(c.addedAfterAnnouncement[0],.5);assert.equal(Rules.clockView(c).addedTargetSeconds,1.5);
});
test('a pending penalty extends either period until its physical sequence finishes',()=>{
 const c=clock({halftimeSeconds:0});assert.equal(Rules.tick(c,10,{penaltyPending:true}).transition,null);assert.equal(c.phase,'playing');assert.equal(Rules.tick(c,1,{penaltyPending:true}).transition,null);
 assert.equal(Rules.tick(c,0).transition,'halftime');assert.equal(Rules.tick(c,0).transition,'second-half');assert.equal(Rules.tick(c,10,{penaltyPending:true}).transition,null);
 assert.equal(Rules.tick(c,.5).transition,'finished');assert.equal(c.periodLengths[1],10.5);
});
test('added time can be explicitly disabled or capped by competition configuration',()=>{
 const disabled=clock({addedTime:false});Rules.tick(disabled,5,{stoppedReason:'goal'});assert.equal(Rules.tick(disabled,5).transition,'halftime');assert.equal(disabled.announcedAdded[0],0);
 const capped=clock({maxAddedSeconds:2});Rules.tick(capped,5,{stoppedReason:'injury'});Rules.tick(capped,5);assert.equal(capped.announcedAdded[0],2);assert.equal(Rules.tick(capped,2).transition,'halftime');
});
test('halftime delay is excluded from second-half added time and report views are copies',()=>{
 const c=clock();Rules.tick(c,10);Rules.tick(c,2,{stoppedReason:'injury'});assert.deepEqual(c.lostSeconds,[0,0]);
 const before=JSON.stringify(c),view=Rules.clockView(c);view.lostSeconds[0]=999;assert.equal(JSON.stringify(c),before);
});
test('negative or nonfinite dt cannot corrupt clocks and final clocks do not advance',()=>{
 const c=clock();for(const dt of [-1,NaN,Infinity])Rules.tick(c,dt);assert.equal(c.elapsed,0);
 Rules.tick(c,10);Rules.tick(c,2);Rules.tick(c,10);const before=JSON.stringify(c);Rules.tick(c,2);assert.equal(JSON.stringify(c),before);
});
test('five substitutions can share three actual stoppages while a fourth window is rejected',()=>{
 const rules=Rules.normalize({}),state=Rules.createSubstitutionState();
 function swap(id){const d=Rules.substitutionAllowance(rules,state,{phase:'playing',deadBall:true,stoppageId:id});Rules.recordSubstitution(state,d);return d;}
 assert(swap(1).ok);assert(swap(1).ok);assert(swap(2).ok);assert(swap(3).ok);assert.equal(state.windowsUsed,3);
 assert.equal(swap(4).ok,false);assert.equal(state.count,4);assert(swap(3).ok);assert.equal(state.count,5);assert.equal(swap(3).ok,false);
});
test('halftime changes consume player rights but no window and live changes are rejected',()=>{
 const rules=Rules.normalize({rules:{maxSubstitutions:3,substitutionWindows:1}}),state=Rules.createSubstitutionState();
 const live=Rules.substitutionAllowance(rules,state,{phase:'playing',deadBall:false});assert.equal(live.ok,false);assert.equal(Rules.recordSubstitution(state,live),false);
 const half=Rules.substitutionAllowance(rules,state,{phase:'halftime'});assert(half.ok);Rules.recordSubstitution(state,half);assert.equal(state.count,1);assert.equal(state.windowsUsed,0);
 const first=Rules.substitutionAllowance(rules,state,{phase:'playing',deadBall:true,stoppageId:1});assert(first.ok);Rules.recordSubstitution(state,first);
 assert.equal(Rules.substitutionAllowance(rules,state,{phase:'playing',deadBall:true,stoppageId:2}).ok,false);
 assert.equal(Rules.substitutionAllowance(rules,state,{phase:'finished',deadBall:true,stoppageId:1}).ok,false);
});
test('missing stoppage identity cannot merge every future substitution window',()=>{
 const rules=Rules.normalize({}),state=Rules.createSubstitutionState();assert.equal(Rules.substitutionAllowance(rules,state,{phase:'playing',deadBall:true}).ok,false);assert.deepEqual(state,{count:0,windowsUsed:0,usedWindows:[]});
});
test('minimum player count produces an explicit abandonment reason',()=>{
 const rules=Rules.normalize({});assert.equal(Rules.abandonment(rules,[7,11]),null);assert.deepEqual(Rules.abandonment(rules,[11,6]),{team:1,reason:'minimum-players',minimum:7,remaining:6});
});
