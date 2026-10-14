import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AreaAnalysis } from '../src/formal/design/workbench-v2/AreaAnalysis';
import { apiClient } from '../src/formal/api-client';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const doc = { id: 'doc', version: '1', title: '压力资料', body: '对应资料完整正文', content_hash: 'hash', provenance: { coverage: '详细版' } };
const baseline = { area: { id: 'pressure', title: '压力' }, revision: 12, available: true, documents: [doc],
  observations: [], recorded: 0, unknown: 2, max_output_tokens: 8192, history: [] };
function mount(onQuestion = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AreaAnalysis caseId="case" areaId="pressure" revision={12} onQuestion={onQuestion} /></QueryClientProvider>);
}

it('shows matched areas and submits one combined request only after a click', async () => {
  const combined = { ...baseline, area: null, areas: [
    { id: 'pressure', title: '压力', document_ids: ['doc'], observation_ids: [], unknown_question_ids: ['P1'] },
    { id: 'actuator', title: '调节机构', document_ids: ['act-doc'], observation_ids: [], unknown_question_ids: ['A1'] },
  ], documents: [doc, { ...doc, id: 'act-doc', title: '调节资料' }] };
  const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path) => path.endsWith('/template-repairs') ? { rounds: [] } : combined);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><AreaAnalysis caseId="case" revision={12} onQuestion={vi.fn()} /></QueryClientProvider>);
  const button = await screen.findByRole('button', { name: '综合分析 2 个有记录区域（真实 AI）' });
  expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
  fireEvent.click(screen.getByText('本次将发送的资料与记录', { exact: false }));
  expect(screen.getByText('压力 · 0 条记录 · 1 份资料')).toBeTruthy();
  expect(screen.getByText('调节机构 · 0 条记录 · 1 份资料')).toBeTruthy();
  fireEvent.click(button);
  await waitFor(() => expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1));
  expect(request.mock.calls.find(([, options]) => options?.method === 'POST')?.[0]).toBe('/cases/case/matched-areas/analysis');
});

it('reads without generating and sends only saved revision when explicitly clicked', async () => {
  const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path) => path.endsWith('/template-repairs') ? { rounds: [] } : baseline);
  mount();
  await screen.findByRole('button', { name: '分析本区域（真实 AI）' });
  expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '分析本区域（真实 AI）' }));
  await waitFor(() => expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1));
  const write = request.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(write?.[0]).toBe('/cases/case/areas/pressure/analysis');
  expect(write?.[1]?.body).toEqual({ expected_revision: 12 });
});

it('enables a manual retry after failure without retrying on render', async () => {
  const failed = { ...baseline, history: [{
    id: 'failed-attempt', status: 'failed', input_revision: 12, stale: false, model: 'deepseek-flash',
    error_code: 'MODEL_INPUT_LIMIT', result: null, documents: [doc], observations: [], questions: [], usage: null,
  }] };
  const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path) => path.endsWith('/template-repairs') ? { rounds: [] } : failed);
  mount();
  const retry = await screen.findByRole('button', { name: '重新分析（上次失败，需手动点击）' });
  expect(retry.hasAttribute('disabled')).toBe(false);
  expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
  fireEvent.click(retry);
  await waitFor(() => expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1));
});

it('keeps references navigational, renders model text inertly and does not save repairs', async () => {
  const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path) => path.endsWith('/template-repairs') ? { rounds: [] } : ({ ...baseline, history: [{
    id: 'attempt', status: 'completed', input_revision: 11, stale: false, model: 'test', error_code: null,
    documents: [doc], observations: [], questions: [{ id: 'P1', title: '检查插头' }], usage: null,
    result: { summary: '<script>bad()</script>', directions: [], missing: [], precautions: [], conditional_branches: [],
      steps: [{ action: '核对插头', question_ids: ['P1', 'unknown'], source_ids: [], basis_observation_ids: [] }] },
  }] }));
  const onQuestion = vi.fn();
  const { container } = mount(onQuestion);
  await screen.findByText('<script>bad()</script>');
  expect(screen.getByRole('heading', { name: '当前判断' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: '现在怎么做' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: '核对插头' })).toBeTruthy();
  expect(container.querySelector('script')).toBeNull();
  expect(screen.queryByText('与本区当前输入一致', { exact: false })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '前往 检查插头' }));
  expect(onQuestion).toHaveBeenCalledWith('P1');
  expect(screen.queryByRole('button', { name: /unknown/ })).toBeNull();
  expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
  expect(screen.queryByRole('button', { name: /记录实际处理/ })).toBeNull();
});

