'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Brain=require('../player-brain'),{Match}=require('../football-sim'),Rig=require('../humanoid-rig');
const keeper=(extra={})=>({role:'GK',id:21,team:1,x:46,z:0,face:Math.PI,vx:0,vz:0,speed:0,energy:1,pace:74,agility:91,vision:94,composure:92,goalkeeping:95,reactions:96,handling:95,...extra});
test('equal overall rating does not imply equal reaction or handling ability',()=>{
 const elite=keeper({skill:85}),slow=keeper({skill:85,reactions:55,goalkeeping:70,agility:60,handling:60});
 assert(Brain.keeperReaction(elite)<Brain.keeperReaction(slow)-.08);
 assert(Brain.keeperReaction({...elite,energy:.3})>Brain.keeperReaction(elite));
 const contact={speed:22,height:1.15,lateral:.12,pressure:8,handHits:2};
 assert(Brain.keeperCatch(elite,contact));assert(!Brain.keeperCatch(slow,contact));
 assert(!Brain.keeperCatch(elite,{...contact,handHits:1,pressure:1.0}));
 assert(!Brain.keeperCatch(elite,{...contact,speed:35}));
});
test('angle bisector protects near post and advances only in an isolated central duel',()=>{
 const gk=keeper(),ball={x:39,z:0};
 const depth=Brain.keeperDepth(gk,ball,{forward:-1,oneOnOne:true});
 assert(depth>4);
 assert(Brain.keeperDepth(gk,ball,{forward:-1,oneOnOne:true,covered:true})<depth);
 assert.equal(Brain.keeperAngle(gk,ball,depth,-1),0);
 const right=Brain.keeperAngle(gk,{x:44,z:18},3,-1),left=Brain.keeperAngle(gk,{x:44,z:-18},3,-1);
 assert(right>0&&left<0&&Math.abs(right+left)<1e-10&&right<=3.45);
 assert.equal(Brain.keeperAngle(gk,{x:-44,z:18},3,1),right);
});
test('sweeper commits outside the box only with high line, skill and a genuine arrival margin',()=>{
 const p=keeper({x:36}),point={x:33,z:0,y:.11,t:1.4};
 const options={forward:-1,highLine:true};
 assert(Brain.keeperSweep(p,point,[],options));
 assert(!Brain.keeperSweep(p,point,[],{...options,highLine:false}));
 assert(!Brain.keeperSweep({...p,vision:58},point,[],options));
 assert(!Brain.keeperSweep(p,point,[{x:32,z:1,pace:88}],options));
 assert(!Brain.keeperSweep(p,{...point,t:.2},[],options));
 assert(!Brain.keeperSweep(p,{...point,y:1.2},[],options));
});
test('cross claim requires a safe reachable descending ball inside the box',()=>{
 const p=keeper(),point={x:45,z:1,y:1.6,vy:-2,t:1.2};
 assert(Brain.keeperClaim(p,point,[],{forward:-1}));
 assert(!Brain.keeperClaim(p,{...point,x:34},[],{forward:-1}));
 assert(!Brain.keeperClaim(p,{...point,y:2.7},[],{forward:-1}));
 assert(!Brain.keeperClaim(p,{...point,vy:5},[],{forward:-1}));
 assert(!Brain.keeperClaim(p,point,[{x:45,z:1,pace:96}],{forward:-1}));
});
test('directed parry chooses space away from a nearby attacker and never toward own goal',()=>{
 const p=keeper(),ball={x:49,z:0},opponents=[{x:45,z:5,vx:0,vz:0},{x:46,z:7,vx:0,vz:0}];
 const safe=Brain.keeperParry(p,ball,opponents,{forward:-1});
 assert(safe.vz<0&&safe.vx<0);
 const mirror=Brain.keeperParry(p,ball,opponents.map(a=>({...a,z:-a.z})),{forward:-1});
 assert(mirror.vz>0&&mirror.vx<0);
 assert.equal(Brain.keeperParry({...p,goalkeeping:50,handling:60},ball,opponents,{forward:-1}),null);
});
function fixture(extra={}){
 const m=new Match({seed:133,individualAI:true},Rig),gk=m.players[21],from=m.players[0];
 for(const p of m.players)p.active=p===gk||p===from;
 Object.assign(gk,keeper(extra),{active:true,action:'idle',actionClock:0,actionElapsed:0,duelRecovery:0,touchClock:0});
 Object.assign(from,{x:30,z:28,active:true,role:'ATT',team:0,vx:0,vz:0});
 m.restart=null;m.kick=null;m.goalPause=null;m.owner=null;m.time=10;m.lastTeam=0;m.lastTouch=from;m.offsidePhase=null;
 m.flight={id:4,kind:'cross',from,age:.3,target:null,offsidePlayers:[]};
 m.targets=new Map();m.updateTeamPhases();return {m,gk,from};
}
test('delivery planner follows real ball trajectory rather than the private target and leaves state unchanged',()=>{
 const {m,gk}=fixture({x:45,z:2.8});
 m.ball={x:42,z:8,y:2.6,vx:3,vz:-8,vy:0};
 Object.defineProperty(m.flight,'point',{get(){throw Error('private aim read');}});
 const before=structuredClone(m.ball),seed=m.seed;
 const result=m.keeperDeliveryPoint(gk);
 assert(result);assert.equal(result.kind,'claim');
 assert.deepEqual(m.ball,before);assert.equal(m.seed,seed);
 m.plan();assert.equal(m.targets.get(gk).state,'keeper-claim');
});
test('real catch-ready hands can claim a crossing ball once, with no remote acquisition',()=>{
 const {m,gk}=fixture();
 Object.assign(gk,{action:'catch-ready',actionClock:.5,actionElapsed:.24,claimFlightId:4,catchPoint:{x:45.75,y:1.1,z:0}});
 m.ball={x:45.9,z:2,y:1.1,vx:5,vz:0,vy:0};
 assert.equal(m.keeperDeliveryContact({x:45.6,y:1.1,z:2}),false);
 assert.equal(m.owner,null);
 m.ball.z=0;
 assert.equal(m.keeperDeliveryContact({x:45.6,y:1.1,z:0}),true);
 assert.equal(m.owner,gk);assert(gk.holdingBall);
 assert.equal(m.telemetry.keeperCrossClaims,1);
 assert.equal(m.ball.vx,0);assert.equal(m.ball.vz,0);
 assert.equal(m.keeperDeliveryContact({x:45.6,y:1.1,z:0}),false);
 assert.equal(m.telemetry.keeperCrossClaims,1);
});
test('cross handling outside the penalty area and own-team deliveries cannot award possession',()=>{
 const {m,gk,from}=fixture({x:34});
 Object.assign(gk,{action:'catch-ready',actionClock:.5,actionElapsed:.24,claimFlightId:4,catchPoint:{x:33.75,y:1.1,z:0}});
 m.ball={x:33.9,z:0,y:1.1,vx:5,vz:0,vy:0};
 assert.equal(m.keeperDeliveryContact({x:33.6,y:1.1,z:0}),false);
 gk.x=46;gk.catchPoint.x=45.75;m.ball.x=45.9;
 from.team=1;
 assert.equal(m.keeperDeliveryContact({x:45.6,y:1.1,z:0}),false);
 assert.equal(m.owner,null);
});
test('sweeper target is actually pursued and only a foot interception counts as a sweep',()=>{
 const {m,gk,from}=fixture({x:33});
 m.t[1].line='high';m.flight.kind='through';m.ball={x:30,z:0,y:.11,vx:4,vz:0,vy:0};
 const point=m.keeperDeliveryPoint(gk);assert(point&&point.kind==='sweep');
 m.plan();assert.equal(m.targets.get(gk).state,'keeper-sweep');
 assert.equal(m.telemetry.keeperSweeps??0,0);
 m.ball={x:33.2,z:0,y:.11,vx:4,vz:0,vy:0};
 m.fieldBallContact({x:32.8,y:.11,z:0});
 assert.equal(m.owner,gk);assert.equal(m.telemetry.keeperSweeps,1);
 assert.equal(gk.holdingBall,false,'outside the box this is foot control, not a hand save');
});
test('real shot hand contact directs rebound away from the occupied side; no save without contact',()=>{
 const {m,gk,from}=fixture({x:51,z:0});
 from.x=45;from.z=5;m.flight.kind='shot';
 Object.assign(gk,{action:'dive',actionClock:.6,actionElapsed:.3,diveSide:1});
 m.ball={x:50.9,z:0,y:1,vx:18,vz:0,vy:0};
 m.motion={saveHands:()=>[{x:50.8,y:1,z:0}]};
 m.keeperVisibility=()=>true;m.goalThreat=()=>true;
 m.keeper({x:50.6,y:1,z:0},1/60);
 assert.equal(m.telemetry.keeperDirectedParries,1);
 assert(m.ball.vx<0&&m.ball.vz<0);assert.equal(m.owner,null);assert.equal(m.flight,null);
});
test('legacy generated matches stay unchanged when the individual keeper feature is off',()=>{
 const a=new Match({seed:17}),b=new Match({seed:17,individualAI:false});
 for(let i=0;i<360;i++){a.step(1/60);b.step(1/60);}
 assert.equal(a.seed,b.seed);assert.deepEqual(a.ball,b.ball);assert.deepEqual(a.events,b.events);assert.deepEqual(a.score,b.score);
});
