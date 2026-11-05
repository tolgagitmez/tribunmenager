#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -v
node tests/v16-regressions.test.cjs
node tests/football.test.cjs
node tests/full-match.test.cjs
node tests/rig.test.cjs
node tests/mesh-render.test.cjs

node tests/regression.test.cjs

node tests/motion.test.cjs
node tests/animation-lab.test.cjs

node tests/player-appearance.test.cjs
node tests/player-studio.test.cjs

node tests/tactical-ai.test.cjs

node tests/config-snapshot.test.cjs

node tests/football-flow.test.cjs
node tests/match-intelligence.test.cjs
node tests/decision-continuity.test.cjs

node tests/attack-coordination.test.cjs

node tests/free-kick-wall.test.cjs

node tests/defensive-balance.test.cjs

node tests/off-ball-continuity.test.cjs

node tests/ball-control.test.cjs

node tests/teamplay.test.cjs

node tests/ball-physics.test.cjs

node tests/press-support.test.cjs

node tests/pressure-exits.test.cjs

node tests/keeper-gather.test.cjs

node tests/defensive-connection.test.cjs

node tests/pass-lane-read.test.cjs

node tests/pass-review.test.cjs

node tests/pass-release-read.test.cjs

node tests/receiver-forecast.test.cjs
