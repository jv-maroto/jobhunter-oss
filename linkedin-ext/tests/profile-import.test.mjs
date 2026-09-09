import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import vm from 'node:vm';

const readBundle = name => readFile(new URL(`../dist/${name}.js`, import.meta.url), 'utf8');
const profile = await readBundle('content/linkedin-profile');
const importer = await readBundle('content/linkedin-profile-import');
const postHelper = await readBundle('content/linkedin-post-helper');
const worker = await readBundle('background/service-worker');
const profileUrl = 'https://www.linkedin.com/in/test-person/';
const event = { addListener() {} };

function mountImporter({ legacy = false, name = 'Test Person', reply = { success: true } } = {}) {
  const messages = [];
  const button = { style: {} };
  const nameNode = { textContent: name };
  const headline = { textContent: 'Data Engineer' };
  const verification = { querySelector: () => nameNode };
  let parent = verification;
  for (let i = 0; i < 4; i++) parent = parent.parentElement = {};
  parent.querySelector = () => headline;
  const document = {
    readyState: 'complete',
    getElementById: () => null,
    createElement: () => button,
    body: { appendChild() {} },
    querySelectorAll: () => [],
    querySelector(selector) {
      if (legacy && selector === 'h1') return nameNode;
      if (legacy && selector === '.text-body-medium.break-words') return headline;
      if (!legacy && selector.startsWith('a[componentkey')) return verification;
      return null;
    },
  };
  const context = vm.createContext({
    document, location: new URL(profileUrl + '?trk=profile#about'),
    console: { log() {}, debug() {} }, window: { addEventListener() {} }, setInterval() {},
    chrome: { runtime: { onMessage: event, async sendMessage(value) {
      messages.push(value);
      return reply;
    } } },
    fetch() { assert.fail('Content script must not fetch the backend'); },
  });
  const globals = Object.keys(context);
  vm.runInContext(profile, context);
  vm.runInContext(importer, context);
  document.getElementById = () => ({});
  vm.runInContext(postHelper, context);
  assert.deepEqual(Object.keys(context), globals, 'Bundles must not leak globals into sibling scripts');
  return { button, messages };
}

for (const legacy of [false, true]) {
  test(`profile import coexists with sibling scripts (${legacy ? 'legacy' : 'current'} selectors)`, async () => {
    const { button, messages } = mountImporter({ legacy });
    assert.equal(messages.length, 0, 'Import must wait for a user click');
    await button.onclick();
    assert.match(button.textContent, /Importado/);
    assert.equal(button.disabled, true);
    assert.equal(messages.length, 1);
    assert.equal(messages[0].type, 'IMPORT_LINKEDIN_PROFILE');
    assert.equal(messages[0].payload.name, 'Test Person');
    assert.equal(messages[0].payload.headline, 'Data Engineer');
    assert.equal(messages[0].payload.profile_url, profileUrl, 'Strip query and fragment');
  });
}

test('missing profile name stops before sending and allows retry', async () => {
  const { button, messages } = mountImporter({ name: '' });
  await button.onclick();
  assert.equal(messages.length, 0);
  assert.equal(button.disabled, false);
  assert.match(button.textContent, /No se encontró el nombre/);
});

test('background failure is shown and allows retry', async () => {
  const { button } = mountImporter({ reply: { success: false, error: 'HTTP 503' } });
  await button.onclick();
  assert.equal(button.disabled, false);
  assert.match(button.textContent, /HTTP 503/);
  assert.doesNotMatch(button.textContent, /Importado/);
});

function startWorker(fetch, backendUrl = 'http://localhost:8000') {
  let listener;
  const chrome = {
    runtime: { id: 'test-extension', onInstalled: event, onStartup: event,
      onMessage: { addListener(fn) { listener = fn; } } },
    alarms: { onAlarm: event },
    storage: { onChanged: event, local: {
      async get(key) {
        return key === 'jobhunter_ext_token'
          ? { [key]: 'test-token' } : { settings: { backend_url: backendUrl } };
      },
    } },
  };
  vm.runInNewContext(worker, { chrome, URL, console, fetch });
  return (sender, payload) => new Promise(resolve => {
    assert.equal(listener({ type: 'IMPORT_LINKEDIN_PROFILE', payload }, sender, resolve), true);
  });
}

test('worker posts the profile through the configured backend', async () => {
  const requests = [];
  const dispatch = startWorker(async (url, init) => {
    requests.push({ url, init });
    return { ok: true, status: 200, json: async () => ({ ok: true }) };
  }, 'http://127.0.0.1:8001///');
  const payload = { name: 'Test Person', profile_url: profileUrl };
  const response = await dispatch({ id: 'test-extension', url: profileUrl + '?trk=profile#about' }, payload);
  assert.equal(response.success, true);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, 'http://127.0.0.1:8001/onboarding/linkedin/from-extension');
  assert.equal(requests[0].init.method, 'POST');
  assert.deepEqual(JSON.parse(requests[0].init.body), payload);
  assert.equal(requests[0].init.headers['X-Extension-Token'], 'test-token');
});

test('worker rejects invalid senders and mismatched profile data without fetching', async () => {
  const dispatch = startWorker(() => assert.fail('Invalid sender or payload must not reach the backend'));
  const sender = { id: 'test-extension', url: profileUrl };
  const payload = { name: 'Test Person', profile_url: profileUrl };
  for (const [invalidSender, invalidPayload] of [
    [{ ...sender, id: 'other-extension' }, payload],
    [{ ...sender, url: 'http://www.linkedin.com/in/test-person/' }, payload],
    [{ ...sender, url: 'https://untrusted.example/in/test-person/' }, payload],
    [{ ...sender, url: 'https://www.linkedin.com.evil.example/in/test-person/' }, payload],
    [{ ...sender, url: 'https://www.linkedin.com:8443/in/test-person/' }, payload],
    [{ ...sender, url: 'https://www.linkedin.com/feed/' }, payload],
    [{ ...sender, url: 'https://www.linkedin.com/in/test-person/edit/' }, payload],
    [{ ...sender, url: undefined }, payload],
    [{ ...sender, url: 'invalid' }, payload],
    [sender, { ...payload, profile_url: 'https://www.linkedin.com/in/someone-else/' }],
    [sender, { ...payload, name: ' ' }],
    [sender, undefined],
  ]) {
    const response = await dispatch(invalidSender, invalidPayload);
    assert.equal(response.success, false);
  }
});

test('worker returns backend failures instead of claiming success', async () => {
  const dispatch = startWorker(async () => ({
    ok: false, status: 503, statusText: 'Service Unavailable', text: async () => '',
  }));
  const response = await dispatch(
    { id: 'test-extension', url: profileUrl }, { name: 'Test Person', profile_url: profileUrl },
  );
  assert.equal(response.success, false);
  assert.match(response.error, /HTTP 503/);
});
