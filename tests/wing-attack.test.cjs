'use strict';

const assert = require('node:assert/strict');
const {test} = require('node:test');
const ContactEvents = require('../match-contact-events.js');
const {runWingAttack} = require('../tools/wing-attack-scenario.cjs');

function traceFrame(match) {
 const {time, ball, owner, flight, score, restart, events} = match;
 return [
  time, {...ball}, owner?.id, flight?.id, score.slice(), restart?.kind,
  events.map(({type, time, playerId}) => [type, time, playerId])
 ];
}

test('a controlled attack sprints, opens up, cuts back and creates a shot with both feet', async t => {
 const outcomes = [];
 for (const foot of ['left', 'right']) {
  for (const pressure of [false, true]) {
   await t.test(`${foot} foot with ${pressure ? 'a nearby defender' : 'space'}`, () => {
    const observer = ContactEvents.create();
    const cues = new Map();
    const frames = [];
    const {complete, summary, match} = runWingAttack({
     foot, pressure,
     onFrame(match) {
      observer.observe(match);
      for (const cue of observer.recent()) cues.set(cue.id, cue);
      frames.push(traceFrame(match));
     }
    });
    assert.equal(complete, true);
    assert(summary.peakWingSpeed > 6);
    const [feed, cutback, shot] = summary.releases;
    const [wingControl, runnerControl] = summary.receives;
    const wingFoot = foot === 'left' ? 0 : 1;
    assert.deepEqual(
     summary.releases.map(({kind, by, to}) => [kind, by, to]),
     [['pass', summary.feeder, summary.wing], ['cutback', summary.wing, summary.runner], ['shot', summary.runner, null]]
    );
    assert.deepEqual(
     summary.receives.map(({by, from}) => [by, from]),
     [[summary.wing, summary.feeder], [summary.runner, summary.wing]]
    );
    assert(summary.startBrake.time < summary.readyAt && summary.readyAt < feed.time);
    assert(summary.startBrake.speed > 6 && wingControl.speed < 1);
    assert.equal(wingControl.mode, 'open');
    assert(wingControl.hadPreparation && wingControl.insideBodyAngle < .4);
    assert(wingControl.incomingBodyAngle > Math.PI / 4 && wingControl.incomingBodyAngle < Math.PI / 2);
    assert(pressure ? wingControl.pressure < 4 : wingControl.pressure > 7);
    assert.equal(wingControl.foot, wingFoot);
    assert.equal(cutback.foot, wingFoot);
    assert(feed.time < wingControl.time && wingControl.time < summary.runnerStart.time);
    assert(summary.runnerStart.time < cutback.time && cutback.time < runnerControl.time);
    assert(summary.runnerAdvance > 4 && runnerControl.time < shot.time);
    assert(cutback.velocity[0] < 0 && cutback.at.z * cutback.velocity[2] < 0, 'cutback travels backwards and infield');
    assert(shot.velocity[0] > 20 && shot.velocity[1] > 0);
    assert(summary.releases.every(({bootGap}) => bootGap <= .11), 'each release was reached by the engine contact point');
    assert.deepEqual(summary.shots, [1, 0]);
    assert.deepEqual(summary.onTarget, [1, 0]);
    assert.equal(summary.turnover, 0);
    assert.equal(summary.abortedKicks, 0);
    assert.equal(summary.response.action, 'dive');
    assert(summary.response.time > shot.time && summary.response.time - shot.time < .3);

    const contacts = [...cues.values()];
    const releases = contacts.filter(({kind}) => kind === 'release');
    assert.deepEqual(
     releases.map(({time, playerId, kickKind, targetId, actor, ball}) => [
      time, playerId, kickKind, targetId, actor.kickFoot, [ball.vx, ball.vy, ball.vz]
     ]),
     summary.releases.map(({time, by, kind, to, foot, velocity}) => [time, by, kind, to, foot, velocity])
    );
    const receives = contacts.filter(({kind}) => kind === 'receive');
    assert.deepEqual(
     receives.map(({time, playerId, flightId}) => [time, playerId, flightId]),
     summary.receives.map(({time, by}, i) => [time, by, releases[i].flightId])
    );
    assert.deepEqual(receives.map(({control}) => control),
     summary.receives.map(({mode, foot}) => ({mode, foot})));
    const keeperPrepare = contacts.find(({kind}) => kind === 'keeper-prepare');
    assert.equal(keeperPrepare.time, summary.response.time);
    assert.equal(keeperPrepare.playerId, summary.keeper);
    assert.equal(keeperPrepare.flightId, releases[2].flightId);

    if (summary.save) {
     const keeperContact = contacts.find(({kind}) => kind === 'keeper-contact');
     assert(keeperContact.time > keeperPrepare.time);
     assert.equal(keeperContact.time, summary.save.time);
     assert.equal(keeperContact.playerId, summary.keeper);
     assert.equal(keeperContact.flightId, releases[2].flightId);
     assert.equal(match.lastTouch.id, summary.keeper);
     assert.deepEqual(keeperContact.ball, summary.save.position);
     outcomes.push('save');
    } else {
     assert.deepEqual(summary.score, [1, 0]);
     assert(summary.events.includes('goal'));
     assert(!contacts.some(({kind}) => kind === 'keeper-contact'));
     outcomes.push('goal');
    }

    if (foot === 'right' && pressure) {
     const unobserved = [];
     const replay = runWingAttack({foot, pressure, onFrame: match => unobserved.push(traceFrame(match))});
     assert.deepEqual(replay.summary, summary);
     assert.deepEqual(unobserved, frames, 'presentation observation preserves every 60 Hz ball and referee frame');
    }
   });
  }
 }
 assert.deepEqual(outcomes.sort(), ['goal', 'goal', 'save', 'save']);
});
