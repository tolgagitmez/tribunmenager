'use strict';
/**
 * Determinism gate for the CURRENT engine, not a frozen pre-kick engine hash.
 * Both matches use the same checked-out football-sim.js and identical inputs;
 * only the historical and current presentation rigs differ.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const Module = require('node:module');

const root = path.resolve(__dirname, '..');
const target = path.join(root, 'docs/validation/character-physics.json');
// A failing rerun must not leave a previous measurement as its result.
// The archived historical report is a separate file.
fs.rmSync(target, {force: true});
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
const oldRigPath = 'docs/validation/baselines/licensed-character-rig-6ddd4f1.js.gz';
const oldRigBytes = zlib.gunzipSync(fs.readFileSync(path.join(root, oldRigPath)));
const oldRigSha = '2c024a0fd130d50baa04533ae255a8f72b7dc93c269ef3d0af86ae6771820b3d';
assert.equal(digest(oldRigBytes), oldRigSha, 'Historical rig bytes must not change');

const previous = new Module(path.join(root, 'character-baseline-motion.js'), module);
previous.filename = path.join(root, 'character-baseline-motion.js');
previous.paths = Module._nodeModulePaths(root);
previous._compile(oldRigBytes.toString('utf8'), previous.filename);
const oldRig = previous.exports;
const currentRig = require('../humanoid-rig');
const {Match} = require('../football-sim');
const Tactics = require('../tactics');

const sourcePaths = [
  'football-sim.js', 'humanoid-rig.js', 'match-animation-bridge.js',
  'tactics.js', 'player-model.js', 'player-model-profiles.js',
  'player-model-profiles.json', 'player-perception.js', 'team-intent.js',
  'match-rules.js', 'referee-laws.js', 'pitch-laws.js', 'live-match-worker.cjs',
  'live_match.py', 'server.py', oldRigPath, 'tools/check-character-physics.cjs'
];
// Capture and freeze fingerprints at run time. Never pin the current engine to
// a previous engine's digest: that would skip the comparison after a feature.
const sources = Object.fromEntries(sourcePaths.map(p =>
  [p, digest(fs.readFileSync(path.join(root, p)))]
));
const snapshot = match => structuredClone({...match, motion: null});
const scenarios = [
  {seed: 21, matchMinutes: 5},
  {seed: 42, matchMinutes: 5, tactics: Tactics.presets.find(p => p.id === 'press').tactics},
  {seed: 77, matchMinutes: 5, formation: '4-4-2'}
];
const results = [];
for (const config of scenarios) {
  const older = new Match(config, oldRig);
  const newer = new Match(config, currentRig);
  const ballTrace = crypto.createHash('sha256');
  const decisionTrace = crypto.createHash('sha256');
  let ticks = 0, comparisons = 0;
  while (!older.done && ticks < 24000) {
    older.step();
    newer.step();
    ticks++;
    for (const player of older.players) if (player.active) oldRig.update(player, 1 / 60);
    for (const player of newer.players) if (player.active) currentRig.update(player, 1 / 60);

    // Inspect every physics tick, not just the occasional complete snapshot.
    assert.equal(older.done, newer.done, 'Completion divergence at seed/tick ' + config.seed + '/' + ticks);
    assert.deepEqual(older.ball, newer.ball, 'Ball divergence at seed/tick ' + config.seed + '/' + ticks);
    assert.deepEqual(older.score, newer.score, 'Score divergence at seed/tick ' + config.seed + '/' + ticks);
    assert.deepEqual(older.cards, newer.cards, 'Yellow cards diverged at seed/tick ' + config.seed + '/' + ticks);
    assert.deepEqual(older.reds, newer.reds, 'Red cards diverged at seed/tick ' + config.seed + '/' + ticks);
    assert.deepEqual(older.referee, newer.referee, 'Referee divergence at seed/tick ' + config.seed + '/' + ticks);
    assert.deepEqual(older.events, newer.events, 'Event divergence at seed/tick ' + config.seed + '/' + ticks);
    assert.equal(older.seed, newer.seed, 'RNG divergence at seed/tick ' + config.seed + '/' + ticks);
    ballTrace.update(JSON.stringify(older.ball) + '\n');
    // The referee's full graph is compared above. Hash a compact, stable
    // account of incident/order/status changes for report provenance.
    decisionTrace.update(JSON.stringify([
      older.fouls, older.cards, older.reds,
      older.referee.decisions.map(x => [x.kind, x.status, x.type, x.team]),
      older.events.filter(x => ['foul', 'yellow', 'red', 'offside', 'penalty'].includes(x.type))
        .map(x => [x.type, x.team, x.time])
    ]) + '\n');

    if (ticks % 120 === 0 || older.done) {
      assert.deepEqual(snapshot(older), snapshot(newer),
        'Full match state diverged at seed/tick ' + config.seed + '/' + ticks);
      comparisons++;
    }
  }
  assert(older.done && newer.done, 'Both natural matches must finish, including added time');
  results.push({
    seed: config.seed,
    ticks,
    completeStateComparisons: comparisons,
    checkedPhysicsTicks: ticks,
    elapsedSeconds: older.time,
    score: older.score,
    shots: older.shots,
    fouls: older.fouls,
    cards: older.cards,
    reds: older.reds,
    refereeDecisions: older.referee.decisions.length,
    ballTrajectorySHA256: ballTrace.digest('hex'),
    refereeTimelineSHA256: decisionTrace.digest('hex'),
    exactBallScoreRefereeAndState: true
  });
}
for (const [file, sha] of Object.entries(sources)) {
  assert.equal(digest(fs.readFileSync(path.join(root, file))), sha,
    'Source changed during verification: ' + file);
}
const report = {
  generatedAt: new Date().toISOString(),
  gitSha: process.env.GITHUB_SHA || null,
  currentEngineSHA256: sources['football-sim.js'],
  baselineRigCommit: '6ddd4f18b8ffb1789379fb8635dd37540983a952',
  baselineRigSHA256: oldRigSha,
  archivedHistoricalMeasurement: 'docs/validation/baselines/character-physics-stage14.json',
  method: 'Current checked-out engine instantiated twice per deterministic scenario; only the presentation rigs differ. Every tick verifies ball, score, cards, referee, events and RNG. Every 120 ticks plus full time compares the complete structured match graph, excluding only the motion module reference. Ball and referee timeline digests are recorded.',
  sources, runs: results,
  totals: {
    scenarios: results.length,
    checkedPhysicsTicks: results.reduce((s, r) => s + r.checkedPhysicsTicks, 0),
    completeStateComparisons: results.reduce((s, r) => s + r.completeStateComparisons, 0)
  },
  verified: true
};
fs.mkdirSync(path.dirname(target), {recursive: true});
fs.writeFileSync(target, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({
  verified: true, currentEngineSHA256: report.currentEngineSHA256,
  ...report.totals, report: path.relative(root, target)
}));
