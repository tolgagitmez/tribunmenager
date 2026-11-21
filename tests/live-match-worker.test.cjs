'use strict';

const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const path = require('node:path');
const readline = require('node:readline');
const {test} = require('node:test');

const workerPath = path.resolve(__dirname, '../live-match-worker.cjs');
const tactics = {
  playstyle: 'wing', crossing: 'early', tempo: 90, mentality: 'attacking',
  aggression: 80, press: 76, passing: 'direct'
};
const config = {
  seed: 6, tactics, awayTactics: tactics,
  rules: {periodSeconds: 45, halftimeSeconds: 0, addedTime: false}
};

function worker() {
  const child = spawn(process.execPath, [workerPath], {stdio: ['pipe', 'pipe', 'pipe']});
  const closed = once(child, 'close');
  const lines = readline.createInterface({input: child.stdout})[Symbol.asyncIterator]();
  let stderr = '';
  child.stderr.setEncoding('utf8').on('data', chunk => { stderr += chunk; });
  return {
    async request(message) {
      child.stdin.write(JSON.stringify(message) + '\n');
      const line = await lines.next();
      assert.equal(line.done, false, `worker closed before answering: ${stderr}`);
      return JSON.parse(line.value);
    },
    async close() {
      child.stdin.end();
      const [code] = await closed;
      assert.equal(code, 0, stderr);
    }
  };
}

async function accepted(engine, operation) {
  const reply = await engine.request(operation);
  assert.equal(reply.ok, true, reply.error);
  return reply;
}

async function reachOffer(engine, teams, allowedSteps) {
  let advanced = 0;
  while (advanced < allowedSteps) {
    const reply = await accepted(engine, {op: 'advance', steps: Math.min(120, allowedSteps - advanced), teams});
    advanced += reply.steps;
    if (reply.state.pendingManagerKick) return {advanced, state: reply.state};
    assert(reply.steps > 0, 'match must advance to the natural kick window');
  }
  assert.fail('seeded match did not reach its next manager kick');
}

async function advanceWithoutOffer(engine, teams, steps) {
  let state;
  for (let advanced = 0; advanced < steps;) {
    const count = Math.min(120, steps - advanced);
    const reply = await accepted(engine, {op: 'advance', steps: count, teams});
    state = reply.state;
    assert.equal(reply.steps, count);
    assert.equal(state.pendingManagerKick, null);
    advanced += reply.steps;
  }
  return state;
}

test('one worker processes both sides of a seeded match and an absent team takes the same AI kick', {timeout: 80000}, async () => {
  const shared = worker();
  const absent = worker();
  try {
    const [start, alternate] = await Promise.all([shared, absent].map(engine =>
      accepted(engine, {op: 'init', config})
    ));
    assert.deepEqual(start.state, alternate.state);
    assert.equal((await shared.request({op: 'advance', steps: 1, teams: [2]})).ok, false);
    assert.equal((await shared.request({op: 'advance', steps: 121, teams: [0, 1]})).ok, false);

    // Both opportunities arise from play with the ordinary roster and match
    // engine, including foul decisions and the normal positioning of bodies.
    const home = await reachOffer(shared, [0, 1], 2400);
    const homeOffer = home.state.pendingManagerKick;
    assert.equal(homeOffer.team, 0);
    assert.equal(homeOffer.kind, 'free-kick');
    assert.equal(home.state.period, 1);
    assert(home.state.events.some(event => event.type === 'foul' && event.team === 0));

    // A different presence mask in a subsequent advance does not mutate an
    // existing decision. The league server delegates it with a null input.
    const paused = await accepted(shared, {op: 'advance', steps: 120, teams: [1]});
    assert.equal(paused.steps, 0);
    assert.deepEqual(paused.state, home.state);
    const delegated = await accepted(shared, {op: 'kick', id: homeOffer.id, input: null});
    assert.equal(delegated.accepted, true);
    assert.equal(delegated.state.pendingManagerKick, null);
    assert.equal(delegated.state.time, home.state.time);

    // A bot or absent side excluded from the mask uses the AI immediately.
    // At the same tick its physical state matches the delegated attempt.
    const bot = await advanceWithoutOffer(absent, [1], home.advanced);
    assert.deepEqual(bot.ball, delegated.state.ball);
    assert.deepEqual(bot.kick, delegated.state.kick);
    assert.deepEqual(bot.score, delegated.state.score);
    assert.equal(bot.time, delegated.state.time);

    const away = await reachOffer(shared, [0, 1], 2700);
    const awayOffer = away.state.pendingManagerKick;
    assert.equal(awayOffer.team, 1);
    assert.equal(awayOffer.kind, 'free-kick');
    assert.equal(away.state.period, 2);
    assert(awayOffer.id > homeOffer.id);
    const stale = await accepted(shared, {op: 'kick', id: homeOffer.id, input: null});
    assert.equal(stale.accepted, false);
    assert.deepEqual(stale.state, away.state);

    const input = {angle: awayOffer.angle + .08, power: .73, contactX: .45, contactY: -.35};
    const invalid = await accepted(shared, {op: 'kick', id: awayOffer.id, input: {...input, power: 2}});
    assert.equal(invalid.accepted, false);
    assert.deepEqual(invalid.state, away.state);
    const manual = await accepted(shared, {op: 'kick', id: awayOffer.id, input});
    assert.equal(manual.accepted, true);
    assert.equal(manual.state.pendingManagerKick, null);
    assert.equal(manual.state.releaseSerial, away.state.releaseSerial, 'the accepted kick still needs foot contact');
    assert.deepEqual(manual.state.ball, away.state.ball);
    const retry = await accepted(shared, {op: 'kick', id: awayOffer.id, input});
    assert.equal(retry.accepted, false);

    let flight = manual.state;
    for (let i = 0; i < 360 && flight.releaseSerial === away.state.releaseSerial; i++) {
      const tick = await accepted(shared, {op: 'advance', steps: 1, teams: [0, 1]});
      assert.equal(tick.steps, 1);
      flight = tick.state;
    }
    assert.equal(flight.releaseSerial, away.state.releaseSerial + 1);
    assert.equal(flight.flight?.fromId, awayOffer.playerId);
    assert(Math.hypot(flight.ball.vx, flight.ball.vz) > 10);
    assert(flight.ball.vy > 1);
    assert(flight.ball.spin < 0, 'the real trajectory carries the chosen sidespin');
    const heading = Math.atan2(flight.ball.vz, flight.ball.vx) - input.angle;
    assert(Math.abs(Math.atan2(Math.sin(heading), Math.cos(heading))) < .35);
    assert(flight.eventSerial > away.state.eventSerial);
    assert(flight.events.some(event => ['cross', 'shot'].includes(event.type) &&
      event.team === 1 && event.playerId === awayOffer.playerId && event.time >= away.state.time));
  } finally {
    await Promise.all([shared.close(), absent.close()]);
  }
});
