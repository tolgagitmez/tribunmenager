'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const ContactEvents = require('../match-contact-events.js');
const {snapshot} = require('../live-match-worker.cjs');
const viewSource = fs.readFileSync(path.join(__dirname, '../live-match-view.js'), 'utf8');
const near = (a,b) => assert(Math.abs(a-b)<1e-6, a+' vs '+b);
const player = (id, role, x, action, elapsed=0, clock=0) => ({
  id, role, x, z:2, face:0, speed:1, vx:1, vz:0, active:true,
  action, actionElapsed:elapsed, actionClock:clock
});
const ball = (x,vx=0,spin) => ({x,y:.11,z:2,vx,vy:0,vz:0,...(spin===undefined?{}:{spin})});
const cue = (id,time,kind,actor,position) => ({
  id,time,tick:Math.round(time*60),kind,playerId:actor.id,flightId:1,kickKind:'shot',
  ball:position,actor
});
function newView(rig={update(){}}){
  const window = {TribunContactEvents:ContactEvents,TribunHumanoidRig:rig};
  vm.runInNewContext(viewSource,{window});
  return new window.TribunLiveMatchView();
}
function packet(time,position,shooter,keeper,extras={}){
  return {time,ball:position,players:[shooter,keeper],ownerId:null,contacts:[],eventSerial:0,events:[],
    direction:[1,-1],score:[0,0],...extras};
}
const ids = cues => Array.from(cues,x=>x.id);

test('buffered live ball, kick and keeper phases arrive at the same exact cue through jitter',()=>{
  const view = newView();
  const shooter = player(1,'ATT',9,'shoot',.18,.25);
  const keeper = player(21,'GK',14,'idle');
  const start = packet(1,ball(10),shooter,keeper);
  view.ingest(start,1000);
  // This packet skips the whole flight. Important contacts are retained in
  // the journal even though flight is already null when the poll arrives.
  const launch = cue(1,1.08,'release',player(1,'ATT',9.2,'shoot',.26,.17),ball(10.2,20,.4));
  const prepare = cue(2,1.14,'keeper-prepare',player(21,'GK',14,'catch-ready',0,.65),ball(11.4,20,.35));
  const catchCue = cue(3,1.20,'keeper-contact',player(21,'GK',14,'catch',0,.75),ball(12.6));
  const events=[{type:'shot',time:1.08},{type:'save',time:1.20}];
  const end = packet(1.24,ball(12.7),player(1,'ATT',9.3,'shoot',.42,.01),
    player(21,'GK',14,'catch',.04,.71),{events,eventSerial:2,contacts:[launch,prepare,catchCue],flight:null,releaseSerial:1});
  const copy = structuredClone(end);
  view.ingest(end,1170);
  assert.equal(view.time,1.24,'official match clock is current');
  near(view.presentationTime,1);
  assert.equal(view.drain().length,0);
  // Duplicate polls do not restart the interpolation or repeat events.
  view.ingest(end,1190);
  const wall = t => 1170+(t-1)/.24*230;
  view.sample(wall(1.04),1/60);
  near(view.visualBall.x,10.1);
  assert.equal(view.visualBall.spin,undefined,'falso does not begin before impact');
  assert.equal(view.visualBall.vx,0);
  near(view.players[0].actionElapsed,.22);
  assert.deepEqual(ids(view.presentation.contacts),[]);

  view.sample(wall(1.08),1/60);
  near(view.visualBall.x,launch.ball.x);
  near(view.visualBall.vx,20);
  near(view.players[0].actionElapsed,launch.actor.actionElapsed);
  assert.deepEqual(ids(view.presentation.contacts),[1]);
  assert.equal(view.drain()[0].type,'shot');
  assert.equal(view.drain().length,0);

  view.sample(wall(1.17),1/60);
  near(view.presentationTime,1.14);
  near(view.visualBall.x,prepare.ball.x);
  near(view.players[1].actionElapsed,0);
  view.sample(wall(1.17),1/60);
  assert.equal(view.players[1].action,'catch-ready');
  near(view.players[1].actionElapsed,.03);
  assert.deepEqual(ids(view.presentation.contacts),[1,2]);
  assert.equal(view.drain().length,0);

  view.sample(wall(1.20),1/60);
  near(view.visualBall.x,catchCue.ball.x);
  near(view.visualBall.vx,0);
  assert.equal(view.players[1].action,'catch');
  near(view.players[1].actionElapsed,0);
  assert.deepEqual(ids(view.presentation.contacts),[1,2,3]);
  assert.equal(view.drain()[0].type,'save');
  assert.equal(view.drain().length,0);
  assert.deepEqual(end,copy,'presentation does not change a received snapshot');
});

