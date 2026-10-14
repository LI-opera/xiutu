import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient, ApiError } from '../src/formal/api-client';
import { DocumentsPage } from '../src/formal/pages/DocumentsPage';

const A = '11111111-1111-4111-8111-111111111111';
const AV = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const B = '22222222-2222-4222-8222-222222222222';
const BV = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const version = (id: string) => ({ document_id: id === AV ? A : B, version_id: id, review_status: 'pending', index_status: 'blocked', index_implemented: true, formal_usable: false, active_index_id: null, index_run_id: null, index_exclusion: 'REVIEW_REQUIRED', last_index_status: null, index_error: {}, sha256: id === AV ? 'hash-a' : 'hash-b', mime: 'text/markdown', metadata: { synthetic: false, source_status: 'unknown', license_status: 'unknown', scope: {} }, parse_status: 'review_pending', run_id: '33333333-3333-4333-8333-333333333333', parser_version: 'p', chunker_version: 'c', tokenizer: 't', page_count: 1, page_issues: [], parse_error: {}, review_history: [] });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><DocumentsPage /></QueryClientProvider>);
}

afterEach(cleanup);

describe('DocumentsPage state wiring', () => {
  it('keeps a late A response from replacing selected B', async () => {
    let resolveA!: (value: unknown) => void;
    const delayedA = new Promise(resolve => { resolveA = resolve; });
    vi.spyOn(apiClient, 'request').mockImplementation(async (path: string) => {
      if (path === '/client-config') return { upload_max_bytes: 4096, retrieval_profile: 'formal' } as never;
      if (path.startsWith('/documents?')) return { items: [{ id: A, title: '资料A', source_kind: 'local', created_at: '', latest_version_id: AV }, { id: B, title: '资料B', source_kind: 'local', created_at: '', latest_version_id: BV }], next_cursor: null } as never;
      if (path.includes(AV) && !path.includes('chunks')) return delayedA as never;
      if (path.includes(BV) && !path.includes('chunks')) return version(BV) as never;
      if (path.includes('chunks')) return { items: [], next_cursor: null } as never;
      throw new Error(path);
    });
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /资料A/ }));
    await userEvent.click(screen.getByRole('button', { name: /资料B/ }));
    expect(await screen.findByText(BV)).toBeTruthy();
    resolveA(version(AV));
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.getByText(BV)).toBeTruthy();
    expect(screen.queryByText(AV)).toBeNull();
  });

  it('resets declarations for a newly selected file even when the name matches', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/client-config') return { upload_max_bytes: 4096, retrieval_profile: 'formal' } as never;
      return { items: [], next_cursor: null } as never;
    });
    mount();
    const input = screen.getByLabelText('Markdown / PDF') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['A'], 'same.md', { type: 'text/markdown' })] } });
    await userEvent.selectOptions(screen.getByLabelText('资料性质 *'), 'synthetic');
    await userEvent.type(screen.getByLabelText(/来源说明/), 'A source');
    fireEvent.change(input, { target: { files: [new File(['B'], 'same.md', { type: 'text/markdown' })] } });
    expect((screen.getByLabelText('资料性质 *') as HTMLSelectElement).value).toBe('');
    expect((screen.getByLabelText(/来源说明/) as HTMLTextAreaElement).value).toBe('');
    expect((screen.getByRole('button', { name: '上传并读取状态' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('keeps selected material and the current file draft after a 413 upload failure', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async (path: string, options?: { method?: string }) => {
      if (path === '/client-config') return { upload_max_bytes: 4096, retrieval_profile: 'formal' } as never;
      if (path.startsWith('/documents?')) return { items: [{ id: A, title: '资料A', source_kind: 'local', created_at: '', latest_version_id: AV }], next_cursor: null } as never;
      if (path.includes(AV) && path.includes('chunks')) return { items: [], next_cursor: null } as never;
      if (path.includes(AV)) return version(AV) as never;
      if (path === '/documents' && options?.method === 'POST') throw new ApiError(413, 'UPLOAD_TOO_LARGE', 'too large', 'trace-413', { limit: 4096 }, false);
      throw new Error(path);
    });
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /资料A/ }));
    expect(await screen.findByText(AV)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Markdown / PDF'), { target: { files: [new File(['B'], 'b.md', { type: 'text/markdown' })] } });
    await userEvent.selectOptions(screen.getByLabelText('资料性质 *'), 'nonfiction');
    await userEvent.type(screen.getByLabelText(/来源说明/), 'draft source');
    await userEvent.click(screen.getByRole('button', { name: '上传并读取状态' }));
    expect(await screen.findByText(/文件超过服务端/)).toBeTruthy();
    expect(screen.getByText(AV)).toBeTruthy();
    expect((screen.getByLabelText('资料性质 *') as HTMLSelectElement).value).toBe('nonfiction');
    expect((screen.getByLabelText(/来源说明/) as HTMLTextAreaElement).value).toBe('draft source');
  });
});
