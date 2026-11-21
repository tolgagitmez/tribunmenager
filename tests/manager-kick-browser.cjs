'use strict';

// Run with CHROMIUM=/path/to/chromium node tests/manager-kick-browser.cjs.
// The fixture only places players for a restart. The real page runs the clock,
// draws the pitch and wires controls to the real match engine.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { createServer } = require('../tools/serve-character-viewer.cjs');

const output = path.resolve(__dirname, '../work/kick-browser');
const panelId = '#managerKickPanel';
const aimId = '#managerKickAim';
const panelInput = name => `${panelId} [data-kick-input="${name}"]`;

async function openMatch(browser, url, options) {
  const page = await browser.newPage({ reducedMotion: 'reduce', ...options });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    const pathname = new URL(response.url()).pathname;
    // A local install without the optional design assets uses fallback fonts.
    if (response.status() >= 400 && !/^\/assets\/(?:ui\/|face\d+\.png$)/.test(pathname)) {
      errors.push(`${response.status()} ${pathname}`);
    }
  });
  await page.addInitScript(() => {
    window.MATCH_CFG = { seed: 21, matchMinutes: 5 };
    // Advance using the page's own fixed-step adapter so the browser checks
    // behave identically on fast GPUs and software WebGL in CI.
    window.requestAnimationFrame = () => 1;
    let football;
    Object.defineProperty(window, 'TribunFootball', {
      get: () => football,
      set(api) {
        football = api;
        api.Match = class extends api.Match {
          constructor(...args) {
            super(...args);
            window.kickBrowserMatch = this;
          }
          resolveManagerKick(id, input) {
            const accepted = super.resolveManagerKick(id, input);
            window.kickBrowserResolution = { id, input, accepted };
            return accepted;
          }
        };
      }
    });
  });
  await page.goto(url, { waitUntil: 'load' });
  assert.deepEqual(errors, []);
  await page.waitForFunction(() => window.kickBrowserMatch?.players.length === 23, null, { polling: 100 });
  await page.waitForFunction(() => {
    const probe = window.TRIBUN_MATCH_TEST.renderProbe();
    return probe.webgl && probe.active === 22 && probe.bridge.players >= 22;
  }, null, { polling: 150, timeout: 45000 });
  assert.deepEqual(errors, []);
  return { page, errors };
}

async function readyRestart(page, kind, team = 0) {
  const state = await page.evaluate(({ kind, team }) => {
    const match = window.kickBrowserMatch;
    const api = window.TRIBUN_MATCH_TEST;
    const side = match.direction(team);
    const spot = kind === 'corner' ? { x: side * 51.8, z: side * 33.8 } : { x: side * 41, z: 0 };
    match.setRestart(kind, team, spot);
    match.restart.clock = 0;
    for (let step = 0; step < 90 && match.restart && !match.pendingManagerKick; step++) {
      // Put the players on their normal legal tactical targets so readiness is
      // deterministic without waiting for both teams to run the full pitch.
      match.plan();
      for (const [player, target] of match.targets) {
        Object.assign(player, { x: target.x, z: target.z, vx: 0, vz: 0, speed: 0 });
      }
      api.advance(1 / 60);
    }
    api.renderProbe();
    return { pending: match.pendingManagerKick, restart: match.restart?.kind, time: match.time, clock: match.clockState().display };
  }, { kind, team });
  if (team === 0) {
    assert.equal(state.pending?.kind, kind, JSON.stringify(state));
    await page.locator(panelId).waitFor({ state: 'visible' });
  } else {
    assert.equal(state.pending, null);
    assert.equal(await page.locator(panelId).isVisible(), false);
  }
  return state;
}

async function advance(page, seconds) {
  return page.evaluate(seconds => {
    const match = window.kickBrowserMatch;
    window.TRIBUN_MATCH_TEST.advance(seconds);
    return { time: match.time, clock: match.clockState().display, shots: match.shots.slice(), crosses: match.telemetry.crosses, pending: match.pendingManagerKick };
  }, seconds);
}

