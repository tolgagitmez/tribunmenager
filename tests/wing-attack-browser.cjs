'use strict';

// Chromium renders a controlled, real Match sequence. The live HTTP transport
// supplies the same authoritative Match frames through the production wire
// projection, without requiring a scheduled league fixture to set up this play.
const assert = require('node:assert/strict');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { createServer } = require('../tools/serve-character-viewer.cjs');
const { runWingAttack, DT } = require('../tools/wing-attack-scenario.cjs');
const { snapshot } = require('../live-match-worker.cjs');
const ContactEvents = require('../match-contact-events.js');

const evidence = path.join(__dirname, '../work/wing-attack-browser');
const fixturePath = path.join(__dirname, '../tools/wing-attack-scenario.cjs');
const endpoint = '/api/league/live-match';
const homeToken = 'wing-fixture-home';
const awayToken = 'wing-fixture-away';
const round = 0;

function authoritativeFrames(options) {
  const frames = [];
  const tracker = ContactEvents.create();
  const result = runWingAttack({
    ...options,
    onFrame(match) {
      tracker.observe(match);
      frames.push(JSON.parse(JSON.stringify(snapshot(match, tracker))));
    }
  });
  for (const stage of ['brake', 'first-control', 'cutback', 'third-player-control', 'shot', 'keeper-response']) {
    assert.ok(result.trace.some(row => row.key === stage), `Fixture lacks ${stage}`);
  }
  assert.ok(result.summary.save || result.summary.score[0] > 0, 'The shot must produce a real save or goal');
  const isWingControl = cue => cue.kind === 'receive' && cue.playerId === result.summary.wing && cue.control;
  const firstControl = frames.find(frame => frame.contacts.some(isWingControl))?.contacts.find(isWingControl);
  assert.ok(firstControl, 'The real ground reception did not produce a presentation cue');
  assert.equal(firstControl.time, result.summary.receives[0].time);
  assert.equal(firstControl.control.foot, options.foot === 'left' ? 0 : 1);
  assert.equal(firstControl.control.mode, result.summary.receives[0].mode);
  return { frames, summary: result.summary, trace: result.trace, firstControl };
}

function fixtureServer() {
  const server = createServer();
  const [serveStatic] = server.listeners('request');
  let state = null;
  const requests = [0, 0];
  server.removeAllListeners('request');
  server.on('request', (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1');
    if (url.pathname !== endpoint) return serveStatic(request, response);
    const side = [homeToken, awayToken].findIndex(token => request.headers.authorization === `Bearer ${token}`);
    if (request.method !== 'GET' || side < 0 || Number(url.searchParams.get('round')) !== round || !state) {
      response.writeHead(403, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify({ error: 'Fixture unavailable' }));
      return;
    }
    requests[side]++;
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify({
      state, side, homeName: 'Kanat FK', awayName: 'Savunma SK',
      homeFormation: '4-3-3', awayFormation: '4-3-3',
      opponentPresent: true, decisionSeconds: null, catchingUp: false
    }));
  });
  return { server, requests, show(frame) { state = frame; } };
}

