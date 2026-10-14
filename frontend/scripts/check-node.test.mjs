import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { assertSupportedNode, requiredVersion } from './check-node.mjs';
test('declared runtime matches package and actual runtime', () => {
  assert.equal(JSON.parse(readFileSync(new URL('../package.json', import.meta.url))).engines.node, requiredVersion);
  assert.doesNotThrow(() => assertSupportedNode());
});
test('isolated unsupported version is explicitly rejected', () => {
  assert.throws(() => assertSupportedNode('18.0.0'), /Node 24.14.0 required; found 18.0.0/);
});
