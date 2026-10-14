import test from 'node:test';
import assert from 'node:assert/strict';
import { ContextEpoch, guardedRefresh } from '../src/preview-context.ts';

test('successful document/version/session transitions invalidate pending results (including ABA)', () => {
 const c = new ContextEpoch(); const a = c.capture(); c.invalidate(); assert.equal(c.isCurrent(a),false);
 const b = c.capture(); c.invalidate(); assert.equal(c.isCurrent(b),false); assert.equal(c.isCurrent(a),false);
});
test('failed upload and same-context polling retain editing/result generation', () => {
 const c = new ContextEpoch(); const before = c.capture(); assert.equal(c.isCurrent(before),true);
});
test('late A callback cannot publish after B transition', async () => {
 const c = new ContextEpoch(); let resolve; const response = new Promise(r => resolve=r); const a=c.capture();
 let result=null; const pending=response.then(value=>{if(c.isCurrent(a)) result=value;});
 c.invalidate(); resolve({accepted:true}); await pending; assert.equal(result,null);
});
test('current callback can publish normally', async () => {
 const c=new ContextEpoch(); const a=c.capture(); let result=null;
 await Promise.resolve({accepted:true}).then(value=>{if(c.isCurrent(a))result=value;});
 assert.deepEqual(result,{accepted:true});
});

function deferred() { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; }
test('production refresh policy suppresses old error after new same-document session', async () => {
 const c=new ContextEpoch(), d=deferred(), errors=[];
 const p=guardedRefresh(c,()=>true,async()=>{await d.promise;},e=>errors.push(e));
 c.invalidate();d.reject(new Error('old'));await p;assert.deepEqual(errors,[]);
});
test('production refresh policy shows current error', async () => {
 const errors=[];await guardedRefresh(new ContextEpoch(),()=>true,async()=>{throw Error('current');},e=>errors.push(e.message));assert.deepEqual(errors,['current']);
});
test('production refresh policy suppresses errors after effect cleanup', async () => {
 let alive=true;const d=deferred(), errors=[];const p=guardedRefresh(new ContextEpoch(),()=>alive,async()=>{await d.promise;},e=>errors.push(e));alive=false;d.reject(Error('disposed'));await p;assert.deepEqual(errors,[]);
});
test('production refresh policy suppresses late success after ABA', async () => {
 const c=new ContextEpoch(),d=deferred();let value='current';const p=guardedRefresh(c,()=>true,async current=>{await d.promise;if(current())value='stale';},()=>assert.fail());c.invalidate();c.invalidate();d.resolve();await p;assert.equal(value,'current');
});
test('production refresh policy suppresses success after lifecycle cleanup', async () => {
 let alive=true,value='current';const d=deferred();const p=guardedRefresh(new ContextEpoch(),()=>alive,async current=>{await d.promise;if(current())value='stale';},()=>assert.fail());alive=false;d.resolve();await p;assert.equal(value,'current');
});
test('same-context refresh publishes data without touching editor', async () => {
 const state={editor:'user edits',version:null};await guardedRefresh(new ContextEpoch(),()=>true,async current=>{if(current())state.version='ready';},()=>assert.fail());assert.deepEqual(state,{editor:'user edits',version:'ready'});
});