async function openView(browser, url, { playerId, token, mobile = false, localFixture }) {
  const context = await browser.newContext({
    viewport: mobile ? { width: 390, height: 820 } : { width: 1050, height: 820 },
    reducedMotion: 'reduce'
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => {
    errors.push(error.message);
    console.error(error.message);
  });
  await page.addInitScript(({ token, localFixture }) => {
    if (token) localStorage.setItem('tribun-league-token', token);
    if (localFixture) {
      // Drive the real local fixed-step path deterministically from the test.
      // Only tactical placements and nominated actions come from the fixture.
      window.requestAnimationFrame = () => 0;
      window.MATCH_CFG = { seed: 23, matchMinutes: 5 };
      let Football;
      Object.defineProperty(window, 'TribunFootball', {
        configurable: true,
        get() { return Football; },
        set(value) {
          const Rig = window.TribunHumanoidRig;
          const entry = { exports: {} };
          const modules = { '../football-sim.js': value, '../humanoid-rig.js': Rig };
          new Function('require', 'module', localFixture.source)(name => {
            if (!(name in modules)) throw Error(`Unknown fixture module ${name}`);
            return modules[name];
          }, entry);
          Football = { ...value, Match: class extends value.Match {
            constructor() {
              super({ seed: 23, matchMinutes: 5 }, Rig);
              window.__wingFixture = entry.exports.createWingAttack({ ...localFixture.options, match: this });
            }
          } };
        }
      });
    }
    // Use the actual match scene and controller. Capture the instance in this
    // test context, leaving production code and match state untouched.
    let Scene;
    Object.defineProperty(window, 'Stadium3D', {
      configurable: true,
      get() { return Scene; },
      set(value) {
        Scene = class extends value {
          constructor(...args) {
            super(...args);
            window.__wingScene = this;
          }
          render(players, ball, ...args) {
            const result = super.render(players, ball, ...args);
            if (token) {
              const { presentationTime: time } = window.TRIBUN_MATCH_TEST.getState();
              if (!window.__wingFirstControl) {
                const pilot = this.matchPilot?.info();
                if (pilot?.lastReceiveContact) {
                  const winger = players.find(p => p.id === pilot.playerId);
                  const { x, y, z } = ball;
                  window.__wingFirstControl = { time, ball: { x, y, z }, face: winger.face, action: winger.action };
                }
              }
              if (!window.__wingKeeper) {
                const keeper = players.find(p => p.team === 1 && p.role === 'GK' &&
                  ['catch-ready', 'dive', 'catch'].includes(p.action));
                if (keeper) window.__wingKeeper = { id: keeper.id, action: keeper.action, time };
              }
            }
            return result;
          }
        };
      }
    });
  }, { token, localFixture });
  const query = new URLSearchParams({ pilot: '1', pilotPlayer: String(playerId) });
  if (token) query.set('live', String(round));
  await page.goto(`${url}/match.html?${query}`, { waitUntil: 'load', timeout: 45000 });
  await page.waitForFunction(() =>
    window.__wingScene?.playerRenderer && window.TRIBUN_MATCH_TEST?.pilotStats().status === 'ready' &&
      Number.isFinite(window.TRIBUN_MATCH_TEST.getState()?.time),
    null, { polling: 40, timeout: 45000 });
  assert.equal((await page.evaluate(() => window.TRIBUN_MATCH_TEST.pilotStats())).playerId, playerId);
  return { context, page, errors };
}

async function verifyLocal(browser, url, fixtureSource, options, authority) {
  const view = await openView(browser, url, {
    playerId: authority.summary.wing, localFixture: { options, source: fixtureSource }
  });
  try {
    const played = await view.page.evaluate(({ dt, ticks, playerId }) => {
      const { __wingScene: scene, __wingFixture: fixture, TRIBUN_MATCH_TEST: matchPage } = window;
      const captures = {};
      const heldStages = [];
      let previousRelease = 0, previousDraw = 0, firstControl;
      const { match } = fixture;
      const draw = key => {
        const { ball, players } = match;
        if (key === 'first-control') {
          const winger = players.find(p => p.id === playerId);
          const { x, y, z } = ball;
          const eye = scene.cameraSmoothing.slice(), target = scene.cameraTarget.slice();
          scene.camera = 'portrait';
          scene.render(players, ball, [(x + winger.x) / 2, (z + winger.z) / 2], {}, 1 / 3);
          scene.camera = 'close';
          scene.cameraSmoothing = eye;
          scene.cameraTarget = target;
          firstControl = { time: match.time, ball: { x, y, z }, face: winger.face, action: winger.action };
        } else {
          scene.render(players, ball, [ball.x + ball.vx * .25, ball.z + ball.vz * .25], {}, match.time - previousDraw);
        }
        previousDraw = match.time;
        if (key) captures[key] = scene.canvas.toDataURL('image/png');
      };
      const step = (addition, remaining) => {
        const fromTime = match.time;
        // The fixture controls batch size. Real wall-time frame budgeting is
        // exercised by the separate 22-player render/profile benchmark.
        const clock = performance.now, frameStart = clock.call(performance);
        performance.now = () => frameStart;
        try { matchPage.frame(dt * addition); }
        finally { performance.now = clock; }
        const advanced = Math.round((match.time - fromTime) / dt);
        if (advanced < 1) throw Error('The fixture did not advance its fixed-step frame');
        let key;
        if (match.releaseSerial !== previousRelease) {
          previousRelease = match.releaseSerial;
          if (['cutback', 'shot'].includes(match.flight.kind)) key = match.flight.kind;
        } else if (!captures['first-control'] && fixture.trace.some(row => row.key === 'first-control')) {
          key = 'first-control';
        } else if (!captures.keeper && fixture.trace.some(row => row.key === 'keeper-response')) {
          key = 'keeper';
        }
        if (advanced < remaining) heldStages.push(key);
        if (key || match.time - previousDraw >= dt * 10 - 1e-6) draw(key);
        return advanced;
      };
      scene.camera = 'close';
      for (let requested = 0; requested < ticks && !fixture.complete;) {
        // Offset the render boundary so both ball contacts happen inside a batch.
        const batch = Math.min(requested === 0 ? 4 : 5, ticks - requested);
        let remaining = batch - step(batch, batch);
        while (remaining > 0) remaining -= step(0, remaining);
        requested += batch;
      }
      return {
        captures,
        summary: fixture.summary(),
        complete: fixture.complete,
        trace: fixture.trace,
        ball: match.ball,
        pilot: matchPage.pilotStats(),
        firstControl,
        heldStages,
        webgl: Boolean(scene.gl),
      };
    }, { dt: DT, ticks: authority.summary.ticks, playerId: authority.summary.wing });
    assert.equal(played.webgl, true);
    assert.equal(played.complete, true);
    assert.ok(played.pilot.blenderSamples > 0, 'Blender palette was never drawn');
    assert.ok(played.pilot.contactFrames > 0, 'No physical kick was drawn');
    assert.equal(played.pilot.contactCount, 1);
    verifyBootSample(played.pilot, options);
    verifyReceiveSample(played.pilot, played.firstControl, authority.firstControl);
    assert.deepEqual(played.heldStages, ['first-control', 'cutback'], 'The busy local frames did not hold both contacts for drawing');
    // Across Node and Chromium allow sub-micrometre differences in the
    // floating-point calculations. Compare events and discrete values exactly.
    const normalise = value => JSON.parse(JSON.stringify(value, (_, item) =>
      typeof item === 'number' ? Math.round(item * 1e7) / 1e7 : item));
    assert.deepEqual(normalise(played.summary), normalise(authority.summary));
    assert.deepEqual(normalise(played.trace), normalise(authority.trace));
    assert.deepEqual(normalise(played.ball), normalise(authority.frames.at(-1).ball));
    for (const key of ['first-control', 'cutback', 'shot', 'keeper']) {
      const png = played.captures[key];
      assert.match(png, /^data:image\/png;base64,/);
      assert.ok(png.length > 5000, `Empty ${key} scene`);
      await writeFile(path.join(evidence, `local-${caseName(options)}-${key}.png`), Buffer.from(png.split(',')[1], 'base64'));
    }
    assert.deepEqual(view.errors, []);
    return {
      player: played.pilot.playerId, contactFrames: played.pilot.contactFrames,
      blenderSamples: played.pilot.blenderSamples, boot: played.pilot.lastBootContact,
      receive: played.pilot.lastReceiveContact, heldStages: played.heldStages
    };
  } finally {
    await view.context.close();
  }
}

function caseName({ foot, pressure }) {
  return `${foot}-${pressure ? 'pressured' : 'unpressured'}`;
}

function verifyBootSample(stats, { foot }) {
  assert.equal(stats.bootContactSamples, 1, stats.bootMeasurementError);
  const sample = stats.lastBootContact;
  assert.equal(sample.kind, 'cutback');
  assert.equal(sample.foot, foot === 'left' ? 0 : 1);
  assert.ok(Number.isFinite(sample.gapMetres) && Number.isFinite(sample.baselineGapMetres));
  assert.ok(Math.abs(sample.firstRenderedSampleMs) < .01, 'The released boot was not drawn at its contact time');
  assert.ok(Math.abs(sample.gapMetres) <= .03, 'The released boot did not reach the ball surface');
  assert.ok(Math.abs(sample.gapMetres) <= Math.abs(sample.baselineGapMetres) + 1e-8);
}

function verifyReceiveSample(stats, drawn, cue) {
  assert.equal(stats.bootReceiveSamples, 1, stats.bootMeasurementError || 'The first control must be measured once');
  const sample = stats.lastReceiveContact;
  assert.equal(sample.foot, cue.control.foot);
  assert.equal(sample.mode, cue.control.mode);
  assert.equal(sample.flightId, cue.flightId);
  assert.ok(Number.isFinite(sample.gapMetres) && Number.isFinite(sample.baselineGapMetres));
  assert.ok(Math.abs(sample.contactTime - cue.time) < 1e-6);
  assert.ok(Math.abs(sample.firstRenderedSampleMs) < .01, 'The receiving boot was not drawn at the ground control time');
  assert.ok(sample.gapMetres >= -.005 && sample.gapMetres <= .01,
    `The receiving boot did not reach the ball surface: ${sample.baselineGapMetres} → ${sample.gapMetres}`);
  assert.ok(drawn && Math.abs(drawn.time - cue.time) < 1e-6, 'The ball and first-control pose were not drawn together');
  assert.equal(drawn.action, cue.actor.action);
  assert.ok(Math.abs(Math.sin((drawn.face - cue.actor.face) / 2)) < 1e-6, 'The receiver changed body angle at contact');
  assert.ok(Math.hypot(drawn.ball.x - cue.ball.x, drawn.ball.y - cue.ball.y, drawn.ball.z - cue.ball.z) < 1e-6,
    'First-control drawing moved the ball away from its physical contact point');
}

function batchFrames(frames, stride = [11, 20, 13, 17]) {
  const batches = [];
  let cursor = 0;
  while (cursor < frames.length - 1) {
    cursor = Math.min(cursor + stride[batches.length % stride.length], frames.length - 1);
    batches.push(frames[cursor]);
  }
  return batches;
}

async function verifyLive(browser, url, transport, options, authority) {
  transport.show(authority.frames[0]);
  const views = [];
  try {
    for (const [token, mobile] of [[homeToken, false], [awayToken, true]]) {
      views.push(await openView(browser, url, { token, mobile, playerId: authority.summary.wing }));
    }
    const repeated = new Set();
    for (const state of batchFrames(authority.frames)) {
      transport.show(state);
      const repeat = state.contacts.find(cue => (cue.kind === 'release' || cue.id === authority.firstControl.id) &&
        cue.playerId === authority.summary.wing && !repeated.has(cue.kind));
      const before = repeat && transport.requests.slice();
      await Promise.all(views.map(({ page }) =>
        page.waitForFunction(time => window.TRIBUN_MATCH_TEST?.getState().presentationTime >= time - 1e-6, state.time,
          { polling: 40, timeout: 15000 })));
      if (repeat) {
        await Promise.all(views.map(({ page }) =>
          page.waitForResponse(response => response.url().includes(`${endpoint}?round=${round}`), { timeout: 15000 })));
        assert.ok(transport.requests.every((count, side) => count > before[side] + 1),
          `A peer did not receive duplicate ${repeat.kind} frames`);
        repeated.add(repeat.kind);
      }
    }
    assert.deepEqual(repeated, new Set(['receive', 'release']), 'Both peers must receive repeated first-control and cutback frames');
    const last = authority.frames.at(-1);
    const result = [];
    for (const { page, errors } of views) {
      await page.waitForFunction(() => window.TRIBUN_MATCH_TEST.pilotStats().contactFrames > 0,
        null, { timeout: 10000 });
      const progress = await page.evaluate(() => {
        const { ball, visualBall, score, releaseSerial, events, contacts } = window.TRIBUN_MATCH_TEST.getState();
        const { blenderSamples, contactFrames, contactCount, lastBootContact, bootContactSamples, bootMeasurementError,
          lastReceiveContact, bootReceiveSamples } = window.TRIBUN_MATCH_TEST.pilotStats();
        return { ball, visualBall, score, releaseSerial, events, contacts, blenderSamples, contactFrames, contactCount,
          lastBootContact, bootContactSamples, bootMeasurementError, lastReceiveContact, bootReceiveSamples,
          firstControl: window.__wingFirstControl, keeper: window.__wingKeeper };
      });
      assert.deepEqual(progress.ball, last.ball);
      assert.deepEqual(progress.score, last.score);
      assert.equal(progress.releaseSerial, last.releaseSerial);
      assert.deepEqual(progress.events, last.events);
      assert.deepEqual(progress.contacts, last.contacts);
      for (const key of ['x', 'y', 'z']) assert.equal(progress.visualBall[key], last.ball[key]);
      assert.ok(progress.blenderSamples > 0, 'Actual match never drew a Blender palette');
      assert.equal(progress.contactCount, 1, 'One wing strike must be presented once despite sparse and repeated packets');
      verifyBootSample(progress, options);
      verifyReceiveSample(progress, progress.firstControl, authority.firstControl);
      assert.equal(progress.keeper?.id, authority.summary.keeper);
      assert.ok(progress.keeper.time >= authority.summary.response.time - 1e-6, 'Keeper was drawn reacting before his authoritative cue');
      assert.deepEqual(errors, []);
      result.push({
        blenderSamples: progress.blenderSamples, contactFrames: progress.contactFrames,
        contactCount: progress.contactCount, boot: progress.lastBootContact,
        receive: progress.lastReceiveContact, keeper: progress.keeper
      });
    }
    for (const [i, { page }] of views.entries()) {
      await page.locator('#stadiumCanvas').screenshot({
        path: path.join(evidence, `live-${caseName(options)}-${i ? 'mobile' : 'desktop'}.png`), timeout: 30000
      });
    }
    return result;
  } finally {
    await Promise.all(views.map(view => view.context.close()));
  }
}

async function main() {
  const cases = ['left', 'right'].flatMap(foot => [false, true].map(pressure => ({ foot, pressure })));
  const fixtureSource = await readFile(fixturePath, 'utf8');
  await mkdir(evidence, { recursive: true });
  const transport = fixtureServer();
  await new Promise(resolve => transport.server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({
      headless: true, executablePath: process.env.CHROMIUM,
      args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox']
    });
    const url = `http://127.0.0.1:${transport.server.address().port}`;
    const results = [];
    for (const options of cases) {
      const authority = authoritativeFrames(options);
      console.log(`Verifying ${caseName(options)} on the local match page`);
      const local = await verifyLocal(browser, url, fixtureSource, options, authority);
      console.log(`Verifying ${caseName(options)} on both live match pages`);
      const live = await verifyLive(browser, url, transport, options, authority);
      const result = { ...options, local, live, score: authority.summary.score };
      results.push(result);
      console.log('WING_CHROMIUM ' + JSON.stringify(result));
    }
    assert.ok(transport.requests.every(count => count > 3));
    await writeFile(path.join(evidence, 'report.json'), JSON.stringify({ results, requestCounts: transport.requests }, null, 2) + '\n');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => transport.server.close(resolve));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
