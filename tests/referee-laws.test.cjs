'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Laws=require('../referee-laws.js');

function foul({side=1,x=5,z=0,...details}={}){
 const victim={id:0,team:0,role:'ATT',active:true,x:x*side,z,vx:4*side,vz:0,speed:4,face:side===1?0:Math.PI};
 const offender={id:11,team:1,role:'DEF',active:true,x:victim.x-.5*side,z:z+.3,vx:0,vz:0};
 const players=[victim,offender,
  {id:12,team:1,role:'DEF',active:true,x:45*side,z:-2},
  {id:13,team:1,role:'DEF',active:true,x:48*side,z:2},
  {id:21,team:1,role:'GK',active:true,x:51*side,z:0}];
 return {offender,victim,spot:{x:victim.x,z:victim.z},attackDirection:side,players,
  ball:{x:victim.x+.4*side,y:.11,z:victim.z,vx:4*side,vy:0,vz:0},attemptedBall:true,...details};
}

for(const side of [1,-1]){
 test(`penalty-area lines belong to the penalty area in direction ${side}`,()=>{
  for(const point of [{x:35.5,z:0},{x:35.5,z:20.16},{x:35.5,z:-20.16},{x:52,z:0},{x:52,z:20.16},{x:52,z:-20.16},{x:45,z:20.16},{x:45,z:-20.16}]){
   assert.equal(Laws.insidePenaltyArea({x:point.x*side,z:point.z},side),true,JSON.stringify(point));
  }
 });
 test(`the nearest positions beyond each penalty-area edge stay outside in direction ${side}`,()=>{
  for(const point of [{x:35.499,z:0},{x:52.001,z:0},{x:45,z:20.161},{x:45,z:-20.161},{x:35.499,z:20.16}]){
   assert.equal(Laws.insidePenaltyArea({x:point.x*side,z:point.z},side),false,JSON.stringify(point));
  }
 });
 test(`an offence on the penalty-area line uses the penalty mark in direction ${side}`,()=>{
  const decision=Laws.classifyFoul(foul({side,x:35.5,z:20.16}));
  assert.equal(decision.restart,'penalty');assert.equal(decision.team,0);
  assert.deepEqual(decision.spot,{x:41*side,z:0});
  assert.deepEqual(decision.incident,{x:35.5*side,z:20.16});
 });
 test(`an offence immediately outside the penalty area preserves its free-kick spot in direction ${side}`,()=>{
  const decision=Laws.classifyFoul(foul({side,x:35.499,z:0}));
  assert.equal(decision.restart,'free-kick');assert.deepEqual(decision.spot,{x:35.499*side,z:0});
 });
}

test('ordinary and reckless fouls retain distinct disciplinary decisions',()=>{
 const ordinary=Laws.classifyFoul(foul()),reckless=Laws.classifyFoul(foul({reckless:true}));
 assert.equal(ordinary.restart,'free-kick');assert.equal(ordinary.card,'none');
 assert.equal(reckless.restart,'free-kick');assert.equal(reckless.card,'yellow');
});

test('serious foul play and violent conduct remain direct reds inside or outside the box',()=>{
 for(const x of [5,40])for(const flag of ['serious','violent']){
  const decision=Laws.classifyFoul(foul({x,[flag]:true,reckless:true,attemptedBall:true}));
  assert.equal(decision.card,'red',`${flag} at ${x}`);
  assert.equal(decision.restart,x===40?'penalty':'free-kick');
 }
});

test('the incident position controls the restart even when the ball lies across the box line',()=>{
 const outside=foul({x:35.499});outside.ball.x=35.8;
 assert.equal(Laws.classifyFoul(outside).restart,'free-kick');
 const inside=foul({x:35.5});inside.ball.x=35.2;
 assert.equal(Laws.classifyFoul(inside).restart,'penalty');
});

test('classifying a foul leaves every player, ball and caller detail unchanged',()=>{
 const context=foul({x:40,reckless:true}),before=structuredClone(context);
 const decision=Laws.classifyFoul(context);assert.deepEqual(context,before);
 decision.spot.x=999;decision.incident.z=999;assert.deepEqual(context,before);
});

function clearChance({side=1,x=30,...details}={}){
 const context=foul({side,x,...details});
 context.players=context.players.filter(p=>p===context.victim||p===context.offender||p.role==='GK');
 return context;
}

for(const side of [1,-1]){
 test(`denying a controlled clear chance outside the box is a direct red (${side})`,()=>{
  const decision=Laws.classifyFoul(clearChance({side,x:30}));
  assert.equal(decision.dogso,true);assert.equal(decision.card,'red');
  assert.equal(decision.restart,'free-kick');assert.deepEqual(decision.spot,{x:30*side,z:0});
 });
 test(`a genuine ball challenge in a penalty DOGSO is mitigated to yellow (${side})`,()=>{
  const decision=Laws.classifyFoul(clearChance({side,x:40,attemptedBall:true}));
  assert.equal(decision.dogso,true);assert.equal(decision.restart,'penalty');assert.equal(decision.card,'yellow');
 });
 test(`a penalty cannot mitigate a DOGSO foul without a ball challenge (${side})`,()=>{
  const decision=Laws.classifyFoul(clearChance({side,x:40,attemptedBall:false}));
  assert.equal(decision.dogso,true);assert.equal(decision.restart,'penalty');assert.equal(decision.card,'red');
 });
 test(`defenders still able to intervene prevent an automatic last-player red (${side})`,()=>{
  const decision=Laws.classifyFoul(foul({side,x:30}));
  assert.equal(decision.dogso,false);assert.equal(decision.card,'none');
 });
}
