'use strict';

// Run with CHROMIUM=/path/to/chromium node tests/live-match-browser.cjs.
// The endpoint fixture controls the timing of two decision windows. Both
// independent browser sessions load the real match UI and use real HTTP.
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const { chromium } = require('playwright');
const { createServer } = require('../tools/serve-character-viewer.cjs');

const round = 0;
const teams = ['Saha FK', 'Tribün SK'];
const tokens = ['browser-home', 'browser-away'];
const panel = '#managerKickPanel';
const endpoint = '/api/league/live-match';
const skillTotals = { dribbleTouches: 18, signatureDrives: 4, feints: 3, beatenDefenders: 1, holdUpPlays: 2, throughBalls: 5 };

function initialSnapshot() {
  const worker = path.resolve(__dirname, '../live-match-worker.cjs');
  const request = JSON.stringify({ op: 'init', config: { seed: 21, matchMinutes: 5 } }) + '\n';
  const reply = JSON.parse(execFileSync(process.execPath, [worker], { input: request, encoding: 'utf8' }));
  assert.equal(reply.ok, true);
  return reply.state;
}

function testServer() {
  const start = initialSnapshot();
  const fixture = { league: 'TEST00', round, home: 0, away: 1, kickoff: Math.floor(Date.now() / 1000) - 30 };
  const calls = [];
  let stage = 0;
  const accepted = [];
  const frames = [
    { time: 29, score: [0, 0] },
    { time: 30, score: [0, 0], side: 0, kind: 'penalty', id: 41 },
    { time: 31, score: [1, 0], type: 'goal', title: 'Ev sahibi golü' },
    { time: 42, score: [1, 0], side: 1, kind: 'corner', id: 42 },
    { time: 43, score: [1, 1], type: 'goal', title: 'Deplasman golü' },
    { time: 300, score: [1, 1], type: 'end', title: 'Son düdük', done: true }
  ];
  const makeReply = side => {
    const frame = frames[stage];
    const state = structuredClone(start);
    const display = `${String(Math.floor(frame.time / 60)).padStart(2, '0')}:${String(frame.time % 60).padStart(2, '0')}`;
    state.time = frame.time;
    state.score = frame.score;
    state.done = !!frame.done;
    if (frame.done) state.telemetry = skillTotals;
    state.lifecycle = frame.done ? 'finished' : 'playing';
    state.phase = frame.done ? 'finished' : frame.kind ? 'restart' : 'open';
    state.clock = { ...state.clock, display, nominalElapsed: frame.time, remaining: 300 - frame.time, phase: state.lifecycle };
    state.restart = null;
    for (const earlier of frames.slice(0, stage + 1)) {
      if (!earlier.type) continue;
      const clockDisplay = earlier.done ? '05:00' : `00:${earlier.time}`;
      state.events.push({ type: earlier.type, title: earlier.title, desc: earlier.title, team: 0, time: earlier.time, clockDisplay });
    }
    state.eventSerial = state.events.length;
    if (frame.kind) {
      const player = state.players.find(p => p.team === frame.side && p.role !== 'GK');
      const direction = frame.side === 0 ? 1 : -1;
      const origin = frame.kind === 'penalty' ? { x: 41, z: 0 } : { x: -51.8, z: -33.8 };
      const target = frame.kind === 'penalty' ? { x: 52, z: 0 } : { x: -43, z: 0 };
      state.ball = { ...state.ball, ...origin };
      state.restart = { id: frame.id, team: frame.side, spot: origin, kind: frame.kind, takerId: player.id, indirect: false };
      state.pendingManagerKick = {
        id: frame.id, kind: frame.kind, team: frame.side, playerId: player.id, playerName: player.name,
        origin, target, direction, angle: Math.atan2(target.z - origin.z, target.x - origin.x),
        angleRange: Math.PI / 4, range: Math.hypot(target.x - origin.x, target.z - origin.z), power: .62, skill: 82
      };
    }
    return { state, side, homeName: teams[0], awayName: teams[1], fixture, opponentPresent: true, decisionSeconds: frame.kind ? 30 : 0, catchingUp: false };
  };
  const server = createServer();
  const [serveStatic] = server.listeners('request');
  server.removeAllListeners('request');
  server.on('request', async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1');
    const send = (status, value) => {
      response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      response.end(JSON.stringify(value));
    };
    if (url.pathname === '/api/league/status') {
      const side = tokens.indexOf(url.searchParams.get('token'));
      if (side < 0) return send(403, { error: 'Oturum bulunamadı.' });
      const frame = frames[stage];
      const match = { ...fixture, home_score: frame.done ? frame.score[0] : null, away_score: frame.done ? frame.score[1] : null };
      return send(200, {
        code: fixture.league, server_time: Date.now() / 1000, day: 1,
        my_slot: side, my_club: teams[side], manager: `Menajer ${side + 1}`, my_match: match,
        my_formation: '4-3-3', my_tactics: { press: 60, aggression: 50 },
        active: frame.done ? [] : [fixture], standings: [],
        teams: teams.map((name, index) => ({ name, manager: `Menajer ${index + 1}`, claimed: true })),
        recent: frame.done ? [{ ...match, home_name: teams[0], away_name: teams[1] }] : []
      });
    }
    if (!url.pathname.startsWith(endpoint)) return serveStatic(request, response);
    const side = tokens.findIndex(token => request.headers.authorization === `Bearer ${token}`);
    calls.push({ side, method: request.method, url: request.url });
    if (side < 0) return send(403, { error: 'Oturum bulunamadı.' });
    if (request.method === 'GET' && url.pathname === endpoint && url.searchParams.get('round') === String(round)) {
      return send(200, makeReply(side));
    }
    if (request.method === 'POST' && url.pathname === endpoint + '/kick') {
      let data = '';
      for await (const chunk of request) data += chunk;
      let command;
      try { command = JSON.parse(data); } catch { return send(400, { error: 'Geçersiz komut.' }); }
      const frame = frames[stage];
      if (frame.side !== side || frame.id !== command.id || command.round !== round) {
        return send(409, { error: 'Vuruş başka bir menajere ait.' });
      }
      accepted.push({ side, ...command });
      stage++;
      return send(200, makeReply(side));
    }
    send(404, { error: 'Maç bulunamadı.' });
  });
  return { server, calls, accepted, show: value => { stage = value; } };
}

