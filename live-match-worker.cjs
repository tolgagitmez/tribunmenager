'use strict';

// The league server owns scheduling and authorization. This process owns the
// simulation, including contact, referee decisions and the final score.
const readline = require('node:readline');
const {Match} = require('./football-sim.js');
const Rig = require('./humanoid-rig.js');
const ContactEvents = require('./match-contact-events.js');

const MAX_STEPS = 120;
const RECENT_EVENTS = 80;

const playerFields = [
  'id', 'index', 'team', 'role', 'position', 'name', 'num', 'rosterId',
  'portraitId', 'referee', 'active', 'yellow', 'skin', 'hair', 'visual',
  'skill', 'fitness', 'stamina', 'energy', 'x', 'z', 'vx', 'vz', 'speed',
  'face', 'selected', 'action', 'actionClock', 'actionDuration', 'actionElapsed',
  'kickFoot', 'kickMoving', 'contactTime', 'footTouch', 'touchPosition',
  'dribbleFoot', 'diveSide', 'diveForward', 'diveContactTime', 'saveTarget',
  'catchPoint', 'gatherStart', 'headerHeight', 'jumpHeight', 'chestContactHeight', 'personality', 'feintClock',
  'feintSign', 'receiveClock', 'receiveMode', 'holdingBall', 'holdClock'
];
const matchFields = [
  'time', 'duration', 'score', 'cards', 'reds', 'shots', 'onTarget', 'fouls',
  'possession', 'completed', 'passes', 'xg', 'tacticalPhase', 'lifecycle',
  'done', 'finishReason', 'phase', 'period', 'goalPause', 'pendingManagerKick',
  'releaseSerial', 'rules', 'subCount', 'subWindowsUsed'
];

function pick(source, fields) {
  return Object.fromEntries(fields.filter(field => source[field] !== undefined)
    .map(field => [field, source[field]]));
}

function restartView(restart) {
  return restart && {
    id: restart.id, kind: restart.kind, team: restart.team, spot: restart.spot,
    takerId: restart.taker?.id ?? null, indirect: !!restart.indirect,
    managerPreparing: !!restart.managerPlan
  };
}

function snapshot(game, contacts) {
  const {owner, flight, kick} = game;
  return {
    ...pick(game, matchFields),
    clock: game.clockState(),
    direction: [game.direction(0), game.direction(1)],
    tactics: game.t,
    ball: game.ball,
    ownerId: owner?.id ?? null,
    restart: restartView(game.restart),
    kick: kick && {
      kind: kick.kind, playerId: kick.p.id, targetId: kick.target?.id ?? null,
      restartContext: restartView(kick.restartContext ?? null)
    },
    flight: flight && {id: flight.id, kind: flight.kind, fromId: flight.from.id,
      age: flight.age, targetId: flight.target?.id ?? null},
    contacts: contacts?.recent() ?? [],
    referee: {pendingAdvantage: !!game.referee.pendingAdvantage},
    players: game.players.map(player => ({
      ...pick(player, playerFields),
      perception: {headYaw: player.perception?.headYaw ?? 0},
      selected: player === owner
    })),
    // Recorded only at final whistle; one physical Match owns these values,
    // not a separate league scorer or an attendance-dependent approximation.
    ...(game.done ? {appearances:game.appearanceReport()} : {}),
    eventSerial: game.events.length,
    events: game.events.slice(-RECENT_EVENTS)
  };
}

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const error = message => ({ok: false, error: message});

function createWorker({createMatch = (config, rig) => new Match(config, rig)} = {}) {
  let game;
  const contacts = ContactEvents.create();
  return request => {
    if (!object(request)) return error('Invalid worker request.');
    if (request.op === 'init') {
      if (game || !object(request.config)) return error('Invalid match initialization.');
      game = createMatch(request.config, Rig);
      game.managerKickTeams = new Set();
      contacts.observe(game);
      game.drain();
      return {ok: true, state: snapshot(game, contacts)};
    }
    if (!game) return error('Match has not been initialized.');

    if (request.op === 'advance') {
      const {steps, teams} = request;
      if (!Number.isInteger(steps) || steps < 0 || steps > MAX_STEPS ||
          !Array.isArray(teams) || teams.some(team => team !== 0 && team !== 1)) {
        return error('Invalid match step request.');
      }
      game.managerKickTeams = new Set(teams);
      let processed = 0;
      while (processed < steps && !game.done && !game.pendingManagerKick) {
        game.step(1 / 60);
        contacts.observe(game);
        processed++;
      }
      game.drain();
      return {ok: true, steps: processed, state: snapshot(game, contacts)};
    }
    if (request.op === 'kick') {
      if (!Number.isSafeInteger(request.id) || request.id < 1 ||
          (request.input !== null && !object(request.input))) {
        return error('Invalid kick request.');
      }
      const accepted = game.resolveManagerKick(request.id, request.input);
      game.drain();
      return {ok: true, accepted, state: snapshot(game, contacts)};
    }
    return error('Unknown worker operation.');
  };
}

async function main() {
  const requests = readline.createInterface({input: process.stdin, crlfDelay: Infinity});
  const handle = createWorker();
  for await (const line of requests) {
    let request;
    try {
      request = JSON.parse(line);
    } catch {
      process.stdout.write(JSON.stringify(error('Invalid worker JSON.')) + '\n');
      continue;
    }
    const response = JSON.stringify(handle(request)) + '\n';
    if (!process.stdout.write(response)) {
      await new Promise(resolve => process.stdout.once('drain', resolve));
    }
  }
}

module.exports = {createWorker, snapshot};
if(require.main===module)main().catch(cause => {
  // The server discards the process on an unexpected engine failure, since a
  // partial step may already have changed the simulation.
  console.error(cause);
  process.exit(1);
});
