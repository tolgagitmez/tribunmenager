'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto'),Module=require('node:module');
const {Match,BallPhysics,distance}=require('../football-sim');
const baseline=zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'../docs/validation/baselines/stage5-football-sim.js.gz')));
assert.equal(crypto.createHash('sha256').update(baseline).digest('hex'),'7038778922feb9f8f24389003b5ddf92fb8c0790280af84ae9818a04198acf60');
const oldModule=new Module(path.join(__dirname,'../reception-facing-stage5-test.js'),module);oldModule.filename=path.join(__dirname,'../reception-facing-stage5-test.js');oldModule.paths=module.paths;oldModule._compile(baseline.toString(),oldModule.filename);
const OldMatch=oldModule.exports.Match,dt=1/60;
const angle=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
function fixture({side=1,x=-5,speed=9}={}){
 const m=new Match({seed:21});m.restart=null;m.owner=null;m.kick=null;m.time=10;m.players.forEach(p=>p.active=false);
 const q=m.players[1],from=m.players[3];
 Object.assign(q,{active:true,x:0,z:0,vx:0,vz:0,speed:0,face:side<0?Math.PI:0,touchClock:0,receiveClock:0,duelRecovery:0,feintReaction:0,holdClock:0,action:'idle',actionClock:0});
 Object.assign(from,{active:true,x:-10*side,z:8*side,vx:0,vz:0,speed:0});
 m.ball={x:x*side,y:.11,z:0,vx:speed*side,vy:0,vz:0};
 m.flight={id:7,kind:'pass',from,target:q,age:0,point:{x:0,z:0},offsidePlayers:[]};m.lastTouch=from;m.lastTeam=q.team;
 q.reception={flightId:7,fromId:from.id,refreshAt:11,at:10,mode:'protect',point:{x:3*side,z:2*side},face:side<0?Math.PI:0,next:null};
 m.targets=new Map([[q,{x:0,z:0,state:'receive-run',pace:1.13}]]);m.planClock=10;
 return {m,q,from,target:m.targets.get(q)};
}
function clone(m,Engine=Match){return Object.assign(Object.create(Engine.prototype),structuredClone(m));}
function receive(m){
 const q=m.players[1],acquire=m.acquire;let contact=null,maxTurn=0,maxStep=0;
 m.acquire=function(p){if(p===q)contact={read:this.firstControlContact(p),ball:{...this.ball},pose:{x:p.x,z:p.z,face:p.face},time:this.time};return acquire.call(this,p);};
 for(let tick=0;tick<60&&!m.owner;tick++){
  const previous={x:q.x,z:q.z,face:q.face};m.step(dt);maxTurn=Math.max(maxTurn,Math.abs(angle(q.face,previous.face)));maxStep=Math.max(maxStep,distance(q,previous));
 }
 delete m.acquire;assert.equal(m.owner,q,'the physical target must actually receive the ball');assert(contact);
 return {contact,maxTurn,maxStep};
}
for(const side of [1,-1])test(`pre-arrival body opening turns a real formerly rear contact into an open-foot reception (${side})`,()=>{
 const {m,q}=fixture({side}),old=clone(m,OldMatch),originalBall={...m.ball},start=m.time;
 const actual=receive(m),previous=receive(old);
 assert.equal(previous.contact.read.ready,false);assert.equal(old.players[q.id].receiveMode,'cushion');
 assert.equal(actual.contact.read.ready,true);assert.equal(q.receiveMode,'open');assert.equal(m.telemetry.cushionedReceives,undefined);assert.equal(m.telemetry.directedTouches,1);
 assert.equal(actual.contact.time,previous.contact.time);assert.deepEqual(actual.contact.ball,previous.contact.ball,'facing cannot steer the incoming pass');
 const physical=BallPhysics.predict(originalBall,actual.contact.time-start);assert(Math.abs(m.ball.x-physical.x)<1e-10);assert(Math.abs(m.ball.z-physical.z)<1e-10);
 assert.deepEqual({x:q.x,z:q.z},{x:0,z:0});assert(actual.maxTurn<=4.5*dt+1e-12);assert.equal(actual.maxStep,0);
});
for(const side of [1,-1])test(`a faster arrival cannot bypass the normal turn limit or the cushion fallback (${side})`,()=>{
 const {m,q}=fixture({side,speed:15}),result=receive(m);
 assert.equal(result.contact.read.ready,false);assert.equal(q.receiveMode,'cushion');assert.equal(m.telemetry.cushionedReceives,1);assert.equal(m.telemetry.directedTouches,0);
 assert(result.maxTurn<=4.5*dt+1e-12);assert(result.contact.time<10.4);assert(q.receiveClock>0);assert.equal(q.nextAction,null);
});
test('distant arrival keeps the normal running posture instead of turning early toward an outlet',()=>{
 const {m,q,target}=fixture({x:-30});q.vx=q.speed=3;q.reception.face=Math.PI/2;target.x=10;
 const old=clone(m,OldMatch);m.move(q,target,.1);old.move(old.players[q.id],old.targets.get(old.players[q.id]),.1);
 assert.equal(q.face,0);assert(old.players[q.id].face>.3);assert(q.x>0);assert.deepEqual(m.ball,old.ball);
});
test('different outlet directions retain distinct open body angles with the close ball still in front',()=>{
 const states=[];
 for(const sign of [-1,1]){
  const {m,q,target}=fixture({x:-1,speed:0});q.face=Math.PI;q.reception.face=Math.PI+sign*Math.PI/2;
  for(let i=0;i<30;i++)m.move(q,target,dt);
  assert(m.firstControlContact(q).ready);const opening=angle(q.face,Math.PI);assert(sign*opening>.3);assert(Math.abs(opening)<Math.PI/2);states.push(q.face);
 }
 assert(Math.abs(angle(states[0],states[1]))>1);
});
test('the isolated receiver forecast uses the same changing ball and facing as real fixed-step movement',()=>{
 const {m,q,target}=fixture(),before=structuredClone(m),forecast=m.projectPlayer(q,.4,target).player,replay=clone(m);
 for(let i=0;i<24;i++)replay.step(dt);
 const actual=replay.players[q.id];assert.equal(replay.owner,null);assert(Math.abs(actual.face)>1,'the forecast must exercise the new opening, not a constant outlet');
 for(const key of ['x','z','vx','vz','face','speed','energy','stamina','anim'])assert(Math.abs(forecast[key]-actual[key])<1e-10,key);
 assert.equal(m.flight.target,q);assert.deepEqual(structuredClone(m),before);
});
test('facing and projection do not read hidden rival commands, future plans or RNG, or change live state',()=>{
 const {m,q,target}=fixture(),before=structuredClone(m),rival=m.players[14],hidden={};Object.defineProperty(hidden,'x',{get(){throw Error('hidden rival command');}});
 m.targets.set(rival,hidden);m.plan=()=>{throw Error('future plan');};m.random=()=>{throw Error('RNG');};
 assert(Number.isFinite(m.receptionFacing(q,0)));m.projectPlayer(q,.3,target);
 m.targets.delete(rival);delete m.plan;delete m.random;assert.deepEqual(structuredClone(m),before);
});
test('aerial, goalkeeper, other recipient, rival pass and unmatched preparations keep exact stage5 movement',()=>{
 for(const variant of ['no-flight','untargeted','rival-pass','unmatched','keeper','cross','long-pass','high','rising','unprepared']){
  const {m,q,from,target}=fixture();
  if(variant==='no-flight')m.flight=null;if(variant==='untargeted')m.flight.target=from;if(variant==='rival-pass')m.flight.from=m.players[14];if(variant==='unmatched')q.reception.flightId=99;
  if(variant==='keeper')q.role='GK';if(['cross','long-pass'].includes(variant))m.flight.kind=variant;if(variant==='high')m.ball.y=.8;if(variant==='rising')m.ball.vy=.5;if(variant==='unprepared')q.reception=null;
  const old=clone(m,OldMatch);for(let i=0;i<10;i++){m.move(q,target,dt);old.move(old.players[q.id],old.targets.get(old.players[q.id]),dt);}
  assert.deepEqual(structuredClone(m),structuredClone(old),variant);
 }
});
test('opening the body cannot redirect free flight before an actual touch',()=>{
 const {m,q,target}=fixture({x:-8}),expected=BallPhysics.predict(m.ball,.2);
 for(let i=0;i<12;i++){m.move(q,target,dt);m.integrateBall(dt);}
 for(const key of Object.keys(expected))assert(Math.abs(m.ball[key]-expected[key])<1e-11,key);assert.equal(m.owner,null);
});
test('an opponent on the incoming path can still intercept ahead of the prepared receiver',()=>{
 const {m,q}=fixture({x:-.95}),defender=m.players[14];Object.assign(defender,{active:true,x:-1.2,z:.05,vx:0,vz:0,speed:0,face:0,touchClock:0,duelRecovery:0});
 m.step(dt);assert.equal(m.owner,defender);assert.notEqual(m.owner,q);assert.equal(m.completed[q.team],0);
});
test('a correctly opened reception is still exposed to a physically reachable ordinary tackle',()=>{
 const {m,q}=fixture();receive(m);const defender=m.players[14];Object.assign(defender,{active:true,x:m.ball.x-.45,z:m.ball.z+.2,vx:0,vz:0,speed:0,face:Math.atan2(q.z-(m.ball.z+.2),q.x-(m.ball.x-.45)),touchClock:0,duelRecovery:0,tackleClock:0});
 assert(q.receiveClock>0);assert.equal(m.tackleAccess(defender,q).attempt,true);const count=m.telemetry.duels;m.doTackle(defender,q);assert.equal(m.telemetry.duels,count+1);assert(defender.tackleClock>0);
});
