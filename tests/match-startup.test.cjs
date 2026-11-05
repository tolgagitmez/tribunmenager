'use strict';
// Real HTML/scripts over HTTP, with a deliberately unavailable WebGL context.
// Canvas calls are recorded; this checks integration, not rendered pixel quality.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { test } = require('node:test');
const { JSDOM, VirtualConsole } = require('jsdom');
const club = require('../club-data.js');

const root = path.resolve(__dirname, '..');

test('static local match starts, draws fallback, and preserves squad/tactics controls', async () => {
  const missing = [], errors = [], frames = [], draws = [];
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const file = path.resolve(root, '.' + pathname);
    if (!file.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return; }
    fs.readFile(file, (error, data) => {
      if (error) { missing.push(pathname); res.writeHead(404); res.end(); return; }
      const type = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css' }[path.extname(file)];
      res.setHeader('Content-Type', type || 'application/octet-stream');
      res.end(data);
    });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const config = { seed: 21, players: club.createRoster(), starters: club.starters, formation: '4-3-3', matchMinutes: 5,
    tactics: { passing: 'short', tempo: 47, onWin: 'retain', width: 'narrow' } };
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', error => {
    // A missing optional visual asset must not stop subsequent script execution.
    if (error.type !== 'resource-loading') errors.push(error.message);
  });
  let dom;
  try {
    dom = await JSDOM.fromURL(`http://127.0.0.1:${server.address().port}/match.html#${encodeURIComponent(JSON.stringify(config))}`, {
      resources: 'usable', runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole,
      beforeParse(window) {
        window.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
        const context = new Proxy({}, { get(object, name) {
          if (!(name in object)) object[name] = (...args) => { draws.push([name, args.length]); };
          return object[name];
        } });
        window.HTMLCanvasElement.prototype.getContext = kind => kind === '2d' ? context : null;
        window.HTMLCanvasElement.prototype.getBoundingClientRect = () => ({ width: 960, height: 540 });
      }
    });
    await new Promise((resolve, reject) => {
      if (dom.window.document.readyState === 'complete') { resolve(); return; }
      const timeout = setTimeout(() => reject(new Error('match HTML load timed out')), 10000);
      dom.window.addEventListener('load', () => { clearTimeout(timeout); resolve(); }, { once: true });
    });
    const window = dom.window, document = window.document, game = window.TRIBUN_MATCH_TEST;
    assert.deepEqual(errors, [], 'actual page scripts must initialize without errors');
    assert.ok(game, 'real presentation adapter exposes initialized match');
    let state = game.getState();
    assert.equal(state.players.filter(p => p.active && p.team === 0).length, 11);
    assert.equal(state.players[0].name, config.players[config.starters[0]].name);
    assert.equal(state.t[0].passing, 'short');
    assert.equal(state.t[0].tempo, 47);
    assert.equal(state.duration, 300);
    assert.equal(document.querySelector('.webgl').textContent, '2D YEDEK');
    assert.equal(document.getElementById('rigButton').disabled, true);
    assert.ok(frames.length, 'actual animation frame callback scheduled');
    frames.shift()(window.performance.now() + 16.7);
    assert.ok(draws.some(([method]) => method === 'arc'), 'actual stadium fallback draws players and ball');
    document.getElementById('playButton').click();
    const pausedAt = game.getState().time;
    game.advance(1);
    assert.equal(game.getState().time, pausedAt, 'pause stops simulation');
    document.getElementById('playButton').click();
    game.advance(5);
    state = game.getState();
    assert.ok(state.time > pausedAt + 4.9, 'resume advances real fixed-step simulation');
    assert.notEqual(document.getElementById('matchClock').textContent, '00:00');
    assert.equal(Number(document.getElementById('scoreHome').textContent), state.score[0]);
    assert.equal(Number(document.getElementById('scoreAway').textContent), state.score[1]);
    assert.ok(state.events.some(event => event.type === 'whistle'));
    document.getElementById('camButton').click();
    assert.match(document.getElementById('camButton').textContent, /Yakın/);
    document.getElementById('restartButton').click();
    assert.equal(game.getState().time, 0);
    assert.deepEqual(errors, []);
    console.log(`Static match integration: ${missing.length} optional asset request(s) missing; 2D canvas recorded, no GPU assertions.`);
  } finally {
    dom?.window.close();
    await new Promise(resolve => server.close(resolve));
  }
});
