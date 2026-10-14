import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { apiClient } from '../src/formal/api-client';
import { DocumentsPage } from '../src/formal/pages/DocumentsPage';
import { HistoryPage } from '../src/formal/pages/HistoryPage';

const A = '11111111-1111-4111-8111-111111111111';
const AV = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const B = '22222222-2222-4222-8222-222222222222';
const BV = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const document = (id: string, title: string, versionId: string) => ({ id, title, source_kind: 'local', created_at: '', latest_version_id: versionId });
const version = (documentId: string, versionId: string) => ({
  document_id: documentId, version_id: versionId, review_status: 'approved', index_status: 'ready', index_implemented: true,
  formal_usable: false, active_index_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', index_run_id: null,
  index_exclusion: null, last_index_status: 'ready', index_error: {}, sha256: `hash-${versionId}`, mime: 'text/markdown',
  metadata: { synthetic: true, source_status: 'verified', license_status: 'private_use', scope: {} }, parse_status: 'review_pending',
  run_id: null, parser_version: 'p', chunker_version: 'c', tokenizer: 't', page_count: 1, page_issues: [], parse_error: {}, review_history: [],
});
const chunk = (ordinal: number, text: string) => ({ ordinal, heading_path: [], page_start: null, page_end: null, char_start: 0, char_end: text.length, kind: 'text', locator_json: {}, text, text_hash: `hash-${ordinal}`, token_count: 1 });
const caseItem = (id: string, model: string) => ({ id, vehicle: { model, year: null, engine_code: null, engine_family: null, vin: null }, fault_description: `${model}故障`, fault_codes: [], revision: 0, graph_epoch: 0, status: 'draft', corpus_manifest: [], created_at: '2026-09-21T00:00:00Z', updated_at: '2026-09-21T00:00:00Z', active_run: null, current_check: null, experience: { category: 'continue', label: '可继续', guidance: '进入病例', priority: 10 }, report_gate: { available: false, reason: 'FINAL_NOT_READY', blocking_items: [] } });

