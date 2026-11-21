'use strict';

const assert = require('node:assert/strict');
const {test} = require('node:test');
const {Match, BallPhysics} = require('../football-sim');
const Club = require('../club-data');
const Rig = require('../humanoid-rig');

const dt = 1 / 60;
const skillFor = {'free-kick': 'freeKick', corner: 'corner', penalty: 'penalty', cross: 'crossing'};
const turn = angle => Math.atan2(Math.sin(angle), Math.cos(angle));

function setup(kind, {team = 0, period = 1, rating = 85, managerKicks = true, rig = null} = {}) {
  const index = kind === 'cross' ? 0 : 1;
  const players = Club.createRoster();
  const starters = Club.starters;
  players[starters[index]] = {
    ...players[starters[index]], [skillFor[kind]]: rating, preferredFoot: 'both'
  };
  const match = new Match({
    seed: 21, players, starters, managerKicks,
    tactics: {playstyle: 'wing'}, awayTactics: {playstyle: 'wing'},
    rules: {minPlayers: 1, periodSeconds: 160}
  }, rig);
  if (period === 2) {
    match.matchClock.phase = 'halftime';
    assert(match.resumeHalf());
  }
  const side = match.direction(team);
  const taker = match.players[team * 11 + index];
  if (kind === 'cross') {
    match.restart = null;
    match.planClock = 1000;
    match.targets.clear();
    for (const player of match.players) player.active = false;
    const receiver = match.players[team * 11 + 1];
    const keeper = match.players[(1 - team) * 11 + 10];
    for (const [player, x, z] of [[taker, 29, -23], [receiver, 41, 0], [keeper, 49, 0]]) {
      Object.assign(player, {
        active: true, x: side * x, z: side * z, vx: 0, vz: 0, speed: 0,
        touchClock: 0, tackleClock: 100, receiveClock: 0, decision: player === taker ? 0 : 100
      });
    }
    taker.face = Math.atan2(receiver.z - taker.z, receiver.x - taker.x);
    const [x, y, z] = match.contactPoint(taker);
    match.ball = {x, y, z, vx: 0, vy: 0, vz: 0};
    match.owner = match.lastTouch = taker;
    match.lastTeam = team;
    assert.equal(match.choose(taker).kind, 'cross', 'fixture produces a real open-play crossing decision');
  } else {
    const spot = kind === 'corner' ? {x: side * 51.8, z: -33.8} : {x: side * 30, z: side * 3};
    match.setRestart(kind, team, spot, taker);
  }
  return {match, taker, side};
}

function waitFor(match, condition, description, limit = 36) {
  for (let i = 0; i < limit / dt && !condition(); i++) {
    match.step(dt);
    if (match.motion) for (const player of match.players) {
      if (player.active) match.motion.update(player, dt);
    }
    if (match.pendingManagerKick && !condition()) break;
  }
  assert(condition(), description);
}

function prompt(fixture, kind) {
  const {match, taker, side} = fixture;
  waitFor(match, () => match.pendingManagerKick, `${kind} must offer manager control`);
  const offer = match.pendingManagerKick;
  assert.equal(offer.kind, kind);
  assert.equal(offer.playerId, taker.id);
  assert.equal(offer.team, taker.team);
  assert.equal(offer.direction, side);
  assert(Object.isFrozen(offer) && Object.isFrozen(offer.origin));
  assert.deepEqual(offer.origin, {x: match.ball.x, z: match.ball.z});
  return offer;
}

function release(fixture, kind, offer, settings = {}) {
  const {match, taker, side} = fixture;
  const angle = kind === 'free-kick'
    ? Math.atan2(-offer.origin.z, 52 * side - offer.origin.x) : offer.angle;
  const input = {angle, power: .72, contactX: 0, contactY: 0, ...settings};
  assert(match.resolveManagerKick(offer.id, input));
  assert.equal(match.pendingManagerKick, null);
  assert.equal(match.releaseSerial, 0, 'confirm must not bypass foot preparation');
  waitFor(match, () => match.releaseSerial === 1, `${kind} must physically release`, 8);
  assert.equal(match.flight?.from, taker);
  assert.equal(match.flight?.managerKick?.kind, kind);
  assert(Math.hypot(match.ball.vx, match.ball.vz) > 3);
  assert(Math.hypot(taker.x - match.ball.x, taker.z - match.ball.z) < 1.1, 'launch must happen at the boot');
  if (kind !== 'cross') {
    assert.equal(match.flight.restartKind, kind);
    assert.deepEqual({x: match.ball.x, z: match.ball.z}, offer.origin, 'placed ball remains on the mark until release');
  }
  return {input, ball: {...match.ball}, flight: match.flight};
}

for (const kind of ['cross', 'free-kick', 'corner', 'penalty']) {
  test(`${kind} uses its specialist rating to change real launch accuracy at equal overall`, () => {
    const weak = setup(kind, {rating: 20});
    const strong = setup(kind, {rating: 94});
    assert.equal(weak.taker.skill, strong.taker.skill);
    const weakOffer = prompt(weak, kind);
    const strongOffer = prompt(strong, kind);
    assert(strongOffer.skill > weakOffer.skill + 50);
    const a = release(weak, kind, weakOffer);
    const b = release(strong, kind, strongOffer);
    const miss = ({ball, input}) => Math.abs(turn(Math.atan2(ball.vz, ball.vx) - input.angle));
    assert(miss(b) < miss(a) * .8, 'the stronger specialist must strike closer to the selected heading');
    if (kind === 'corner') {
      assert.deepEqual(b.flight.offsidePlayers, []);
      assert.equal(strong.match.offsidePhase, null, 'a corner is exempt from receiving directly offside');
    }
    if (kind === 'penalty') {
      assert.equal(b.flight.penalty, true);
      assert.equal(strong.match.penaltyAttempt.state, 'released');
    }
  });
}

