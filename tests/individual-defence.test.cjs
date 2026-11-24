'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Brain=require('../player-brain.js'),{Match}=require('../football-sim.js'),Perception=require('../player-perception.js');
const defender=(extra={})=>({id:12,active:true,team:1,role:'DEF',x:15,z:20,face:Math.PI,vx:-2,vz:0,speed:2,tackling:94,composure:93,vision:91,agility:90,energy:1,yellow:0,...extra});
const carrier={id:1,active:true,team:0,role:'ATT',x:10,z:20,face:0,vx:0,vz:0,weakFoot:55,footPreference:'right',confidence:1,age:0};
const ball={x:10.7,z:20,y:.11,vx:0,vz:0,vy:0};
test('goal-side jockeying closes the known strong-foot side while respecting cover and central safety',()=>{
 const p=defender(),cover=defender({x:19,z:20});
 const right=Brain.jockeyOption(p,carrier,ball,{forward:-1,cover});
 const left=Brain.jockeyOption(p,{...carrier,footPreference:'left'},ball,{forward:-1,cover});
 assert.equal(right.kind,'weak-foot');assert.equal(left.kind,'weak-foot');
 assert(right.point.z>ball.z&&left.point.z<ball.z);
 assert(right.point.x>ball.x&&left.point.x>ball.x);
 const both=Brain.jockeyOption(p,{...carrier,footPreference:'both'},ball,{forward:-1,cover});
 assert.equal(both.kind,'jockey');assert.equal(both.point.z,ball.z);
 const middle=Brain.jockeyOption({...p,z:0},{...carrier,z:0},{...ball,z:0},{forward:-1,cover:{...cover,z:0}});
 assert.equal(middle.kind,'jockey');assert(Math.abs(middle.point.z)<=.35);
 assert.equal(Brain.jockeyOption(p,{...carrier,age:.9},ball,{forward:-1,cover}),null);
 assert.equal(Brain.jockeyOption({...p,x:9},carrier,ball,{forward:-1,cover}),null);
});
test('screening moves the cover player onto an observed passing lane without abandoning the defensive block',()=>{
 const p=defender({x:15,z:3}),origin={...carrier,x:10,z:0},receiver={x:22,z:0,confidence:1,age:0};
 const base={x:15,z:2};
 const target=Brain.screenOption(p,origin,receiver,base,{forward:-1});
 assert(target);assert.equal(target.z,0);assert(target.x>13);
 assert.equal(Brain.screenOption(p,origin,{...receiver,confidence:.1},base,{forward:-1}),null);
 assert.equal(Brain.screenOption(p,origin,receiver,{x:15,z:9},{forward:-1}),null);
 assert.equal(Brain.screenOption(p,origin,{...receiver,x:3},base,{forward:-1}),null);
});
test('challenge timing waits only for marginal shielded/rear contacts, never an immediate danger',()=>{
 const p=defender({x:10.5,z:20.9,vx:0,vz:-2});
 const c={...carrier,x:10,z:20},b={...ball,x:10.5,z:20};
 const args={gap:.9,shield:true,fromBehind:false,aggression:.5};
 assert.equal(Brain.tackleDecision(p,c,b,args).kind,'wait');
 assert.equal(Brain.tackleDecision(p,c,b,{...args,emergency:true}).kind,'standing');
 assert.equal(Brain.tackleDecision(p,c,b,{...args,aggression:.9}).kind,'standing');
 assert.equal(Brain.tackleDecision({...p,tackling:40,composure:40},c,b,args).kind,'standing');
});
test('sliding is reserved for an exposed ground ball, safe approach, adequate skill, cover and no booking',()=>{
 const p=defender({x:12.05,z:20,vx:-2,vz:0}),c={...carrier},b={...ball,x:11};
 const args={gap:1.05,cover:true,aggression:.5};
 assert.equal(Brain.tackleDecision(p,c,b,args).kind,'slide');
 for(const [actor,target,context] of [
  [{...p,yellow:1},b,args],[{...p,energy:.2},b,args],[{...p,vx:1},b,args],
  [p,{...b,y:.5},args],[p,b,{...args,fromBehind:true}],[p,b,{...args,shield:true}],
  [p,b,{...args,cover:false}],[p,b,{...args,gap:1.6}],[p,b,{...args,aggression:.95}]
 ])assert.notEqual(Brain.tackleDecision(actor,c,target,context).kind,'slide');
});
function fixture(){
 const m=new Match({seed:84,individualAI:true}),p=m.players[6],d=m.players[17],cover=m.players[18];
 for(const a of m.players)a.active=false;
 Object.assign(p,carrier,{id:6,active:true,team:0,role:'ATT',name:'Forward',dribbling:85,strength:75,balance:75,duelRecovery:0,touchClock:0});
 Object.assign(d,defender({id:17,x:12.05,z:20}),{active:true,tackleClock:0,duelRecovery:0,name:'Defender',personality:0,strength:80,balance:80});
 Object.assign(cover,defender({id:18,x:17,z:20}),{active:true,duelRecovery:0});
 m.restart=null;m.goalPause=null;m.kick=null;m.flight=null;m.time=10;m.owner=p;m.lastTeam=0;
 m.ball={...ball,x:11};m.t[1].aggression=50;m.updateTeamPhases();
 return {m,p,d,cover};
}
test('real physical tackle gate, release and bounded momentum recovery for a sliding challenge',()=>{
 const {m,p,d}=fixture();
 const before=structuredClone(m.ball),seed=m.seed,access=m.tackleAccess(d,p);
 assert.equal(access.attempt,true);assert.equal(access.style,'slide');
 assert.deepEqual(m.ball,before);assert.equal(m.seed,seed);
 m.random=()=>0;
 m.doTackle(d,p);
 assert.equal(m.owner,null);assert.equal(m.telemetry.slidingChallenges,1);assert.equal(m.telemetry.slidingWins,1);
 assert.equal(d.action,'tackle');assert.equal(d.actionDuration,.52);assert(d.duelRecovery>=.48);
 assert.equal(m.ball.x,before.x);assert.equal(m.ball.z,before.z);
 assert(Math.hypot(m.ball.vx,m.ball.vz)>2);
 const x=d.x,z=d.z,old=d.speed;
 const released=structuredClone(m.ball);
 m.move(d,{x:d.x+10,z:d.z+8,pace:1,state:'press'},1/60);
 assert(d.x<x);assert(Math.abs(d.z-z)<1e-8);assert(d.speed<old);
 assert(Math.hypot(d.x-x,d.z-z)<.15);assert.deepEqual(m.ball,released);
 assert.equal(m.tackleAccess(d,p).attempt,false);
});
test('the same failed slide still goes through the actual referee foul decision',()=>{
 const {m,p,d}=fixture();const values=[.5,.99,.0,.0];m.random=()=>values.shift()??0;
 m.doTackle(d,p);
 assert.equal(m.telemetry.slidingChallenges,1);assert.equal(m.telemetry.slidingWins??0,0);
 assert.equal(m.fouls[d.team],1);assert.equal(m.referee.decisions.length,1);
 assert(['free-kick','penalty'].includes(m.referee.decisions[0].restart));
});
test('no new style or bonus bypasses physical access restrictions',()=>{
 const {m,p,d}=fixture();
 for(const change of [{x:13},{face:0},{duelRecovery:.4},{tackleClock:.2}]){
  const prior={...d};Object.assign(d,change);assert.equal(m.tackleAccess(d,p).attempt,false);Object.assign(d,prior);
 }
 m.ball.y=.9;assert.equal(m.tackleAccess(d,p).attempt,false);
});
test('pressing unit uses the actual observed carrier and publishes goal-side defensive pace',()=>{
 const {m,p,d,cover}=fixture();d.x=15;
 const unit={assignments:new Map()},policy={active:true};
 const result=m.pressUnit(1,p,d,cover,unit,policy);
 assert.equal(result.defenceKind,'weak-foot');assert(result.pressPace<1);
 assert(result.pressPoint.x>m.ball.x&&result.pressPoint.z>m.ball.z);
 m._perceptionActive=true;Perception.clear(d,m.time);Perception.clear(cover,m.time);
 const hidden=m.pressUnit(1,p,d,cover,unit,policy);
 assert.equal(hidden.defenceKind,undefined);
});
test('known preferred foot is retained only in actual observed records; querying cannot refresh a hidden change',()=>{
 const {m,p,d}=fixture();d.face=Math.PI;
 Perception.update(m.players,m.time,0,{scanAllowed:false});m._perceptionActive=true;
 const read=m.rivals(d).find(q=>q.id===p.id);
 assert(read);assert.equal(read.footPreference,'right');
 p.footPreference='left';
 assert.equal(m.rivals(d).find(q=>q.id===p.id).footPreference,'right');
});
test('legacy fixtures with new defensive intelligence disabled remain deterministic',()=>{
 const a=new Match({seed:71}),b=new Match({seed:71,individualAI:false});
 for(let i=0;i<360;i++){a.step(1/60);b.step(1/60);}
 assert.equal(a.seed,b.seed);assert.deepEqual(a.ball,b.ball);assert.deepEqual(a.events,b.events);assert.deepEqual(a.score,b.score);
});