function mount(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('WP-14 pagination remediation', () => {
  it('loads, encodes and stably deduplicates later document pages', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/client-config') return { upload_max_bytes: 4096, retrieval_profile: 'formal' } as never;
      if (path === '/documents?limit=50') return { items: [document(A, '第一页资料', AV)], next_cursor: 'page 2/资料' } as never;
      if (path === '/documents?limit=50&cursor=page%202%2F%E8%B5%84%E6%96%99') return { items: [document(A, '重复资料', AV), document(B, '第二页资料', BV)], next_cursor: null } as never;
      throw new Error(path);
    });
    mount(<DocumentsPage />);
    await userEvent.click(await screen.findByRole('button', { name: '加载更多资料' }));
    expect(await screen.findByRole('button', { name: /第二页资料/ })).toBeTruthy();
    expect(screen.getAllByRole('button', { name: /第一页资料|重复资料/ })).toHaveLength(1);
  });

  it('retains loaded documents when a later page fails and can retry that page', async () => {
    let laterAttempts = 0;
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/client-config') return { upload_max_bytes: 4096, retrieval_profile: 'formal' } as never;
      if (path === '/documents?limit=50') return { items: [document(A, '保留资料', AV)], next_cursor: 'next' } as never;
      if (path.endsWith('cursor=next') && ++laterAttempts === 1) throw new Error('后续页失败');
      if (path.endsWith('cursor=next')) return { items: [document(B, '重试资料', BV)], next_cursor: null } as never;
      throw new Error(path);
    });
    mount(<DocumentsPage />);
    await userEvent.click(await screen.findByRole('button', { name: '加载更多资料' }));
    expect(await screen.findByText('后续页失败')).toBeTruthy();
    expect(screen.getByRole('button', { name: /保留资料/ })).toBeTruthy();
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('button', { name: /重试资料/ })).toBeTruthy();
  });

  it('treats chunk cursor zero as a real next page and keeps version pages isolated', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/client-config') return { upload_max_bytes: 4096, retrieval_profile: 'formal' } as never;
      if (path === '/documents?limit=50') return { items: [document(A, '资料A', AV), document(B, '资料B', BV)], next_cursor: null } as never;
      if (path.includes(`${A}/versions/${AV}/chunks?limit=100&cursor=0`)) return { items: [chunk(1, 'A第二页切块')], next_cursor: null } as never;
      if (path.includes(`${A}/versions/${AV}/chunks?limit=100`)) return { items: [chunk(0, 'A第一页切块')], next_cursor: 0 } as never;
      if (path.includes(`${B}/versions/${BV}/chunks?limit=100`)) return { items: [chunk(0, 'B独立切块')], next_cursor: null } as never;
      if (path.includes(AV)) return version(A, AV) as never;
      if (path.includes(BV)) return version(B, BV) as never;
      throw new Error(path);
    });
    mount(<DocumentsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /资料A/ }));
    await userEvent.click(await screen.findByRole('button', { name: '加载更多切块' }));
    expect(await screen.findByText('A第二页切块')).toBeTruthy();
    await userEvent.click(screen.getByRole('button', { name: /资料B/ }));
    expect(await screen.findByText('B独立切块')).toBeTruthy();
    expect(screen.queryByText('A第一页切块')).toBeNull();
    expect(screen.queryByText('A第二页切块')).toBeNull();
  });

  it('switches history scope without leaking an in-flight page from the previous scope', async () => {
    let release!: (value: unknown) => void;
    const pending = new Promise(resolve => { release = resolve; });
    const request = vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/cases?limit=50&scope=daily') return { items: [caseItem(A, '日常车辆')], next_cursor: 'older' } as never;
      if (path === '/cases?limit=50&scope=daily&cursor=older') return pending as never;
      if (path === '/cases?limit=50&scope=test') return { items: [caseItem(B, '验证车辆')], next_cursor: null } as never;
      if (path === '/cases?limit=50&scope=all') return { items: [caseItem(A, '日常车辆'), caseItem(B, '验证车辆')], next_cursor: null } as never;
      throw new Error(path);
    });
    mount(<HistoryPage />);
    expect(await screen.findByText('日常车辆')).toBeTruthy();
    await userEvent.click(screen.getByRole('button', { name: '加载更早病例' }));
    await userEvent.click(screen.getByRole('button', { name: '测试与验证' }));
    expect(await screen.findByText('验证车辆')).toBeTruthy();
    release({ items: [caseItem(A, '不应混入的日常车辆')], next_cursor: null });
    await waitFor(() => expect(screen.queryByText('不应混入的日常车辆')).toBeNull());
    expect(screen.queryByText('日常车辆')).toBeNull();
    expect(screen.queryByRole('button', { name: '加载更早病例' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: '全部病例' }));
    expect(await screen.findByText('日常车辆')).toBeTruthy();
    expect(screen.getByText('验证车辆')).toBeTruthy();
    expect(request).toHaveBeenCalledWith('/cases?limit=50&scope=all', expect.any(Object));
  });

  it('continues history pages with a visible status and stops after a repeated cursor', async () => {
    let release!: (value: unknown) => void;
    const second = new Promise(resolve => { release = resolve; });
    let requests = 0;
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      requests += 1;
      if (path === '/cases?limit=50&scope=daily') return { items: [], next_cursor: 'page-2' } as never;
      if (path.endsWith('cursor=page-2')) return second as never;
      throw new Error(path);
    });
    mount(<HistoryPage />);
    await userEvent.click(await screen.findByRole('button', { name: '加载更早病例' }));
    expect(await screen.findByText(/正在继续搜索后续病例/)).toBeTruthy();
    release({ items: [], next_cursor: 'page-2' });
    expect(await screen.findByText('没有匹配病例')).toBeTruthy();
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(requests).toBe(2);
  });

  it('finds and stably deduplicates a match from a later history page', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/cases?limit=50&scope=daily') return { items: [caseItem(A, '第一页车型')], next_cursor: 'page-2' } as never;
      if (path.endsWith('cursor=page-2')) return { items: [caseItem(A, '重复车型'), caseItem(B, '目标车型')], next_cursor: null } as never;
      throw new Error(path);
    });
    mount(<HistoryPage />);
    await userEvent.click(await screen.findByRole('button', { name: '加载更早病例' }));
    expect(await screen.findByText('目标车型')).toBeTruthy();
    expect(screen.queryByText('重复车型')).toBeNull();
  });

  it('filters loaded history without starting another request generation', async () => {
    let releaseOld!: (value: unknown) => void;
    const oldPage = new Promise(resolve => { releaseOld = resolve; });
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/cases?limit=50&scope=daily') return { items: [], next_cursor: 'page-2' } as never;
      if (path.endsWith('cursor=page-2')) return oldPage as never;
      throw new Error(path);
    });
    mount(<HistoryPage />);
    const input = screen.getByLabelText(/筛选病例/);
    await userEvent.click(await screen.findByRole('button', { name: '加载更早病例' }));
    await userEvent.type(input, '新目标');
    releaseOld({ items: [caseItem(A, '旧目标车型')], next_cursor: null });
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByText('旧目标车型')).toBeNull();
  });
});