test('the pending opportunity freezes the clock and geometry, and rejects invalid and stale controls', () => {
  const fixture = setup('penalty');
  const {match} = fixture;
  const offer = prompt(fixture, 'penalty');
  const state = () => structuredClone({
    time: match.time, clock: match.clockState(), ball: match.ball, seed: match.seed,
    players: match.players, events: match.events, release: match.releaseSerial
  });
  const before = state();
  match.advance(4);
  assert.deepEqual(state(), before);
  for (const input of [
    {angle: NaN, power: .4, contactX: 0, contactY: 0},
    {angle: offer.angle, power: 1.3, contactX: 0, contactY: 0},
    {angle: offer.angle, power: .4, contactX: 1, contactY: 1},
    {angle: offer.angle + Math.PI, power: .4, contactX: 0, contactY: 0}
  ]) assert.equal(match.resolveManagerKick(offer.id, input), false);
  assert.equal(match.pendingManagerKick, offer);
  assert.equal(match.resolveManagerKick(offer.id + 1), false);
  match.setRestart('throw', 0, {x: 16, z: 34});
  assert.equal(match.resolveManagerKick(offer.id), false);
  assert.equal(match.pendingManagerKick, null);
});

test('direction, power and vertical contact change a second-half penalty with the normal animation rig', () => {
  const free = setup('penalty', {period: 2, rig: Rig});
  const curved = setup('penalty', {period: 2, rig: Rig});
  const a = prompt(free, 'penalty');
  const b = prompt(curved, 'penalty');
  assert.equal(a.origin.x, -41);
  const left = release(free, 'penalty', a, {angle: a.angle - .12, power: .45, contactY: .25});
  const right = release(curved, 'penalty', b, {angle: b.angle + .11, power: .88, contactX: .55, contactY: -.35});
  assert(left.ball.vx < 0 && right.ball.vx < 0);
  assert(Math.hypot(right.ball.vx, right.ball.vz) > Math.hypot(left.ball.vx, left.ball.vz) + 5);
  assert(right.ball.vy > left.ball.vy + 1);
  assert(turn(Math.atan2(right.ball.vz, right.ball.vx) - Math.atan2(left.ball.vz, left.ball.vx)) > .12);
  const curvedPrediction = BallPhysics.predict(right.ball, .3);
  const straightPrediction = BallPhysics.predict({...right.ball, spin: 0}, .3);
  assert(Math.hypot(curvedPrediction.x - straightPrediction.x, curvedPrediction.z - straightPrediction.z) > .03);
});

test('delegating an open-play cross matches the ordinary AI result without repeating the opportunity', () => {
  const controlled = setup('cross');
  const automatic = setup('cross', {managerKicks: false});
  const offer = prompt(controlled, 'cross');
  assert(controlled.match.resolveManagerKick(offer.id));
  assert.equal(controlled.match.resolveManagerKick(offer.id), false);
  for (const {match} of [controlled, automatic]) {
    waitFor(match, () => match.releaseSerial === 1, 'AI cross releases normally', 3);
    assert.equal(match.flight?.kind, 'cross');
    assert.equal(match.pendingManagerKick, null);
  }
  assert.deepEqual(controlled.match.ball, automatic.match.ball);
  assert.equal(controlled.match.seed, automatic.match.seed);
  assert.equal(controlled.match.time, automatic.match.time);
});

test('opponent penalty stays automatic even when the manager feature is enabled', () => {
  const {match, taker} = setup('penalty', {team: 1});
  waitFor(match, () => match.releaseSerial === 1, 'opponent completes the penalty without interruption');
  assert.equal(match.pendingManagerKick, null);
  assert.equal(match.flight?.from, taker);
  assert(match.flight.penalty);
  assert.equal(match.flight.managerKick, undefined);
});

test('manual indirect free kick still requires a touch before entering the goal', () => {
  const fixture = setup('free-kick', {rating: 94});
  const {match} = fixture;
  match.restart.indirect = true;
  const offer = prompt(fixture, 'free-kick');
  assert.equal(offer.indirect, true);
  match.random = () => .5; // Isolate the rule with a centered strike.
  const {flight} = release(fixture, 'free-kick', offer, {contactY: .99});
  assert.equal(flight.restartIndirect, true);
  // Clear the trajectory after the actual boot release to isolate a direct
  // crossing of the goal line without a keeper or outfield touch.
  for (const player of match.players) player.z = player.id % 2 ? -25 : 25;
  for (let i = 0; i < 120 && !match.restart && !match.goalPause; i++) match.ballStep(dt);
  assert.deepEqual(match.score, [0, 0]);
  assert.equal(match.restart?.kind, 'goal-kick');
  assert(match.events.some(event => event.type === 'restart-goal-disallowed'));
});

test('when the away team is managed, its penalty uses the corresponding goal and taker', () => {
  const fixture = setup('penalty', {team: 1});
  const {match} = fixture;
  match.managerKickTeams = new Set([1]);
  const offer = prompt(fixture, 'penalty');
  assert.equal(offer.origin.x, -41);
  const {ball, flight} = release(fixture, 'penalty', offer);
  assert(ball.vx < 0);
  assert.equal(flight.penalty, true);
  assert.deepEqual(match.shots, [0, 1]);
});
