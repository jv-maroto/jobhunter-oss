import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInThisContext } from 'node:vm';
import ts from 'typescript';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

function loadTypeScript(relativePath, imports = {}) {
  const url = new URL(relativePath, import.meta.url);
  const { outputText } = ts.transpileModule(readFileSync(url, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
    fileName: url.pathname,
  });
  const exports = {};
  const require = createRequire(url);
  runInThisContext(`(function(require, exports) { ${outputText}\n})`, { filename: url.pathname })((id) => imports[id] ?? require(id), exports);
  return exports;
}

const utils = loadTypeScript('../lib/utils.ts');
const { Button } = loadTypeScript('../components/ui/button.tsx', { '@/lib/utils': utils });
for (const shimmer of [false, true]) {
  const buttonLink = renderToStaticMarkup(createElement(Button, { asChild: true, shimmer }, createElement('a', { href: '/jobs' }, 'Jobs')));
  assert.match(buttonLink, /^<a /);
  assert.match(buttonLink, /href="\/jobs"/);
  assert.match(buttonLink, /Jobs<\/a>$/);
}
assert.match(renderToStaticMarkup(createElement(Button, {}, 'Save')), /^<button /);
const { formatSalary } = utils;
const { JOB_TRACK_LABELS } = loadTypeScript('../lib/types.ts');

assert.equal(formatSalary(100000, 130000, 'CHF', 'year'), '100k–130k CHF / year');
assert.equal(formatSalary(8000, 9000, 'CHF', 'month'), '8k–9k CHF / month');
assert.equal(formatSalary(95, 120, 'CHF', 'hour'), '95–120 CHF / hour');
assert.equal(formatSalary(undefined, 60000, 'EUR', 'year'), '≤60k € / year');
assert.equal(formatSalary(40000, undefined, 'USD', 'year'), '40k+ USD / year');
assert.equal(formatSalary(undefined, undefined, 'CHF'), '—');
assert.equal(formatSalary(0, 0, 'CHF'), '0 CHF');
assert.equal(formatSalary(Number.NaN, 50000, null), '≤50k currency unknown');
assert.deepEqual(Object.keys(JOB_TRACK_LABELS), ['data_engineer', 'data_analyst', 'data_scientist', 'analytics_eng', 'bi', 'ai_ml', 'quant', 'dev', 'sysadmin']);
const { ScoreBadge } = loadTypeScript('../components/jobs/ScoreBadge.tsx', { '@/lib/utils': utils });
const reason = 'Heuristic fit estimate: matched Python and SQL';
const heuristicMarkup = renderToStaticMarkup(createElement(ScoreBadge, { score: 71, reason }));
assert.match(heuristicMarkup, />Heuristic<\/span>/);
assert.ok(heuristicMarkup.includes(`title="${reason}"`));
assert.doesNotMatch(renderToStaticMarkup(createElement(ScoreBadge, { score: 71, reason: 'Matches Python and SQL' })), />Heuristic<\/span>/);
assert.match(renderToStaticMarkup(createElement(ScoreBadge, { score: 71 })), /estimate, not hiring probability/);
assert.equal(utils.apiDate('2026-04-08T11:30:00')?.toISOString(), '2026-04-08T11:30:00.000Z');
assert.equal(utils.apiDate('2026-04-08T13:30:00+02:00')?.toISOString(), '2026-04-08T11:30:00.000Z');
assert.equal(utils.apiDate('invalid'), null);
assert.equal(utils.localDateTimeInput(null), '');
const localInput = utils.localDateTimeInput('2026-04-08T11:30:00Z');
assert.equal(new Date(localInput).toISOString(), '2026-04-08T11:30:00.000Z');
assert.equal(utils.publicJobUrl('https://example.test/jobs/1'), 'https://example.test/jobs/1');
for (const url of ['javascript:alert(1)', 'file:///etc/passwd', 'https://user:password@example.test', 'bad url']) assert.equal(utils.publicJobUrl(url), null);
assert.equal(utils.sourceFriction('linkedin').level, 'medium');
assert.doesNotMatch(utils.sourceFriction('linkedin').label, /easy/i);

const client = loadTypeScript('../lib/api.ts');
const realFetch = globalThis.fetch;
try {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ loc: ['body', 'title'], msg: 'Field required' }] }), { status: 422 });
  await assert.rejects(client.api('/jobs/import'), (error) => error.status === 422 && error.message === 'title: Field required');
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Prepare a new version' }), { status: 409 });
  await assert.rejects(client.apiUpload('/upload', new FormData()), (error) => error.status === 409 && error.message === 'Prepare a new version');
  globalThis.fetch = async () => new Response('<html>Unavailable</html>', { status: 503 });
  await assert.rejects(client.api('/jobs'), (error) => error.status === 503 && error.message === 'Request failed (503)');
  globalThis.fetch = async () => new Response(null, { status: 204 });
  assert.equal(await client.api('/jobs/1', { method: 'DELETE' }), null);
} finally {
  globalThis.fetch = realFetch;
}
console.log('Profile and application support regression checks passed.');
