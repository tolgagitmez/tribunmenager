'use strict';

// A controlled tactical sequence on the production Match and Rig. This fixture
// places the teams and nominates movement targets and kick intent. Physical
// contact, first control, shot error, the save and referee logic stay in Match.
const {Match} = require('../football-sim.js');
const Rig = require('../humanoid-rig.js');

const DT = 1 / 60;
const LIMIT = 900;
const turn = (a, b) => Math.atan2(Math.sin(a - b), Math.cos(a - b));
const distance = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
const point = p => ({x: p.x, z: p.z});
const heading = (a, b) => Math.atan2(b.z - a.z, b.x - a.x);

function createWingAttack({
 foot = 'right', pressure = false, onFrame,
 match = new Match({seed: 23, matchMinutes: 5}, Rig)
} = {}) {
 if (!['left', 'right'].includes(foot)) throw Error('Choose the left or right foot');
 const left = foot === 'left';
 const coordinates = (x, z) => ({x, z: left ? z : -z});
 const wing = match.players[left ? 0 : 2];
 const feeder = match.players[3];
 const runner = match.players[1];
 const keeper = match.team(1).find(p => p.role === 'GK');
 const defender = match.field(1)[4];
 const trace = [], releases = [], receives = [];
 let phase = 'sprint', peakWingSpeed = 0, ticks = 0;
 let startBrake = null, readyAt = null, runnerStart = null, save = null, response = null;
 let complete = false;
 const note = (key, detail) => trace.push({key, ...detail});

 const placements = new Map();
 for (const p of match.players) {
  let at;
  if (p === wing) at = coordinates(32, 22);
  else if (p === feeder) at = coordinates(34, 15);
  else if (p === runner) at = coordinates(34.2, 6);
  else if (p === keeper) at = coordinates(50, 0);
  else if (p === defender) at = coordinates(pressure ? 43 : 48, pressure ? 28 : 32);
  else if (p.team === 1) at = coordinates(40 + p.index % 4 * 2, (p.index % 2 ? 1 : -1) * (29 + p.index % 3 * 2));
  else at = coordinates(8 + p.index * 1.1, (p.index % 2 ? 1 : -1) * (7 + p.index * 1.6));
  placements.set(p, at);
  Object.assign(p, at, {
   vx: 0, vz: 0, speed: 0, face: p.team === 1 ? Math.PI : 0, action: 'idle',
   actionClock: 0, actionElapsed: 0, receiveClock: 0, touchClock: 0,
   tackleClock: 0, decision: 40
  });
 }
 for (const p of [wing, runner]) {
  p.preferredFoot = p.kickFoot = left ? 0 : 1;
  p.footPreference = foot;
  p.passing = 76; // Prefer physically receiving and then playing the ball.
 }
 feeder.face = heading(feeder, coordinates(44, 22));
 feeder.touchClock = 40;
 const ball = {
  x: feeder.x + .88 * Math.cos(feeder.face), y: .11,
  z: feeder.z + .88 * Math.sin(feeder.face), vx: 0, vy: 0, vz: 0
 };
 Object.assign(match, {
  restart: null, goalPause: null, kick: null, flight: null, owner: feeder,
  lastTouch: feeder, lastTeam: 0, phase: 'carry', planClock: 0, ball,
  managerKickTeams: new Set()
 });

 const engineRelease = match.release.bind(match);
 const engineAcquire = match.acquire.bind(match);
 const engineChoose = match.choose.bind(match);
 const engineStep = match.step.bind(match);
 const runnerOrigin = point(runner);
 const nominalCutback = coordinates(40, 3);

 match.release = function () {
  const kick = match.kick;
  const boot = match.contactPoint(kick.p, kick.kind);
  const {x, y, z} = match.ball;
  const detail = {
   kind: kick.kind, time: match.time, by: kick.p.id, to: kick.target?.id ?? null,
   foot: kick.p.kickFoot, speed: kick.p.speed, at: {x, y, z},
   bootGap: Math.hypot(boot[0] - x, boot[1] - y, boot[2] - z)
  };
  const result = engineRelease();
  if (match.flight?.from === kick.p && !match.kick) {
   const release = {...detail, velocity: [match.ball.vx, match.ball.vy, match.ball.vz]};
   releases.push(release);
   note(kick.p === feeder ? 'feed' : kick.p === wing ? 'cutback' : 'shot', release);
   if (kick.kind === 'shot') phase = 'shot';
  }
  return result;
 };
 match.acquire = function (p) {
  const flight = match.flight, prep = p.reception;
  const detail = {
   time: match.time, by: p.id, from: flight?.from.id ?? null,
   point: point(p), speed: p.speed, face: p.face,
   incomingBodyAngle: Math.abs(turn(p.face, heading(p, match.ball))),
   insideBodyAngle: Math.abs(turn(p.face, heading(p, nominalCutback))),
   hadPreparation: !!prep,
   pressure: Math.min(...match.field(1 - p.team).map(q => distance(p, q)))
  };
  const taken = engineAcquire(p);
  if (taken && flight?.target === p && (p === wing || p === runner)) {
   const touch = {...detail, mode: p.receiveMode, foot: p.kickFoot};
   receives.push(touch);
   note(p === wing ? 'first-control' : 'third-player-control', touch);
   phase = p === wing ? 'cutback' : 'finish';
  }
  return taken;
 };
 match.choose = function (p) {
  if (p === wing && phase === 'cutback') return {kind: 'cutback', q: runner, point: nominalCutback};
  if (p === runner && phase === 'finish') return {kind: 'shot', point: coordinates(52, 0)};
  return engineChoose(p);
 };
 match.plan = function () {
  const targets = new Map([...placements].map(([p, at]) => [p, {...at, pace: .85, state: 'shape'}]));
  targets.set(wing, {...coordinates(phase === 'sprint' ? 50 : 44, 22), state: 'channel-run', pace: 1.12});
  if (phase === 'cutback' || phase === 'finish' || match.flight?.target === runner) {
   const dest = match.owner === runner ? runner.carryTarget || point(runner) : nominalCutback;
   targets.set(runner, {...dest, state: match.owner === runner ? 'receive' : 'receive-run', pace: 1.12});
  }
  for (const p of [wing, runner]) {
   if (match.flight?.target !== p) continue;
   const meeting = match.interceptPoint(p);
   targets.set(p, {x: meeting.x, z: meeting.z, state: 'receive-run', pace: p === wing ? 1 : 1.12});
   match.prepareReception(p, meeting);
  }
  if (match.owner === wing && !match.kick) {
   const dest = wing.carryTarget || point(wing);
   targets.set(wing, {...dest, state: wing.receiveClock > 0 ? 'receive' : 'dribble', pace: .72});
  }
  targets.set(keeper, {...coordinates(50, 0), state: 'goalkeeper', pace: .85});
  if (pressure) targets.set(defender, {...coordinates(43.5, 25.2), state: 'delay', pace: .84});
  match.targets = targets;
 };

 match.step = function (dt = DT) {
  if (complete) return engineStep(dt);
  if (dt !== DT) throw Error('The wing attack fixture requires the normal 60 Hz step');
  if (phase === 'sprint' && wing.x >= 40) {
   phase = 'brake';
   startBrake = {time: match.time, speed: wing.speed, point: point(wing)};
   note('brake', startBrake);
   match.planClock = 0;
  }
  if (phase === 'brake' && wing.speed < 1.15) {
   phase = 'feed';
   readyAt = match.time;
   feeder.touchClock = 0;
   // The fixture nominates this pass. Release still requires foot contact.
   if (!match.startKick(feeder, 'pass', wing, coordinates(44.7, 22))) {
    throw Error('Controlled feeder could not prepare the pass');
   }
   note('feed-intent', {time: readyAt, speed: wing.speed, point: point(wing)});
  }

  engineStep(dt);
  ticks++;
  for (const p of match.players) if (p.active) Rig.update(p, dt);
  peakWingSpeed = Math.max(peakWingSpeed, wing.speed);
  if (!runnerStart && runner.speed >= .5) {
   runnerStart = {time: match.time, speed: runner.speed, point: point(runner)};
   note('runner-run', runnerStart);
  }
  if (!response && ['catch-ready', 'dive', 'catch'].includes(keeper.action)) {
   response = {time: match.time, action: keeper.action, position: point(keeper)};
   note('keeper-response', response);
  }
  if (!save) {
   const event = match.events.find(e => e.type === 'save' && e.playerId === keeper.id);
   if (event) {
    save = {time: event.time, action: keeper.action, position: {...match.ball}};
    note('keeper-contact', save);
   }
  }
  complete = !!save || match.score[0] > 0 || phase === 'shot' && !match.flight && !!match.restart;
  if (complete) phase = 'outcome';
  onFrame?.(match, phase);
 };

 for (const p of match.players) {
  Rig.reset(p);
  Rig.update(p, 0);
 }
 onFrame?.(match, phase);

 function summary() {
  const onBall = receives.find(touch => touch.by === runner.id);
  return {
   foot, pressure, wing: wing.id, feeder: feeder.id, runner: runner.id, keeper: keeper.id, ticks,
   peakWingSpeed, startBrake, readyAt, runnerStart, receives, releases, response, save,
   runnerAdvance: onBall ? distance(onBall.point, runnerOrigin) : null,
   score: match.score.slice(), shots: match.shots.slice(), onTarget: match.onTarget.slice(),
   events: match.events.map(e => e.type), turnover: match.telemetry.turnovers,
   abortedKicks: match.telemetry.abortedKicks ?? 0
  };
 }
 return {match, trace, summary, get complete() { return complete; }};
}

function runWingAttack(options) {
 const fixture = createWingAttack(options);
 for (let i = 0; i < LIMIT && !fixture.complete && !fixture.match.done; i++) fixture.match.step(DT);
 return {summary: fixture.summary(), trace: fixture.trace, match: fixture.match, complete: fixture.complete};
}
module.exports = {createWingAttack, runWingAttack, DT, LIMIT};

if (require.main === module) {
 const report = ['left', 'right'].flatMap(foot => [false, true].map(pressure => {
  const {summary, complete} = runWingAttack({foot, pressure});
  if (!complete) process.exitCode = 1;
  return {complete, ...summary};
 }));
 console.log(JSON.stringify(report, null, 2));
}
