import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { apiClient } from '../src/lib/api-client';
import { HistoryPage } from '../src/pages/HistoryPage';

const A = '11111111-1111-4111-8111-111111111111';
const B = '22222222-2222-4222-8222-222222222222';
const caseItem = (id: string, model: string) => ({ id, vehicle: { model, year: null, engine_code: null, engine_family: null, vin: null }, fault_description: `${model}故障`, fault_codes: [], intake_snapshot: {}, revision: 0, status: 'draft', created_at: '2026-09-21T00:00:00Z', updated_at: '2026-09-21T00:00:00Z', experience: { category: 'continue', label: '可继续', guidance: '进入病例', priority: 10 } });

function mount(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('history pagination', () => {
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
