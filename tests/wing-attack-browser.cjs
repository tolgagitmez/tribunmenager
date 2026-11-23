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
  return { frames, summary: result.summary, trace: result.trace };
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
          render(players, ...args) {
            const result = super.render(players, ...args);
            if (token && !window.__wingKeeper) {
              const keeper = players.find(p => p.team === 1 && p.role === 'GK' &&
                ['catch-ready', 'dive', 'catch'].includes(p.action));
              if (keeper) {
                const { presentationTime } = window.TRIBUN_MATCH_TEST.getState();
                window.__wingKeeper = { id: keeper.id, action: keeper.action, time: presentationTime };
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
    const played = await view.page.evaluate(({ dt, ticks }) => {
      const { __wingScene: scene, __wingFixture: fixture, TRIBUN_MATCH_TEST: matchPage } = window;
      const captures = {};
      let previousRelease = 0, truncatedBatches = 0;
      let previousDraw = 0;
      const draw = (match, key) => {
        const { ball, players } = match;
        scene.render(players, ball, [ball.x + ball.vx * .25, ball.z + ball.vz * .25], {}, match.time - previousDraw);
        previousDraw = match.time;
        if (key) captures[key] = scene.canvas.toDataURL('image/png');
      };
      const { match } = fixture;
      scene.camera = 'close';
      for (let counter = 0; counter < ticks && !fixture.complete;) {
        const batch = Math.min(5, ticks - counter);
        const fromTime = match.time;
        matchPage.frame(dt * batch);
        if (match.releaseSerial !== previousRelease) {
          previousRelease = match.releaseSerial;
          draw(match, ['cutback', 'shot'].includes(match.flight.kind) ? match.flight.kind : null);
        } else if (!captures.keeper && fixture.trace.some(row => row.key === 'keeper-response')) {
          draw(match, 'keeper');
        } else if (counter % 10 === 0) draw(match);
        if (match.time - fromTime < dt * batch - 1e-6) {
          truncatedBatches++;
          matchPage.frame(0);
        }
        counter += batch;
      }
      return {
        captures,
        summary: fixture.summary(),
        complete: fixture.complete,
        trace: fixture.trace,
        ball: match.ball,
        pilot: matchPage.pilotStats(),
        truncatedBatches,
        webgl: Boolean(scene.gl),
      };
    }, { dt: DT, ticks: authority.summary.ticks });
    assert.equal(played.webgl, true);
    assert.equal(played.complete, true);
    assert.ok(played.pilot.blenderSamples > 0, 'Blender palette was never drawn');
    assert.ok(played.pilot.contactFrames > 0, 'No physical kick was drawn');
    assert.equal(played.pilot.contactCount, 1);
    verifyBootSample(played.pilot, options);
    if (options.foot === 'left' && !options.pressure) {
      assert.equal(played.truncatedBatches, 1, 'The busy local frame did not hold its cutback for drawing');
    }
    // Across Node and Chromium allow sub-micrometre differences in the
    // floating-point calculations. Compare events and discrete values exactly.
    const normalise = value => JSON.parse(JSON.stringify(value, (_, item) =>
      typeof item === 'number' ? Math.round(item * 1e7) / 1e7 : item));
    assert.deepEqual(normalise(played.summary), normalise(authority.summary));
    assert.deepEqual(normalise(played.trace), normalise(authority.trace));
    assert.deepEqual(normalise(played.ball), normalise(authority.frames.at(-1).ball));
    for (const key of ['cutback', 'shot', 'keeper']) {
      const png = played.captures[key];
      assert.match(png, /^data:image\/png;base64,/);
      assert.ok(png.length > 5000, `Empty ${key} scene`);
      await writeFile(path.join(evidence, `local-${caseName(options)}-${key}.png`), Buffer.from(png.split(',')[1], 'base64'));
    }
    assert.deepEqual(view.errors, []);
    return {
      player: played.pilot.playerId, contactFrames: played.pilot.contactFrames,
      blenderSamples: played.pilot.blenderSamples, boot: played.pilot.lastBootContact,
      heldLocalBatches: played.truncatedBatches
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
    let repeatedRelease = false;
    for (const state of batchFrames(authority.frames)) {
      transport.show(state);
      const repeats = !repeatedRelease && state.contacts.some(cue => cue.kind === 'release' &&
        cue.playerId === authority.summary.wing) ? transport.requests.slice() : null;
      await Promise.all(views.map(({ page }) =>
        page.waitForFunction(time => window.TRIBUN_MATCH_TEST?.getState().presentationTime >= time - 1e-6, state.time,
          { polling: 40, timeout: 15000 })));
      if (repeats) {
        await Promise.all(views.map(({ page }) =>
          page.waitForResponse(response => response.url().includes(`${endpoint}?round=${round}`), { timeout: 15000 })));
        assert.ok(transport.requests.every((count, side) => count > repeats[side] + 1), 'A peer did not receive duplicate frames');
        repeatedRelease = true;
      }
    }
    assert.equal(repeatedRelease, true, 'No cutback frame was repeated on both peers');
    const last = authority.frames.at(-1);
    const result = [];
    for (const { page, errors } of views) {
      await page.waitForFunction(() => window.TRIBUN_MATCH_TEST.pilotStats().contactFrames > 0,
        null, { timeout: 10000 });
      const progress = await page.evaluate(() => {
        const { ball, visualBall, score, releaseSerial, events, contacts } = window.TRIBUN_MATCH_TEST.getState();
        const { blenderSamples, contactFrames, contactCount, lastBootContact, bootContactSamples, bootMeasurementError } = window.TRIBUN_MATCH_TEST.pilotStats();
        return { ball, visualBall, score, releaseSerial, events, contacts, blenderSamples, contactFrames, contactCount,
          lastBootContact, bootContactSamples, bootMeasurementError, keeper: window.__wingKeeper };
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
      assert.equal(progress.keeper?.id, authority.summary.keeper);
      assert.ok(progress.keeper.time >= authority.summary.response.time - 1e-6, 'Keeper was drawn reacting before his authoritative cue');
      assert.deepEqual(errors, []);
      result.push({
        blenderSamples: progress.blenderSamples, contactFrames: progress.contactFrames,
        contactCount: progress.contactCount, boot: progress.lastBootContact, keeper: progress.keeper
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
