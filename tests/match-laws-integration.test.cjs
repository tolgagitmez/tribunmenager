'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),Club=require('../club-data'),D=require('../attack-diagnostics');
const dt=1/60;
function game(rules={}){return new Match({seed:21,players:Club.createRoster(),starters:Club.starters,formation:'4-3-3',rules});}
function isolated(side=1){const m=game({minPlayers:1}),p=m.players[0],d=m.players[11];m.period=side===1?1:2;m.matchClock.period=m.period;m.restart=null;m.owner=null;m.flight=null;m.kick=null;m.planClock=100;m.targets=new Map();for(const q of m.players)q.active=false;for(const q of [p,d])Object.assign(q,{active:true,vx:0,vz:0,speed:0,touchClock:0,tackleClock:0,duelRecovery:0,action:'idle',actionClock:0});return {m,p,d};}
for(const side of [-1,1]){
 test(`real tackle foul on box boundary awards a penalty (${side})`,()=>{
  const {m,p,d}=isolated(side);Object.assign(p,{x:35.5*side,z:0,face:side===1?0:Math.PI});Object.assign(d,{x:35.9*side,z:0,face:side===1?Math.PI:0});m.owner=p;m.ball={x:35.6*side,y:.11,z:0,vx:0,vy:0,vz:0};
  const rolls=[.5,.99,0,.99];m.random=()=>rolls.shift()??.5;assert(m.tackleAccess(d,p).attempt);m.doTackle(d,p);
  assert.equal(m.restart.kind,'penalty');assert.deepEqual(m.restart.spot,{x:41*side,z:0});assert.equal(m.fouls[1],1);assert.equal(m.referee.decisions[0].incident.x,35.5*side);assert(m.events.some(e=>e.type==='penalty'));
 });
 test(`a foul just outside the box keeps the incident spot (${side})`,()=>{const {m,p,d}=isolated(side);m.players[21].active=true;p.x=35.49*side;p.z=0;m.ball={x:35.8*side,y:.11,z:0,vx:0,vy:0,vz:0};m.adjudicateFoul(d,p,{advantage:false});assert.equal(m.restart.kind,'free-kick');assert.equal(m.restart.spot.x,p.x);});
 test(`whole-ball goal line and period direction agree (${side})`,()=>{const {m,p,d}=isolated(side);d.active=false;p.active=false;m.lastTouch=p;m.ball={x:52.08*side,y:.11,z:0,vx:side,vy:0,vz:0};m.ballStep(dt);assert.equal(m.score[0],0);assert.equal(m.restart,null);m.ballStep(.1);assert.equal(m.score[0],1);assert.equal(m.score[1],0);assert(m.goalPause);});
 test(`post and crossbar contacts bounce before goal decisions (${side})`,()=>{for(const [z,y,type]of [[3.72,1,'post'],[0,2.5,'crossbar']]){const {m,p,d}=isolated(side);p.active=d.active=false;m.lastTouch=p;m.ball={x:50.8*side,y,z,vx:100*side,vy:0,vz:0};m.ballStep(dt);assert.equal(m.score[0],0);assert.equal(m.restart,null);assert(m.ball.vx*side<0);assert(m.events.some(e=>e.type===type));}});
}
test('a body block before whole-ball crossing prevents a goal in the same swept step',()=>{const {m,p,d}=isolated();p.active=false;Object.assign(d,{x:51.95,z:0,touchClock:0});m.lastTouch=p;m.ball={x:51.5,y:.5,z:0,vx:50,vy:0,vz:0};m.flight={kind:'shot',id:1,from:p,age:0,offsidePlayers:[]};m.ballStep(dt);assert.equal(m.score[0],0);assert.equal(m.lastTouch,d);assert(m.events.some(e=>e.type==='block'));assert(m.ball.vx<0);});
test('serious foul is a direct red and uses the matching restart',()=>{const {m,p,d}=isolated();m.players[21].active=true;p.x=40;p.z=0;m.adjudicateFoul(d,p,{serious:true,advantage:false});assert.equal(d.active,false);assert.equal(m.reds[1],1);assert.equal(m.cards[1],0);assert.equal(m.restart.kind,'penalty');assert(m.events.some(e=>e.type==='red'&&e.title==='Doğrudan kırmızı kart'));});
test('falling below the competition minimum abandons the match without a new restart',()=>{const m=game(),p=m.players[0],d=m.players[11];for(const q of m.team(1).slice(1,5))q.active=false;m.adjudicateFoul(d,p,{serious:true,advantage:false});assert.equal(m.done,true);assert.equal(m.finishReason,'minimum-players');assert.equal(m.restart,null);});
test('failed advantage recalls the original foul and applies its deferred card',()=>{const {m,p,d}=isolated();Object.assign(p,{x:5,z:0});m.owner=p;m.ball={x:5.5,y:.11,z:0,vx:3,vy:0,vz:0};m.adjudicateFoul(d,p,{advantage:true,reckless:true});assert.equal(m.restart,null);assert.equal(m.cards[1],0);assert(m.referee.pendingAdvantage);m.owner=d;m.updateReferee();assert.equal(m.restart.kind,'free-kick');assert.deepEqual(m.restart.spot,{x:5,z:0});assert.equal(m.cards[1],1);assert.equal(m.referee.decisions[0].status,'recalled');});
test('successful advantage keeps play live and delays discipline until a stoppage',()=>{const {m,p,d}=isolated();p.x=5;p.z=0;m.owner=p;m.ball={x:5.5,y:.11,z:0,vx:3,vy:0,vz:0};m.adjudicateFoul(d,p,{advantage:true,reckless:true});m.ball.x=12;p.x=11.5;m.updateReferee();assert.equal(m.referee.pendingAdvantage,null);assert.equal(m.restart,null);assert.equal(m.cards[1],0);m.setRestart('throw',0,{x:12,z:34});assert.equal(m.cards[1],1);assert.equal(m.restart.kind,'throw');});
test('halftime freezes ball and players, changes ends and gives the other team kickoff',()=>{const m=game({periodSeconds:.1,halftimeSeconds:1,addedTime:false});m.advance(.1);assert.equal(m.lifecycle,'halftime');const before=structuredClone({ball:m.ball,players:m.players});m.advance(.3);assert.deepEqual({ball:m.ball,players:m.players},before);assert(Math.abs(m.clockState().nominalElapsed-.1)<1e-9);assert(m.resumeHalf());assert.equal(m.period,2);assert.equal(m.direction(0),-1);assert.equal(m.restart.kind,'kickoff');assert.equal(m.restart.team,1);assert(m.team(0).every(p=>p.homeX*(p.role==='ATT'?-1:1)>=0||p.role==='MID'));m.advance(.1);assert(m.done);assert.equal(m.events.filter(e=>e.type==='end').length,1);});
test('announced additional time extends the half and halftime is a separate observer bin',()=>{const m=game({periodSeconds:1,halftimeSeconds:.2,restartGraceSeconds:0,roundSeconds:.1});m.advance(1);assert.equal(m.lifecycle,'playing');assert(m.clockState().addedSeconds>=.9);m.restart=null;m.owner=null;m.kick=null;m.planClock=100;m.targets.clear();const o=D.attach(m);m.advance(0);for(let i=0;i<150&&m.lifecycle==='playing';i++)o.step(dt);assert.equal(m.lifecycle,'halftime');for(let i=0;i<6;i++)o.step(dt);assert(o.report().clock.halftimeSeconds>.09);assert(o.report().valid);o.detach();});
test('substitution limits/windows come from rules and live substitutions are rejected',()=>{const m=game({maxSubstitutions:5,substitutionWindows:1,substitutionPauseSeconds:0});assert(m.substitute(0,12).ok);assert(m.substitute(1,13).ok);assert.equal(m.subWindowsUsed,1);assert.equal(m.subCount,2);m.setRestart('throw',0,{x:5,z:34});assert.equal(m.canSubstitute().ok,false);m.lifecycle='halftime';m.matchClock.phase='halftime';m.restart=null;assert(m.substitute(2,14).ok);assert.equal(m.subWindowsUsed,1);m.lifecycle='playing';m.restart=null;m.goalPause=null;assert.equal(m.canSubstitute().ok,false);});
test('a ready penalty executes through ordinary windup and actual foot release',()=>{const m=game({periodSeconds:100,minPlayers:1}),p=m.players[1],g=m.players[21];m.setRestart('penalty',0,{x:40,z:0},p);const r=m.restart;r.clock=0;r.aimZ=1.4;m.planPenalty(r);for(const [q,t] of m.targets){q.x=t.x;q.z=t.z;q.vx=q.vz=q.speed=0;}p.face=Math.atan2(1.4,13);assert(m.penaltyReady(r));m.advance(2);assert(m.shots[0]>=1);assert(m.events.some(e=>e.type==='shot'));assert(m.penaltyAttempt);assert.equal(m.penaltyAttempt.takerId,p.id);});
test('offside active interference needs a sightline or a real challenge',()=>{for(const blocking of [false,true]){const {m,p,d}=isolated(),g=m.players[21];Object.assign(p,{x:45,z:blocking?0:5,active:true});Object.assign(g,{active:true,x:49,z:0,role:'GK'});d.active=false;m.ball={x:40,y:1,z:0,vx:20,vy:0,vz:0};m.flight={from:m.players[3],kind:'shot',age:0,offsidePlayers:[p.id]};m.offsidePhase={team:0,playerIds:[p.id],fromId:3};assert.equal(m.offsideInterference(),blocking);if(blocking){assert.equal(m.restart.indirect,true);assert.equal(m.telemetry.offsides,1);}else assert.equal(m.restart,null);}});
test('an actual headed pass captures offside at the header rather than the preceding cross',()=>{
 const {m,p,d}=isolated(),q=m.players[3],r=m.players[4],g=m.players[21];
 for(const actor of [p,q,r,d,g])Object.assign(actor,{active:true,touchClock:0,tackleClock:100,duelRecovery:0});
 Object.assign(p,{x:0,z:0,heading:99});Object.assign(q,{x:6,z:7});Object.assign(r,{x:15,z:10});Object.assign(d,{x:10,z:-8});Object.assign(g,{x:12,z:4});
 m.ball={x:0,y:1.9,z:0,vx:0,vy:-1,vz:0};m.flight={kind:'cross',from:m.players[1],age:0,id:1,offsidePlayers:[]};
 assert(m.aerial({x:0,y:1.91,z:0}));assert.equal(m.flight.kind,'pass');assert(m.flight.offsidePlayers.includes(r.id));assert(!m.flight.offsidePlayers.includes(q.id));assert.equal(m.telemetry.headedPasses,1);
 m.ball={x:r.x+.2,y:.11,z:r.z,vx:0,vy:0,vz:0};assert.equal(m.acquire(r),false);assert.equal(m.restart.indirect,true);
});
test('a body deflection preserves offside while deliberate opponent control resets it',()=>{
 for(const controlled of [false,true]){const {m,p,d}=isolated(),r=m.players[4],g=m.players[21];Object.assign(r,{active:true,x:45,z:4});Object.assign(d,{x:42,z:0,role:'DEF'});Object.assign(g,{active:true,x:49,z:10});p.active=false;
  m.ball={x:41,y:controlled?.11:.5,z:0,vx:20,vy:0,vz:0};m.lastTouch=p;m.flight={kind:'shot',id:1,from:p,age:0};m.offsidePhase=m.captureOffside(p);assert(m.offsidePhase.playerIds.includes(r.id));
  if(controlled){m.ball.x=d.x+.3;assert(m.acquire(d));assert.equal(m.offsidePhase,null);}
  else{m.ballStep(.1);assert.equal(m.flight,null);assert.equal(m.lastTouch,d);assert(m.offsidePhase.playerIds.includes(r.id));}
 }
});
test('a penalty awarded at the period limit completes its kick before the halftime whistle',()=>{
 const m=game({periodSeconds:.1,addedTime:false,halftimeSeconds:5,minPlayers:1}),p=m.players[1];m.setRestart('penalty',0,{x:40,z:0},p);const r=m.restart;r.clock=0;r.shotAim={x:54,z:10};m.planPenalty(r);for(const [q,t]of m.targets){q.x=t.x;q.z=t.z;q.vx=q.vz=q.speed=0;}p.face=Math.atan2(10,13);
 m.advance(.2);assert.equal(m.lifecycle,'playing');assert.equal(m.done,false);m.advance(2);assert(m.shots[0]>=1);assert.equal(m.lifecycle,'halftime');assert(m.matchClock.periodLengths[0]>.5);
});
test('five configured changes can include the goalkeeper within one stoppage',()=>{
 const m=game({maxSubstitutions:5,substitutionWindows:3,substitutionPauseSeconds:0});
 assert(m.substitute(10,11).ok);assert.equal(m.players[10].role,'GK');
 for(const [index,id]of [[0,12],[1,13],[2,14],[4,15]])assert(m.substitute(index,id).ok);
 assert.equal(m.subCount,5);assert.equal(m.subWindowsUsed,1);assert.equal(m.substitute(5,16).ok,false);
});
test('extended penalty play ends on a field player touch while a keeper parry stays live',()=>{
 for(const keeper of [false,true]){const {m,p,d}=isolated();m.penaltyAttempt={state:'released',team:0,takerId:p.id};Object.assign(d,{role:keeper?'GK':'DEF'});m.lastTouch=d;m.owner=null;m.ball={x:48,y:.5,z:0,vx:4,vy:1,vz:0};m.flight=null;m.updateReferee();assert.equal(m.penaltyAttempt.state,keeper?'released':'settled');}
});
test('direct indirect-free-kick and throw-in goals use the legal defending restart',()=>{
 for(const kind of ['throw','free-kick']){const {m,p,d}=isolated();p.active=d.active=false;m.lastTouch=p;m.ball={x:51.99,y:.11,z:0,vx:12,vy:0,vz:0};m.flight={from:p,kind:'pass',id:1,age:0,restartKind:kind,restartIndirect:kind==='free-kick'};m.ballStep(dt);assert.equal(m.score[0],0);assert.equal(m.restart.kind,'goal-kick');}
});
test('diagnostics records the referee-resolved restart after an advantage recall',()=>{
 const {m,p,d}=isolated();m.players[21].active=true;Object.assign(p,{x:5,z:0});m.ball={x:5.3,y:.11,z:0,vx:0,vy:0,vz:0};m.lastTeam=1;m.owner=null;const o=D.attach(m);assert(m.acquire(p));m.adjudicateFoul(d,p,{advantage:true});m.setRestart('throw',1,{x:8,z:34});assert.equal(m.restart.kind,'free-kick');assert.equal(m.restart.team,0);const episode=o.report().episodes.find(e=>e.team===0);assert.equal(episode.endReason,'foul-won');o.detach();
});
