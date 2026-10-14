// Mechanical export of the reviewed TS topic catalog for the formal API.
// The prototype remains a consumer of the original source until retirement.
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import ts from 'typescript';

const here = path.dirname(fileURLToPath(import.meta.url));
const sourceDir = path.resolve(here, '../src/formal/design/workbench-v2');
const output = path.resolve(here, '../../backend/app/topics/dkvb_p0299_v2.json');
const identityOutput = path.resolve(sourceDir, 'topicIdentity.ts');
const nodeRequire = createRequire(import.meta.url);
const cache = new Map();

function load(file) {
  const resolved = path.resolve(sourceDir, file);
  if (cache.has(resolved)) return cache.get(resolved).exports;
  const module = { exports: {} };
  cache.set(resolved, module);
  const source = fs.readFileSync(resolved, 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const wrapper = vm.runInThisContext(`(function(require,module,exports){${js}\n})`, { filename: resolved });
  wrapper(specifier => specifier.startsWith('.') ? load(`${specifier}.ts`) : nodeRequire(specifier), module, module.exports);
  return module.exports;
}

const topic = load('prototypeKnowledge.ts');
const data = {
  topic_id: 'tanyue-dkvb-p0299-demo-v2',
  version: topic.contentPrototypeVersion,
  synthetic: true,
  formal_usable: false,
  areas: topic.prototypeAreas,
  cards: topic.topicCards,
  questions: topic.questionBlocks,
  assets: topic.sourceAssets,
  results: topic.resultStates,
  transitions: topic.transitions,
};
if (data.questions.length !== 78 || data.cards.length !== 34 || data.areas.length !== 5) throw new Error('Unexpected topic cardinality');
fs.mkdirSync(path.dirname(output), { recursive: true });
const json = JSON.stringify(data, null, 2) + '\n';
fs.writeFileSync(output, json, 'utf8');
const contentHash = createHash('sha256').update(json, 'utf8').digest('hex');
fs.writeFileSync(identityOutput,
  `// Generated with export-workbench-v2-topic.mjs; never edit this hash by hand.\n` +
  `export const formalTopicIdentity = ${JSON.stringify({ topicId: data.topic_id, version: data.version, contentHash }, null, 2)} as const;\n`, 'utf8');
process.stdout.write(`Exported ${data.questions.length} questions to ${output}\n`);
