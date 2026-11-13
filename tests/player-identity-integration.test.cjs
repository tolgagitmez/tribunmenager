'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim.js'),Model=require('../player-model.js');
const stats={passing:75,shooting:75,tackling:75,dribbling:75,pace:75,acceleration:75,agility:75,heading:75,crossing:75,vision:75,composure:75,strength:75,balance:75,endurance:75,goalkeeping:75,reactions:75,handling:75};
function raw(extra={}){return {id:0,name:'Profil',pos:'ATT',subposition:'ST',rating:80,fitness:100,form:100,preferredFoot:'right',weakFoot:65,...stats,...extra};}
function fixture(profile={},index=1,rosterId=index){
 const players=Model.demoTeam(0,'4-3-3');players[index]=raw({...profile,id:rosterId});
 const m=new Match({seed:21,formation:'4-3-3',players,starters:players.map(p=>p.id)}),p=m.players[index];
 m.players.forEach(q=>q.active=false);Object.assign(p,{active:true,x:0,z:0,vx:0,vz:0,speed:0,face:0,action:'idle',actionClock:0,touchClock:0,receiveClock:0,duelRecovery:0,tackleClock:0});
 m.restart=null;m.kick=null;m.owner=null;m.flight=null;m.time=10;m.planClock=100;m.targets=new Map();
 return {m,p};
}
function run(profile,seconds=2){const f=fixture(profile);for(let i=0;i<seconds*60;i++)f.m.move(f.p,{x:40,z:0,pace:1,state:'run'},1/60);return f;}
test('home and away records use one slot contract without changing raw squads',()=>{
 const home=Model.demoTeam(0,'4-3-3'),away=Model.demoTeam(1,'4-4-2');
 home[0]=raw({id:404,name:'Sol ayak',preferredFoot:'left',form:60,fitness:70,passing:91});
 away[0]=raw({id:808,name:'Rakip sol ayak',preferredFoot:'left',form:60,fitness:70,passing:91});
 const cfg={formation:'4-3-3',awayFormation:'4-4-2',players:home,awayPlayers:away,starters:home.map(p=>p.id),awayStarters:away.map(p=>p.id)},before=JSON.stringify(cfg),m=new Match(cfg);
 for(const [team,roster,formation] of [[0,home,'4-3-3'],[1,away,'4-4-2']])for(let i=0;i<11;i++){
  const p=m.players[team*11+i],expected=Model.forSlot(roster[i],Model.slotFor(formation,i));
  for(const key of ['skill','passing','pace','fitness','stamina','preferredFoot','weakFoot','strength','balance','vision','form','roleFit'])assert.equal(p[key],expected[key],`${team}/${i}/${key}`);
  assert.equal(p.rosterId,roster[i].id);assert.equal(p.name,roster[i].name);
 }
 assert.equal(JSON.stringify(cfg),before);assert.equal(m.players[0].preferredFoot,0);assert.equal(m.players[11].preferredFoot,0);
});
test('equal overall striker, stopper and playmaker retain distinct actual movement and passing',()=>{
 const striker=raw({pace:95,acceleration:94,passing:65,strength:62}),stopper=raw({pace:58,acceleration:55,passing:64,strength:95}),maker=raw({pace:72,acceleration:73,passing:95,vision:96,composure:94});
 const fast=run(striker),strong=run(stopper),creative=run(maker);
 assert.equal(fast.p.baseRating,80);assert.equal(strong.p.baseRating,80);assert.equal(creative.p.baseRating,80);
 assert.equal(fast.p.skill,strong.p.skill);assert.equal(strong.p.skill,creative.p.skill);assert(fast.p.x>creative.p.x);assert(creative.p.x>strong.p.x);
 function pass(profile){const {m,p}=fixture(profile);p.kickFoot=p.preferredFoot;m.ball={x:.88,y:.11,z:.18,vx:0,vy:0,vz:0};m.owner=p;m.random=()=>.95;
  assert(m.touchContact(p).ready);assert(m.startKick(p,'pass',null,{x:20,z:.18}));const before={x:m.ball.x,z:m.ball.z};m.release();assert.equal(m.ball.x,before.x);assert.equal(m.ball.z,before.z);assert.equal(m.flight.kind,'pass');return Math.abs(Math.atan2(m.ball.vz,m.ball.vx));}
 assert(pass(maker)<pass(striker));assert(pass(maker)<pass(stopper));
});
test('acceleration and agility alter actual acceleration and body turning at equal pace',()=>{
 const quick=fixture({pace:80,acceleration:96,agility:96}),slow=fixture({pace:80,acceleration:45,agility:45});
 for(const f of [quick,slow])for(let i=0;i<15;i++)f.m.move(f.p,{x:0,z:40,pace:1,state:'run'},1/60);
 assert(quick.p.speed>slow.p.speed);assert(quick.p.face>slow.p.face);assert(quick.p.z>slow.p.z);
});
test('fitness is applied once at kickoff; additional match fatigue reduces capacity',()=>{
 const {m,p}=fixture({pace:90,fitness:50});
 const expected=Model.forSlot(raw({pace:90,fitness:50}),Model.slotFor('4-3-3',1));assert.equal(p.pace,expected.pace);assert.equal(p.stamina,50);
 const originalEffort=m.effort;m.effort=()=>{};const command={x:40,z:0,pace:1,state:'run'};
 for(let i=0;i<120;i++)m.move(p,command,1/60);const initialTop=p.speed,limit=5.7+(expected.pace-75)*.04;
 assert(Math.abs(initialTop-limit)<1e-9,'conditioned pace does not receive a second initial stamina penalty');
 p.x=0;p.stamina=25;for(let i=0;i<120;i++)m.move(p,command,1/60);assert(p.speed<initialTop);m.effort=originalEffort;
});
test('endurance changes actual repeated sprint fatigue without altering intrinsic strength',()=>{
 const high=fixture({endurance:96,strength:90}),low=fixture({endurance:45,strength:90});
 for(const f of [high,low]){f.p.speed=5;for(let i=0;i<600;i++)f.m.effort(f.p,{state:'press'},1/60);}
 assert(high.p.energy>low.p.energy);assert(high.p.stamina>low.p.stamina);assert.equal(high.p.strength,low.p.strength);
});
function duel(strength,balance=75,reachable=true){
 const {m,p:carrier}=fixture({strength:75,balance:75,dribbling:75}),d=m.players[14];
 Object.assign(d,Model.forSlot(raw({strength,balance,pos:'DEF',subposition:'CB',tackling:75}),{role:'DEF',position:'CB'}),{id:14,team:1,role:'DEF',active:true,x:reachable?.8:8,z:.35,vx:0,vz:0,speed:0,face:Math.atan2(-.35,reachable?-.8:-8),tackleClock:0,duelRecovery:0,touchClock:0});
 m.owner=carrier;m.lastTouch=carrier;m.ball={x:.6,y:.11,z:0,vx:0,vy:0,vz:0};const rolls=[.5,.575,.99];m.random=()=>rolls.shift()??.99;
 const allowed=m.tackleAccess(d,carrier).attempt;m.doTackle(d,carrier);return {m,d,carrier,allowed};
}
test('strength and balance help a legal tackle while the same roll preserves a weaker carrier duel',()=>{
 const strong=duel(95,92),weak=duel(50,55);assert(strong.allowed);assert(weak.allowed);assert.equal(strong.m.telemetry.duels,1);assert.equal(weak.m.telemetry.duels,1);
 assert.equal(strong.m.owner,null);assert.equal(strong.m.lastTouch,strong.d);assert.equal(weak.m.owner,weak.carrier);
});
test('maximum strength cannot bypass physical reach or create a remote tackle',()=>{
 const f=duel(99,99,false);assert.equal(f.allowed,false);assert.equal(f.m.telemetry.duels,0);assert.equal(f.m.owner,f.carrier);assert.deepEqual(f.m.ball,{x:.6,y:.11,z:0,vx:0,vy:0,vz:0});
});
test('substitution uses the same slot evaluation and preserves actor identity',()=>{
 const players=Model.demoTeam(0,'4-3-3');players.push(raw({id:909,name:'Oyun kurucu yedek',pos:'MID',subposition:'CM',passing:94,vision:96,preferredFoot:'left',fitness:72,form:64}));
 const cfg={formation:'4-3-3',players,starters:players.slice(0,11).map(p=>p.id)},m=new Match(cfg),before=JSON.stringify(cfg),actor=m.players[0],old=actor.rosterId;
 assert(m.bench().some(p=>p.id===909));assert.equal(m.substitute(0,909).ok,true);const expected=Model.forSlot(players.at(-1),Model.slotFor('4-3-3',0));
 assert.equal(actor.id,0);assert.equal(actor.index,0);assert.equal(actor.team,0);assert.equal(actor.role,'ATT');assert.equal(actor.rosterId,909);assert.equal(actor.preferredFoot,0);
 for(const key of ['skill','passing','pace','vision','stamina','roleFit','strength','endurance'])assert.equal(actor[key],expected[key]);
 assert(!m.bench().some(p=>p.id===old||p.id===909));assert.equal(JSON.stringify(cfg),before);
});
test('unknown-foot and missing-attribute identity does not depend on shirt ID or roster order',()=>{
 const first=fixture({preferredFoot:undefined,pace:undefined,passing:undefined},1,1),second=fixture({preferredFoot:undefined,pace:undefined,passing:undefined},1,999);
 for(const key of ['pace','passing','preferredFoot','weakFoot','acceleration','strength'])assert.equal(first.p[key],second.p[key]);
 const a=new Match({seed:21}),b=new Match({seed:21});a.advance(3);b.advance(3);assert.deepEqual(a.players,b.players);assert.deepEqual(a.ball,b.ball);assert.equal(a.seed,b.seed);
});
test('equal overall goalkeepers use handling for the same real two-hand incoming flight',()=>{
 const Rig=require('../humanoid-rig.js'),{BallPhysics}=require('../football-sim.js');
 function trial(handling){
  const away=Model.demoTeam(1,'4-2-3-1');away[10]=raw({id:10,pos:'GK',subposition:'GK',handling,reactions:94});
  const m=new Match({seed:21,awayFormation:'4-2-3-1',awayPlayers:away,awayStarters:away.map(p=>p.id)},Rig),g=m.players[21],from=m.players[0];
  for(const p of m.players)p.active=false;
  Object.assign(g,{active:true,x:49,z:0,vx:0,vz:0,speed:0,face:Math.PI,action:'idle',actionClock:0,touchClock:0,receiveClock:0,duelRecovery:0,decision:100});
  Object.assign(from,{active:true,x:35,z:8,vx:0,vz:0,speed:0,action:'idle',actionClock:0,touchClock:100,decision:100});
  m.restart=null;m.kick=null;m.owner=null;m.goalPause=null;m.time=10;m.planClock=1e6;m.targets=new Map();m.events=[];m.queue=[];
  m.ball={x:38,y:1,z:0,vx:30,vy:BallPhysics.verticalLaunch(11,30,1,1,7,0),vz:0};m.lastTouch=from;m.lastTeam=0;m.flight={id:1,kind:'shot',from,target:null,age:0};m.releaseSerial=1;
  const start={...m.ball};for(let i=0;i<90&&!m.events.some(e=>['save','goal'].includes(e.type));i++)m.step(1/60);
  return {m,g,start};
 }
 const high=trial(94),low=trial(60);assert.deepEqual(high.start,low.start);assert.equal(high.g.skill,low.g.skill);assert.equal(high.g.baseRating,80);
 assert.equal(high.m.telemetry.keeperCatches,1);assert.equal(high.m.owner,high.g);assert.equal(low.m.telemetry.keeperCatches,0);assert.equal(low.m.owner,null);assert(low.m.events.some(e=>e.type==='save'));
});
test('two-footed players have equal technique on both reachable feet and weak foot cannot increase skill',()=>{
 const both=fixture({preferredFoot:'both',dribbling:60,passing:60,weakFoot:99}),one=fixture({preferredFoot:'right',dribbling:60,passing:60,weakFoot:99});
 for(const f of [both,one]){f.m.ball={x:.8,y:.11,z:0,vx:0,vy:0,vz:0};assert(f.m.touchContact(f.p,f.m.ball,0).ready);assert(f.m.touchContact(f.p,f.m.ball,1).ready);}
 assert.equal(both.m.touchContact(both.p,both.m.ball,0).technique,both.m.touchContact(both.p,both.m.ball,1).technique);
 assert(one.m.touchContact(one.p,one.m.ball,0).technique<=one.p.dribbling);
});
