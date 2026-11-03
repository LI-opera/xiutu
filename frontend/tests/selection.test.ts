import { expect, it } from 'vitest';
import { nextSelection } from '../src/workbench/selection';

const multi = { answer_kind: 'multi_choice', exclusive_options: ['clean', 'unavailable'] };

it('keeps several findings together in a multi-choice answer', () => {
  expect(nextSelection(multi, ['restricted'], 'wet')).toEqual(['restricted', 'wet']);
});

it('an exclusive option of the template replaces the findings, and a finding replaces it', () => {
  expect(nextSelection(multi, ['restricted', 'wet'], 'clean')).toEqual(['clean']);
  expect(nextSelection(multi, ['clean'], 'wet')).toEqual(['wet']);
  expect(nextSelection(multi, ['unavailable'], 'clean')).toEqual(['clean']);
});

it('clicking a selected option clears it; single choice keeps one option', () => {
  expect(nextSelection(multi, ['restricted', 'wet'], 'wet')).toEqual(['restricted']);
  expect(nextSelection({ answer_kind: 'single_choice' }, ['a'], 'b')).toEqual(['b']);
});

it('templates without exclusive_options keep the old none ids', () => {
  expect(nextSelection({ answer_kind: 'multi_choice' }, ['x'], 'none')).toEqual(['none']);
});
