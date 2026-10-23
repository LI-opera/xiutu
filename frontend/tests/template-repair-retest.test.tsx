import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TemplateRepairRetest } from '../src/workbench/TemplateRepairRetest';
import { apiClient } from '../src/lib/api-client';
afterEach(cleanup);
const props = { caseId: 'case', areaId: 'alpha', revision: 7, onArea: vi.fn(), onChanged: vi.fn(),
  cards: [{ id: 'a', title: '部件甲' }, { id: 'b', title: '部件乙' }],
  questions: [{ id: 'A1', cardId: 'a', area_id: 'alpha', title: '甲的检查', answer_kind: 'single',
      options: [{ id: 'bad', label: '连接松动', outcome: 'abnormal' }, { id: 'ok', label: '未见异常', outcome: 'normal' }] },
    { id: 'A2', cardId: 'a', area_id: 'alpha', title: '未检查项', answer_kind: 'single',
      options: [{ id: 'bad2', label: '有异常', outcome: 'abnormal' }] },
    { id: 'B1', cardId: 'b', area_id: 'beta', title: '乙的检查', answer_kind: 'single' }],
  observations: [{ question_id: 'A1', effective: true, payload: { option_ids: ['bad'] } }, { question_id: 'A2', effective: false }, { question_id: 'B1', effective: true }] };
const snapshot = { revision: 7, areas: { alpha: '区域甲', beta: '区域乙' }, rounds: [] };
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
it('changes question groups with upstream area and discards the previous unsaved draft without writing', async () => {
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue(snapshot);
  const ui = render(<TemplateRepairRetest {...props} />, { wrapper: wrapper() });
  await screen.findByRole('button', { name: /本轮对区域甲做了什么处理/ });
  // Before a repair is saved there is nothing to re-check, so step 2 shows no candidates.
  expect(screen.queryByRole('checkbox', { name: '甲的检查' })).toBeNull();
  expect(screen.queryByRole('heading', { name: '部件甲 · 处理后重新记录' })).toBeNull();
  expect(screen.queryByRole('button', { name: /未检查项/ })).toBeNull();
  expect(screen.queryByLabelText('实际处理动作')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /本轮对区域甲做了什么处理/ }));
  fireEvent.change(screen.getByLabelText('实际处理动作'), { target: { value: '尚未保存的甲动作' } });
  ui.rerender(<TemplateRepairRetest {...props} areaId="beta" />);
  await screen.findByRole('button', { name: /本轮对区域乙做了什么处理/ });
  expect(screen.queryByRole('heading', { name: '部件甲 · 处理后重新记录' })).toBeNull();
  expect(screen.queryByLabelText('实际处理动作')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /本轮对区域乙做了什么处理/ }));
  expect((screen.getByLabelText('实际处理动作') as HTMLTextAreaElement).value).toBe('');
  expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});
it('saves re-checked items as records alongside the readable round summary', async () => {
  const pending = { id: 'round', area_id: 'alpha', repair_action: '已完成动作', repair_note: '', created_at: '2026-09-26T00:00:00Z', retested_at: null };
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ ...snapshot, rounds: [pending] });
  render(<TemplateRepairRetest {...props} />, { wrapper: wrapper() });
  expect(await screen.findByRole('heading', { name: '第 2 步 · 独立复检' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /处理后工况与故障发生时是否可比/ }));
  expect(screen.getByRole('button', { name: '与故障发生时可比' }).getAttribute('aria-pressed')).toBe('false');
  fireEvent.click(screen.getByRole('button', { name: '与故障发生时可比' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '甲的检查' }));
  fireEvent.click(screen.getByRole('button', { name: /甲的检查处理前：连接松动/ }));
  fireEvent.click(screen.getByRole('button', { name: '未见异常' }));
  fireEvent.change(screen.getByLabelText('甲的检查：补充说明'), { target: { value: '复紧后无松动' } });
  fireEvent.click(screen.getByRole('button', { name: /本轮处理后，原问题是否仍存在/ }));
  expect(screen.getByRole('button', { name: '保存本轮独立复检' }).hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '原问题仍存在' }));
  fireEvent.change(screen.getByLabelText('下一排查区域（可选）'), { target: { value: 'beta' } });
  fireEvent.click(screen.getByRole('button', { name: '保存本轮独立复检' }));
  await waitFor(() => expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1));
  const write = request.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(write?.[0]).toBe('/cases/case/template-repairs/round/retest');
  expect(write?.[1]?.body).toEqual({ expected_revision: 7, retest_condition: 'same', retest_outcome: 'persists',
    retest_evidence: '甲的检查\n处理前：连接松动\n处理后：未见异常\n说明：复紧后无松动', next_area_id: 'beta',
    observations: [{ question_id: 'A1', option_ids: ['ok'], fields: {}, note: '复紧后无松动', unavailable_reason: '' }] });
});

