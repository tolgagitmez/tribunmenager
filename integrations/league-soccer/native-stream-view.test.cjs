'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{create}=require('./native-stream-view.js');
function packet(seq,x,score=[0,0]){
 return {engine:'league-soccer',authoritative:false,sequence:seq,phase:'playing',players:[{nativeId:1,name:'A',slot:0,number:9}],frame:{schema:1,engine:'league-soccer',elapsedMs:seq*100,matchMs:seq*1800,done:false,score,ball:[x,0,.11],ballVelocity:[1,0,0],players:[{id:0,team:0,databaseId:1,position:[x,0,0],velocity:[1,0,0],direction:[1,0,0]},{id:1,team:1,databaseId:12,position:[-20,0,0],velocity:[0,0,0],direction:[-1,0,0]}]}};
}
test('late join, stable actor identity and stale response rejection',()=>{
 const v=create(),a=packet(20,10),b=packet(21,12,[1,0]);
 assert(v.ingest(a,100));const before=v.sample(100,0),actor=before.players[0];assert.equal(actor.name,'A');
 assert(v.ingest(b,280));assert.equal(v.sample(370,0).players[0],actor);
 assert.ok(Math.abs(actor.x-11*52/55)<1e-8);assert.deepEqual(v.sample(460,0).score,[1,0]);
 assert.equal(v.ingest(a,500),false);assert.deepEqual(v.sample(500,0).score,[1,0]);
 v.reset();assert.equal(v.sample(500,0),null);
});
test('early final rejected and authoritative data never accepted',()=>{
 const v=create(),a=packet(1,0);a.frame.done=true;
 assert.throws(()=>v.ingest(a,0));a.authoritative=true;assert.equal(v.ingest(a,0),false);
});

test('render budget avoids hidden work and caps idle/performance without capping balanced live',()=>{
 const r=require('./native-stream-view.js').createRenderBudget();
 assert.equal(r.next(0,{hidden:true}),null);
 assert.equal(r.next(10,{playing:true}).dt,0);
 assert.ok(r.next(26,{playing:true}));
 assert.equal(r.next(42,{playing:true,mode:'performance'}),null);
 assert.ok(r.next(60,{playing:true,mode:'performance'}));
 assert.equal(r.next(80,{}),null);
 assert.ok(r.next(127,{}));
 assert.equal(r.next(130,{hidden:true}),null);
 assert.equal(r.next(10000,{playing:true}).dt,0);
});

test('stage100 optional stream stature and gait use only received validated frames',()=>{
 const old=create(),v=create(null,{advancedPresentation:true});
 const a=packet(20,10),b=packet(21,10.2,[1,0]);
 for(const p of [a,b]){
  p.frame.inPlay=true;p.frame.setPiece=false;
  p.frame.players[0].heightMetres=1.72;
  p.frame.players[0].motionIdentity={agility:.8,velocity:.7,acceleration:.6,balance:.8,dribble:.7,control:.7,fatigueFactor:.9};
 }
 for(const [p,t] of [[a,100],[b,200]]){
  assert(old.ingest(p,t));assert(v.ingest(p,t));
  const x=old.sample(t+100,.02),y=v.sample(t+100,.02);
  assert.deepEqual(x.ball,y.ball);assert.deepEqual(x.score,y.score);
  assert.equal(x.players[0].x,y.players[0].x);assert.equal(y.players[0].nativeAnatomy.height,1.72);
 }
 const p=v.sample(300,.02).players[0];assert.equal(p.nativeMotionMatch,true);assert.equal(p.nativeMotionIdentity.agility,.8);
 assert.equal(p.nativeContact,undefined);
 assert.equal(v.sample(300,0).players[1].nativeAnatomy.height,null);
 const c=packet(22,10.4,[1,0]);c.frame.inPlay=false;c.frame.setPiece=true;
 assert(v.ingest(c,300));assert.equal(v.sample(300,0).players[0].nativeMotionMatch,false);
 v.setPresentation(false);assert.equal(v.sample(310,0).players[0].nativeAnatomy,undefined);
 assert.equal(v.ingest(a,400),false);
});

test('stage101 duplicate frames cannot rewrite score, positions or phase',()=>{
 const v=create(),a=packet(20,10,[1,0]);assert(v.ingest(a,100));
 const duplicate=JSON.parse(JSON.stringify(a));duplicate.remainingMs=200;
 assert(v.ingest(duplicate,200));
 duplicate.frame.score=[2,0];assert.equal(v.ingest(duplicate,300),false);
 duplicate.frame.score=[1,0];duplicate.frame.players[0].position=[30,0,0];
 assert.equal(v.ingest(duplicate,300),false);
 duplicate.frame.players[0].position=[10,0,0];duplicate.phase='finished';
 assert.throws(()=>v.ingest(duplicate,300));
 assert.deepEqual(v.sample(300,0).score,[1,0]);
 assert.equal(v.sample(300,0).done,false);
});
test('stage101 reject regression and post-final frames; reset permits new match',()=>{
 const v=create();assert(v.ingest(packet(20,10,[1,0]),100));
 assert.equal(v.ingest(packet(21,11,[0,0]),200),false);
 const older=packet(21,11,[1,0]);older.frame.matchMs=0;
 assert.equal(v.ingest(older,200),false);
 const final=packet(22,12,[2,0]);final.frame.done=true;final.phase='finished';final.frame.matchMs=5400000;
 assert(v.ingest(final,300));
 assert.equal(v.ingest(packet(23,13,[2,0]),400),false);
 assert.deepEqual(v.sample(400,0).score,[2,0]);
 v.reset();assert(v.ingest(packet(0,0),500));
});
test('stage101 stalled stream freezes rig stepping and resumes on new frame',()=>{
 const updates=[];const v=create({update(p,dt){updates.push(dt);},reset(){}});
 const a=packet(10,1);v.ingest(a,100);v.sample(200,.02);assert.equal(updates.at(-1),.02);
 v.ingest(a,1100);assert.equal(v.isStale(1200),true);assert.equal(v.sample(1200,.02).stale,true);
 assert.equal(updates.at(-1),0);
 assert(v.ingest(packet(11,1.2),1300));assert.equal(v.sample(1400,.02).stale,false);assert.equal(updates.at(-1),.02);
});
