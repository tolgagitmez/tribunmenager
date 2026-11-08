'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const Perception=require('../player-perception');
function fixture(side=1){
 const p={id:0,team:0,rosterId:100,role:'MID',active:true,x:0,z:0,vx:0,vz:0,face:side===1?0:Math.PI,vision:82,skill:82};
 const q={id:11,team:1,rosterId:200,role:'ATT',active:true,x:10*side,z:0,vx:2*side,vz:0,face:Math.PI,skill:81,pace:86,touchClock:.3,duelRecovery:.5,tackleClock:.7,receiveClock:.2,runIntent:{point:{x:20,z:5}},nextAction:{kind:'shot'},action:'pass'};
 return {p,q,players:[p,q]};
}
for(const side of [1,-1])test(`front vision and near contact respect mirrored body direction (${side})`,()=>{
 const {p,q,players}=fixture(side);Perception.update(players,0);
 assert.equal(Perception.rivals(p,0)[0].id,q.id);
 q.x=-3*side;Perception.clear(p,0);Perception.update(players,.1,1/60,{scanAllowed:false});
 assert.deepEqual(Perception.rivals(p,.1),[],'a blind presser outside contact range is unknown');
 q.x=-1.5*side;Perception.update(players,.2,1/60,{scanAllowed:false});
 assert.equal(Perception.rivals(p,.2)[0].source,'contact');assert.equal(p.face,side===1?0:Math.PI);
});
test('field of view and observation range exclude an unseen flank or distant player',()=>{
 const {p,q,players}=fixture();q.x=-8;q.z=-8;Perception.update(players,0);
 assert.deepEqual(Perception.rivals(p,0),[]);
 q.x=60;q.z=0;Perception.update(players,.1,1/60,{scanAllowed:false});assert.deepEqual(Perception.rivals(p,.1),[]);
 q.x=18;q.z=12;Perception.update(players,.2,1/60,{scanAllowed:false});assert.equal(Perception.rivals(p,.2).length,1);
});
test('short scheduled shoulder scan observes a blind rival without turning the body',()=>{
 const {p,q,players}=fixture();q.x=-8;Perception.update(players,0);
 const due=p.perception.nextScanAt,face=p.face;Perception.update(players,due,1/60);
 const read=Perception.rivals(p,due)[0];assert.equal(read.id,q.id);assert.equal(read.source,'scan');assert.equal(read.seenAt,due);assert.equal(p.face,face);assert.notEqual(p.perception.headYaw,0);
});
test('scan completion leaves a memory rather than a continuous rear position feed',()=>{
 const {p,q,players}=fixture();q.x=-8;Perception.update(players,0);
 const due=p.perception.nextScanAt;Perception.update(players,due,1/60);const seen=Perception.rivals(p,due)[0];
 q.x=-20;q.z=0;q.vx=-7;Perception.update(players,due+.18,1/60);
 const later=Perception.rivals(p,due+.18)[0];assert.equal(p.perception.headYaw,0);assert.equal(later.seenAt,seen.seenAt);assert.equal(later.vx,seen.vx*Math.exp(-.18/.4));assert(later.x>-8&&later.x<-7);assert.notEqual(later.x,q.x);
});
test('zero-duration updates cannot start a new scan even after its scheduled time',()=>{
 const {p,q,players}=fixture();q.x=-8;Perception.update(players,0);
 const due=p.perception.nextScanAt;Perception.update(players,due,0);
 assert.deepEqual(Perception.rivals(p,due),[]);assert.equal(p.perception.headYaw,0);assert.equal(p.perception.nextScanAt,due);
 Perception.update(players,due+.01,1/60);assert.equal(Perception.rivals(p,due+.01).length,1);
});
test('kick and recovery activity postpone a shoulder scan',()=>{
 for(const occupied of [{action:'shot',actionClock:.2},{duelRecovery:.2},{receiveClock:.2}]){
  const {p,q,players}=fixture();q.x=-8;Object.assign(p,occupied);Perception.update(players,0);
  const due=p.perception.nextScanAt;Perception.update(players,due,1/60);
  assert.deepEqual(Perception.rivals(p,due),[]);assert.equal(p.perception.headYaw,0);assert(p.perception.nextScanAt>due);
 }
});
test('memory queries read no live opponent positions or movement commands',()=>{
 const {p,q,players}=fixture();Perception.update(players,0);
 Object.defineProperty(q,'x',{get(){throw Error('live opponent was read');}});
 const read=Perception.rivals(p,.2)[0];assert(read.x>10&&read.x<10.4);assert(!('runIntent' in read));assert(!('nextAction' in read));assert(!('action' in read));
});
test('hidden motion does not rewrite memory and bounded extrapolation loses confidence',()=>{
 const {p,q,players}=fixture();q.vx=8;Perception.update(players,0);p.face=Math.PI;q.x=40;q.vx=-8;
 Perception.update(players,.2,1/60,{scanAllowed:false});const early=Perception.rivals(p,.2)[0],late=Perception.rivals(p,1)[0];
 assert.equal(early.seenAt,0);assert.equal(late.seenAt,0);assert(early.x>10&&late.x<13.2);assert(late.confidence<early.confidence);assert(late.uncertainty>early.uncertainty);assert(late.vx<early.vx);
});
test('expired blind observations disappear without a live-state fallback',()=>{
 const {p,q,players}=fixture();Perception.update(players,0);p.face=Math.PI;
 const end=Perception.limits(p).ttl+.001;Perception.update(players,end,1/60,{scanAllowed:false});
 assert.deepEqual(Perception.rivals(p,end),[]);assert.deepEqual(p.perception.records,{});
 assert.deepEqual(Perception.rivals(p,100),[]);
});
test('only clocks from the original observation decay, never a hidden future command',()=>{
 const {p,q,players}=fixture();Perception.update(players,1);q.touchClock=5;q.duelRecovery=5;
 const read=Perception.rivals(p,1.25)[0];assert(Math.abs(read.touchClock-.05)<1e-10);assert.equal(read.duelRecovery,.25);assert.equal(read.receiveClock,0);assert(Math.abs(read.tackleClock-.45)<1e-10);
});
test('snapshots and returned arrays cannot mutate the live actors or stored memory',()=>{
 const {p,q,players}=fixture();Perception.update(players,0);const first=Perception.rivals(p,0);first[0].x=999;first[0].skill=0;first.push({id:99});
 assert.equal(q.x,10);assert.equal(q.skill,81);const second=Perception.rivals(p,0);assert.equal(second.length,1);assert.equal(second[0].x,10);assert.equal(second[0].skill,81);
 const serialized=JSON.parse(JSON.stringify(p.perception));assert.deepEqual(serialized,p.perception);
});
test('teammates and officials are excluded, opposition goalkeeper remains observable',()=>{
 const {p,q,players}=fixture();q.role='GK';players.push({...q,id:1,team:0},{...q,id:22,team:2,referee:true});Perception.update(players,0);
 assert.equal(Perception.rivals(p,0).length,1);assert.equal(Perception.rivals(p,0)[0].role,'GK');
});
test('inactive and replaced identities cannot retain or donate another actor memory',()=>{
 const {p,q,players}=fixture();Perception.update(players,0);q.active=false;Perception.update(players,.1,1/60,{scanAllowed:false});assert.deepEqual(Perception.rivals(p,.1),[]);assert.equal(q.perception,null);
 q.active=true;q.x=-5;q.rosterId=201;Perception.update(players,.2,1/60,{scanAllowed:false});assert.deepEqual(Perception.rivals(p,.2),[]);
 q.x=10;Perception.update(players,.3,1/60,{scanAllowed:false});assert.equal(Perception.rivals(p,.3)[0].rosterId,201);
 p.rosterId=101;q.x=-5;Perception.update(players,.4,1/60,{scanAllowed:false});assert.deepEqual(Perception.rivals(p,.4),[]);
 p.active=false;Perception.update(players,.5);assert.equal(p.perception,null);
});
test('rival substitution removes an old blind identity without exposing the replacement',()=>{
 const {p,q,players}=fixture();Perception.update(players,0);q.x=-8;q.rosterId=202;
 Perception.update(players,.1,1/60,{scanAllowed:false});assert.deepEqual(Perception.rivals(p,.1),[]);
});
test('explicit reset and lifecycle epoch discard old observations, possession is not implicitly read',()=>{
 const {p,q,players}=fixture();Perception.update(players,0);q.x=-8;Perception.reset(players,.1);assert.deepEqual(Perception.rivals(p,.1),[]);
 q.x=10;Perception.update(players,.2,1/60,{epoch:'restart-1'});assert.equal(Perception.rivals(p,.2).length,1);
 q.x=-8;Perception.update(players,.3,1/60,{epoch:'restart-2',scanAllowed:false});assert.deepEqual(Perception.rivals(p,.3),[]);
});
test('time rewind clears stale future observations',()=>{
 const {p,q,players}=fixture();Perception.update(players,10);q.x=-8;assert.deepEqual(Perception.rivals(p,9),[]);
 Perception.update(players,1,1/60,{scanAllowed:false});assert.deepEqual(Perception.rivals(p,1),[]);
});
test('deterministic scans are independent of actor array order and RNG',()=>{
 const a=fixture(),b=fixture();b.players.reverse();const old=Math.random;Math.random=()=>{throw Error('perception consumes RNG');};
 try{for(let i=0;i<=180;i++){const t=i/60;a.q.x=b.q.x=-8;a.q.z=b.q.z=Math.sin(t)*3;Perception.update(a.players,t,1/60);Perception.update(b.players,t,1/60);}assert.deepEqual(a.p.perception,b.p.perception);assert.deepEqual(Perception.rivals(a.p,3),Perception.rivals(b.p,3));}finally{Math.random=old;}
});
test('browser UMD export has the same observation API',()=>{
 const sandbox={window:{}};vm.runInNewContext(fs.readFileSync(require.resolve('../player-perception'),'utf8'),sandbox);
 for(const key of ['update','rivals','clear','reset'])assert.equal(typeof sandbox.window.TribunPerception[key],'function');
});
