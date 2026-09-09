import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import vm from 'node:vm';
import { build } from 'esbuild';

const source = await readFile(new URL('../src/content/application-reporter.ts', import.meta.url), 'utf8');
const { outputFiles } = await build({
  stdin: { contents: source + '\nexport { matchTask, buildPanel, api };',
    resolveDir: fileURLToPath(new URL('../src/content/', import.meta.url)), loader: 'ts' },
  bundle: true, platform: 'node', format: 'cjs', write: false,
});

function harness(href, document = {}) {
  const context = {
    module: { exports: {} }, exports: {}, URL, location: new URL(href),
    document: { readyState: 'loading', title: 'Acme Careers', addEventListener() {}, ...document },
    setTimeout() {},
  };
  vm.runInNewContext(outputFiles[0].text, context);
  return { ...context.module.exports, location: context.location };
}

function matchOn(href, tasks) {
  return harness(href).matchTask(tasks);
}

const first = { job_id: 1, apply_url: 'https://jobs.lever.co/acme/RoleA', company: 'Acme' };
const second = { job_id: 2, apply_url: 'https://jobs.lever.co/acme/RoleB', company: 'Acme' };

test('same ATS host selects only the exact queued job', () => {
  assert.equal(matchOn(second.apply_url, [first, second]), second);
});

test('unrelated pages and unknown redirects do not match host or company', () => {
  for (const href of [
    'https://jobs.lever.co/other/RoleA',
    'https://jobs.lever.co/acme/RoleC',
    'https://jobs.lever.co/acme/RoleA/apply',
    'https://careers.example/acme/RoleA',
  ]) assert.equal(matchOn(href, [first, second]), null, href);
});

test('fragments do not change job identity', () => {
  const task = { ...first, apply_url: first.apply_url + '#description' };
  assert.equal(matchOn(first.apply_url + '#application', [task]), task);
});

test('identity query parameters distinguish jobs and remain case sensitive', () => {
  const a = { ...first, apply_url: 'https://careers.example/apply?jobId=RoleA' };
  const b = { ...second, apply_url: 'https://careers.example/apply?jobId=RoleB' };
  assert.equal(matchOn(b.apply_url, [a, b]), b);
  assert.equal(matchOn('https://careers.example/apply?jobId=roleA', [a]), null);
  assert.equal(matchOn('https://careers.example/apply', [a, b]), null);
});

test('path case remains part of job identity', () => {
  assert.equal(matchOn('https://jobs.lever.co/acme/rolea', [first]), null);
});

test('malformed and empty queue URLs cannot match a company title', () => {
  assert.equal(matchOn(first.apply_url, [
    { ...first, apply_url: 'not a URL' },
    { ...second, apply_url: '' },
  ]), null);
});

test('reporting requires a click while the same job URL is still open', async () => {
  for (const navigated of [false, true]) {
    let panel;
    const reporter = harness(first.apply_url, {
      getElementById: () => null,
      createElement: () => ({
        style: {}, append(...children) { this.children = children; },
        remove() { this.removed = true; },
      }),
      body: { appendChild(element) { panel = element; } },
    });
    const reports = [];
    reporter.api.reportApplied = async report => {
      reports.push(report);
      return { job_status: 'applied' };
    };
    reporter.buildPanel(first);
    assert.equal(reports.length, 0);
    if (navigated) reporter.location.href = second.apply_url;
    await panel.children.at(-1).onclick();
    assert.equal(reports.length, navigated ? 0 : 1);
    if (navigated) assert.equal(panel.removed, true);
    else assert.equal(reports[0].job_id, first.job_id);
  }
});