for (const [label, action, branch] of [
  ['供电', '核对连接点压降', '供电恢复后仍无法启动'],
  ['温度', '先处理已记录的外部泄漏', '密封恢复后温度仍异常'],
]) {
  it(`prioritizes current actions and collapses future evidence for ${label}`, async () => {
    const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path) => path.endsWith('/template-repairs') ? { rounds: [] } : ({ ...baseline, history: [{
      id: label, status: 'completed', stale: false, model: 'fixture', input_revision: 12,
      documents: [], observations: [], questions: [], usage: null,
      result: { summary: '当前判断', steps: [{ kind: 'check', action, question_ids: [], source_ids: [], basis_observation_ids: [] }],
        directions: [{ title: '支持依据', source_ids: [], basis_observation_ids: [] }], missing: [], precautions: [],
        conditional_branches: [{ trigger: branch, steps: [] }] },
    }] }));
    const { container } = mount();
    await screen.findByRole('button', { name: '分析已完成' });
    expect(screen.getByRole('heading', { name: action })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: '影响决定的待确认事项' })).toBeNull();
    for (const title of ['待确认与补充说明', branch]) {
      expect(screen.getByText(title).closest('details')?.open).toBe(false);
    }
    const headings = [...container.querySelectorAll('h3')].map(el => el.textContent);
    expect(headings.slice(0, 2)).toEqual(['当前判断', '现在怎么做']);
    expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
  });
}

it('separates action headings, keeps conditions visible and groups valid question links', async () => {
  const action = { kind: 'check', title: '核对供电', action: '测量两个连接点并比较记录。', prerequisites: '完成断电准备',
    question_ids: ['Q1', 'Q2', 'Q1', 'unknown'], source_ids: [], basis_observation_ids: [] };
  const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path) => path.endsWith('/template-repairs') ? { rounds: [] } : ({ ...baseline, history: [{
    id: 'new', status: 'completed', stale: false, model: 'fixture', input_revision: 12,
    documents: [], observations: [], questions: [{ id: 'Q1', title: '第一连接点' }, { id: 'Q2', title: '第二连接点' }],
    result: { summary: '核对后决定去向', directions: [], missing: [], precautions: [], steps: [action],
      conditional_branches: [{ trigger: '供电正常后', steps: [{ ...action, title: '核对控制', question_ids: [] }] }] },
  }] }));
  const onQuestion = vi.fn();
  const { container } = mount(onQuestion);
  await screen.findByRole('heading', { name: '核对供电' });
  expect(screen.queryByRole('heading', { name: action.action })).toBeNull();
  const group = screen.getByText('相关检查项（2）').closest('details');
  expect(group?.open).toBe(false);
  expect(screen.getByRole('button', { name: '前往 第一连接点' }).closest('details')).toBe(group);
  fireEvent.click(screen.getByText('相关检查项（2）'));
  fireEvent.click(screen.getByRole('button', { name: '前往 第二连接点' }));
  expect(onQuestion).toHaveBeenCalledWith('Q2');
  expect(container.querySelector('.formal-v2-guidance-list li')?.textContent?.indexOf('执行条件')).toBeLessThan(
    container.querySelector('.formal-v2-guidance-list li')?.textContent?.indexOf(action.action) ?? 0);
  expect(screen.queryByText('查看依据')).toBeNull();
  expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});
