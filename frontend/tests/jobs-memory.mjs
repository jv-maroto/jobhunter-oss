import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInThisContext } from 'node:vm';
import ts from 'typescript';

const code = ts.transpileModule(readFileSync(new URL('../hooks/useJobs.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exports = {};
const keys = [];
const data = { items: [
  { id: 1, status: 'detected', source: 'indeed', track: 'dev', match_score: 45, availability: { status: 'active', checked_at: new Date().toISOString() } },
  { id: 2, status: 'detected', source: 'linkedin', track: 'dev', match_score: 90 },
  { id: 3, status: 'applied', source: 'indeed', track: 'sysadmin', match_score: 80 },
], total: 3 };
const countryExports = {};
const countryCode = ts.transpileModule(readFileSync(new URL('../lib/jobCountries.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
runInThisContext(`(function(exports){${countryCode}\n})`)(countryExports);
const imports = {
  '@/lib/jobCountries': countryExports,
  '@tanstack/react-query': { useQuery: options => { keys.push(options.queryKey); return { data }; } },
  '@/lib/api': { api: () => { throw new Error('Filtering must not request the API'); } },
};
runInThisContext(`(function(require,exports){${code}\n})`)(id => imports[id], exports);
for (const score of [0, 50, 90, 100, 20]) {
  const result = exports.useJobsPage({ min_score: score, status: 'detected', limit: 1, offset: 0 });
  assert.equal(result.data.total, data.items.filter(j => j.status === 'detected' && j.match_score >= score).length);
  assert.ok(result.data.items.every(j => j.match_score >= score));
}
assert.deepEqual(exports.useJobs({ min_score: 60, source: 'linkedin' }).data.map(j => j.id), [2]);
assert.ok(keys.every(key => JSON.stringify(key) === '["jobs","snapshot"]'));
assert.deepEqual(exports.useJobsPage({ status: 'detected', limit: 1 }).data.items.map(j => j.id), [2]);
assert.deepEqual(data.items.map(j => j.id), [1, 2, 3]);
console.log('Job filters reuse one query and filter before pagination.');
const locations = [
  { id: 10, location: 'Madrid, ES', remote: false, match_score: 60 },
  { id: 11, location: 'Home based - Worldwide', remote: false, match_score: 50 },
  { id: 12, location: 'United States', remote: true, match_score: 80 },
  { id: 13, location: 'Tokyo, JP', remote: false, match_score: 90 },
  { id: 14, location: '', remote: true, match_score: 70 },
  { id: 15, location: 'Worldwide (US only)', remote: true, match_score: 85 },
  { id: 16, location: 'Port of Spain', remote: false, match_score: 40 },
];
assert.deepEqual(locations.filter(j=>exports.matchesJobLocation(j,'spain')).map(j=>j.id),[10]);
assert.deepEqual(locations.filter(j=>exports.matchesJobLocation(j,'remote_worldwide')).map(j=>j.id),[11]);
assert.deepEqual(locations.filter(j=>exports.matchesJobLocation(j,'remote')).map(j=>j.id),[11,12,14,15]);
assert.equal(locations.filter(j=>exports.matchesJobLocation(j,'all')).length,7);
data.items=locations;
assert.deepEqual(exports.useJobsPage({ location_filter:'remote_worldwide', limit:1 }).data.items.map(j=>j.id),[11]);
console.log('Location filters distinguish worldwide remote from country-limited remote before pagination.');

assert.equal(exports.matchesJobLocation({ location:'Madrid, ES', remote:true },'spain_remote'),true);
assert.equal(exports.matchesJobLocation({ location:'Madrid, ES', remote:false },'spain_remote'),false);
assert.equal(exports.matchesJobLocation({ location:'US', remote:true },'spain_remote'),false);
assert.equal(exports.matchesJobLocation({ location:'Home based - Worldwide', remote:false },'spain_remote'),false);

assert.deepEqual(countryExports.jobCountries({location:'San Francisco, CA, US'}),['US']);
assert.deepEqual(countryExports.jobCountries({location:'Toronto, ON, CA'}),['CA']);
assert.deepEqual(countryExports.jobCountries({location:'Japan; Spain'}),['JP','ES']);
assert.deepEqual(countryExports.jobCountries({location:'Home based - Worldwide'}),[]);
assert.deepEqual(countryExports.jobCountries({location:'Port of Spain'}),[]);
assert.deepEqual(exports.useJobsPage({country:'JP'}).data.items.map(j=>j.id),[13]);

const stale = { status: 'active', checked_at: new Date(Date.now() - 25 * 3600_000).toISOString() };
data.items = [
 { id: 1, status: 'detected', source: 'indeed', match_score: 90, availability: stale },
 { id: 2, status: 'detected', source: 'manual', source_url: 'https://uk.indeed.com/viewjob?jk=a', match_score: 80 },
 { id: 3, status: 'detected', source: 'linkedin', match_score: 70, availability: { status: 'active', checked_at: new Date().toISOString(), expires_at: '2020-01-01' } },
 { id: 4, status: 'applied', source: 'indeed', match_score: 60, availability: stale },
 { id: 5, status: 'detected', source: 'linkedin', match_score: 50, availability: stale },
];
assert.deepEqual(exports.useJobsPage({}).data.items.map(j => j.id), [4, 5]);
assert.equal(exports.useJobsPage({ verified_only: true }).data.total, 0);
console.log('Cached availability expires locally and preserves application history.');
