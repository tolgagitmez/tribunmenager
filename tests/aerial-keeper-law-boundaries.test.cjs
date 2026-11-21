'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Match}=require('../football-sim.js');
const Laws=require('../referee-laws.js');

function match(){
 const m=new Match({seed:148,rules:{periodSeconds:20,halftimeSeconds:0,addedTime:false}});
 m.owner=null;m.restart=null;m.kick=null;m.goalPause=null;m.offsidePhase=null;
 return m;
}
function airborne(m,height,kind,contested=false){
 const actor=m.players[0],from=m.players[5],enemy=m.players[11];
 for(const p of m.players)if(p!==actor&&p!==from&&p!==enemy){p.x=-39;p.z=p.id*.2-20;p.touchClock=0;}
 Object.assign(actor,{x:0,z:0,heading:96,energy:1,speed:2,vx:0,vz:0,touchClock:0,duelRecovery:0,face:0});
 Object.assign(from,{x:-15,z:15,touchClock:0});
 Object.assign(enemy,{x:contested?.22:17,z:contested?.1:22,heading:94,energy:1,speed:1,
  touchClock:0,duelRecovery:0});
 m.ball={x:.21,z:0,y:height,vx:9,vy:-2,vz:0};
 m.flight=kind?{id:13,kind,from,point:{x:30,z:0},target:actor,age:0,
  aerialResolved:false,offsidePlayers:[]}:null;
 m.lastTeam=0;
 m.passOptions=()=>[];
 m.shotWindow=()=>({distance:30,quality:0,open:0,point:{x:52,z:0}});
 return {actor,enemy,from,previous:{x:-.05,y:height+.04,z:0}};
}
test('a long pass can be jumped for and headed only at a reachable height',()=>{
 const m=match(),{actor,previous}=airborne(m,2.19,'long-pass');
 assert(m.aerial(previous));
 assert.equal(m.telemetry.aerialLongBalls,1);
 assert.equal(m.telemetry.aerialHeaders,1);
 assert(actor.jumpHeight>.3,'heading ability, speed and energy must grant jump reach');
 assert.equal(actor.action,'header');
 assert.equal(m.ball.vy,-1);
 const high=match(),fixture=airborne(high,2.68,'long-pass');
 assert.equal(high.aerial(fixture.previous),false,'no unreachable 2.68 m instant header');
});
test('mid-height long ball is cushioned on the chest, not counted as a header',()=>{
 const m=match(),{actor,previous}=airborne(m,1.39,'long-pass');
 assert(m.aerial(previous));
 assert.equal(m.owner,actor);
 assert.equal(actor.action,'chest');
 assert.equal(m.telemetry.chestControls,1);
 assert.equal(m.telemetry.aerialHeaders||0,0);
 assert(m.ball.y>1,'chest touch cannot teleport the ball down to boots');
 assert(m.ball.vy<=0);
});
test('opponents reaching the same long ball force a loose second ball',()=>{
 const m=match(),{actor,enemy,previous}=airborne(m,2.10,'long-pass',true);
 assert(m.aerial(previous));
 assert.equal(m.owner,null);
 assert.equal(m.flight,null);
 assert.equal(m.telemetry.aerialDuels,1);
 assert.equal(m.telemetry.secondBallContests,1);
 assert.equal(m.telemetry.looseBalls>0,true);
 assert.equal(actor.action,'header');
 assert.equal(enemy.action,'header');
});
test('a rebounding loose aerial ball permits a genuine chest recovery',()=>{
 const m=match(),{actor,previous}=airborne(m,1.3,null);
 assert(m.aerial(previous));
 assert.equal(m.owner,actor);
 assert.equal(m.telemetry.aerialSecondBalls,1);
 assert.equal(m.telemetry.secondBallRecoveries,1);
});
test('legal body-part line excludes arms and includes head, torso and feet',()=>{
 const armsOnly={x:9.3,face:0,offsideBodyParts:[
  {part:'arm',x:24},{part:'head',x:9.7},{part:'torso',x:9.6},{part:'foot',x:9.5}]};
 assert.equal(Laws.offsideBodyPoint(armsOnly,1),9.7);
 const headAhead={...armsOnly,offsideBodyParts:[
  {part:'arm',x:24},{part:'head',x:10.4},{part:'torso',x:9.4},{part:'rightFoot',x:10.1}]};
 assert.equal(Laws.offsideBodyPoint(headAhead,1),10.4);
 const defenders=[{x:11,offsideBodyParts:[{part:'torso',x:11}]},
                  {x:10,offsideBodyParts:[{part:'torso',x:10}]},
                  {x:3,offsideBodyParts:[{part:'torso',x:3}]}];
 assert.equal(Laws.offsideLineOfDefenders(defenders,1),10);
 const m=match(),passer=m.players[5],target=m.players[0];
 m.ball.x=0;passer.x=-5;target.x=9.7;target.offsideBodyParts=armsOnly.offsideBodyParts;
 for(const p of m.team(1))Object.assign(p,{x:-12,offsideBodyParts:[{part:'torso',x:-12}]});
 for(const [p,x] of [[m.players[11],11],[m.players[12],10]]){
  p.x=x;p.offsideBodyParts=[{part:'torso',x}];
 }
 assert.equal(m.captureOffside(passer).playerIds.includes(target.id),false);
 target.offsideBodyParts=headAhead.offsideBodyParts;
 assert.equal(m.captureOffside(passer).playerIds.includes(target.id),true);
});
test('keeper foot line and both-side penalty arc encroachment use actual foot points',()=>{
 const players=[
  {id:1,team:0,x:41,z:0,role:'ATT'},
  {id:2,team:0,x:30,z:0,role:'MID',penaltyFeet:[{x:36.0,z:0}]},
  {id:3,team:1,x:30,z:10,role:'DEF',penaltyFeet:[{x:36.0,z:5}]},
  {id:4,team:1,x:51.7,z:0,role:'GK',penaltyFeet:[{x:51.75},{x:51.7}]}
 ];
 let v=Laws.penaltyPositionSnapshot({players,team:0,side:1,takerId:1,spot:{x:41,z:0}});
 assert.deepEqual(v.attacking,[2]);assert.deepEqual(v.defending,[3]);assert(v.keeperOffLine);
 players[3].penaltyFeet[0].x=52;
 v=Laws.penaltyPositionSnapshot({players,team:0,side:1,takerId:1,spot:{x:41,z:0}});
 assert.equal(v.keeperOffLine,false,'one foot on or behind line is sufficient');
});
test('IFAB material impact separates legitimate goal, retake, indirect free kick and play-on',()=>{
 assert.equal(Laws.penaltyDecision({keeperOffLine:true,goal:true}).kind,'goal');
 assert.equal(Laws.penaltyDecision({keeperOffLine:true,keeperSaved:true}).kind,'retake');
 assert.equal(Laws.penaltyDecision({keeperOffLine:true}).kind,'play-on');
 assert.equal(Laws.penaltyDecision({attackingImpact:true,goal:true}).kind,'retake');
 assert.equal(Laws.penaltyDecision({attackingImpact:true}).kind,'indirect-free-kick');
 assert.equal(Laws.penaltyDecision({defendingImpact:true}).kind,'retake');
 assert.equal(Laws.penaltyDecision({attackingImpact:true,defendingImpact:true}).kind,'retake');
});
function penaltyFixture(){
 const m=match(),taker=m.players[0],keeper=m.players[21];
 m.setRestart('penalty',0,{x:41,z:0},taker);
 keeper.x=51.4;keeper.z=0;keeper.penaltyFeet=[{x:51.4},{x:51.45}];
 return {m,taker,keeper};
}
test('real penalty launch records keeper off-line and early entrant; illegally saved penalty is retaken',()=>{
 const {m,taker,keeper}=penaltyFixture(),entrant=m.players[3];
 entrant.x=36;entrant.z=0;
 m.penaltyReleased({p:taker,restartContext:m.restart},{id:84,penalty:false});
 assert.equal(m.penaltyAttempt.position.keeperOffLine,true);
 assert(m.penaltyAttempt.position.attacking.includes(entrant.id));
 m.flight={id:84,kind:'shot',from:taker,penalty:true};
 m.ball={x:51.6,y:1,z:0,vx:13,vy:0,vz:0};
 keeper.action='dive';keeper.actionClock=.6;keeper.keeperRead=null;
 m.goalThreat=()=>true;
 m.keeperVisibility=()=>true;
 m.ballCrossing=()=>({x:keeper.x,y:1,z:0,t:.32});
 m.motion={saveHands:()=>[{x:51.5,y:1,z:0}]};
 m.keeper({x:51.4,y:1,z:0},1/60);
 assert.equal(m.restart?.kind,'penalty');
 assert.equal(m.telemetry.penaltyRetakes,1);
 assert(m.events.some(e=>e.type==='penalty-retake'));
});
test('early attacker touching rebound means IFK; early defender intervention means retake',()=>{
 for(const team of [0,1]){
  const {m,taker,keeper}=penaltyFixture(),p=m.players[team?12:2];
  p.x=36;p.z=0;
  keeper.penaltyFeet=[{x:52},{x:52}];
  m.penaltyReleased({p:taker,restartContext:m.restart},{id:37,penalty:false});
  m.ball.x=p.x;m.ball.z=p.z;
  assert(m.penaltyImpact(p));
  if(team===0){
   assert.equal(m.restart?.kind,'free-kick');
   assert.equal(m.restart?.indirect,true);
  }else{
   assert.equal(m.restart?.kind,'penalty');
   assert.equal(m.telemetry.penaltyRetakes,1);
  }
 }
});
test('keeper reachability denominator is not all shots; catch/parry rates are conditional',()=>{
 const m=match(),gk=m.players[21];gk.x=52;gk.z=0;
 assert.equal(m.keeperReachability(gk,{t:.75,z:2.1,y:1.2},.2,true).reachable,true);
 assert.equal(m.keeperReachability(gk,{t:.1,z:2.1,y:1.2},.2,true).reachable,false);
 assert.equal(m.keeperReachability(gk,{t:.75,z:6.4,y:1.2},.2,true).reachable,false);
 assert.equal(m.keeperReachability(gk,{t:.75,z:0,y:1.2},.2,false).reachable,false);
 m.telemetry.keeperReachableShots=10;
 m.telemetry.keeperReachableCatches=4;
 m.telemetry.keeperReachableParries=3;
 assert.deepEqual(m.keeperSummary(),{reachableShots:10,catches:4,parries:3,catchRate:.4,parryRate:.3});
});