async function desktopPenalty(browser, url) {
  const { page, errors } = await openMatch(browser, url, { viewport: { width: 1280, height: 900 } });
  try {
    const { pending, time, clock } = await readyRestart(page, 'penalty');
    assert.match(await page.locator('[data-kick-kind]').innerText(), /Penaltı/);
    assert.match(await page.locator('[data-kick-skill]').innerText(), /\d+ \/ 100/);
    assert.equal(await page.locator('#playButton').isDisabled(), true);
    const frozen = await advance(page, 3);
    assert.equal(frozen.time, time);
    assert.equal(frozen.clock, clock);
    assert.equal(frozen.pending.id, pending.id);

    const direction = page.locator(panelInput('direction'));
    const power = page.locator(panelInput('power'));
    const aim = page.locator(aimId);
    await aim.scrollIntoViewIfNeeded();
    const box = await aim.boundingBox();
    assert.ok(box?.width > 200 && box.height > 150);
    assert.ok(await aim.evaluate(canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      for (let index = 0; index < pixels.length; index += 4) {
        if (pixels[index] === 216 && pixels[index + 1] === 255 && pixels[index + 2] === 101) return true;
      }
      return false;
    }), 'the projected aim arrow must be painted');
    await page.mouse.move(box.x + box.width * .5, box.y + box.height * .63);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * .69, box.y + box.height * .49, { steps: 4 });
    await page.mouse.up();
    const aimedDirection = Number(await direction.inputValue());
    assert.ok(aimedDirection > 0, `drag right should aim right, got ${aimedDirection}`);
    await direction.press('ArrowLeft');
    const expectedDirection = Number(await direction.inputValue());
    assert.equal(expectedDirection, aimedDirection - 1);
    await power.press('End');
    assert.equal(await power.inputValue(), '100');
    await power.press('ArrowLeft');
    assert.equal(await power.inputValue(), '99');
    // Return to the suggested heading for the preview.
    await direction.fill('4');
    assert.equal(await direction.inputValue(), '4');
    await page.screenshot({ path: path.join(output, 'desktop-aim.png'), animations: 'disabled' });

    const ball = page.locator('[data-kick-ball]');
    await page.locator('[data-kick-next]').click();
    assert.equal(await page.locator('[aria-current="step"]').getAttribute('data-kick-step'), '2');
    assert.equal(await aim.isVisible(), false);
    await ball.press('ArrowRight');
    await ball.press('Shift+ArrowDown');
    assert.equal(await page.locator(panelInput('contactX')).inputValue(), '5');
    assert.equal(await page.locator(panelInput('contactY')).inputValue(), '-20');
    await page.locator('[data-kick-back]').click();
    assert.equal(await direction.inputValue(), '4');
    assert.equal(await power.inputValue(), '99');
    await page.locator('[data-kick-next]').click();
    assert.equal(await page.locator(panelInput('contactY')).inputValue(), '-20');
    await page.locator('[data-kick-strike]').click();
    assert.equal(await page.locator(panelId).isVisible(), false);
    const resolution = await page.evaluate(() => window.kickBrowserResolution);
    assert.deepEqual(resolution, {
      id: pending.id, accepted: true, input: { angle: pending.angle + 4 * Math.PI / 180, power: .99, contactX: .05, contactY: -.2 }
    });
    const resumed = await advance(page, 3);
    assert.ok(resumed.time > time);
    assert.ok(resumed.shots[0] > 0, 'manual penalty must release a real shot');
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

async function mobileCorner(browser, url) {
  const { page, errors } = await openMatch(browser, url, {
    viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1
  });
  try {
    const { pending, time } = await readyRestart(page, 'corner');
    assert.match(await page.locator('[data-kick-kind]').innerText(), /Korner/);
    const aim = page.locator(aimId);
    await aim.scrollIntoViewIfNeeded();
    const box = await aim.boundingBox();
    await aim.tap({ position: { x: box.width * .6, y: box.height * .48 } });
    assert.notEqual(await page.locator(panelInput('direction')).inputValue(), '0');
    await page.locator('[data-kick-next]').tap();
    const ball = page.locator('[data-kick-ball]');
    const ballBox = await ball.boundingBox();
    assert.ok(ballBox.width >= 130 && Math.abs(ballBox.width - ballBox.height) < 1);
    await ball.tap({ position: { x: ballBox.width * .65, y: ballBox.height * .72 } });
    assert.ok(Number(await page.locator(panelInput('contactX')).inputValue()) > 20);
    assert.ok(Number(await page.locator(panelInput('contactY')).inputValue()) < -30);
    await page.screenshot({ path: path.join(output, 'mobile-contact.png'), animations: 'disabled' });
    await page.locator('[data-kick-auto]').tap();
    assert.deepEqual(await page.evaluate(() => window.kickBrowserResolution), { id: pending.id, input: undefined, accepted: true });
    assert.equal(await page.locator(panelId).isVisible(), false);
    const resumed = await advance(page, 3);
    assert.ok(resumed.time > time);
    assert.ok(resumed.crosses > 0, 'delegated corner must release a real cross');
    await readyRestart(page, 'penalty', 1);
    assert.ok((await advance(page, 3)).shots[1] > 0, 'opponent penalty should play automatically');
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

async function main() {
  await fs.mkdir(output, { recursive: true });
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM, headless: true,
      args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox']
    });
    const url = `http://127.0.0.1:${server.address().port}/match.html`;
    await desktopPenalty(browser, url);
    await mobileCorner(browser, url);
    console.log('Manager kick browser: desktop penalty and mobile corner passed with WebGL, frozen clock and real releases.');
    console.log(`Evidence: ${output}`);
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
