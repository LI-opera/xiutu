import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../src/lib/api-client';
import { ReferencesPage } from '../src/pages/ReferencesPage';
import { groupReferences, referenceIdFrom, sectionHeadings, suggestions, vehicleText } from '../src/lib/references';
import type { ReferenceItem } from '../src/lib/types';

const vehicle = { brand: '大众', model: '探岳', year: 2019, engine_code: 'DKVB' };
const item = (version: string, status: string, extra: Partial<ReferenceItem> = {}): ReferenceItem => ({
  document_id: 'boost-manual', version, title: '增压空气通路', status, error_code: null, source_kind: 'upload',
  content_hash: 'h' + version, chars: 1200, chunk_count: status === 'ready' ? 3 : null, chunker_version: null,
  vector_fingerprint: status === 'ready' ? 'bge-m3-onnx-v1' : null, always_include: [], vehicle,
  created_at: `2026-10-22T0${version}:00:00Z`, updated_at: `2026-10-22T0${version}:00:00Z`, ...extra,
});
const chunks = { document_id: 'boost-manual', version: '1', status: 'ready', vector_fingerprint: 'bge-m3-onnx-v1', items: [
  { ordinal: 0, section: '## 1. 阅读入口', subsection: null, text: '导航', char_start: 0, char_end: 5, identifiers: [], searchable: false, has_vector: false },
  { ordinal: 1, section: '## 2. 检查接头', subsection: '### 2.1 外观', text: '检查 G31 插头', char_start: 6, char_end: 20, identifiers: ['G31'], searchable: true, has_vector: true },
] };