async function setupPage(browser, token, url) {
  const context = await browser.newContext({ viewport: { width: 1050, height: 820 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(token => {
    localStorage.setItem('tribun-league-token', token);
    // The separate manager-kick browser test exercises real WebGL rendering.
    // Fallback here lets two complete pages poll and animate concurrently in CI.
    const context = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      return type.startsWith('webgl') ? null : context.call(this, type, ...args);
    };
  }, token);
  await page.goto(url + '/league.html', { waitUntil: 'load' });
  const watch = page.locator('#watchLive');
  await watch.waitFor({ state: 'visible' });
  assert.equal(await watch.getAttribute('href'), `match.html?live=${round}`);
  await watch.click();
  await page.waitForURL(url + `/match.html?live=${round}`);
  return { context, page, errors };
}

async function see(view, clock, score, eventTitle) {
  await view.page.waitForFunction(({ clock, score, eventTitle }) => {
    const text = id => document.getElementById(id)?.textContent?.trim();
    return text('matchClock') === clock && text('scoreHome') === String(score[0]) &&
      text('scoreAway') === String(score[1]) &&
      (!eventTitle || document.getElementById('eventList')?.textContent.includes(eventTitle));
  }, { clock, score, eventTitle }, { timeout: 15000 });
}

async function assertReadOnlyControls(view) {
  for (const id of ['playButton', 'restartButton', 'speedButton']) {
    const control = view.page.locator('#' + id);
    assert.ok(!await control.isVisible() || await control.isDisabled(), `live control ${id} must not change the shared match`);
  }
}

async function submit(view, button) {
  const [response] = await Promise.all([
    view.page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === endpoint + '/kick'),
    view.page.locator(button).click()
  ]);
  if (response.status() !== 200) assert.fail(`Vuruş isteği ${response.status()} döndü: ${await response.text()}`);
}

async function main() {
  const { server, calls, accepted, show } = testServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.CHROMIUM, headless: true });
    const url = `http://127.0.0.1:${server.address().port}`;
    const views = await Promise.all(tokens.map(token => setupPage(browser, token, url)));
    const [home, away] = views;
    const shared = (...args) => Promise.all(views.map(view => see(view, ...args)));
    await shared('00:29', [0, 0]);
    for (const view of views) assert.equal(await view.page.locator('#individualSkills').isVisible(), true);
    await Promise.all(views.map(assertReadOnlyControls));
    for (const view of views) {
      assert.equal(await view.page.locator('.scoreboard .club:not(.away) strong').textContent(), teams[0]);
      assert.equal(await view.page.locator('.scoreboard .club.away strong').textContent(), teams[1]);
    }
    assert.match(await home.page.locator('.scoreboard .club:not(.away) small').textContent(), /SENİN TAKIMIN/);
    assert.match(await away.page.locator('.scoreboard .club.away small').textContent(), /SENİN TAKIMIN/);

    show(1);
    await shared('00:30', [0, 0]);
    await home.page.locator(panel).waitFor({ state: 'visible' });
    assert.match(await home.page.locator('[data-kick-kind]').innerText(), /Penaltı/);
    assert.equal(await away.page.locator(panel).isVisible(), false);
    await home.page.locator('[data-kick-input="power"]').fill('76');
    await home.page.locator('[data-kick-next]').click();
    await home.page.locator('[data-kick-ball]').press('ArrowDown');
    // New JSON objects for the same decision must preserve the manager's
    // in-progress selection across more than one polling cycle.
    for (let poll = 0; poll < 2; poll++) {
      await home.page.waitForResponse(response => response.ok() && response.url().includes(endpoint + '?round='));
    }
    assert.equal(await home.page.locator('[data-kick-input="contactY"]').inputValue(), '-5');
    assert.equal(await home.page.locator('[data-kick-strike]').isVisible(), true);
    await shared('00:30', [0, 0]);
    await submit(home, '[data-kick-strike]');
    await shared('00:31', [1, 0], 'Ev sahibi golü');
    assert.deepEqual(accepted, [{ side: 0, round, id: 41, input: { angle: 0, power: .76, contactX: 0, contactY: -.05 } }]);
    assert.equal(await home.page.locator(panel).isVisible(), false);
    await assertReadOnlyControls(home);

    show(3);
    await shared('00:42', [1, 0]);
    await away.page.locator(panel).waitFor({ state: 'visible' });
    assert.match(await away.page.locator('[data-kick-kind]').innerText(), /Korner/);
    assert.equal(await home.page.locator(panel).isVisible(), false);
    await submit(away, '[data-kick-auto]');
    await shared('00:43', [1, 1], 'Deplasman golü');
    assert.deepEqual(accepted[1], { side: 1, round, id: 42, input: null });

    show(5);
    await shared('05:00', [1, 1], 'Son düdük');
    for (const view of views) {
      assert.equal(await view.page.locator('#finishScreen').isVisible(), true);
      assert.match(await view.page.locator('#finishScore').textContent(), /1\s*[–-]\s*1/);
      assert.equal(await view.page.locator(panel).isVisible(), false);
      assert.deepEqual(await view.page.locator('#individualSkills div b').allTextContents(),
        Object.values(skillTotals).map(String));
      assert.deepEqual(view.errors, []);
    }
    const timelines = await Promise.all(views.map(view => view.page.locator('#eventList .incident b').allTextContents()));
    assert.deepEqual(timelines[0], timelines[1]);
    assert.equal(timelines[0].filter(title => title === 'Ev sahibi golü').length, 1);
    assert.ok(calls.some(call => call.side === 0 && call.method === 'GET'));
    assert.ok(calls.some(call => call.side === 1 && call.method === 'GET'));
    assert.equal(calls.some(call => call.side < 0), false, 'credentials travel in the Authorization header');
    assert.equal(calls.some(call => tokens.some(token => call.url.includes(token))), false, 'credentials never appear in a URL');
    await home.page.locator('#finishScreen a[href="league.html"]').click();
    await home.page.locator('#results .result-row').waitFor({ state: 'visible' });
    assert.equal(await home.page.locator('#results .result-row b').textContent(), '1 – 1');
    await Promise.all(views.map(view => view.context.close()));
    console.log('Live match browser: both sessions shared score, clock, skill counts and timeline, with independent kick controls.');
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