test('an arrival during an existing blend preserves the sampled clock and does not replay contacts',()=>{
  const view = newView();
  const attacker = player(1,'ATT',0,'idle'), keeper = player(21,'GK',50,'idle');
  const first = packet(2,ball(0),attacker,keeper);
  view.ingest(first,1000);
  const release = cue(1,2.1,'release',attacker,ball(2,20)),events=[{type:'shot',time:2.1}];
  const next = packet(2.2,ball(4,20),attacker,keeper,{contacts:[release],events,eventSerial:1});
  view.ingest(next,1200);
  view.sample(1250,1/60);
  const shown = view.presentationTime;
  const x = view.visualBall.x;
  view.ingest(packet(2.34,ball(6.8,20),attacker,keeper,{contacts:[release],events,eventSerial:1}),1250);
  near(view.presentationTime,shown);
  near(view.visualBall.x,x);
  // A request response timestamp can be slightly ahead of a RAF timestamp.
  view.sample(1245,1/60);
  near(view.presentationTime,shown);
  view.sample(1400,1/60);
  near(view.presentationTime,2.1);
  assert.equal(view.drain().length,1);
  view.sample(1415,1/60);
  assert(view.presentationTime>2.1);
  view.ingest(next,1420);
  assert(view.presentationTime>2.1,'stale response cannot rewind presentation');
  assert.equal(view.drain().length,0);
});

test('ingest keeps unread exact contacts for even a sparse render and groups equal-time cues',()=>{
  const view = newView();
  const attacker = player(1,'ATT',8,'shoot',.01,.19), keeper = player(21,'GK',24,'idle');
  view.ingest(packet(9,ball(10),attacker,keeper),1000);
  const launch = cue(1,9.05,'release',player(1,'ATT',9,'shoot',.06,.14),ball(10.3,20,.2));
  const prepare = cue(2,9.05,'keeper-prepare',player(21,'GK',24,'dive',0,1),launch.ball);
  const save = cue(3,9.14,'keeper-contact',player(21,'GK',23.8,'dive',.09,.91),ball(12.1,-4));
  const events = [{type:'shot',time:9.05},{type:'save',time:9.14}];
  const notes = {events,eventSerial:2,contacts:[launch,prepare,save]};
  const polled = packet(9.20,ball(11.8,-4),attacker,keeper,notes);
  view.ingest(polled,1200);
  view.ingest(polled,1390); // Duplicate arrives after both contact timestamps.
  view.ingest(packet(9.36,ball(0),attacker,keeper,{...notes,restart:{id:3,kind:'kickoff'}}),1410);
  near(view.presentationTime,9);
  assert.equal(view.time,9.36);
  assert.equal(view.drain().length,0);

  view.sample(1690,1/10);
  near(view.presentationTime,9.05);
  near(view.visualBall.x,10.3);
  near(view.visualBall.vx,20);
  near(view.players[0].actionElapsed,.06);
  assert.equal(view.players[1].action,'dive');
  assert.deepEqual(ids(view.presentation.contacts),[1,2]);
  assert.equal(view.drain()[0].type,'shot');
  view.sample(1692,0);
  near(view.presentationTime,9.05);
  assert.equal(view.drain().length,0);

  view.sample(1830,1/10);
  near(view.presentationTime,9.14);
  near(view.visualBall.x,12.1);
  near(view.visualBall.vx,-4);
  near(view.players[1].actionElapsed,.09);
  assert.equal(view.drain()[0].type,'save');
  view.sample(1970,1/10);
  near(view.presentationTime,9.36);
  near(view.visualBall.x,0);
  assert.equal(view.drain().length,0);
});

