import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import vm from 'node:vm';
import { build } from 'esbuild';

const source = await readFile(new URL('../src/content/application-autofill.ts', import.meta.url), 'utf8');
const { outputFiles } = await build({
  stdin: { contents: source + '\nexport { matchRule, valueForRule, loadProfile };',
    resolveDir: fileURLToPath(new URL('../src/content/', import.meta.url)), loader: 'ts' },
  bundle: true, platform: 'node', format: 'cjs', write: false,
});

function harness() {
  let requests = 0;
  const window = { addEventListener() {} };
  window.top = window;
  const context = {
    module: { exports: {} }, exports: {}, window, document: { body: null },
    location: { host: 'test.invalid' }, console, setInterval() {},
    chrome: { runtime: { id: 'test-extension', async sendMessage() {
      return { success: true, data: { full_name: `Profile version ${++requests}` } };
    } } },
  };
  vm.runInNewContext(outputFiles[0].text, context);
  return context.module.exports;
}

test('permission answers require an explicit fact for the requested country', () => {
  const { matchRule, valueForRule } = harness();
  const ch = matchRule(['Are you authorized to work in Switzerland?']);
  const eu = matchRule(['Are you legally able to work in the EU?']);
  assert.equal(valueForRule(ch, { work_authorization_eu: true }), null);
  assert.equal(valueForRule(ch, { work_authorization_ch: true }), 'Yes');
  assert.equal(valueForRule(ch, { work_authorization_ch: false }), 'No');
  assert.equal(valueForRule(eu, {}), null);
  assert.equal(valueForRule(eu, { work_authorization_eu: false }), 'No');
  assert.equal(valueForRule(matchRule(['US work authorization']), {}), null);
  assert.equal(valueForRule(matchRule(['Do you require sponsorship for US employment?']), {}), null);
});

test('autofill does not invent experience, citizenship, residence or permits', () => {
  const { matchRule, valueForRule } = harness();
  for (const question of [
    'Do you have at least 4 years of experience?',
    'Do you have 10 years of experience in data science?',
    'Are you currently based in France?',
    'Do you have a Swiss residence permit?',
    'Are you an EU citizen?',
  ]) {
    const rule = matchRule([question]);
    assert.equal(rule && valueForRule(rule, { work_authorization_eu: true, years_experience: 12 }), null, question);
  }
});

test('each autofill request reads the current backend profile', async () => {
  const { loadProfile } = harness();
  assert.equal((await loadProfile()).full_name, 'Profile version 1');
  assert.equal((await loadProfile()).full_name, 'Profile version 2');
});