it('sends field values with their units and keeps batch readings out of single re-entry', async () => {
  const pending = { id: 'round', area_id: 'alpha', repair_action: '处理', repair_note: '', created_at: '2026-09-26T00:00:00Z', retested_at: null };
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ ...snapshot, rounds: [pending] });
  const questions = [
    { id: 'M1', cardId: 'a', area_id: 'alpha', title: '电压', answer_kind: 'numeric_with_choice',
      options: [{ id: 'low', label: '偏低', outcome: 'abnormal' }, { id: 'ok', label: '正常', outcome: 'normal' }],
      fields: [{ id: 'v', label: '电压', type: 'number', unit: 'V' }] },
    { id: 'S1', cardId: 'a', area_id: 'alpha', title: '静态压力', answer_kind: 'numeric_with_choice', capture: { batch_id_required: true },
      options: [{ id: 'recorded', label: '已记录', outcome: 'normal' }] },
  ];
  const records = [{ question_id: 'M1', effective: true, payload: { option_ids: ['low'] } }, { question_id: 'S1', effective: true, payload: { option_ids: ['recorded'] } }];
  render(<TemplateRepairRetest {...props} questions={questions} observations={records} />, { wrapper: wrapper() });
  fireEvent.click(await screen.findByRole('checkbox', { name: '电压' }));
  expect(screen.queryByRole('checkbox', { name: '静态压力' })).toBeNull();
  expect(screen.getByText(/成组采集的读数（静态压力）/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /电压处理前：偏低/ }));
  fireEvent.click(screen.getByRole('button', { name: '正常' }));
  fireEvent.change(screen.getByLabelText('电压：电压'), { target: { value: '12.6' } });
  fireEvent.click(screen.getByRole('button', { name: /处理后工况与故障发生时是否可比/ }));
  fireEvent.click(screen.getByRole('button', { name: '工况不同' }));
  fireEvent.click(screen.getByRole('button', { name: /本轮处理后，原问题是否仍存在/ }));
  fireEvent.click(screen.getByRole('button', { name: '结果尚不确定' }));
  fireEvent.click(screen.getByRole('button', { name: '保存本轮独立复检' }));
  await waitFor(() => expect(request.mock.calls.some(([, o]) => o?.method === 'POST')).toBe(true));
  const body = request.mock.calls.find(([, o]) => o?.method === 'POST')?.[1]?.body as { observations: unknown[]; retest_evidence: string };
  expect(body.observations).toEqual([{ question_id: 'M1', option_ids: ['ok'], fields: { v: { value: 12.6, unit: 'V' } }, note: '', unavailable_reason: '' }]);
  expect(body.retest_evidence).toBe('电压\n处理前：偏低\n处理后：正常（电压 12.6 V）');
});

