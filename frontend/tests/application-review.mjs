import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInThisContext } from 'node:vm';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

function loadTypeScript(path, overrides) {
  const cache = new Map();
  function load(url) {
    if (cache.has(url.href)) return cache.get(url.href);
    const exports = {};
    cache.set(url.href, exports);
    const require = createRequire(url);
    const { outputText } = ts.transpileModule(readFileSync(url, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
      fileName: url.pathname,
    });
    runInThisContext(`(function(require, exports) { ${outputText}\n})`, { filename: url.pathname })((id) => {
      if (id in overrides) return overrides[id];
      if (!id.startsWith('@/')) return require(id);
      const base = new URL(`../${id.slice(2)}`, import.meta.url);
      return load(new URL(base.href + (existsSync(new URL(base.href + '.tsx')) ? '.tsx' : '.ts')));
    }, exports);
    return exports;
  }
  return load(new URL(path, import.meta.url));
}

const review = {
  application_id: 101, status: 'prepared', submitted_at: null,
  prepared_at: '2026-01-01T12:00:00Z',
  cv_url: '/applications/101/cv', cover_url: '/applications/101/cover',
  cv_source_filename: 'local/resume.pdf', cover_letter_content: '<script>Example letter</script>',
  job: { id: 1, title: 'Example role', company: 'Example employer', location: '',
    source_url: 'javascript:alert(1)', status: 'prepared', notes: 'Follow up after review' },
};
let listState = { data: { total: 2, items: [review, { ...review, application_id: null, job: { ...review.job, id: 2 } }] } };
let reviewState = { data: review, dataUpdatedAt: 9 };
let listQuery;
let mutationCalls = 0;
const links = [];
const idleMutation = () => ({ isPending: false, mutateAsync: async () => { mutationCalls++; return review; } });
const overrides = {
  'next/navigation': { useParams: () => ({ id: '101' }), useRouter: () => ({ push() {} }) },
  'next/link': ({ children, ...props }) => { links.push({ ...props }); delete props.onNavigate; return createElement('a', props, children); },
  '@/hooks/useApplications': {
    useApplications: (query) => { listQuery = query; return listState; },
    useApplication: () => reviewState,
    useApplicationVersions: () => ({ data: [review, { ...review, application_id: 100, status: 'applied', submitted_at: '2025-12-01T12:00:00Z' }] }),
    useSaveApplicationCover: idleMutation,
  },
  '@/hooks/useJobs': { useUpdateJobStatus: idleMutation, usePrepareApplication: idleMutation },
};
const Register = loadTypeScript('../app/applications/page.tsx', overrides).default;
const Review = loadTypeScript('../app/applications/[id]/page.tsx', overrides).default;
let html = renderToStaticMarkup(createElement(Register));
assert.ok(html.includes('href="/applications/101"') && html.includes('href="/jobs/2"'));
assert.deepEqual(listQuery, { limit: 50, offset: 0, due_before: undefined });
assert.ok(html.includes('Follow up after review'));
listState = { data: { items: [], total: 0 } };
assert.ok(renderToStaticMarkup(createElement(Register)).includes('No applications on this page'));
listState = { isError: true, error: new Error('Synthetic backend unavailable') };
html = renderToStaticMarkup(createElement(Register));
assert.ok(html.includes('Synthetic backend unavailable') && !html.includes('No applications on this page'));

links.length = 0;
html = renderToStaticMarkup(createElement(Review));
assert.ok(html.includes('I submitted this application') && html.includes('/applications/101/cover?v=9'));
assert.ok(html.includes('&lt;script&gt;Example letter&lt;/script&gt;'));
assert.ok(!html.includes('href="javascript:') && !html.includes('local/resume.pdf'));
assert.ok(html.includes('href="/jobs/1"') && html.includes('Notes &amp; next action'));
assert.ok(html.includes('Document versions (2)') && html.includes('href="/applications/100"'));
assert.ok(html.includes('Version #100') && html.includes('Current version') && html.includes('aria-current="page"'));
assert.equal(links.find((link) => link.href === '/applications/100').onNavigate, links.find((link) => link.href === '/jobs/1').onNavigate);
reviewState = { data: { ...review, status: 'applied', submitted_at: '2026-01-02T12:00:00Z' }, dataUpdatedAt: 10 };
html = renderToStaticMarkup(createElement(Review));
assert.ok(html.includes('read-only') && html.includes('Prepare a new version'));
assert.ok(!html.includes('I submitted this application') && !html.includes('Save letter &amp; PDF'));
assert.equal(mutationCalls, 0);

const requests = [];
const cacheWrites = [];
const invalidated = [];
const hooks = loadTypeScript('../hooks/useApplications.ts', {
  '@tanstack/react-query': {
    useQuery: (options) => options, useMutation: (options) => options,
    useQueryClient: () => ({ setQueryData: (...args) => cacheWrites.push(args), invalidateQueries: (args) => invalidated.push(args.queryKey) }),
  },
  '@/lib/api': { api: async (...args) => { requests.push(args); return review; } },
});
assert.equal(hooks.useApplications().throwOnError, false);
assert.equal(hooks.useApplication(101).throwOnError, false);
assert.equal(hooks.useApplication(Number.NaN).enabled, false);
assert.equal(hooks.useApplicationVersions(101).throwOnError, false);
assert.equal(hooks.useApplicationVersions(0).enabled, false);
await hooks.useApplicationVersions(101).queryFn();
assert.equal(requests.pop()[0], '/applications/101/versions');
const mutation = hooks.useSaveApplicationCover(101);
await mutation.mutationFn('Revised letter');
mutation.onSuccess(review);
assert.equal(requests[0][0], '/applications/101/cover');
assert.equal(requests[0][1].method, 'PATCH');
assert.deepEqual(JSON.parse(requests[0][1].body), { cover_letter_content: 'Revised letter' });
assert.deepEqual(cacheWrites[0], [['applications', 101], review]);
assert.deepEqual(invalidated, [['applications', 'list'], ['job', 1]]);
console.log('PASS: application register/review rendering and version-specific cover mutation checks.');
