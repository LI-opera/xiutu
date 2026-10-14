import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiClient } from '../src/formal/api-client';
import { AreaTree, EvidenceDrawer, FinalAdvice, ObservationForm } from '../src/formal/diagnosis/WorkbenchParts';
import { consumeRunEvents } from '../src/formal/diagnosis/run-events';
import type { StepCandidate } from '../src/formal/diagnosis/types';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const wrapper = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{ui}</QueryClientProvider>);
const candidate: StepCandidate = { type: 'propose_step', component_key: 'P01', title: '检查插头', purpose: { text: '检查连接状态' }, prerequisites: [{ text: '发动机关闭' }], actions: [{ operation: 'inspect', text: '检查插头是否牢固' }], input: { kind: 'choice', choices: [{ text: 'P01 插头牢固。' }, { text: 'P01 插头松动。' }] }, interpretation: [] };

function stream(text: string) {
  return new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode(text)); controller.close(); } }), { status: 200, headers: { 'content-type': 'text/event-stream' } });
}

describe('WP-15 workbench', () => {
  it('lets keyboard users inspect completed areas while pending activation remains gated', async () => {
    const select = vi.fn(); const activate = vi.fn();
    wrapper(<AreaTree areas={[
      { id: 'done', title: '已完成区域', component_key: 'P01', status: 'completed', conclusion: null } as never,
      { id: 'pending', title: '待生成区域', component_key: 'Q02', status: 'pending', conclusion: null } as never,
    ]} currentAreaId={undefined} selectedAreaId="done" busy={false} canActivate={false} onSelect={select} onActivate={activate} />);
    const done = screen.getByRole('button', { name: /已完成区域/ });
    done.focus(); await userEvent.keyboard('{Enter}');
    expect(select).toHaveBeenCalledWith('done');
    expect(screen.queryByRole('button', { name: '生成本区域检查' })).toBeNull();
  });

  it('submits the server choice and required conditions without inventing facts', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ run_id: 'r', status: 'queued', parent_run_id: null });
    wrapper(<ObservationForm caseId="case" revision={4} epoch={2} stepId="step" candidate={candidate} requiredConditions={{ engine: 'off' }} onSubmitted={() => undefined} onConflict={() => undefined} />);
    await userEvent.click(screen.getByLabelText('P01 插头松动。'));
    await userEvent.click(screen.getByRole('button', { name: '保存观察并启动下一轮' }));
    expect(request).toHaveBeenCalledWith('/cases/case/observations', expect.objectContaining({ method: 'POST', body: expect.objectContaining({ expected_revision: 4, graph_epoch: 2, step_id: 'step', kind: 'choice', choice_index: 1, conditions: { engine: 'off' } }) }));
  });

  it('keeps a valid draft visible when the server reports a revision conflict', async () => {
    const conflict = vi.fn();
    vi.spyOn(apiClient, 'request').mockRejectedValue(new ApiError(409, 'REVISION_CONFLICT', 'changed', 'trace', { current_revision: 5 }, false));
    wrapper(<ObservationForm caseId="case" revision={4} epoch={2} stepId="step" candidate={candidate} requiredConditions={null} onSubmitted={() => undefined} onConflict={conflict} />);
    const selected = screen.getByLabelText('P01 插头牢固。') as HTMLInputElement;
    await userEvent.click(selected); await userEvent.click(screen.getByRole('button', { name: '保存观察并启动下一轮' }));
    expect(await screen.findByText(/当前数据已变化/)).toBeTruthy(); expect(selected.checked).toBe(true); expect(conflict).toHaveBeenCalledOnce();
  });

  it('submits composite conditions and refuses non-finite numeric text', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ run_id: 'r', status: 'queued', parent_run_id: null });
    const composite: StepCandidate = { ...candidate, input: { kind: 'composite', choices: candidate.input.choices, measurements: [{ spec_id: '11111111-1111-4111-8111-111111111111', quantity: 'voltage', unit: 'V', conditions: { engine: 'off' } }] } };
    wrapper(<ObservationForm caseId="case" revision={4} epoch={2} stepId="step" candidate={composite} requiredConditions={{ engine: 'off' }} onSubmitted={() => undefined} onConflict={() => undefined} />);
    await userEvent.click(screen.getByLabelText('P01 插头松动。'));
    await userEvent.type(screen.getByLabelText('voltage'), 'NaN');
    expect((screen.getByRole('button', { name: '保存观察并启动下一轮' }) as HTMLButtonElement).disabled).toBe(true);
    const input = screen.getByLabelText('voltage'); await userEvent.clear(input); await userEvent.type(input, '4.2');
    await userEvent.click(screen.getByRole('button', { name: '保存观察并启动下一轮' }));
    expect(request).toHaveBeenCalledWith('/cases/case/observations', expect.objectContaining({ body: expect.objectContaining({ kind: 'composite', conditions: { engine: 'off' }, measurements: [expect.objectContaining({ value: '4.2', conditions: { engine: 'off' } })] }) }));
  });

  it('records unavailable only with an explicit reason', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ run_id: 'r', status: 'queued', parent_run_id: null });
    wrapper(<ObservationForm caseId="case" revision={4} epoch={2} stepId="step" candidate={candidate} requiredConditions={null} onSubmitted={() => undefined} onConflict={() => undefined} />);
    await userEvent.click(screen.getByLabelText('当前无法测量或检查'));
    expect((screen.getByRole('button', { name: '保存观察并启动下一轮' }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.type(screen.getByLabelText('无法完成原因'), '接头无法安全接近');
    await userEvent.click(screen.getByRole('button', { name: '保存观察并启动下一轮' }));
    expect(request).toHaveBeenCalledWith('/cases/case/observations', expect.objectContaining({ body: expect.objectContaining({ kind: 'unavailable', reason: '接头无法安全接近' }) }));
  });

  it('does not offer a final report while the server gate is closed', async () => {
    vi.spyOn(apiClient, 'request').mockResolvedValue({ case_id: 'case', items: [] });
    wrapper(<FinalAdvice caseId="case" revision={7} gate={{ allowed: false, blocking_items: [{ code: 'CONCLUSION_NOT_FINAL' }], case_revision: 7, graph_epoch: 1 }} />);
    expect((screen.getByRole('button', { name: '生成最终报告' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('CONCLUSION_NOT_FINAL')).toBeTruthy();
    expect((screen.getByRole('button', { name: '生成进度报告' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('keeps a revoked PDF citation bound to the server-provided version and page URL', async () => {
    vi.spyOn(apiClient, 'request').mockResolvedValue({
      evidence_id: 'evidence-old', case_id: 'case', document_version_id: 'version-old',
      index_id: 'index-old', chunk_id: 'chunk-old', synthetic: false,
      snapshot: { locator: { page: 7 }, sha256: 'old-version-hash' },
      current_validity: { valid: false, reasons: ['SOURCE_REVOKED'] },
      source_content_url: '/api/v2/documents/doc/versions/version-old/content?page=7#page=7',
      source_access: { kind: 'pdf', status: 'available', page: 7, page_count: 12, needs_ocr: false, content_url: '/api/v2/documents/doc/versions/version-old/content?page=7#page=7', page_image_url: null, page_image_status: 'unavailable' },
    });
    wrapper(<EvidenceDrawer evidenceIds={["evidence-old"]} onClose={() => undefined} />);
    expect(await screen.findByText('来源失效')).toBeTruthy();
    const link = screen.getByRole('link', { name: '打开原文与定位' }) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/api/v2/documents/doc/versions/version-old/content?page=7#page=7');
    expect(screen.getByText(/old-version-hash/)).toBeTruthy();
  });

  it('deduplicates event ids and closes on a terminal event', async () => {
    const events: string[] = [];
    const fetcher = vi.fn().mockResolvedValue(stream('id: 1\nevent: run.progress\ndata: {}\n\nid: 1\nevent: run.progress\ndata: {}\n\nid: 2\nevent: run.waiting_input\ndata: {}\n\n'));
    await consumeRunEvents({ runId: 'run', signal: new AbortController().signal, contextValid: () => true, fetcher, onEvent: event => { events.push(event.id); }, onDisconnect: async () => ({ terminal: false }), reconnectDelayMs: 0 });
    expect(events).toEqual(['1', '2']); expect(fetcher).toHaveBeenCalledOnce();
  });

  it('recovers the snapshot then reconnects with the last event id', async () => {
    const headers: Array<string | null> = [];
    const fetcher = vi.fn().mockImplementation(async (_url, init) => { headers.push((init?.headers as Headers).get('Last-Event-ID')); return fetcher.mock.calls.length === 1 ? stream('id: 7\nevent: run.progress\ndata: {}\n\n') : stream('id: 8\nevent: run.succeeded\ndata: {}\n\n'); });
    const recover = vi.fn().mockResolvedValue({ terminal: false });
    await consumeRunEvents({ runId: 'run', signal: new AbortController().signal, contextValid: () => true, fetcher, onEvent: () => undefined, onDisconnect: recover, reconnectDelayMs: 0 });
    expect(recover).toHaveBeenCalledOnce(); expect(headers).toEqual([null, '7']);
  });

  it('clears a stale cursor after reset_required', async () => {
    const headers: Array<string | null> = [];
    const fetcher = vi.fn().mockImplementation(async (_url, init) => { headers.push((init?.headers as Headers).get('Last-Event-ID')); if (fetcher.mock.calls.length === 1) return stream('id: 7\nevent: run.progress\ndata: {}\n\nevent: reset_required\ndata: {}\n\n'); return stream('id: 9\nevent: run.failed\ndata: {}\n\n'); });
    await consumeRunEvents({ runId: 'run', signal: new AbortController().signal, contextValid: () => true, fetcher, onEvent: () => undefined, onDisconnect: async () => ({ terminal: false }), reconnectDelayMs: 0 });
    expect(headers).toEqual([null, null]);
  });

  it('stops updating after the owning context becomes stale', async () => {
    let valid = true; const seen: string[] = [];
    const fetcher = vi.fn().mockResolvedValue(stream('id: 1\nevent: run.progress\ndata: {}\n\nid: 2\nevent: run.waiting_input\ndata: {}\n\n'));
    await consumeRunEvents({ runId: 'run', signal: new AbortController().signal, contextValid: () => valid, fetcher, onEvent: event => { seen.push(event.id); valid = false; }, onDisconnect: async () => ({ terminal: false }), reconnectDelayMs: 0 });
    expect(seen).toEqual(['1']);
  });

  it('keeps reconnecting with controlled recovery after the first snapshot failure', async () => {
    const errors: unknown[] = [];
    const fetcher = vi.fn()
      .mockResolvedValueOnce(stream('id: 7\nevent: run.progress\ndata: {}\n\n'))
      .mockResolvedValueOnce(stream('id: 8\nevent: run.waiting_input\ndata: {}\n\n'));
    const recover = vi.fn().mockRejectedValueOnce(new Error('snapshot unavailable')).mockResolvedValueOnce({ terminal: false });
    await consumeRunEvents({ runId: 'run', signal: new AbortController().signal, contextValid: () => true, fetcher, onEvent: () => undefined, onDisconnect: recover, onRecoveryError: error => { if (error) errors.push(error); }, reconnectDelayMs: 0 });
    expect(errors).toHaveLength(1); expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('reuses a report idempotency key after an ambiguous failure', async () => {
    const posts: Array<{ idempotencyKey?: string }> = [];
    vi.spyOn(apiClient, 'request').mockImplementation(async (_path, options = {}) => {
      if (options.method === 'POST') { posts.push(options); if (posts.length === 1) throw new Error('response lost after commit'); return { run_id: 'run', status: 'queued' } as never; }
      return { case_id: 'case', items: [] } as never;
    });
    wrapper(<FinalAdvice caseId="case" revision={7} gate={{ allowed: false, blocking_items: [], case_revision: 7, graph_epoch: 1 }} />);
    await userEvent.click(screen.getByRole('button', { name: '生成进度报告' })); await screen.findByText(/response lost/);
    await userEvent.click(screen.getByRole('button', { name: '生成进度报告' }));
    expect(posts).toHaveLength(2); expect(posts[0].idempotencyKey).toBe(posts[1].idempotencyKey);
  });

  it('requires trusted localized fields and never sends a transition id', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ run_id: 'r', status: 'queued', parent_run_id: null });
    const guided = { ...candidate, component_key: '增压空气系统', input: { kind: 'choice' as const, choices: [{ text: '已定位局部泄漏' }, { text: '未发现局部泄漏' }, { text: '无法确定' }] } };
    const protocol = { decision: 'next_check' as const, protocol_id: 'dkvb-p0299-guided-demo', protocol_version: '2.1.0', transition_id: 'PROTOCOL_START_CHK05', current_check_id: null, observation_id: null, next_check_id: 'CHK-05', reason_code: 'TRUSTED_TRANSITION', options: [
      { option_id: 'leak.localized', label: '已定位局部泄漏', fields: [
        { name: 'leak_object_id' as const, label: '发现泄漏的对象', kind: 'text' as const, required: true, options: [] },
        { name: 'leak_location' as const, label: '泄漏位置', kind: 'text' as const, required: true, options: [] },
        { name: 'evidence_kind' as const, label: '定位依据', kind: 'select' as const, required: true, options: ['visual','touch'] },
      ] },
      { option_id: 'leak.not_found', label: '未发现局部泄漏', fields: [] },
      { option_id: 'leak.inconclusive', label: '无法确定', fields: [] },
    ] };
    wrapper(<ObservationForm caseId="case" revision={2} epoch={0} stepId="step" candidate={guided} requiredConditions={null} protocol={protocol} onSubmitted={() => undefined} onConflict={() => undefined} />);
    await userEvent.click(screen.getByRole('button', { name: '已发现明确漏点' }));
    expect((screen.getByRole('button', { name: '保存观察并进入下一步' }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.type(screen.getByLabelText('发现泄漏的对象'), '演示管路');
    await userEvent.type(screen.getByLabelText('泄漏位置'), '右侧连接处');
    await userEvent.selectOptions(screen.getByLabelText('定位依据'), 'visual');
    await userEvent.click(screen.getByRole('button', { name: '保存观察并进入下一步' }));
    const sent = request.mock.calls[0][1] as { body: Record<string, unknown> };
    expect(sent.body.protocol_fields).toEqual({ leak_object_id: '演示管路', leak_location: '右侧连接处', evidence_kind: 'visual' });
    expect(sent.body).not.toHaveProperty('transition_id');
  });

  it('drops localized draft fields when the user changes to another protocol branch', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ run_id: 'r', status: 'queued', parent_run_id: null });
    const guided = { ...candidate, input: { kind: 'choice' as const, choices: [{ text: '已定位局部泄漏' }, { text: '未发现局部泄漏' }, { text: '无法确定' }] } };
    const protocol = { decision: 'next_check' as const, protocol_id: 'dkvb-p0299-guided-demo', protocol_version: '2.1.0', transition_id: 'PROTOCOL_START_CHK05', current_check_id: null, observation_id: null, next_check_id: 'CHK-05', reason_code: 'TRUSTED_TRANSITION', options: [
      { option_id: 'leak.localized', label: '已定位局部泄漏', fields: [
        { name: 'leak_object_id' as const, label: '发现泄漏的对象', kind: 'text' as const, required: true, options: [] },
        { name: 'leak_location' as const, label: '泄漏位置', kind: 'text' as const, required: true, options: [] },
        { name: 'evidence_kind' as const, label: '定位依据', kind: 'select' as const, required: true, options: ['visual'] },
      ] },
      { option_id: 'leak.not_found', label: '未发现局部泄漏', fields: [] },
      { option_id: 'leak.inconclusive', label: '无法确定', fields: [] },
    ] };
    wrapper(<ObservationForm caseId="case" revision={2} epoch={0} stepId="step" candidate={guided} requiredConditions={null} protocol={protocol} onSubmitted={() => undefined} onConflict={() => undefined} />);
    await userEvent.click(screen.getByRole('button', { name: '已发现明确漏点' }));
    await userEvent.type(screen.getByLabelText('发现泄漏的对象'), '上一分支对象');
    await userEvent.type(screen.getByLabelText('泄漏位置'), '上一分支位置');
    await userEvent.click(screen.getByRole('button', { name: '未发现明确漏点' }));
    await userEvent.click(screen.getByRole('button', { name: '保存观察并进入下一步' }));
    const sent = request.mock.calls[0][1] as { body: Record<string, unknown> };
    expect(sent.body.protocol_fields).toEqual({});
  });

  it('presents a supplement observation as the primary action', () => {
    const guided = { ...candidate, component_key: '增压空气系统定位证据', input: { kind: 'choice' as const, choices: [{ text: '已定位局部泄漏' }, { text: '仍无法确定' }] } };
    const protocol = { decision: 'need_input' as const, protocol_id: 'dkvb-p0299-guided-demo', protocol_version: '2.1.0', transition_id: 'CHK05_INCONCLUSIVE_NEEDS_INPUT', current_check_id: 'CHK-05', observation_id: 'obs', next_check_id: 'CHK-05-SUPPLEMENT', reason_code: 'GUIDED_INPUT_REQUIRED', options: [
      { option_id: 'supplement.localized', label: '已补充明确定位', fields: [] },
      { option_id: 'supplement.inconclusive', label: '仍然无法确定', fields: [] },
    ] };
    wrapper(<ObservationForm caseId="case" revision={3} epoch={0} stepId="supplement" candidate={guided} requiredConditions={null} protocol={protocol} onSubmitted={() => undefined} onConflict={() => undefined} />);
    expect(screen.getByRole('button', { name: '补充观察并继续' })).toBeTruthy();
  });

});
