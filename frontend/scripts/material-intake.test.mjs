import test from 'node:test';
import assert from 'node:assert/strict';
import {intakeMetadata,emptyFields,uploadProblem,uploadFailure} from '../src/material-intake.ts';
for (const size of [1023,1024,1025]) test(`actual byte limit ${size}`,()=>assert.equal(!!uploadProblem(size,1024),size>1024));
test('nature required',()=>assert.throws(()=>intakeMetadata('x.md','',emptyFields,{})));
test('nonfiction unknowns stay unknown, never demo scope',()=>{const m=intakeMetadata('x.md','nonfiction',emptyFields,{model:'HT-2.0'});assert.equal(m.synthetic,false);assert.equal(m.source_status,'unknown');assert.equal(m.license_status,'unknown');assert.equal(m.scope.model,null);assert.equal(m.scope.engine_code,null);});
test('explicit nonfiction fields retain semantics',()=>{const m=intakeMetadata('x.md','nonfiction',{...emptyFields,model:'User model',yearFrom:'2020',code:'CODE',source:'Unverified publisher'},{});assert.equal(m.scope.model,'User model');assert.equal(m.scope.year_from,2020);assert.equal(m.scope.year_to,null);assert.equal(m.source_reference,'Unverified publisher');});
test('synthetic is explicit and uses demo scope',()=>assert.deepEqual(intakeMetadata('x.md','synthetic',emptyFields,{model:'HT-2.0'}).scope,{model:'HT-2.0'}));
test('413 translated, unrelated errors remain distinct',()=>{assert.match(uploadFailure(413,1024),/原资料保持不变/);assert.equal(uploadFailure(422,1024),null);});

import {selectUploadFile,selectedUploadMetadata} from '../src/material-intake.ts';
import {readFileSync} from 'node:fs';
test('new selection clears every declaration including same filename',()=>{
 const a=new File(['A'],'same.md'),b=new File(['B'],'same.md');
 const draft={...selectUploadFile(a),nature:'nonfiction',fields:{source:'A',model:'A',yearFrom:'2020',yearTo:'2021',family:'A',code:'A'}};
 const next=selectUploadFile(b);assert.equal(next.file,b);assert.equal(next.nature,'');assert.deepEqual(next.fields,emptyFields);
 assert.throws(()=>selectedUploadMetadata(b,next,{}));assert.throws(()=>selectedUploadMetadata(b,draft,{}));
 assert.equal(draft.fields.source,'A');
});
test('synthetic selection also requires a fresh declaration; B uses only its fields',()=>{
 const a=new File(['A'],'a.md'),b=new File(['B'],'b.md');
 const old={...selectUploadFile(a),nature:'synthetic',fields:{...emptyFields,source:'A'}};
 const fresh=selectUploadFile(b);assert.equal(fresh.nature,'');assert.deepEqual(fresh.fields,emptyFields);
 const next={...fresh,nature:'nonfiction',fields:{...fresh.fields,source:'B',model:'B'}};
 const metadata=selectedUploadMetadata(b,next,{});assert.equal(metadata.synthetic,false);assert.equal(metadata.source_reference,'B');assert.equal(metadata.scope.model,'B');assert.equal(metadata.scope.engine_code,null);assert.equal(old.fields.source,'A');
});
test('submission failure leaves the selected declaration available for retry',()=>{
 const f=new File(['invalid bytes'],'retry.md');const draft={...selectUploadFile(f),nature:'nonfiction',fields:{...emptyFields,source:'keep'}};
 const before=structuredClone(draft.fields);const first=selectedUploadMetadata(f,draft,{});uploadFailure(413,1024);
 assert.deepEqual(draft.fields,before);assert.equal(draft.file,f);assert.deepEqual(selectedUploadMetadata(f,draft,{}),first);
});
test('page uses selection transition and bound metadata; dedicated sample bypasses ordinary draft',()=>{
 const source=readFileSync(new URL('../src/main.tsx',import.meta.url),'utf8');
 assert.match(source,/onChange=\{e => setUploadDraft\(selectUploadFile\(e.target.files\?\.\[0\] \?\? null\)\)\}/);
 assert.match(source,/selectedUploadMetadata\(f,uploadDraft,config.scope\)/);
 assert.match(source,/example \? \{title:/);assert.match(source,/!file \|\| !!busy \|\| !nature/);
 const upload=source.slice(source.indexOf('async function upload('),source.indexOf('async function viewChunks('));assert.doesNotMatch(upload,/setUploadDraft|setNature|setIntake/);
});
