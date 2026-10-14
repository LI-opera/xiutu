import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TemplateRepairRetest } from '../src/formal/design/workbench-v2/TemplateRepairRetest';
import { apiClient } from '../src/formal/api-client';
afterEach(cleanup);
const props = { caseId: 'case', areaId: 'alpha', revision: 7, onArea: vi.fn(), onChanged: vi.fn(),
  cards: [{ id: 'a', title: '部件甲' }, { id: 'b', title: '部件乙' }],
  questions: [{ id: 'A1', cardId: 'a', area_id: 'alpha', title: '甲的检查', answer_kind: 'single' },
    { id: 'A2', cardId: 'a', area_id: 'alpha', title: '未检查项', answer_kind: 'single' },
    { id: 'B1', cardId: 'b', area_id: 'beta', title: '乙的检查', answer_kind: 'single' }],
  observations: [{ question_id: 'A1', effective: true }, { question_id: 'A2', effective: false }, { question_id: 'B1', effective: true }] };
const snapshot = { revision: 7, areas: { alpha: '区域甲', beta: '区域乙' }, rounds: [] };
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
it('changes question groups with upstream area and discards the previous unsaved draft without writing', async () => {
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue(snapshot);
  const ui = render(<TemplateRepairRetest {...props} />, { wrapper: wrapper() });
  await screen.findByRole('checkbox', { name: '甲的检查' });
  expect(screen.queryByRole('heading', { name: '部件甲 · 处理后复检' })).toBeNull();
  expect(screen.queryByRole('button', { name: /未检查项/ })).toBeNull();
  expect(screen.queryByLabelText('实际处理动作')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /本轮对区域甲做了什么处理/ }));
  fireEvent.change(screen.getByLabelText('实际处理动作'), { target: { value: '尚未保存的甲动作' } });
  ui.rerender(<TemplateRepairRetest {...props} areaId="beta" />);
  await screen.findByRole('checkbox', { name: '乙的检查' });
  expect(screen.queryByRole('heading', { name: '部件甲 · 处理后复检' })).toBeNull();
  expect(screen.queryByLabelText('实际处理动作')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /本轮对区域乙做了什么处理/ }));
  expect((screen.getByLabelText('实际处理动作') as HTMLTextAreaElement).value).toBe('');
  expect(request.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});
it('saves only explicitly entered new evidence into the pending round after condition and outcome are selected', async () => {
  const pending = { id: 'round', area_id: 'alpha', repair_action: '已完成动作', repair_note: '', created_at: '2026-09-26T00:00:00Z', retested_at: null };
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ ...snapshot, rounds: [pending] });
  render(<TemplateRepairRetest {...props} />, { wrapper: wrapper() });
  fireEvent.click(await screen.findByRole('button', { name: /处理后工况与故障发生时是否可比/ }));
  expect(screen.getByRole('button', { name: '与故障发生时可比' }).getAttribute('aria-pressed')).toBe('false');
  fireEvent.click(screen.getByRole('button', { name: '与故障发生时可比' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '甲的检查' }));
  fireEvent.click(screen.getByRole('button', { name: /甲的检查来自/ }));
  fireEvent.click(screen.getByRole('button', { name: '仍有异常' }));
  fireEvent.change(screen.getByLabelText('甲的检查：处理后新记录'), { target: { value: '本次新读数 12 V' } });
  fireEvent.click(screen.getByRole('button', { name: /本轮处理后，原问题是否仍存在/ }));
  expect(screen.getByRole('button', { name: '保存本轮独立复检' }).hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '原问题仍存在' }));
  fireEvent.change(screen.getByLabelText('下一排查区域（可选）'), { target: { value: 'beta' } });
  fireEvent.click(screen.getByRole('button', { name: '保存本轮独立复检' }));
  await waitFor(() => expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1));
  const write = request.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(write?.[0]).toBe('/cases/case/template-repairs/round/retest');
  expect(write?.[1]?.body).toEqual({ expected_revision: 7, retest_condition: 'same', retest_outcome: 'persists', retest_evidence: '甲的检查\n复检变化：仍有异常\n处理后新记录：本次新读数 12 V', next_area_id: 'beta' });
});

it('excludes deselected drafts and preserves selected but unverified items in saved evidence', async () => {
  const pending = { id: 'round', area_id: 'alpha', repair_action: '实际动作', repair_note: '', created_at: '2026-09-26T00:00:00Z', retested_at: null };
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ ...snapshot, rounds: [pending] });
  render(<TemplateRepairRetest {...props} observations={[...props.observations, {question_id:'A2',effective:true}]} />, { wrapper: wrapper() });
  fireEvent.click(await screen.findByRole('checkbox', { name: '甲的检查' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '未检查项' }));
  fireEvent.click(screen.getByRole('button', { name: /甲的检查来自/ }));
  fireEvent.change(screen.getByLabelText('甲的检查：处理后新记录'), {target:{value:'新测量结果'}});
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
  expect(body.retest_evidence).toBe('甲的检查\n处理后新记录：新测量结果\n\n本轮已选但尚未取得新记录：\n未检查项');
});

it('regroups effective answers without selecting facts and keeps normal candidates folded', async () => {
  vi.spyOn(apiClient, 'request').mockResolvedValue(snapshot);
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
  fireEvent.click(screen.getByRole('button',{name:/甲的检查来自/}));
  fireEvent.change(screen.getByLabelText('甲的检查：处理后新记录'),{target:{value:'第一轮草稿'}});
  ui.rerender(<TemplateRepairRetest {...props} revision={8} />);
  await waitFor(()=>expect(request).toHaveBeenCalledTimes(2));
  expect((await screen.findByLabelText('甲的检查：处理后新记录') as HTMLTextAreaElement).value).toBe('第一轮草稿');
  roundId='second';
  ui.rerender(<TemplateRepairRetest {...props} revision={9} />);
  await waitFor(()=>expect(request).toHaveBeenCalledTimes(3));
  await waitFor(()=>expect((screen.getByRole('checkbox',{name:'甲的检查'}) as HTMLInputElement).checked).toBe(false));
  fireEvent.click(screen.getByRole('checkbox',{name:'甲的检查'}));
  fireEvent.click(screen.getByRole('button',{name:/甲的检查来自/}));
  expect((screen.getByLabelText('甲的检查：处理后新记录') as HTMLTextAreaElement).value).toBe('');
  expect(request.mock.calls.every(([,options])=>options?.method!=='POST')).toBe(true);
});
