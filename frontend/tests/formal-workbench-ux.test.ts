import { describe, expect, it } from 'vitest';
import { codeText, flowPresentation, observationSummary, runExplanation, statusText } from '../src/formal/diagnosis/presentation';

describe('formal workbench user-facing presentation', () => {
  it('turns internal status and report codes into user-facing Chinese', () => {
    expect(statusText('unknown')).toBe('资料不足');
    expect(codeText('CASE_NEEDS_REVIEW')).toContain('人工核对');
    expect(codeText('AREA_UNFINISHED')).toContain('区域未完成');
    expect(codeText('CONCLUSION_MISSING')).toContain('结论');
  });

  it('distinguishes waiting, processing, conservative closure and failure', () => {
    expect(flowPresentation({ caseStatus: 'waiting_input', currentStep: true, latestRun: null, areas: [] }).title).toBe('等待填写观察');
    expect(flowPresentation({ caseStatus: 'running', currentStep: false, latestRun: { status: 'running' }, areas: [] }).title).toBe('正在生成下一步');
    expect(flowPresentation({ caseStatus: 'needs_review', currentStep: false, latestRun: { status: 'waiting_input' }, areas: [{ conclusion: { assessment: 'unknown' } } as never] }).title).toBe('资料不足');
    expect(flowPresentation({ caseStatus: 'needs_review', currentStep: false, latestRun: { status: 'failed', error_code: 'MODEL_PRICE_UNVERIFIED' }, areas: [] })).toEqual(expect.objectContaining({ title: '本次运行无法继续', description: expect.stringContaining('模型配置') }));
    expect(flowPresentation({ caseStatus: 'needs_review', currentStep: false, latestRun: { status: 'failed', error_code: 'AREA_NEEDS_INPUT' }, areas: [] })).toEqual(expect.objectContaining({ title: '资料不足，暂时无法继续', action: expect.stringContaining('进度报告') }));
    expect(flowPresentation({ caseStatus: 'needs_review', currentStep: false, latestRun: null, areas: [], terminal: { decision: 'area_summary', terminal_code: 'AREA_SUMMARY_DEMO_PASS' } }).title).toBe('本次增压空气系统演示复检已完成');
    expect(flowPresentation({ caseStatus: 'needs_review', currentStep: false, latestRun: null, areas: [], terminal: { decision: 'handoff', terminal_code: 'HANDOFF_UNAVAILABLE' } }).title).toContain('已暂停');
  });

  it('explains pre-send failure without claiming usage and preserves saved observation', () => {
    const result = runExplanation({ id: 'run', case_id: 'case', kind: 'diagnosis', status: 'failed', attempt: 1, max_attempts: 1, parent_run_id: null, error: { code: 'MODEL_PRICE_UNVERIFIED' }, usage: {} }, true);
    expect(result).toEqual(expect.objectContaining({ saved: expect.stringContaining('已经保存'), usage: expect.stringContaining('没有模型 usage'), recovery: expect.stringContaining('管理员') }));
    const needsInput = runExplanation({ id: 'run2', case_id: 'case', kind: 'diagnosis', status: 'failed', attempt: 1, max_attempts: 1, parent_run_id: null, error: { code: 'AREA_NEEDS_INPUT' }, usage: {} }, true);
    expect(needsInput).toEqual(expect.objectContaining({ conservative: true, stage: expect.stringContaining('资料不足'), recovery: expect.stringContaining('无需重复提交') }));
  });

  it('renders observation meaning instead of raw payload', () => {
    const summary = observationSummary({ kind: 'choice', payload: { choice_index: 1 }, input_schema: { choices: [{ text: '未见明显异常' }, { text: '接头座合疑似不到位' }] } } as never);
    expect(summary).toBe('接头座合疑似不到位');
    expect(observationSummary({ kind: 'unavailable', payload: { reason: '位置无法安全接近' }, input_schema: null } as never)).toContain('位置无法安全接近');
  });
});