it('excludes deselected drafts and preserves selected but unverified items in saved evidence', async () => {
  const pending = { id: 'round', area_id: 'alpha', repair_action: '实际动作', repair_note: '', created_at: '2026-09-26T00:00:00Z', retested_at: null };
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ ...snapshot, rounds: [pending] });
  render(<TemplateRepairRetest {...props} observations={[...props.observations, {question_id:'A2',effective:true,payload:{option_ids:['bad2']}}]} />, { wrapper: wrapper() });
  fireEvent.click(await screen.findByRole('checkbox', { name: '甲的检查' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '未检查项' }));
  fireEvent.click(screen.getByRole('button', { name: /甲的检查处理前/ }));
  fireEvent.click(screen.getByRole('button', { name: '未见异常' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '甲的检查' }));
  fireEvent.click(screen.getByRole('button', { name: /处理后工况与故障发生时是否可比/ }));
  fireEvent.click(screen.getByRole('button', { name: '工况不同' }));
  fireEvent.click(screen.getByRole('button', { name: /本轮处理后，原问题是否仍存在/ }));
  fireEvent.click(screen.getByRole('button', { name: '结果尚不确定' }));
  expect(screen.getByRole('button', {name:'保存本轮独立复检'}).hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByRole('checkbox', { name: '甲的检查' }));
  fireEvent.click(screen.getByRole('button', {name:'保存本轮独立复检'}));
  await waitFor(() => expect(request.mock.calls.some(([,o])=>o?.method==='POST')).toBe(true));
  const body=request.mock.calls.find(([,o])=>o?.method==='POST')?.[1]?.body as {retest_evidence:string};
  expect(body.retest_evidence).toBe('甲的检查\n处理前：连接松动\n处理后：未见异常\n\n本轮已选但尚未取得新记录：\n未检查项');
});