for(const mode of ['catch-ready','dive']){
 test('actual reachable shot '+mode+' counts exactly one keeper '+(mode==='catch-ready'?'catch':'parry'),()=>{
  const m=match(),shooter=m.players[0],gk=m.players[21];
  Object.assign(gk,{x:52,z:0,role:'GK',active:true,action:mode,
   actionClock:.7,actionElapsed:.32,speed:0,vx:0,vz:0,touchClock:0,duelRecovery:0});
  m.ball={x:51.9,y:1,z:0,vx:18,vy:0,vz:0};
  m.flight={id:119,kind:'shot',from:shooter,age:.2};
  m.lastTouch=shooter;m.lastTeam=0;
  m.goalThreat=()=>true;m.keeperVisibility=()=>true;
  m.ballCrossing=()=>({x:52,y:1,z:0,t:.4});
  m.motion={saveHands:()=>[{x:51.8,y:1,z:0},{x:51.8,y:1,z:0}]};
  const prev={x:51.7,y:1,z:0};
  m.keeper(prev,1/60);
  assert.equal(m.telemetry.keeperReachableShots,1);
  const stats=m.keeperSummary();
  if(mode==='catch-ready'){
   assert.equal(stats.catches,1);assert.equal(stats.parries,0);assert.equal(stats.catchRate,1);
   assert.equal(m.owner,gk);
  }else{
   assert.equal(stats.catches,0);assert.equal(stats.parries,1);assert.equal(stats.parryRate,1);
   assert.equal(m.owner,null);
  }
 });
}

test('a screened shot can become reachable later, but is counted once',()=>{
 const m=match(),gk=m.players[21],shooter=m.players[0];gk.x=52;gk.z=0;gk.action='idle';
 m.ball={x:49,y:1,z:0,vx:12,vy:0,vz:0};
 m.flight={id:201,kind:'shot',from:shooter,age:.1};
 m.lastTouch=shooter;m.goalThreat=()=>true;
 m.ballCrossing=()=>({x:52,t:.5,y:1,z:0});
 m.keeperVisibility=()=>false;
 m.keeper({x:48.8,y:1,z:0},1/60);
 assert.equal(m.telemetry.keeperReachableShots||0,0);
 m.keeperVisibility=()=>true;
 m.keeper({x:48.8,y:1,z:0},1/60);
 m.keeper({x:48.8,y:1,z:0},1/60);
 assert.equal(m.telemetry.keeperReachableShots,1);
 assert.equal(m.keeperSummary().reachableShots,1);
});
