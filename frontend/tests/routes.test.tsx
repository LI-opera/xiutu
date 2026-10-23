import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { apiClient, ApiError } from '../src/formal/api-client';
import { HistoryPage } from '../src/formal/pages/HistoryPage';
import { WorkbenchPage } from '../src/formal/pages/WorkbenchPage';
import { SessionBoundary } from '../src/formal/session';

const wrapper = (ui: React.ReactNode, initial = ['/']) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={initial}>{ui}</MemoryRouter></QueryClientProvider>);
};
const caseItem = { id: '11111111-1111-4111-8111-111111111111', vehicle: { model: '测试车型', year: null, engine_code: null, engine_family: null, vin: null }, fault_description: '故障描述', fault_codes: [], intake_snapshot: {}, revision: 1, status: 'waiting_input', created_at: '2026-09-21T00:00:00Z', updated_at: '2026-09-21T00:00:00Z', experience: { category: 'continue', label: '可继续', guidance: '进入病例', priority: 10 } };
afterEach(cleanup);

describe('formal routes', () => {
  it('history loads prioritized cases and opens only the case the user selects', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ items: [caseItem], next_cursor: null });
    function Location() { return <output>{useLocation().pathname}</output>; }
    wrapper(<Routes><Route path="/history" element={<HistoryPage />} /><Route path="/workbench/:caseId" element={<Location />} /></Routes>, ['/history']);
    expect(await screen.findByText('测试车型')).toBeTruthy();
    expect(request).toHaveBeenCalledWith('/cases?limit=50&scope=daily', expect.any(Object));
    await userEvent.click(screen.getByRole('button', { name: /测试车型/ }));
    expect(screen.getByText(`/workbench/${caseItem.id}`)).toBeTruthy();
  });

  it('opens a template case in the template workbench and refuses any other case', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue(caseItem as never);
    wrapper(<Routes><Route path="/workbench/:caseId" element={<WorkbenchPage />} /></Routes>, [`/workbench/${caseItem.id}`]);
    expect(await screen.findByText('无法打开此病例')).toBeTruthy();
    expect(request).toHaveBeenCalledWith(`/cases/${caseItem.id}`, expect.any(Object));
  });

  it('shows login after a 401 session failure instead of swallowing it', async () => {
    vi.spyOn(apiClient, 'request').mockRejectedValue(new ApiError(401, 'UNAUTHORIZED', 'Authentication required', 'trace', null, false));
    wrapper(<SessionBoundary><div>private</div></SessionBoundary>);
    expect(await screen.findByText('连接修途工作台')).toBeTruthy();
    expect(screen.queryByText('private')).toBeNull();
  });

  it('refreshes the local session after a stale-cookie response', async () => {
    const session = { actor_id: caseItem.id, csrf_token: 'local-csrf', expires_in: 3600 };
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue(session);
    wrapper(<SessionBoundary><div>private</div></SessionBoundary>);
    expect(await screen.findByText('private')).toBeTruthy();
    window.dispatchEvent(new Event('xiutu:unauthorized'));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('连接修途工作台')).toBeNull();
  });
});

it('keeps an entered draft mounted when the restored session arrives', async()=>{
  const session={actor_id:caseItem.id,csrf_token:'old',expires_in:3600};
  vi.spyOn(apiClient,'request').mockResolvedValue(session);
  wrapper(<SessionBoundary><input aria-label="接诊草稿" defaultValue="" /></SessionBoundary>);
  const input=await screen.findByLabelText('接诊草稿');
  fireEvent.change(input,{target:{value:'用户尚未提交的内容'}});
  window.dispatchEvent(new CustomEvent('xiutu:session-restored',{detail:{...session,csrf_token:'fresh'}}));
  await waitFor(()=>expect(screen.getByLabelText('接诊草稿')).toBe(input));
  expect((input as HTMLInputElement).value).toBe('用户尚未提交的内容');
});
