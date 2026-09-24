import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
const timers=[];
const fakeSignal={ any:AbortSignal.any.bind(AbortSignal), timeout(ms) { const controller=new AbortController(); timers.push({ms,controller}); return controller.signal; } };
let finish;
const apiExports={};
function load(file,exports,extra={}) {
 const code=ts.transpileModule(readFileSync(new URL(file,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 runInNewContext(code,{exports,process:{env:{}},AbortSignal:fakeSignal,...extra});
}
load('../lib/api.ts',apiExports,{fetch:(_url,{signal})=>new Promise((resolve,reject)=>{signal.addEventListener('abort',()=>reject(signal.reason));finish=()=>resolve({ok:true,text:async()=>'{"application_id":217}'});})});
const hooks={};
load('../hooks/useJobs.ts',hooks,{require:id=>id==='@/lib/api'?apiExports:id==='@/lib/jobCountries'?{jobCountries:()=>[]}:{useMutation:options=>options,useQueryClient:()=>({invalidateQueries(){}})}});
const preparation=hooks.usePrepareApplication().mutationFn(5685);
assert.equal(timers.at(-1).ms,300000);
// Simulate 65 seconds: an ordinary request would have timed out, while CV preparation survives.
for(const timer of timers)if(timer.ms<=65000)timer.controller.abort(new DOMException('Timed out','TimeoutError'));
assert.equal(timers.at(-1).controller.signal.aborted,false);
finish();assert.equal((await preparation).application_id,217);
const ordinary=apiExports.api('/health');
assert.equal(timers.at(-1).ms,60000);
finish();await ordinary;
console.log('CV preparation survives the former 60-second cutoff; ordinary requests keep their timeout.');
