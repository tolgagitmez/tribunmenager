'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Intent=require('../team-intent');
const player=()=>({id:1,team:0,active:true,x:0,z:0});
const support=(x=8,z=6)=>({x,z,pace:.94,state:'support',focusId:2});
const run=(x=16,z=4)=>({x,z,pace:1.07,state:'penetration',partnerId:2,focusId:2});
const context=(time=0,extra={})=>({time,phase:'possession',phaseEpoch:1,attackEpoch:1,...extra});
test('task captures purpose, epoch, partners and fixed lifetime without RNG',()=>{
 const p=player(),q=support(),random=Math.random;Math.random=()=>{throw Error('random is not an observation');};
 try{assert.equal(Intent.resolve(p,q,context()).purpose,'support');}finally{Math.random=random;}
 assert.equal(p.task.focusId,2);assert.equal(p.task.since,0);assert.equal(p.task.commitUntil,.5);assert.equal(p.task.expiresAt,1.8);
 assert.deepEqual(q,support());assert.equal(p.taskHistory[0].reason,'start');
});
test('minimum commitment protects a useful support from a new run',()=>{
 const p=player();Intent.resolve(p,support(),context());const point=Intent.resolve(p,run(),context(.16));
 assert.equal(point.state,'support');assert.equal(point.x,8);assert.equal(p.task.reason,'commitment');assert.equal(p.task.since,0);
});
test('materially different task needs a consistently observed challenger',()=>{
 const p=player();Intent.resolve(p,support(),context());
 assert.equal(Intent.resolve(p,run(),context(.51)).state,'support');
 assert.equal(Intent.resolve(p,run(),context(.7)).state,'support');
 assert.equal(Intent.resolve(p,run(),context(.84)).state,'penetration');
 assert.equal(p.taskHistory.at(-1).reason,'replan');
});
test('alternating challengers cannot accumulate one another confirmation time',()=>{
 const p=player();Intent.resolve(p,support(),context());
 Intent.resolve(p,run(16,4),context(.5));Intent.resolve(p,run(16,-4),context(.7));
 assert.equal(Intent.resolve(p,run(16,4),context(.9)).state,'support');
});
test('same task reviews at its absolute expiry instead of sliding the deadline',()=>{
 const p=player();Intent.resolve(p,support(),context());
 for(const time of [.16,.5,.9,1.3,1.79]){Intent.resolve(p,support(),context(time));assert.equal(p.task.since,0);assert.equal(p.task.expiresAt,1.8);}
 assert.equal(Intent.resolve(p,run(),context(1.8)).state,'penetration');assert.equal(p.taskHistory.at(-1).reason,'expiry');
});
test('target noise does not make a static supporting point drift each plan',()=>{
 const p=player();Intent.resolve(p,support(),context());
 for(let i=1;i<=6;i++){const point=Intent.resolve(p,support(8+i*.1,6),context(i*.16));assert.equal(point.x,8);assert.equal(p.task.since,0);}
});
test('a confirmed static target change keeps the original task deadline',()=>{
 const p=player();Intent.resolve(p,support(),context());Intent.resolve(p,support(12,6),context(.5));
 const result=Intent.resolve(p,support(12,6),context(.84));assert.equal(result.x,12);assert.equal(p.task.since,0);assert.equal(p.task.expiresAt,1.8);
 assert.equal(p.taskHistory.at(-1).reason,'target-update');
});
test('marking follows the same observed runner without resetting commitment or expiry',()=>{
 const p=player(),c=time=>context(time,{phase:'defence'}),q={x:-6,z:4,pace:.98,state:'mark',partnerId:12};
 Intent.resolve(p,q,c(0));const point=Intent.resolve(p,{...q,x:-10,z:9},c(.16));
 assert.equal(point.x,-10);assert.equal(point.z,9);assert.equal(p.task.since,0);assert.equal(p.task.expiresAt,2.1);assert.equal(p.task.reason,'track');
});
test('mark identity changes require confirmation while the old observed runner stays valid',()=>{
 const p=player(),c=time=>context(time,{phase:'defence'}),q={x:-6,z:4,state:'mark',partnerId:12};
 Intent.resolve(p,q,c(0));assert.equal(Intent.resolve(p,{...q,partnerId:13},c(.16)).partnerId,12);
 assert.equal(Intent.resolve(p,{...q,partnerId:13},c(.61)).partnerId,13);
});
test('win to possession promotes a compatible run rather than restarting it',()=>{
 const p=player();Intent.resolve(p,run(),context(0,{phase:'win'}));Intent.resolve(p,run(),context(.2,{phase:'possession',phaseEpoch:2}));
 assert.equal(p.task.since,0);assert.equal(p.task.phase,'possession');assert.equal(p.task.expiresAt,3.2);assert(p.taskHistory.some(e=>e.reason==='phase-continue'));
});
test('loss to defence retains a tracking assignment within the same attack epoch',()=>{
 const p=player(),q={x:-6,z:4,state:'mark',partnerId:12};Intent.resolve(p,q,context(0,{phase:'loss'}));
 Intent.resolve(p,q,context(.2,{phase:'defence',phaseEpoch:2}));assert.equal(p.task.since,0);assert.equal(p.task.phase,'defence');
});
test('a turnover abandons attacking runs immediately and explains the loss',()=>{
 const p=player();Intent.resolve(p,run(),context());const point=Intent.resolve(p,{x:-9,z:0,state:'recovery'},context(.05,{phase:'loss',attackEpoch:2}));
 assert.equal(point.state,'recovery');assert.equal(p.taskHistory.at(-1).reason,'loss');
});
test('a new attacking generation invalidates an old same-phase run',()=>{
 const p=player();Intent.resolve(p,run(),context());Intent.resolve(p,support(),context(.05,{attackEpoch:2}));
 assert.equal(p.task.state,'support');assert.equal(p.taskHistory.at(-1).reason,'epoch');
});
test('a physically urgent reception or block bypasses the minimum commitment',()=>{
 for(const q of [{x:1,z:2,state:'receive-run'},{x:2,z:0,state:'block'}]){
  const p=player();Intent.resolve(p,support(),context());const result=Intent.resolve(p,q,context(.05));
  assert.equal(result.state,q.state);assert.equal(p.taskHistory.at(-1).reason,'urgent');
 }
});
test('immediate direct threat and explicit high priority can replace a commitment',()=>{
 for(const extra of [{directThreat:true},{}]){
  const p=player();Intent.resolve(p,support(),context());const q={...run(),priority:extra.directThreat?0:20};
  assert.equal(Intent.resolve(p,q,context(.05,extra)).state,'penetration');assert.equal(p.taskHistory.at(-1).reason,extra.directThreat?'urgent':'priority');
 }
});
test('an inactive partner cancels a run before its deadline',()=>{
 const p=player(),players=[p,{id:2,active:true}];Intent.resolve(p,run(),context(0,{players}));players[1].active=false;
 Intent.resolve(p,support(),context(.1,{players}));assert.equal(p.task.state,'support');assert.equal(p.taskHistory.at(-1).reason,'partner');
});
test('observed safety cancellation is immediate without reading any live rival',()=>{
 const p=player();Intent.resolve(p,run(),context());const blocked={...context(.05),safe:()=>false};
 Intent.resolve(p,support(),blocked);assert.equal(p.task.state,'support');assert.equal(p.taskHistory.at(-1).reason,'safety');
});
test('arrival gives an open supporting connection a short readiness dwell',()=>{
 const p=player();Intent.resolve(p,support(),context());Object.assign(p,{x:8,z:6});
 assert.equal(Intent.resolve(p,run(),context(.5)).state,'support');assert.equal(Intent.reserved(p,context(.8)),true);
 assert.equal(Intent.resolve(p,run(),context(.96)).state,'penetration');assert.equal(p.taskHistory.at(-1).reason,'arrived');
});
test('a run that makes no progress yields instead of freezing the player forever',()=>{
 const p=player();Intent.resolve(p,run(),context());assert.equal(Intent.resolve(p,support(),context(1.21)).state,'support');
 assert.equal(p.taskHistory.at(-1).reason,'stalled');
});
test('reservations protect the commitment and allow its own allocator to renew proposals',()=>{
 const p=player();Intent.resolve(p,run(),context());assert.equal(Intent.reserved(p,context(.1)),true);
 assert.equal(Intent.reserved(p,context(.1),['run']),false);assert.equal(Intent.reserved(p,context(.71)),false);
 assert.equal(Intent.reserved(p,context(.1,{phase:'loss'})),false);
});
test('restart clearing and inactive players leave no lingering reservation',()=>{
 const p=player();Intent.resolve(p,run(),context());Intent.clear(p,'restart',context(.1));assert.equal(p.task,null);assert.equal(p.taskHistory.at(-1).reason,'restart');
 Intent.resolve(p,run(),context(.2));p.active=false;const point=Intent.resolve(p,support(),context(.3));
 assert.equal(p.task,null);assert.equal(point.pace,0);assert.equal(point.state,'inactive');assert.equal(p.taskHistory.at(-1).reason,'inactive');
});
test('invalid proposal coordinates cannot enter the movement command',()=>{
 const p=player();Intent.resolve(p,support(),context());const result=Intent.resolve(p,{x:NaN,z:0,state:'penetration'},context(.1));
 assert.equal(result.x,8);assert.equal(result.state,'support');Intent.clear(p,'restart',context());assert.deepEqual(Intent.resolve(p,{},context()),{x:0,z:0,pace:0,state:'shape'});
});
test('transition history remains bounded and trace receives independent entry values',()=>{
 const p=player(),events=[];
 for(let i=0;i<80;i++){Intent.resolve(p,support(),context(i*2,{trace:e=>{events.push({...e});e.reason='external';}}));}
 assert.equal(p.taskHistory.length,24);assert.equal(events.length,80);assert.notEqual(p.taskHistory[0].reason,'external');
});
test('two independent replays produce identical task state and decisions',()=>{
 const a=player(),b=player(),commands=[support(),run(),run(),run(),support(),support()];
 for(let i=0;i<commands.length;i++)assert.deepEqual(Intent.resolve(a,commands[i],context(i*.25)),Intent.resolve(b,commands[i],context(i*.25)));
 assert.deepEqual(a,b);
});
test('mark to tracking-run follows the same man while preserving the task lifetime',()=>{
 const p=player(),c=time=>context(time,{phase:'defence'}),q={x:-6,z:4,state:'mark',partnerId:12};
 Intent.resolve(p,q,c(0));const result=Intent.resolve(p,{...q,x:-12,state:'track-run'},c(.16));
 assert.equal(result.state,'track-run');assert.equal(result.x,-12);assert.equal(p.task.since,0);assert.equal(p.task.expiresAt,2.1);
});
test('a substituted actor or partner cannot inherit an old run contract',()=>{
 const p={...player(),rosterId:100},other={id:2,rosterId:101,active:true},players=[p,other];
 Intent.resolve(p,run(),context(0,{players}));other.rosterId=202;
 Intent.resolve(p,support(),context(.1,{players}));assert.equal(p.taskHistory.at(-1).reason,'partner');
 p.rosterId=303;Intent.resolve(p,run(),context(.2,{players}));assert.equal(p.taskHistory.at(-1).reason,'substitution');
});
test('an urgent reroute changes a static destination without extending its absolute lifetime',()=>{
 const p=player();Intent.resolve(p,run(),context());const result=Intent.resolve(p,{...run(16,-4),urgent:true},context(.1));
 assert.equal(result.z,-4);assert.equal(p.task.since,0);assert.equal(p.task.expiresAt,3.2);assert.equal(p.taskHistory.at(-1).reason,'urgent-target');
});
test('resolving a shallow forecast actor never mutates the original task or history',()=>{
 const p=player();Intent.resolve(p,support(),context());const before=structuredClone(p),forecast={...p};
 Intent.resolve(forecast,run(),context(.5));assert.deepEqual(p,before);
 Intent.resolve(forecast,run(),context(.85));assert.deepEqual(p,before);assert.equal(forecast.task.state,'penetration');
 Intent.clear({...p},'restart',context(.9));assert.deepEqual(p,before);
});
test('the same objective accepts current pace and priority while retaining its static destination',()=>{
 const p=player(),q={x:8,z:0,pace:1,state:'dribble',priority:90};
 Intent.resolve(p,q,context());const result=Intent.resolve(p,{...q,x:8.4,pace:.34,priority:100},context(.16));
 assert.equal(result.x,8);assert.equal(result.pace,.34);assert.equal(p.task.priority,100);
 assert.equal(p.task.since,0);assert.equal(p.task.expiresAt,1.2);
});
test('a pending same-objective reroute still uses the current pace and priority',()=>{
 const p=player(),q={...support(),priority:30};Intent.resolve(p,q,context());
 const result=Intent.resolve(p,{...support(14,9),pace:.6,priority:35},context(.16));
 assert.equal(result.x,8);assert.equal(result.z,6);assert.equal(result.pace,.6);assert.equal(p.task.priority,35);
 assert.equal(p.task.since,0);assert.equal(p.task.expiresAt,1.8);
});
test('a rejected different task cannot overwrite the held tasks operational inputs',()=>{
 const p=player(),q={...support(),priority:30};Intent.resolve(p,q,context());
 const result=Intent.resolve(p,{...run(),pace:1.12,priority:35},context(.16));
 assert.equal(result.state,'support');assert.equal(result.pace,.94);assert.equal(p.task.priority,30);
});
test('a confirmed ordinary challenger cannot close a newly arrived support before its readiness dwell',()=>{
 const p=player();Intent.resolve(p,support(),context());Object.assign(p,{x:8,z:6});
 const shape={x:-4,z:0,pace:.88,state:'shape'};
 assert.equal(Intent.resolve(p,shape,context(.8)).state,'support');
 assert.equal(Intent.resolve(p,shape,context(1.2)).state,'support');assert.equal(p.task.reason,'ready-window');
 assert.equal(Intent.resolve(p,shape,context(1.26)).state,'shape');assert.equal(p.taskHistory.at(-1).reason,'arrived');
});
test('urgent danger and observed unsafety can end the support readiness window immediately',()=>{
 for(const emergency of ['urgent','unsafe']){
  const p=player();Intent.resolve(p,support(),context());Object.assign(p,{x:8,z:6});Intent.resolve(p,support(),context(.8));
  const result=Intent.resolve(p,emergency==='urgent'?{x:1,z:0,state:'block'}:run(),context(.9,emergency==='unsafe'?{safe:false}:{}));
  assert.notEqual(result.state,'support');assert.equal(p.taskHistory.at(-1).reason,emergency==='unsafe'?'safety':'urgent');
 }
});