test('a stopped manager prompt draws the current pose and its same-tick answer starts the kick preparation',()=>{
  const rendered = new Map();
  const view = newView({update(actor,dt){
    if (dt>0 || !rendered.has(actor.id)) rendered.set(actor.id,{x:actor.x,action:actor.action});
  }});
  const keeper = player(21,'GK',14,'idle');
  view.ingest(packet(3,ball(10),player(1,'ATT',9,'idle'),keeper),1000);
  const pendingManagerKick = {id:1,team:0};
  view.ingest(packet(3.18,ball(11),player(1,'ATT',10,'idle'),keeper,{pendingManagerKick}),1180);
  near(view.presentationTime,3.18);
  assert.equal(view.pendingManagerKick,pendingManagerKick);
  assert.deepEqual(rendered.get(1),{x:10,action:'idle'});
  view.sample(1400,0);
  assert.deepEqual(rendered.get(1),{x:10,action:'idle'});

  view.ingest(packet(3.18,ball(11),player(1,'ATT',10,'shoot',0,.45),keeper,
    {pendingManagerKick:null,kick:{kind:'shot',playerId:1}}),1410);
  near(view.presentationTime,3.18);
  assert.equal(view.pendingManagerKick,null);
  assert.equal(view.players[0].action,'shoot');
  assert.deepEqual(rendered.get(1),{x:10,action:'shoot'});
});

test('second-half side switch draws actors at the current end of the pitch',()=>{
  const view = newView();
  const shooter = player(1,'ATT',-35,'idle'), keeper = player(21,'GK',49,'idle');
  view.ingest(packet(4,ball(35),shooter,keeper,{period:1}),1000);
  view.ingest(packet(4.18,ball(0),player(1,'ATT',35,'idle'),player(21,'GK',-49,'idle'),
    {period:2,direction:[-1,1],restart:{id:2,kind:'kickoff'}}),1180);
  near(view.presentationTime,4.18);
  near(view.players[0].x,35);
  near(view.players[1].x,-49);
  near(view.visualBall.x,0);
  assert.equal(view.direction(0),-1);
});

test('worker wire projection retains independent contact data after the ball changes',()=>{
  const passer = player(1,'ATT',1,'pass',.2,.12);
  const keeper = player(21,'GK',14,'idle');
  const match = {
    time:0,ball:ball(1),players:[passer,keeper],flight:null,owner:passer,events:[],
    t:[],clockState(){return {}},direction(team){return team?-1:1},referee:{},done:false
  };
  const observer = ContactEvents.create();
  observer.observe(match);
  match.time=1/60;
  match.owner=null;
  match.flight={id:1,from:passer,target:null,kind:'shot',age:0};
  match.ball=ball(2,20,.4);
  observer.observe(match);
  const launch=snapshot(match,observer);
  assert.equal(launch.flight.age,0);
  assert.equal(launch.contacts[0].tick,1);
  assert.equal(launch.contacts[0].time,match.time);
  assert.equal(launch.contacts[0].ball.x,2);
  match.ball.x=5;
  match.time=2/60;
  match.flight.age=1/60;
  keeper.action='catch-ready';
  observer.observe(match);
  match.time=3/60;
  match.owner=keeper;
  match.flight=null;
  keeper.holdingBall=true;
  keeper.action='catch';
  match.events.push({type:'save',playerId:21,time:match.time});
  observer.observe(match);
  const end=snapshot(match,observer);
  assert.equal(end.flight,null);
  assert.deepEqual(end.contacts.map(c=>c.kind),['release','keeper-prepare','keeper-contact']);
  assert.equal(end.contacts[0].ball.x,2);
  assert.equal(end.contacts[2].flightId,1);
  assert.equal(end.contacts[2].actor.action,'catch');
  observer.observe(match);
  assert.equal(observer.recent().length,3,'cached polls and reads create no new motion event');
});
