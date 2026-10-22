import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../src/formal/api-client';
import { ReferencesPage } from '../src/formal/pages/ReferencesPage';
import { groupReferences, referenceIdFrom, sectionHeadings } from '../src/formal/references';
import type { ReferenceItem } from '../src/formal/types';

const area = { template_id: 'tayron-dkvb-p0299', template_version: '2', area_id: 'boost-air' };
const item = (version: string, status: string, extra: Partial<ReferenceItem> = {}): ReferenceItem => ({
  document_id: 'boost-manual', version, title: '增压空气通路', status, error_code: null, source_kind: 'upload',
  content_hash: 'h' + version, chars: 1200, chunk_count: status === 'ready' ? 3 : null, chunker_version: null,
  vector_fingerprint: status === 'ready' ? 'bge-m3-onnx-v1' : null, always_include: [], requested_areas: [area],
  bound_areas: status === 'ready' ? [area] : [], created_at: `2026-10-22T0${version}:00:00Z`,
  updated_at: `2026-10-22T0${version}:00:00Z`, ...extra,
});
const targets = { templates: [{ template_id: 'tayron-dkvb-p0299', version: '2', title: '增压不足初始排查',
  areas: [{ id: 'boost-air', title: '增压空气通路' }, { id: 'pressure', title: '压力信号' }] }] };
const chunks = { document_id: 'boost-manual', version: '2', status: 'ready', vector_fingerprint: 'bge-m3-onnx-v1', items: [
  { ordinal: 0, section: '## 1. 阅读入口', subsection: null, text: '导航', char_start: 0, char_end: 5, identifiers: [], searchable: false, has_vector: false },
  { ordinal: 1, section: '## 2. 检查接头', subsection: '### 2.1 外观', text: '检查 G31 插头', char_start: 6, char_end: 20, identifiers: ['G31'], searchable: true, has_vector: true },
] };

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
});

describe('ReferencesPage', () => {
  it('shows versions with status and the chunks of a ready version', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async (path: string) => {
      if (path === '/area-references') return { items: [item('1', 'ready'), item('2', 'failed', { error_code: 'MODEL_PATH_UNAVAILABLE' })] } as never;
      if (path === '/area-references/targets') return targets as never;
      if (path === '/area-references/boost-manual/versions/1/chunks') return { ...chunks, version: '1' } as never;
      throw new Error(path);
    });
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /第 2 版/ }));
    expect(screen.getByRole('alert').textContent).toContain('MODEL_PATH_UNAVAILABLE');
    await userEvent.click(screen.getByRole('button', { name: /第 1 版/ }));
    expect(await screen.findByText(/2\. 检查接头/)).toBeTruthy();
    expect(screen.getByText('增压不足初始排查 v2 · 增压空气通路', { selector: 'dd' })).toBeTruthy();
    // Navigation sections are hidden until asked for.
    expect(screen.queryByText('导航章节，不参与检索')).toBeNull();
    await userEvent.click(screen.getByLabelText('只看参与检索的'));
    expect(screen.getByText('导航章节，不参与检索')).toBeTruthy();
  });

  it('asks for the file, title and vehicle only, with no template or area choices', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async (path: string) => {
      if (path === '/area-references') return { items: [] } as never;
      if (path === '/area-references/targets') return targets as never;
      throw new Error(path);
    });
    mount();
    const markdown = '# 增压\n\n## 1. 检查什么\n\n正文\n\n## 2. 怎样确认\n\n正文\n';
    fireEvent.change(await screen.findByLabelText('Markdown 文件'), { target: { files: [new File([markdown], 'Boost v3.md', { type: 'text/markdown' })] } });
    expect(await screen.findByLabelText('2. 怎样确认')).toBeTruthy();
    expect((screen.getByLabelText('资料编号') as HTMLInputElement).value).toBe('boost-v3');
    expect((screen.getByLabelText('标题') as HTMLInputElement).value).toBe('Boost v3');
    for (const name of ['品牌', '车型', '年款', '发动机代码']) expect(screen.getByLabelText(name)).toBeTruthy();
    expect(screen.queryByText(/请填写适用车型/)).toBeNull();  // optional
    expect(screen.queryByText('用于哪些区域 *')).toBeNull();
    expect(screen.queryByText('新资料还是新版本')).toBeNull();
    expect((screen.getByRole('button', { name: '上传并处理' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('offers a new version from the manual itself', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async (path: string) => {
      if (path === '/area-references') return { items: [item('1', 'ready')] } as never;
      if (path === '/area-references/targets') return targets as never;
      throw new Error(path);
    });
    mount();
    await userEvent.click(await screen.findByRole('button', { name: '上传新版本' }));
    expect(screen.getByLabelText('增压空气通路 的新版本（Markdown）')).toBeTruthy();
    await userEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.queryByLabelText('增压空气通路 的新版本（Markdown）')).toBeNull();
  });

  it('refuses a file without ## sections', async () => {
    vi.spyOn(apiClient, 'request').mockImplementation(async (path: string) => {
      if (path === '/area-references') return { items: [] } as never;
      if (path === '/area-references/targets') return targets as never;
      throw new Error(path);
    });
    mount();
    fireEvent.change(await screen.findByLabelText('Markdown 文件'), { target: { files: [new File(['# 只有标题\n正文'], 'x.md')] } });
    expect(await screen.findByText(/没有 "## " 二级标题/)).toBeTruthy();
  });
});
