// Node 22+ and an installed Chrome. Run against an isolated --browser HTTP test.
// node tests/e2e/browser-gallery.mjs http://127.0.0.1:39082
// After WAIT start-upload, create that file in the HTTP test's run directory.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setTimeout as sleep} from 'node:timers/promises';

const url = new URL(process.argv[2]);
assert.equal(url.hostname, '127.0.0.1', 'Use a locally isolated HTTP endpoint');
const base = url.origin;
const filename = '<b>demo & [sample].mp4';
const profile = await mkdtemp(join(tmpdir(), 'mediadock-browser.'));
const binary = process.env.CHROME_BIN ||
  (process.platform === 'darwin' ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : 'google-chrome');
const browser = spawn(binary, [
  `--user-data-dir=${profile}`, '--remote-debugging-port=0', '--no-first-run',
  '--no-default-browser-check', '--disable-background-networking', '--disable-sync',
  '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
  '--window-size=1120,860', ...(process.env.CHROME_HEADLESS === '1' ? ['--headless'] : []), 'about:blank'
], {stdio: 'ignore'});
const browserExited = once(browser, 'exit');
browserExited.catch(() => {});
let cdp;

async function waitUntil(description, check, timeout = 12000) {
  const deadline = performance.now() + timeout;
  let lastError;
  while (performance.now() < deadline) {
    try {
      const value = await check();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(100);
  }
  throw new Error(`Timed out waiting for ${description}`, {cause: lastError});
}

try {
  const port = await Promise.race([
    waitUntil('isolated Chrome debugger', async () => (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]),
    browserExited.then(([code, signal]) => { throw new Error(`Chrome exited during startup (${code}, ${signal})`); })
  ]);
  const describe = async path => (await fetch(`http://127.0.0.1:${port}/json/${path}`, {signal: AbortSignal.timeout(3000)})).json();
  const {Browser: version} = await describe('version');
  const target = (await describe('list')).find(item => item.type === 'page');
  cdp = new WebSocket(target.webSocketDebuggerUrl);
  await Promise.race([
    once(cdp, 'open'),
    sleep(5000, undefined, {ref: false}).then(() => { throw new Error('Chrome DevTools connection timed out'); })
  ]);
  let nextId = 0;
  const pending = new Map();
  const thumbnailResponses = [];
  cdp.addEventListener('message', ({data}) => {
    const {id, method, params, result, error} = JSON.parse(data);
    if (method === 'Network.responseReceived' && params.response.url.endsWith('/thumbnail')) {
      thumbnailResponses.push(params.response.status);
    }
    if (!pending.has(id)) return;
    pending.get(id)(error, result);
    pending.delete(id);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Chrome DevTools ${method} timed out`));
    }, 4000);
    pending.set(id, (error, result) => {
      clearTimeout(timer);
      if (error) reject(new Error(error.message));
      else resolve(result);
    });
    cdp.send(JSON.stringify({id, method, params}));
  });
  const evaluate = async expression => {
    const {result, exceptionDetails} = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    assert.ok(!exceptionDetails, exceptionDetails?.text);
    return result.value;
  };
  const waitFor = (description, expression, timeout) => waitUntil(description, () => evaluate(expression), timeout);

  await send('Network.enable');
  await send('Page.bringToFront');
  await send('Emulation.setFocusEmulationEnabled', {enabled: true});
  await send('Page.navigate', {url: base});
  await waitFor('initial empty gallery',
    "document.querySelector('.empty')?.textContent.startsWith('No processed videos')");

  // Simulate an unavailable API in this temporary tab and allow polling to recover.
  await send('Network.setBlockedURLs', {urls: [`${base}/api/*`]});
  await evaluate("document.getElementById('refresh').click()");
  await waitFor('unavailable message',
    "document.querySelector('.empty')?.textContent.startsWith('Unable to load videos')");
  await send('Network.setBlockedURLs', {urls: []});
  await waitFor('empty gallery restored after failed fetch',
    "document.querySelector('#health')?.textContent === 'Consumer online' && document.querySelector('.empty')?.textContent.startsWith('No processed videos')");
  console.log('PASS H07 empty gallery recovers after an API failure');
  console.log('WAIT start-upload');
  await waitFor('upload entering processing',
    "fetch('/api/stats', {cache: 'no-store'}).then(r => r.json()).then(s => s.active_workers === 1 && s.ready_total === 0)", 75000);
  await send('Page.reload', {ignoreCache: true});
  await waitFor('reopened gallery showing processing without a card',
    "document.querySelector('#workers-count')?.textContent === '1' && !document.querySelector('.video-card')");
  await waitFor('automatically refreshed card and READY counter',
    "document.querySelector('#ready-count')?.textContent === '1' && !!document.querySelector('.video-card')");
  console.log('PASS H07 reload during processing and automatic READY refresh');

  assert.equal(await evaluate("document.querySelector('.video-name').textContent"), filename);
  assert.equal(await evaluate("document.querySelector('.video-name').childElementCount"), 0);
  console.log('PASS H08 filename rendered as literal text');

  const point = await evaluate(`(() => {
    const card = document.querySelector('.video-card');
    card.scrollIntoView({block: 'center'});
    const rect = card.getBoundingClientRect();
    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
  })()`);
  try {
    await waitFor('loaded JPEG thumbnail', "document.querySelector('.video-card img')?.naturalWidth > 0");
  } catch (error) {
    const image = await evaluate(`(() => {
      const image = document.querySelector('.video-card img');
      return {currentSrc: image.currentSrc, complete: image.complete, rect: image.getBoundingClientRect().toJSON(),
        viewport: [innerWidth, innerHeight], visibility: document.visibilityState};
    })()`);
    throw new Error(JSON.stringify({image, thumbnailResponses}), {cause: error});
  }
  await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: 5, y: 5});
  await send('Input.dispatchMouseEvent', {type: 'mouseMoved', ...point});
  const previewDuration = await waitFor('muted preview playback', `(() => {
    const video = document.querySelector('.video-card video');
    return video.muted && video.currentSrc.endsWith('/preview') &&
      video.classList.contains('playing') && !video.paused && video.currentTime > 0.1 && video.duration;
  })()`);
  assert.ok(previewDuration <= 10);
  await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: 5, y: 5});
  await waitFor('preview stopped on pointer exit',
    "document.querySelector('.video-card video').paused && !document.querySelector('.video-card video').hasAttribute('src')");
  console.log(`PASS H05 muted ${previewDuration}s hover preview played and stopped on exit`);

  for (const type of ['mousePressed', 'mouseReleased']) {
    await send('Input.dispatchMouseEvent', {type, ...point, button: 'left', clickCount: 1});
  }
  const fullDuration = await waitFor('full-video playback', `(() => {
    const video = document.querySelector('#full-player');
    return document.querySelector('dialog').open && video.currentSrc.endsWith('/stream') &&
      !video.paused && video.currentTime > 0.1 && video.duration;
  })()`);
  assert.ok(fullDuration > 12);
  assert.equal(await evaluate("document.querySelector('#modal-title').textContent"), filename);
  await evaluate("document.querySelector('#full-player').currentTime = 11.5");
  const playedAt = await waitFor('playback advancing after seeking past 10 seconds', `(() => {
    const video = document.querySelector('#full-player');
    return !video.seeking && !video.paused && video.currentTime > 11.65 && video.currentTime;
  })()`);
  for (const type of ['rawKeyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', {type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27});
  }
  await waitFor('Escape stops and closes player',
    "!document.querySelector('dialog').open && !document.querySelector('#full-player').hasAttribute('src')");
  console.log(`PASS H06 full ${fullDuration}s playback sought to 11.5s, advanced to ${playedAt.toFixed(2)}s and closed using Escape`);

  await send('Emulation.setDeviceMetricsOverride', {width: 390, height: 800, deviceScaleFactor: 1, mobile: false});
  const narrowLayout = await evaluate(`({
    columns: getComputedStyle(document.querySelector('#gallery')).gridTemplateColumns.split(' ').length,
    overflow: document.documentElement.scrollWidth > innerWidth
  })`);
  assert.deepEqual(narrowLayout, {columns: 1, overflow: false});
  console.log(`PASS responsive single-column layout in ${version} (${process.env.CHROME_HEADLESS === '1' ? 'headless' : 'headful'})`);
} finally {
  cdp?.close();
  browser.kill();
  await browserExited.catch(() => {});
  await rm(profile, {recursive: true, force: true});
}
