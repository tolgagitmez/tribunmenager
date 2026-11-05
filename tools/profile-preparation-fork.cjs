#!/usr/bin/env node
'use strict';
// Find a natural baseline decision; branch the same complete object graph/RNG.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..'), Tactics = require(path.join(root, 'tactics.js'));
const option = (name, fallback) => { const i = process.argv.indexOf(name); return i < 0 ? fallback : process.argv[i + 1]; };
const sha = text => crypto.createHash('sha256').update(text).digest('hex');
const baselineFile = option('--baseline-file', null), baselineRef = option('--baseline-ref', 'HEAD');
const sources = {
  baseline: baselineFile ? fs.readFileSync(path.resolve(baselineFile), 'utf8') : execFileSync('git', ['show', `${baselineRef}:football-sim.js`], { cwd: root, encoding: 'utf8' }),
  current: fs.readFileSync(path.join(root, 'football-sim.js'), 'utf8')
};
function load(source, label) {
  const instance = new Module(path.join(root, label), module);
  instance.filename = path.join(root, label); instance.paths = module.paths;
  instance._compile(source, instance.filename); return instance.exports.Match;
}
const versions = { baseline: load(sources.baseline, 'fork-baseline.js'), current: load(sources.current, 'fork-current.js') };
const mode = option('--mode', 'divergent'), seconds = Number(option('--seconds', '5400'));
const followSeconds = Number(option('--follow-seconds', '4'));
assert(['safe', 'divergent', 'controlled'].includes(mode), '--mode must be safe, divergent or controlled');
assert(seconds > 0 && seconds <= 5400 && Number.isFinite(seconds));
assert(followSeconds > 0 && followSeconds <= 30 && Number.isFinite(followSeconds));
const preset = id => { const p = Tactics.presets.find(p => p.id === id); assert(p, `Unknown plan ${id}`); return p.tactics; };
const cfg = {
  seed: Number(option('--seed', '21')), starters: [8, 9, 10, 7, 5, 6, 4, 2, 3, 1, 0],
  formation: option('--formation', '4-3-3'), matchMinutes: 90, tactics: preset(option('--home', 'balanced'))
};
assert(Number.isFinite(cfg.seed));
const away = option('--away', 'engine-default');
if (away !== 'engine-default') cfg.awayTactics = preset(away);
const strength = option('--strength', null);
if (strength !== null) {
  const n = Number(strength); assert(Number.isFinite(n) && n >= 40 && n <= 99);
  cfg.players = Array.from({ length: 11 }, (_, id) => ({ id, name: `Synthetic ${id}`, rating: n, passing: n, shooting: n, tackling: n, vision: n, composure: n, dribbling: n, pace: n, agility: n, fitness: 92, preferredFoot: id % 2 ? 'right' : 'left', weakFoot: n - 12 }));
}
const plain = game => Object.fromEntries(Object.entries(game).filter(([, value]) => typeof value !== 'function'));
const clone = (state, Constructor) => Object.assign(Object.create(Constructor.prototype), structuredClone(state));
function physical(game) {
  return { seed: game.seed, ball: { ...game.ball }, players: game.players.map(p => ({ id: p.id, x: p.x, z: p.z, vx: p.vx, vz: p.vz, face: p.face })) };
}
const baseline = new versions.baseline(cfg), review = baseline.reviewPass;
let snapshot = null, alternatives = 0;
let controlled = null;
if (mode === 'controlled') {
  const side = Number(option('--side', '1')), defenderX = Number(option('--defender-x', '2')), defenderZ = Number(option('--defender-z', '0'));
  const blocker = process.argv.includes('--blocker'), gap = Math.hypot(defenderX, defenderZ);
  assert(side === 1 || side === -1); assert([defenderX, defenderZ].every(Number.isFinite) && gap > 0 && gap <= 25);
  controlled = { side, defenderX, defenderZ, blocker, description: 'Manually sustained initial lane threat; all following motion, preparation, touches and tackles are normal engine steps. Four active players (six with --blocker, including a goalkeeper to establish the offside line), fixed initial commands; no forced duel/RNG result. Normal planning may revise those commands after review.' };
  baseline.restart = null; baseline.kick = null; baseline.phase = 'carry'; baseline.time = 10; baseline.planClock = 100;
  baseline.players.forEach(p => { p.active = false; });
  const [p, q, original, d] = [baseline.players[3], baseline.players[4], baseline.players[5], baseline.players[14]];
  for (const actor of [p, q, original, d]) Object.assign(actor, { active: true, vx: 0, vz: 0, speed: 0, face: side === 1 ? 0 : Math.PI, action: 'idle', actionClock: 0, duelRecovery: 0, tackleClock: 0, touchClock: 0, receiveClock: 0 });
  Object.assign(p, { x: 0, z: 0, kickFoot: 1, preferredFoot: 1 });
  Object.assign(q, { x: 3 * side, z: 12 * side }); Object.assign(original, { x: 12 * side, z: 0 });
  Object.assign(d, { x: defenderX * side, z: defenderZ * side, vx: -5 * defenderX / gap * side, vz: -5 * defenderZ / gap * side, speed: 5, face: Math.atan2(-defenderZ * side, -defenderX * side) });
  baseline.owner = p; baseline.lastTouch = p; baseline.ball = { x: .88 * side, y: .11, z: .18 * side, vx: 0, vy: 0, vz: 0 };
  baseline.targets = new Map([[p, { x: 0, z: 0, pace: 1, state: 'dribble' }], [q, { x: q.x, z: q.z, pace: 1, state: 'support' }], [original, { x: original.x, z: original.z, pace: 1, state: 'support' }], [d, { x: -30 * side, z: 0, pace: 1, state: 'press' }]]);
  if (blocker) {
    const extra = baseline.players[15];
    Object.assign(extra, { active: true, x: 6 * side, z: 0, vx: 0, vz: 0, speed: 0, face: side === 1 ? Math.PI : 0, action: 'idle', actionClock: 0, duelRecovery: 0, tackleClock: 0, touchClock: 0, receiveClock: 0 });
    baseline.targets.set(extra, { x: extra.x, z: extra.z, pace: 0, state: 'cover' });
    const keeper = baseline.players[21];
    Object.assign(keeper, { active: true, x: 49 * side, z: 0, vx: 0, vz: 0, speed: 0, face: side === 1 ? Math.PI : 0, action: 'idle', actionClock: 0, duelRecovery: 0, tackleClock: 0, touchClock: 0, receiveClock: 0 });
    baseline.targets.set(keeper, { x: keeper.x, z: keeper.z, pace: 0, state: 'goalkeeper' });
  }
  baseline.startKick(p, 'pass', original, { x: original.x, z: original.z });
  baseline.kick.duration = .6; baseline.kick.clock = .15;
  baseline.kick.passRead = { base: 0, next: 0, badSince: 9, motionAt: 10, motion: new Map() };
  snapshot = structuredClone(plain(baseline));
} else baseline.reviewPass = function (kick) {
  const read = kick.passRead, p = kick.p; let prior = null;
  if (read && this.kick === kick && kick.duration - kick.clock > .12 && kick.clock + 1e-9 >= read.next) {
    const speed = this.passSpeed('pass', Math.hypot(this.ball.x - kick.point.x, this.ball.z - kick.point.z), this.t[p.team]);
    const risk = this.laneRisk(p, kick.point, speed, 'pass');
    if (risk >= .75 && risk >= read.base + .30 && read.badSince !== null && this.time - read.badSince >= .10) prior = structuredClone(plain(this));
  }
  const redirects = this.telemetry.passRedirects || 0, result = review.call(this, kick);
  if (prior && (this.telemetry.passRedirects || 0) > redirects) {
    alternatives++;
    const current = clone(prior, versions.current); current.reviewPass(current.kick);
    const changed = current.kick?.target?.id !== this.kick?.target?.id;
    if (mode === 'safe' && !changed || mode === 'divergent' && changed) snapshot = prior;
  }
  return result;
};
for (let i = 0; i < Math.round(seconds * 60) && !baseline.done && !snapshot; i++) baseline.step();
const report = {
  generatedAt: new Date().toISOString(), baselineRef, mode, cfg, searchSeconds: baseline.time,
  baselineAlternativeDecisions: alternatives, found: !!snapshot, controlled,
  sources: { baseline: sha(sources.baseline), current: sha(sources.current), tactics: sha(fs.readFileSync(path.join(root, 'tactics.js'))), observer: sha(fs.readFileSync(__filename)) },
  limitations: 'This is a search in one synthetic match, not a pass success rate. Observation invokes each original action once; no future opponent targets are passed into the forecast. A missing divergent decision is reported as not found, not success.',
  branches: {}
};
if (snapshot) {
  report.time = snapshot.time;
  const team = snapshot.kick.p.team;
  for (const [name, Constructor] of Object.entries(versions)) {
    const game = clone(snapshot, Constructor), before = physical(game);
    const reconsidered = game.reviewPass(game.kick), after = physical(game);
    assert.deepEqual(after, before, `${name} review changed physical state or RNG`);
    const selected = game.kick?.target?.id ?? null;
    const actions = [], ownership = [], interventions = []; let lastOwner = null;
    const tackle = game.doTackle;
    game.doTackle = function (defender, carrier) {
      const duels = this.telemetry.duels, result = tackle.call(this, defender, carrier);
      if (this.telemetry.duels > duels) interventions.push({ time: this.time, defenderId: defender.id, carrierId: carrier.id, carrierRetainsIntention: this.owner === carrier, kickContinues: !!this.kick });
      return result;
    };
    const release = game.release;
    game.release = function () {
      const kick = this.kick, count = this.passes[kick.p.team] + this.shots[kick.p.team], result = release.call(this);
      if (this.passes[kick.p.team] + this.shots[kick.p.team] > count) actions.push({ time: this.time, kind: kick.kind, from: kick.p.id, target: kick.target?.id ?? null });
      return result;
    };
    let maxStep = 0, previous = game.players.map(p => ({ x: p.x, z: p.z }));
    const preparation = game.lastPassPreparation ? structuredClone(game.lastPassPreparation) : null;
    for (let i = 0; i < Math.round(followSeconds * 60) && !game.done; i++) {
      game.step();
      for (const [j, p] of game.players.entries()) {
        assert([p.x, p.z, p.vx, p.vz, p.face].every(Number.isFinite));
        maxStep = Math.max(maxStep, Math.hypot(p.x - previous[j].x, p.z - previous[j].z));
        previous[j] = { x: p.x, z: p.z };
      }
      assert(Object.values(game.ball).every(Number.isFinite));
      if (game.owner && game.owner.id !== lastOwner) { ownership.push({ time: game.time, id: game.owner.id, team: game.owner.team }); lastOwner = game.owner.id; }
    }
    assert(maxStep <= .15, `position jump ${maxStep}`);
    report.branches[name] = {
      initialRngState: before.seed, physicalStateUnchangedByReview: true, reconsidered, selectedTarget: selected,
      preparation, actions, interventions, ownership, firstOpponentOwnership: ownership.find(o => o.team !== team) ?? null,
      final: { time: game.time, rngState: game.seed, ownerId: game.owner?.id ?? null, ownerTeam: game.owner?.team ?? null, score: [...game.score], telemetry: JSON.parse(JSON.stringify(game.telemetry)) }, maxStep
    };
  }
}
const output = option('--output', null), json = JSON.stringify(report, null, 2) + '\n';
if (output) { fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true }); fs.writeFileSync(output, json); }
else process.stdout.write(json);
process.stderr.write(`${mode}: ${report.found ? `found at ${report.time.toFixed(3)}s` : `not found by ${report.searchSeconds.toFixed(3)}s`} (${alternatives} baseline redirects)\n`);
