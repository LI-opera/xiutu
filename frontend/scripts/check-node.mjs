import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
export const requiredVersion = readFileSync(new URL('../../.node-version', import.meta.url), 'utf8').trim();
export function assertSupportedNode(actual = process.versions.node) {
  if (actual !== requiredVersion) throw new Error(`Node ${requiredVersion} required; found ${actual}. Select the declared runtime manually.`);
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { assertSupportedNode(); console.log(`Node ${requiredVersion}: OK`); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