describe('WP-14 evidence search context remediation', () => {
  function mockDocuments(searches: Array<Promise<unknown> | Error>) {
    let searchCall = 0;
    return vi.spyOn(apiClient, 'request').mockImplementation(async (path, options) => {
      if (path === '/client-config') return { upload_max_bytes: 4096, retrieval_profile: 'formal' } as never;
      if (path === '/documents?limit=50') return { items: [document(A, '资料A', AV), document(B, '资料B', BV)], next_cursor: null } as never;
      if (path.includes('/chunks')) return { items: [], next_cursor: null } as never;
      if (path.includes(AV)) return version(A, AV) as never;
      if (path.includes(BV)) return version(B, BV) as never;
      if (path === '/evidence/search' && options?.method === 'POST') {
        const item = searches[searchCall++];
        if (item instanceof Error) throw item;
        return item as never;
      }
      throw new Error(path);
    });
  }

  it('ignores late success and late error after A changes to B', async () => {
    let resolveLate!: (value: unknown) => void;
    let rejectLate!: (error: Error) => void;
    const lateSuccess = new Promise(resolve => { resolveLate = resolve; });
    const lateError = new Promise((_resolve, reject) => { rejectLate = reject; });
    mockDocuments([lateSuccess, lateError]);
    mount(<DocumentsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /资料A/ }));
    await userEvent.type(screen.getByLabelText('问题'), '第一次');
    await userEvent.click(screen.getByRole('button', { name: '调用真实检索' }));
    await userEvent.click(screen.getByRole('button', { name: /资料B/ }));
    resolveLate({ chunks: [{ text: 'A迟到成功' }], excluded: [], trace: {} });
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByText(/A迟到成功/)).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: /资料A/ }));
    await userEvent.click(screen.getByRole('button', { name: '调用真实检索' }));
    await userEvent.click(screen.getByRole('button', { name: /资料B/ }));
    rejectLate(new Error('A迟到错误'));
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByText('A迟到错误')).toBeNull();
  });

  it('blocks ABA stale results while allowing the newest same-context result', async () => {
    let releaseOld!: (value: unknown) => void;
    const old = new Promise(resolve => { releaseOld = resolve; });
    mockDocuments([old, Promise.resolve({ chunks: [{ text: 'A最新结果' }], excluded: [], trace: {} })]);
    mount(<DocumentsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /资料A/ }));
    await userEvent.type(screen.getByLabelText('问题'), '同一问题');
    await userEvent.click(screen.getByRole('button', { name: '调用真实检索' }));
    await userEvent.click(screen.getByRole('button', { name: /资料B/ }));
    await userEvent.click(screen.getByRole('button', { name: /资料A/ }));
    await userEvent.click(screen.getByRole('button', { name: '调用真实检索' }));
    expect(await screen.findByText(/A最新结果/)).toBeTruthy();
    releaseOld({ chunks: [{ text: 'A旧代次结果' }], excluded: [], trace: {} });
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByText(/A旧代次结果/)).toBeNull();
    expect(screen.getByText(/A最新结果/)).toBeTruthy();
  });

  it('shows the latest current-context error instead of swallowing it', async () => {
    mockDocuments([new Error('当前检索失败')]);
    mount(<DocumentsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /资料A/ }));
    await userEvent.type(screen.getByLabelText('问题'), '检查当前错误');
    await userEvent.click(screen.getByRole('button', { name: '调用真实检索' }));
    expect(await screen.findByText('当前检索失败')).toBeTruthy();
    expect((screen.getByLabelText('问题') as HTMLInputElement).value).toBe('检查当前错误');
  });
});
