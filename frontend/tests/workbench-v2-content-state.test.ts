import { describe, expect, it } from 'vitest';
import { countVisibleOptions, demoCases, questionBlocks, resultStates, sourceAssets, topicCards, transitions } from './fixtures/workbench-v2-prototype/prototypeKnowledge';
import { activeAnswers, activeResultStates, areaView, createInitialKnowledgeState, explanation, isHistorical, rankedAreas, reducer, reducerWithIntake } from './fixtures/workbench-v2-prototype/prototypeKnowledgeState';
import { emptyIntakeProfile, intakeApplicability, intakeDtcSignals, parseDtcInput } from './fixtures/workbench-v2-prototype/prototypeIntake';

const loadCase = (id: string) => reducer(reducer(createInitialKnowledgeState(), { type: 'request-case', caseId: id }), { type: 'confirm-case' });

describe('DKVB content prototype v2', () => {
  it('starts without a selected demo case or prefilled inspection evidence', () => {
    const state = createInitialKnowledgeState();
    expect(state.confirmedIntake).toBeNull();
    expect(state.answers).toEqual({});
  });

  it('parses one DTC entry conservatively and leaves unknown codes unclassified', () => {
    expect(parseDtcInput('p0299，P0236 P0299')).toEqual({ codes: ['P0299', 'P0236'], invalid: [] });
    expect(parseDtcInput('P0299, nonsense').invalid).toEqual(['NONSENSE']);
    const unknown = intakeDtcSignals({ ...emptyIntakeProfile, dtcCodes: 'P1234' });
    expect(unknown.unclassified).toEqual(['P1234']);
    expect(unknown.boostDtcs).toBe('unavailable');
    expect(intakeDtcSignals(emptyIntakeProfile).p0299State).toBe('unavailable');
    const noScan = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile: { ...emptyIntakeProfile, model: '探岳', engineCode: 'DKVB', complaint: '加速无力', symptomCondition: 'high_load', safetyGate: 'none' } });
    expect(noScan.answers['IN-04']?.optionId).toBe('unavailable');
    expect(explanation(noScan).supports).not.toContain('IN-04');
    expect(areaView(noScan, 'boost-air').done).toBe(0);
  });

  it('generates different initial areas from structured intake without inventing inspection results', () => {
    const base = { ...emptyIntakeProfile, model: '探岳', engineCode: 'DKVB', complaint: '中高负荷加速无力', symptomCondition: 'high_load', safetyGate: 'none' };
    const pressure = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile: { ...base, dtcCodes: 'P0299、P0236' } });
    const crossSystem = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile: { ...base, dtcCodes: 'P0302' } });
    expect(pressure.selectedAreaId).toBe('pressure');
    expect(crossSystem.selectedAreaId).toBe('powertrain');
    expect(pressure.answers['IN-05']?.optionId).toBe('p0236_family');
    expect(crossSystem.answers['IN-06']?.optionId).toBe('misfire');
    expect(activeAnswers(pressure).every(item => item.questionId.startsWith('IN-'))).toBe(true);
    expect(areaView(pressure, 'pressure').done).toBe(0);
  });

  it('orders area cards by recommendation and displays consecutive ranks from left to right', () => {
    const profile = { ...emptyIntakeProfile, model: '探岳', engineCode: 'DKVB', complaint: '增压读数异常', symptomCondition: 'high_load', dtcCodes: 'P0299、P0236', safetyGate: 'none' };
    const state = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile });
    const cards = rankedAreas(state);
    expect(cards[0].area.id).toBe('pressure');
    expect(cards.map(card => card.rank)).toEqual([1, 2, 3, 4, 5]);
    expect(cards.map(card => card.view.sortTier)).toEqual([...cards.map(card => card.view.sortTier)].sort((a, b) => a - b));
  });

  it('freezes the area order after intake while inspection records change', () => {
    const profile = { ...emptyIntakeProfile, model: '探岳', engineCode: 'DKVB', complaint: '加速无力', symptomCondition: 'high_load', dtcCodes: 'P0299', safetyGate: 'none' };
    let state = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile });
    const initialOrder = rankedAreas(state).map(item => item.area.id);
    state = reducerWithIntake(state, { type: 'record', questionId: 'AIR-01', optionId: 'open_or_misaligned' });
    state = reducerWithIntake(state, { type: 'record', questionId: 'PRS-01', optionId: 'recorded' });
    expect(rankedAreas(state).map(item => item.area.id)).toEqual(initialOrder);
    expect(rankedAreas(state).map(item => item.rank)).toEqual([1, 2, 3, 4, 5]);
    const changed = reducerWithIntake(state, { type: 'confirm-intake', profile: { ...profile, dtcCodes: 'P0299、P0302' } });
    expect(rankedAreas(changed)[0].area.id).toBe('powertrain');
  });

  it('does not apply the DKVB path to another engine or unresolved safety risk', () => {
    const profile = { ...emptyIntakeProfile, model: '探岳', engineCode: 'OTHER', complaint: '加速无力', symptomCondition: 'high_load', dtcCodes: 'P0299', safetyGate: 'none' };
    expect(intakeApplicability(profile)).toBe('outside_scope');
    const state = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile });
    expect(areaView(state, 'boost-air').entryState).toBe('unavailable');
    expect(intakeApplicability({ ...profile, engineCode: 'DKVB', safetyGate: 'stop_now' })).toBe('safety_stop');
  });

  it('keeps prior inspections as history when intake is regenerated', () => {
    const profile = { ...emptyIntakeProfile, model: '探岳', engineCode: 'DKVB', complaint: '加速无力', symptomCondition: 'high_load', dtcCodes: 'P0299', safetyGate: 'none' };
    let state = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile });
    state = reducerWithIntake(state, { type: 'record', questionId: 'AIR-01', optionId: 'normal' });
    state = reducerWithIntake(state, { type: 'confirm-intake', profile: { ...profile, dtcCodes: 'P0302' } });
    expect(state.selectedAreaId).toBe('powertrain');
    expect(state.selectedAreaId).toBe(rankedAreas(state)[0].area.id);
    expect(isHistorical(state, 'AIR-01')).toBe(true);
    expect(activeAnswers(state).some(item => item.questionId === 'AIR-01')).toBe(false);
  });

  it('focuses the first ranked card after confirmation without archiving unchanged facts', () => {
    const profile = { ...emptyIntakeProfile, model: '探岳', engineCode: 'DKVB', complaint: '加速无力', symptomCondition: 'high_load', dtcCodes: 'P0299', safetyGate: 'none' };
    let state = reducerWithIntake(createInitialKnowledgeState(), { type: 'confirm-intake', profile });
    state = reducerWithIntake(state, { type: 'record', questionId: 'AIR-01', optionId: 'normal' });
    const unchanged = reducerWithIntake(state, { type: 'confirm-intake', profile });
    expect(isHistorical(unchanged, 'AIR-01')).toBe(false);
    expect(unchanged.selectedAreaId).toBe(rankedAreas(unchanged)[0].area.id);
    const changed = reducerWithIntake(unchanged, { type: 'confirm-intake', profile: { ...profile, complaint: '主诉已更正' } });
    expect(isHistorical(changed, 'AIR-01')).toBe(true);
    expect(changed.selectedAreaId).toBe(rankedAreas(changed)[0].area.id);
  });

  it('contains the complete unique catalog and local source assets', () => {
    expect(questionBlocks).toHaveLength(78);
    expect(new Set(questionBlocks.map(item => item.id)).size).toBe(78);
    expect(topicCards).toHaveLength(34);
    expect(demoCases).toHaveLength(12);
    expect(sourceAssets).toHaveLength(19);
    expect(resultStates).toHaveLength(26);
    expect(transitions).toHaveLength(12);
    expect(countVisibleOptions()).toBeGreaterThanOrEqual(260);
  });

  it('loads C04 as a G31 signal path and pauses turbo interpretation', () => {
    const state = loadCase('C04');
    expect(explanation(state).text).toContain('G31');
    expect(activeResultStates(state).map(item => item.id)).toContain('R11');
    expect(areaView(state, 'pressure').done).toBeGreaterThanOrEqual(6);
  });

  it('loads C09 with a conservative professional turbo handoff', () => {
    const state = loadCase('C09');
    expect(areaView(state, 'turbo').entryState).toBe('in_progress');
    expect(explanation(state).text).toContain('尚未确诊内部损坏');
    expect(activeResultStates(state).map(item => item.id)).toContain('R22');
  });

  it('loads C10 into an evidence-derived ignition direction', () => {
    const state = loadCase('C10');
    expect(areaView(state, 'powertrain').entryState).toBe('in_progress');
    expect(explanation(state).text).toContain('点火方向');
    expect(activeResultStates(state).map(item => item.id)).toContain('R23');
  });

  it('preserves downstream answers as history after upstream correction', () => {
    let state = loadCase('C10');
    state = reducer(state, { type: 'correct', questionId: 'ACT-10' });
    expect(state.answers['X-05']).toBeDefined();
    expect(isHistorical(state, 'X-05')).toBe(true);
    expect(activeAnswers(state).some(item => item.questionId === 'X-05')).toBe(false);
    expect(explanation(state).text).not.toContain('点火方向');
    expect(activeResultStates(state).map(item => item.id)).not.toContain('R23');
    expect(areaView(state, 'powertrain').done).toBeGreaterThan(0);
    expect(areaView(state, 'powertrain').entryState).toBe('historical_completed');
  });
});