type Handler = (path: string, options?: { body?: unknown }) => unknown;
function serve(extra: Handler = () => undefined, items: ReferenceItem[] = []) {
  return vi.spyOn(apiClient, 'request').mockImplementation(async (path: string, options?: { body?: unknown }) => {
    const answer = extra(path, options);
    if (answer !== undefined) return answer as never;
    if (path === '/area-references') return { items } as never;
    if (path === '/area-references/vehicles') return { vehicles: [vehicle] } as never;
    throw new Error(path);
  });
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ReferencesPage /></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('reference helpers', () => {
  it('derives a valid document ID from a file name', () => {
    expect(referenceIdFrom('Boost Air_v3.md')).toBe('boost-air-v3');
    expect(referenceIdFrom('增压资料.md', () => 'abc123')).toBe('doc-abc123');
  });

  it('offers only ## headings as always-included sections', () => {
    expect(sectionHeadings('# 标题\r\n## 1. 范围\n### 1.1 细节\n##没有空格\n## 2. 确认\n')).toEqual(['## 1. 范围', '## 2. 确认']);
  });

  it('groups versions by document, newest first', () => {
    const [group] = groupReferences([item('1', 'ready'), item('2', 'processing', { title: '增压空气通路（新）' })]);
    expect(group.versions.map(v => v.version)).toEqual(['2', '1']);
    expect(group.title).toBe('增压空气通路（新）');
  });

  it('shows vehicles and suggests known values', () => {
    expect(vehicleText(vehicle)).toBe('大众 探岳 2019 DKVB');
    expect(vehicleText({ brand: null, model: null, year: null, engine_code: null })).toBe('未填写');
    expect(suggestions([vehicle, { ...vehicle, model: '途观' }], 'model')).toEqual(['探岳', '途观']);
  });
});

describe('ReferencesPage', () => {
  it('lists one row per manual and opens its latest version, history and chunks in place', async () => {
    serve(path => (path === '/area-references/boost-manual/versions/1/chunks' ? chunks : undefined),
      [item('1', 'ready'), item('2', 'failed', { error_code: 'MODEL_PATH_UNAVAILABLE' })]);
    mount();
    const row = await screen.findByRole('button', { name: /增压空气通路/ });
    expect(screen.getByText('第 2 版')).toBeTruthy();
    expect(screen.getByText('大众 探岳 2019 DKVB')).toBeTruthy();
    await userEvent.click(row);
    expect(screen.getByRole('alert').textContent).toContain('MODEL_PATH_UNAVAILABLE');
    await userEvent.click(screen.getByRole('button', { name: '第 1 版' }));
    await userEvent.click(screen.getByText(/^切块/));
    expect(await screen.findByText(/2\. 检查接头/)).toBeTruthy();
    expect(screen.queryByText('导航章节，不参与检索')).toBeNull();
    await userEvent.click(screen.getByLabelText('只看参与检索的'));
    expect(screen.getByText('导航章节，不参与检索')).toBeTruthy();
  });

  it('filters manuals by name, number or vehicle', async () => {
    serve(undefined, [item('1', 'ready'), item('1', 'ready', { document_id: 'turbo-manual', title: '涡轮增压器本体', vehicle: { ...vehicle, model: '途观' } })]);
    mount();
    await screen.findByRole('button', { name: /涡轮增压器本体/ });
    await userEvent.type(screen.getByLabelText('搜索资料'), '途观');
    expect(screen.queryByRole('button', { name: /增压空气通路/ })).toBeNull();
    expect(screen.getByRole('button', { name: /涡轮增压器本体/ })).toBeTruthy();
  });

  it('uploads a manual with its required vehicle and no template or area choices', async () => {
    const posted: unknown[] = [];
    serve((path, options) => {
      if (path === '/area-references' && options?.body) {
        posted.push(options.body);
        return { document_id: 'boost-v3', version: '1', status: 'queued', reused: false, run_id: 'r1' };
      }
      return undefined;
    });
    mount();
    const submit = await screen.findByRole('button', { name: '上传并处理' });
    const markdown = '# 增压\n\n## 1. 检查什么\n\n正文\n\n## 2. 怎样确认\n\n正文\n';
    fireEvent.change(screen.getByLabelText('Markdown 文件'), { target: { files: [new File([markdown], 'Boost v3.md', { type: 'text/markdown' })] } });
    expect(await screen.findByLabelText('2. 怎样确认')).toBeTruthy();
    expect((screen.getByLabelText('资料编号') as HTMLInputElement).value).toBe('boost-v3');
    expect(screen.getByText('请填写适用车型的品牌、车型和发动机代码')).toBeTruthy();
    expect(screen.queryByText('用于哪些区域 *')).toBeNull();
    expect((submit as HTMLButtonElement).disabled).toBe(true);
    await userEvent.type(screen.getByLabelText('品牌'), '大众');
    await userEvent.type(screen.getByLabelText('车型'), '探岳');
    await userEvent.type(screen.getByLabelText('年款'), '2019');
    await userEvent.type(screen.getByLabelText('发动机代码'), 'DKVB');
    await userEvent.click(screen.getByLabelText('2. 怎样确认'));
    await waitFor(() => expect((submit as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(submit);
    expect(await screen.findByText(/已受理为第 1 版/)).toBeTruthy();
    expect(posted).toEqual([{ document_id: 'boost-v3', title: 'Boost v3', filename: 'Boost v3.md', content: markdown,
      always_include: ['## 2. 怎样确认'], vehicle }]);
  });

  it('uploads a new version from the manual itself with only the file', async () => {
    const posted: unknown[] = [];
    serve((path, options) => {
      if (path === '/area-references/boost-manual/versions' && options?.body) {
        posted.push(options.body);
        return { document_id: 'boost-manual', version: '2', status: 'queued', reused: false, run_id: 'r2' };
      }
      return undefined;
    }, [item('1', 'ready')]);
    mount();
    await userEvent.click(await screen.findByRole('button', { name: '上传新版本' }));
    const markdown = '# 增压\n\n## 1. 检查什么\n\n新正文\n';
    fireEvent.change(screen.getByLabelText('增压空气通路 的新版本（Markdown）'), { target: { files: [new File([markdown], 'v2.md')] } });
    const send = screen.getAllByRole('button', { name: '上传新版本' }).find(b => b.closest('.new-version-form'))!;
    await waitFor(() => expect((send as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(send);
    await waitFor(() => expect(posted).toEqual([{ filename: 'v2.md', content: markdown }]));
    expect(screen.queryByLabelText('增压空气通路 的新版本（Markdown）')).toBeNull();
  });

  it('refuses a file without ## sections before sending anything', async () => {
    const request = serve();
    mount();
    fireEvent.change(await screen.findByLabelText('Markdown 文件'), { target: { files: [new File(['# 只有标题\n正文'], 'x.md')] } });
    expect(await screen.findByText(/没有 "## " 二级标题/)).toBeTruthy();
    expect(request.mock.calls.some(([, options]) => options?.body !== undefined)).toBe(false);
  });
});
