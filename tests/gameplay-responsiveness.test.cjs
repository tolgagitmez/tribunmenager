'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{Match}=require('../football-sim');
function fixture(side=1,pilot=true){
 const m=new Match({seed:113,individualAI:true,gameplayResponsiveness:pilot,rules:{minPlayers:1}});if(side<0){m.period=2;m.matchClock.period=2}
 for(const q of m.players)q.active=false;
 const p=m.players[5],g=m.players[10];
 Object.assign(p,{active:true,role:'MID',position:'CM',x:12*side,z:0,face:side>0?0:Math.PI,vx:0,vz:0,speed:0,energy:1,dribbling:86,shooting:86,carryTime:.3,receiveClock:0,touchClock:0,duelRecovery:0,shieldUntil:0,task:null,carryIntent:null});
 Object.assign(g,{active:true,role:'GK',x:-49*side,z:0,face:side>0?0:Math.PI,vx:0,vz:0,speed:0,duelRecovery:0,touchClock:0,energy:1});
 m.restart=m.kick=m.flight=m.goalPause=null;m.owner=p;m.lastTeam=0;m.time=10;m.ball={x:p.x+.7*side,z:0,y:.11,vx:0,vz:0,vy:0};m.targets=new Map();m.updateTeamPhases();return {m,p,g};
}
for(const side of [1,-1]){
 test('open corridor beats retreat, but not useful forward pass '+side,()=>{
  const {m,p}=fixture(side),carry={kind:'carry',point:{x:p.x+5*side,z:0},clearance:5};
  const backward={kind:'pass',point:{x:p.x-7*side,z:0},risk:.1,arrivalRisk:.1,space:5,score:20};
  const shot={distance:40,open:0};
  const c=m.responsiveAttack(p,shot,carry,[backward],9);assert(c?.responsiveCarry);
  assert.equal(m.responsiveAttack(p,shot,carry,[{...backward,point:{x:p.x+8*side,z:0}}],9),null);
  assert.equal(m.responsiveAttack(p,shot,carry,[backward],2),null);
  m.passOptions=()=>[backward];m.carryOption=()=>carry;m.crossingOption=()=>null;
  assert(m.choose(p).responsiveCarry);
 });
 test('controlled open shot near box is selected; blocked lane not forced '+side,()=>{
  const {m,p}=fixture(side);p.x=34*side;m.ball.x=p.x+.7*side;
  const shot=m.shotWindow(p);assert(shot.open>=.6);
  assert.equal(m.responsiveAttack(p,shot,{point:p},[],8)?.kind,'shot');
  assert.equal(m.responsiveAttack(p,{...shot,open:0},{point:p},[],8),null);
 });
 test('keeper moves toward safe rolling or stationary ball, no hand teleport '+side,()=>{
  const {m,p,g}=fixture(side);p.active=false;m.owner=null;m.ball={x:-39*side,z:3,y:.11,vx:-.4*side,vz:0,vy:0};
  const before={...m.ball},target=m.safeKeeperCollect(g);assert(target);assert((target.x-g.x)*side>0);assert.deepEqual(m.ball,before);
  const enemy=m.players[11];Object.assign(enemy,{active:true,x:m.ball.x,z:m.ball.z,vx:0,vz:0});
  assert.equal(m.safeKeeperCollect(g),null);enemy.active=false;m.ball.x=-33*side;assert.equal(m.safeKeeperCollect(g),null);
 });
 test('shorter free kick preparation keeps legal distance gate '+side,()=>{
  const {m,p}=fixture(side);m.setRestart('free-kick',0,{x:5*side,z:0},p);
  assert.equal(m.restart.clock,2);const d=m.players[11];Object.assign(d,{active:true,x:6*side,z:0});assert.equal(m.restartReady(m.restart),false);
  d.x=16*side;assert(m.restartReady(m.restart));assert.equal(new Match({seed:113}).cfg.gameplayResponsiveness,undefined);
 });
}
test('dribble request reduces excess impulse and still uses actual next-touch gate',()=>{
 const {m,p}=fixture();Object.assign(p,{speed:1,vx:1,carryTarget:{x:p.x+5,z:0}});
 let request;m.touchPlan=(actor,velocity,opts)=>{request={velocity,opts};return {ready:false}};
 const before={...m.ball};assert.equal(m.dribbleTouch(p),false);assert.deepEqual(m.ball,before);assert(request);assert(Math.hypot(request.velocity.vx,request.velocity.vz)<=2.1+1e-9);assert(request.opts.interval<=.24);
});