it('regroups effective answers without selecting facts and keeps normal candidates folded', async () => {
  vi.spyOn(apiClient, 'request').mockResolvedValue({ ...snapshot, rounds: [{ id: 'round', area_id: 'alpha', repair_action: '处理', repair_note: '', created_at: '2026-09-26T00:00:00Z', retested_at: null }] });
  const questions = [
    { ...props.questions[0], options: [{id:'bad',label:'连接松动',outcome:'abnormal'}, {id:'ok',label:'未见异常',outcome:'normal'}] },
    { ...props.questions[1], options: [{id:'unknown',label:'无法取得',outcome:'unavailable'}] },
  ];
  const records = [{question_id:'A1', effective:true, payload:{option_ids:['bad']}}, {question_id:'A2',effective:true,payload:{option_ids:['unknown']}}];
  const ui = render(<TemplateRepairRetest {...props} questions={questions} observations={records} />, {wrapper:wrapper()});
  const abnormal = await screen.findByRole('region', {name:'本次异常项 · 优先复检'});
  expect(within(abnormal).getByText('本次记录：连接松动')).toBeTruthy();
  expect((within(abnormal).getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
  expect(within(screen.getByRole('region', {name:'无法检查或待确认项'})).getByText('本次记录：无法取得')).toBeTruthy();
  ui.rerender(<TemplateRepairRetest {...props} questions={questions} observations={[{...records[0],payload:{option_ids:['ok']}},records[1]]} />);
  expect(screen.queryByRole('region', {name:'本次异常项 · 优先复检'})).toBeNull();
  const normal = screen.getByText(/正常或已完成记录项/).closest('details')!;
  expect(normal.open).toBe(false);
  fireEvent.click(within(normal).getByText(/正常或已完成记录项/));
  expect(within(normal).getByText('本次记录：未见异常')).toBeTruthy();
});

it('refreshes round state on revision changes and clears drafts only when the round changes', async () => {
  let roundId = 'first';
  const request=vi.spyOn(apiClient,'request').mockImplementation(async () => ({...snapshot,rounds:[{id:roundId,area_id:'alpha',repair_action:'处理',repair_note:'',created_at:'2026-09-26T00:00:00Z',retested_at:null}]} as never));
  const ui=render(<TemplateRepairRetest {...props} />, {wrapper:wrapper()});
  const check=await screen.findByRole('checkbox',{name:'甲的检查'});
  fireEvent.click(check);
  fireEvent.click(screen.getByRole('button',{name:/甲的检查处理前/}));
  fireEvent.change(screen.getByLabelText('甲的检查：补充说明'),{target:{value:'第一轮草稿'}});
  ui.rerender(<TemplateRepairRetest {...props} revision={8} />);
  await waitFor(()=>expect(request).toHaveBeenCalledTimes(2));
  expect((await screen.findByLabelText('甲的检查：补充说明') as HTMLTextAreaElement).value).toBe('第一轮草稿');
  roundId='second';
  ui.rerender(<TemplateRepairRetest {...props} revision={9} />);
  await waitFor(()=>expect(request).toHaveBeenCalledTimes(3));
  await waitFor(()=>expect((screen.getByRole('checkbox',{name:'甲的检查'}) as HTMLInputElement).checked).toBe(false));
  fireEvent.click(screen.getByRole('checkbox',{name:'甲的检查'}));
  fireEvent.click(screen.getByRole('button',{name:/甲的检查处理前/}));
  expect((screen.getByLabelText('甲的检查：补充说明') as HTMLTextAreaElement).value).toBe('');
  expect(request.mock.calls.every(([,options])=>options?.method!=='POST')).toBe(true);
});

it('shows the saved conclusion instead of disabled inputs once the round is retested', async () => {
  const done = { id: 'round', area_id: 'alpha', repair_action: '复紧卡扣', repair_note: '', pre_repair_revision: 3,
    retest_condition: 'same', retest_outcome: 'resolved', retest_evidence: '甲的检查\n处理前：连接松动\n处理后：未见异常',
    next_area_id: null, created_at: '2026-09-26T00:00:00Z', retested_at: '2026-09-26T01:00:00Z' };
  vi.spyOn(apiClient, 'request').mockResolvedValue({ ...snapshot, rounds: [done] });
  render(<TemplateRepairRetest {...props} />, { wrapper: wrapper() });
  const conclusion = await screen.findByRole('region', { name: '本轮复检结论' });
  expect(within(conclusion).getByText('与故障发生时可比 · 原问题未再出现')).toBeTruthy();
  expect(within(conclusion).getByText(/本轮可以结束/)).toBeTruthy();
  expect(screen.queryByRole('checkbox')).toBeNull();
  expect(screen.queryByRole('button', { name: /本轮处理后，原问题是否仍存在/ })).toBeNull();
  expect(screen.queryByRole('heading', { name: '结果与转区' })).toBeNull();
});

it('keeps the section on screen after saving a repair and moves straight to step 2', async () => {
  const scroll = vi.fn();
  Element.prototype.scrollIntoView = scroll;
  let rounds: unknown[] = [];
  let release: () => void = () => undefined;
  vi.spyOn(apiClient, 'request').mockImplementation(async (_path, options) => {
    if (options?.method === 'POST') { rounds = [{ id: 'round', area_id: 'alpha', repair_action: '复紧卡扣', repair_note: '', created_at: '2026-09-26T00:00:00Z', retested_at: null }]; return {} as never; }
    return { ...snapshot, rounds } as never;
  });
  const ui = render(<TemplateRepairRetest {...props} />, { wrapper: wrapper() });
  fireEvent.click(await screen.findByRole('button', { name: /本轮对区域甲做了什么处理/ }));
  fireEvent.change(screen.getByLabelText('实际处理动作'), { target: { value: '复紧卡扣' } });
  fireEvent.click(screen.getByRole('button', { name: '保存实际处理，进入复检' }));
  expect(await screen.findByRole('button', { name: '与故障发生时可比' })).toBeTruthy();
  expect(scroll).toHaveBeenCalled();
  // A new revision refetches the rounds; the previous content stays mounted meanwhile.
  vi.spyOn(apiClient, 'request').mockImplementation(() => new Promise(resolve => { release = () => resolve({ ...snapshot, rounds } as never); }));
  ui.rerender(<TemplateRepairRetest {...props} revision={8} />);
  expect(screen.getByRole('heading', { name: '第 2 步 · 独立复检' })).toBeTruthy();
  expect(screen.queryByText('正在读取处理记录…')).toBeNull();
  release();
});
