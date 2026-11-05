#!/usr/bin/env node
'use strict';
// Observe the original engine once per step/action; never inject decisions or RNG.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const Tactics = require(path.join(root, 'tactics.js'));
const digest = text => crypto.createHash('sha256').update(text).digest('hex');
const option = (name, fallback) => {
  const at = process.argv.indexOf(name);
  return at < 0 ? fallback : process.argv[at + 1];
};
const seconds = Number(option('--seconds', '300'));
assert(Number.isFinite(seconds) && seconds > 0 && seconds <= 5400, '--seconds must be in (0, 5400]');
const baselineRef = option('--baseline-ref', 'HEAD');
const baselineFile = option('--baseline-file', null);
const baseline = baselineFile ? fs.readFileSync(path.resolve(baselineFile), 'utf8') : execFileSync('git', ['show', `${baselineRef}:football-sim.js`], { cwd: root, encoding: 'utf8' });
const current = fs.readFileSync(path.join(root, 'football-sim.js'), 'utf8');
function load(source, label) {
  // Separate CommonJS modules retain each version's lexical Match/BallPhysics.
  // Using the normal JS realm avoids expensive cross-context globals per tick.
  const instance = new Module(path.join(root, label), module);
  instance.filename = path.join(root, label);
  instance.paths = module.paths;
  instance._compile(source, instance.filename);
  return instance.exports.Match;
}
function roster(strength) {
  return Array.from({ length: 11 }, (_, id) => ({
    id, name: `Synthetic ${id}`, rating: strength, passing: strength,
    shooting: strength, tackling: strength, vision: strength, composure: strength,
    dribbling: strength, pace: strength, agility: strength, fitness: 92,
    preferredFoot: id % 2 ? 'right' : 'left', weakFoot: strength - 12
  }));
}
const preset = id => Tactics.presets.find(p => p.id === id).tactics;
const scenarios = [
  { id: 'balanced-21', seed: 21, strength: 82, formation: '4-3-3', home: 'balanced', away: 'counter' },
  { id: 'press-opponent-42', seed: 42, strength: 82, formation: '4-3-3', home: 'balanced', away: 'press' },
  { id: 'narrow-21', seed: 21, strength: 82, formation: '4-3-3', home: 'balanced', away: 'counter', change: { width: 'narrow' } },
  { id: 'wide-21', seed: 21, strength: 82, formation: '4-3-3', home: 'balanced', away: 'counter', change: { width: 'wide' } },
  { id: 'short-42', seed: 42, strength: 82, formation: '4-3-3', home: 'balanced', away: 'press', change: { passing: 'short' } },
  { id: 'direct-42', seed: 42, strength: 82, formation: '4-3-3', home: 'balanced', away: 'press', change: { passing: 'direct' } },
  { id: 'weak-442-77', seed: 77, strength: 65, formation: '4-4-2', home: 'possession', away: 'press' },
  { id: 'strong-352-21', seed: 21, strength: 91, formation: '3-5-2', home: 'counter', away: 'wide' }
];
function run(Match, scenario) {
  const cfg = {
    seed: scenario.seed, players: roster(scenario.strength),
    starters: [8, 9, 10, 7, 5, 6, 4, 2, 3, 1, 0],
    formation: scenario.formation, awayFormation: '4-2-3-1',
    matchMinutes: seconds > 300 ? 90 : 5,
    tactics: { ...preset(scenario.home), ...scenario.change }, awayTactics: preset(scenario.away)
  };
  const game = new Match(cfg);
  const pass = [0, 1].map(() => ({ count: 0, distance: 0, forward: 0, backward: 0, lateral: 0, angle: 0 }));
  const shape = [0, 1].map(() => ({ samples: 0, width: 0, length: 0, defenceLine: 0, supportDistance: 0, supportSamples: 0, supportCount: 0, counterSamples: 0, counterpressSamples: 0 }));
  const originalRelease = game.release;
  game.release = function () {
    const k = this.kick;
    const from = { x: this.ball.x, z: this.ball.z };
    const before = this.passes[k.p.team];
    const result = originalRelease.call(this);
    if (this.passes[k.p.team] > before) {
      const dx = (k.point.x - from.x) * (k.p.team === 0 ? 1 : -1), dz = k.point.z - from.z;
      const m = pass[k.p.team];
      m.count++; m.distance += Math.hypot(dx, dz); m.angle += Math.atan2(Math.abs(dz), dx);
      m[dx > 2 ? 'forward' : dx < -2 ? 'backward' : 'lateral']++;
    }
    return result;
  };
  let maxStep = 0, previous = game.players.map(p => ({ x: p.x, z: p.z }));
  let maxBallSpeed = 0, maxPlayerSpeed = 0;
  for (let step = 0; step < Math.round(seconds * 60) && !game.done; step++) {
    game.step();
    for (const [i, p] of game.players.entries()) {
      assert([p.x, p.z, p.vx, p.vz, p.face].every(Number.isFinite), `nonfinite player ${i}`);
      const delta = Math.hypot(p.x - previous[i].x, p.z - previous[i].z);
      maxStep = Math.max(maxStep, delta); previous[i] = { x: p.x, z: p.z };
      maxPlayerSpeed = Math.max(maxPlayerSpeed, Math.hypot(p.vx, p.vz));
    }
    assert(Object.values(game.ball).every(Number.isFinite), 'nonfinite ball');
    maxBallSpeed = Math.max(maxBallSpeed, Math.hypot(game.ball.vx, game.ball.vy, game.ball.vz));
    if (step % 60 !== 0 || game.restart || game.kick?.restartContext || game.goalPause) continue;
    for (const team of [0, 1]) {
      const players = game.field(team), m = shape[team], side = team === 0 ? 1 : -1;
      m.samples++;
      m.width += Math.max(...players.map(p => p.z)) - Math.min(...players.map(p => p.z));
      m.length += Math.max(...players.map(p => p.x)) - Math.min(...players.map(p => p.x));
      const defenders = players.filter(p => p.role === 'DEF');
      m.defenceLine += defenders.reduce((sum, p) => sum + p.x * side, 0) / Math.max(1, defenders.length);
      const owner = game.owner;
      if (owner?.team === team) {
        const supports = players.filter(p => p !== owner && ['support', 'build-support', 'return-support'].includes(game.targets.get(p)?.state));
        m.supportSamples++; m.supportCount += supports.length;
        for (const p of supports) m.supportDistance += Math.hypot(p.x - owner.x, p.z - owner.z);
      }
      if (game.tacticalPhase[team] === 'counter') m.counterSamples++;
      if (game.tacticalPhase[team] === 'counterpress') m.counterpressSamples++;
    }
  }
  const goals = [0, 1].map(team => game.events.filter(e => e.type === 'goal' && e.team === team).length);
  assert.deepEqual([...game.score], goals, 'score must equal actual goal events');
  assert(maxStep <= .15, `player displacement exceeded .15 m per step: ${maxStep}`);
  if (seconds === 300 || seconds === 5400) assert(game.done, 'full selected match must finish');
  return {
    seconds: game.time, completed: game.done, initialRngState: game.initialSeed, finalRngState: game.seed,
    score: [...game.score], shots: [...game.shots], passes: [...game.passes], completedPasses: [...game.completed],
    pass: pass.map(m => ({ ...m, meanDistance: m.distance / (m.count || 1), meanAbsoluteDirectionRadians: m.angle / (m.count || 1) })),
    shape: shape.map(m => ({
      samples: m.samples, meanWidth: m.width / (m.samples || 1), meanLength: m.length / (m.samples || 1),
      meanDefenceLine: m.defenceLine / (m.samples || 1), meanSupportDistance: m.supportDistance / (m.supportCount || 1),
      meanSupportCount: m.supportCount / (m.supportSamples || 1), counterSamples: m.counterSamples, counterpressSamples: m.counterpressSamples
    })),
    physics: { maxStep, maxPlayerSpeed, maxBallSpeed, finite: true, goalsMatchScore: true },
    telemetry: JSON.parse(JSON.stringify(game.telemetry))
  };
}
const versions = { baseline: load(baseline, 'baseline-football-sim.js'), current: load(current, 'current-football-sim.js') };
const result = {
  generatedAt: new Date().toISOString(), baselineRef,
  sources: { baseline: digest(baseline), current: digest(current), tactics: digest(fs.readFileSync(path.join(root, 'tactics.js'))), observer: digest(fs.readFileSync(__filename)) },
  definitions: { shape: 'One sample per second in open play, outfield players only; defence line is mean defender X in own attacking coordinates.', support: 'Existing support/build-support/return-support target states; measured actual positions, not target positions.', pass: 'All actual release() actions counted by passes[], including restarts; direction is relative to own attack.', limitations: 'Small synthetic sample; divergent match trajectories do not establish causal win-rate or realism gains. Legacy tests/assets were absent in supplied checkout.' },
  seconds, runs: []
};
for (const scenario of scenarios) {
  const row = { scenario };
  for (const [version, Match] of Object.entries(versions)) row[version] = run(Match, scenario);
  result.runs.push(row);
  process.stderr.write(`${scenario.id}: ${row.baseline.score.join('-')} -> ${row.current.score.join('-')} (${seconds}s each)\n`);
}
// Replay one complete scenario, including all observed metrics/RNG, to prove determinism.
result.deterministicReplay = {};
for (const [version, Match] of Object.entries(versions)) {
  const again = run(Match, scenarios[0]);
  assert.deepEqual(again, result.runs[0][version], `${version} replay differs`);
  result.deterministicReplay[version] = true;
}
const output = option('--output', null), json = JSON.stringify(result, null, 2) + '\n';
if (output) { fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true }); fs.writeFileSync(output, json); }
else process.stdout.write(json);
