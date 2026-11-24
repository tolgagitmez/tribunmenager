'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Brain=require('../player-brain'),Intent=require('../team-intent'),{Match}=require('../football-sim');
const actor=(extra={})=>({id:3,active:true,role:'MID',position:'AM',x:13,z:-6,vx:0,vz:0,face:0,energy:1,vision:94,acceleration:92,pace:90,composure:90,tackling:90,agility:90,...extra});
const from=actor({id:1,x:0,z:0}),wall=actor({id:2,x:9,z:3});
test('third man chooses a genuine forward triangle and respects onside braking and reserved roles',()=>{
 const p=actor(),c={forward:1,line:25,opponents:[],reserved:[]},r=Brain.thirdManOption(p,from,wall,c);
 assert(r);assert(r.point.x>p.x&&r.point.x<=25-Brain.runMargin(p,1));assert(Math.abs(r.point.z-p.z)>=3);
 assert.equal(Brain.thirdManOption({...p,position:'DM'},from,wall,c),null);
 assert.equal(Brain.thirdManOption({...p,energy:.2},from,wall,c),null);
 assert.equal(Brain.thirdManOption(p,from,wall,{...c,line:14}),null);
 const mirror=a=>({...a,x:-a.x,vx:-a.vx});
 const b=Brain.thirdManOption(mirror(p),mirror(from),mirror(wall),{...c,forward:-1});
 assert(b);assert.equal(b.point.x,-r.point.x);assert.equal(b.point.z,r.point.z);
});
test('third man pass bonus does not override closed lanes or poor receiver safety',()=>{
 const c={risk:.12,arrivalRisk:.2,space:7,gain:9};
 assert(Brain.thirdManBias(wall,c)>0);
 for(const change of [{risk:.7},{arrivalRisk:.9},{space:1},{gain:-4}])assert.equal(Brain.thirdManBias(wall,{...c,...change}),0);
});
test('press trap requires a separate visible outlet and reachable screening point',()=>{
 const p=actor({x:6,z:17}),carrier=actor({id:11,x:0,z:24}),receiver=actor({id:12,x:9,z:13});
 const c={forward:1,ball:carrier,pressPoint:{x:0,z:24},coverPoint:{x:-4,z:20}};
 const r=Brain.trapOutlet(p,carrier,receiver,c);assert(r);assert.equal(r.receiverId,12);
 assert.equal(Brain.trapOutlet(p,carrier,{...receiver,confidence:.1},c),null);
 assert.equal(Brain.trapOutlet({...p,role:'DEF'},carrier,receiver,c),null);
 assert.equal(Brain.trapOutlet(p,carrier,receiver,{...c,coverPoint:r.point}),null);
});
function fixture(){
 const m=new Match({seed:52,individualAI:true,tactics:{playstyle:'possession',passing:'short'}});
 for(const p of m.players)p.active=false;
 const a=m.players[3],b=m.players[5],c=m.players[1],g=m.players[21],d=m.players[18];
 const set=(p,v)=>Object.assign(p,actor({id:p.id,team:p.team,rosterId:p.rosterId}),{active:true,task:null,runIntent:null,supportIntent:null,duelRecovery:0,receiveClock:0,touchClock:0,comboCooldown:0,speed:0},v);
 set(a,{x:0,z:0,homeX:0,homeZ:-10,detailedRole:true,position:'AM'});set(b,{x:9,z:3,homeX:7,homeZ:10});set(c,{role:'ATT',position:'ST',x:13,z:-6,homeX:22,homeZ:0});
 set(g,{role:'GK',x:49,z:0});set(d,{role:'DEF',x:25,z:18});
 m.restart=null;m.kick=null;m.flight=null;m.goalPause=null;m.owner=a;m.lastTeam=0;m.lastTouch=a;m.time=10;m.ball={x:.88,y:.11,z:.18,vx:0,vy:0,vz:0};m.targets=new Map();m.updateTeamPhases();
 m.t[0].playstyle='possession';return {m,a,b,c};
}
test('first real delivery reserves exactly one third runner; accepted task is visible to wall player only',()=>{
 const {m,a,b,c}=fixture();
 m.afterPass(a,{kind:'pass',target:b,point:{x:b.x,z:b.z}},9.5);
 assert.equal(c.runIntent?.kind,'third-man');
 assert.equal(c.runIntent.partnerId,b.id);
 assert.equal(m.field(0).filter(p=>p.runIntent?.kind==='third-man').length,1);
 assert.equal(m.thirdManLink(b,c),null);
 m.owner=null;m.flight={id:9,kind:'pass',from:a,target:b,point:{x:b.x,z:b.z},age:.1,offsidePlayers:[]};m.ball.x=3;m.ball.vx=12;
 m.plan();assert.equal(m.targets.get(c).state,'channel-run');assert.equal(c.runIntent.accepted,true);
 assert(m.thirdManLink(b,c));assert.equal(m.thirdManLink(a,c),null);
 m.attackEpoch[0]++;assert.equal(m.thirdManLink(b,c),null);
});
test('three-player connection is counted only on the actual third player reception, not proposal',()=>{
 const {m,a,b,c}=fixture();
 m.afterPass(a,{kind:'pass',target:b,point:{x:b.x,z:b.z}},9.5);
 const run=c.runIntent;assert(run);
 m.owner=null;m.flight={id:9,kind:'pass',from:a,target:b,point:{x:b.x,z:b.z},age:.1,offsidePlayers:[]};
 m.ball={x:b.x+.7,y:.11,z:b.z,vx:9,vy:0,vz:0};m.plan();
 assert(m.acquire(b));
 m.time+=.4;c.x+=2;m.plan();
 assert(m.thirdManLink(b,c));
 m.ball={x:b.x+.88,y:.11,z:b.z+.18,vx:0,vy:0,vz:0};
 assert(m.startKick(b,'pass',c,{x:c.x+2,z:c.z}));
 assert(m.kick.thirdManRead);
 const k=m.kick;
 m.owner=null;m.afterPass(b,k,12);
 assert.equal(m.telemetry.thirdManReleases,1);assert.equal(m.telemetry.thirdManCompletions??0,0);
 m.kick=null;m.flight={id:10,kind:'pass',from:b,target:c,thirdManReturn:k.thirdManReturn,offsidePlayers:[]};
 m.ball={x:c.x+.65,y:.11,z:c.z,vx:8,vy:0,vz:0};
 assert(m.acquire(c));assert.equal(m.telemetry.thirdManCompletions,1);
});
test('trap screen uses cover task and cannot survive loss of observed outlet',()=>{
 const {m,a,b,c}=fixture();m.owner=m.players[18];m.lastTeam=1;m.updateTeamPhases();
 const point={x:7,z:8,state:'trap-screen',pace:1.01,priority:40,focusId:m.owner.id,partnerId:a.id};
 const chosen=Intent.resolve(c,point,m.taskContext(c));
 assert.equal(chosen.purpose,'cover');
 assert.equal(m.taskSafe(c,c.task,{rivals:[]}),false);
});
test('legacy generated fixtures retain deterministic state with individual AI disabled',()=>{
 const a=new Match({seed:61}),b=new Match({seed:61,individualAI:false});
 for(let i=0;i<360;i++){a.step(1/60);b.step(1/60);}
 assert.equal(a.seed,b.seed);assert.deepEqual(a.ball,b.ball);assert.deepEqual(a.events,b.events);assert.deepEqual(a.score,b.score);
});
