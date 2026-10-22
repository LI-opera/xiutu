import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import { ColumnHeader } from '../components/ColumnHeader';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/States';
import {
  groupReferences, isWorking, MAX_REFERENCE_CHARS, REFERENCE_ID, referenceIdFrom, sectionHeadings,
  statusLabel, statusTone, targetKey,
} from '../references';
import type { AreaTarget, ReferenceChunkList, ReferenceList, ReferenceTargets } from '../types';

type Selected = { documentId: string; version: string };

function areaNames(targets: ReferenceTargets | undefined) {
  const names = new Map<string, string>();
  targets?.templates.forEach(t => t.areas.forEach(a => names.set(
    targetKey({ template_id: t.template_id, template_version: t.version, area_id: a.id }), `${t.title} v${t.version} · ${a.title}`)));
  return names;
}

export function ReferencesPage() {
  const [selected, setSelected] = useState<Selected | null>(null);
  const [newVersionOf, setNewVersionOf] = useState<string | null>(null);
  const [onlySearchable, setOnlySearchable] = useState(true);

  const list = useQuery({
    queryKey: ['area-references'],
    queryFn: ({ signal }) => apiClient.request<ReferenceList>('/area-references', { signal }),
    refetchInterval: query => (query.state.data?.items.some(item => isWorking(item.status)) ? 1_500 : false),
  });
  const targets = useQuery({
    queryKey: ['area-reference-targets'],
    queryFn: ({ signal }) => apiClient.request<ReferenceTargets>('/area-references/targets', { signal }),
  });
  const groups = useMemo(() => groupReferences(list.data?.items ?? []), [list.data]);
  const names = useMemo(() => areaNames(targets.data), [targets.data]);
  const current = list.data?.items.find(i => i.document_id === selected?.documentId && i.version === selected?.version) ?? null;
  const chunks = useQuery({
    queryKey: ['area-reference-chunks', selected?.documentId, selected?.version],
    queryFn: ({ signal }) => apiClient.request<ReferenceChunkList>(
      `/area-references/${encodeURIComponent(selected!.documentId)}/versions/${encodeURIComponent(selected!.version)}/chunks`, { signal }),
    enabled: !!selected && current?.status === 'ready',
  });
  const shownChunks = (chunks.data?.items ?? []).filter(c => !onlySearchable || c.searchable);
  const label = (target: AreaTarget) => names.get(targetKey(target)) ?? targetKey(target);

  return <div className="references-page">
    <section className="page-card upload-card"><ColumnHeader eyebrow="UPLOAD" title="上传资料" />
      <UploadForm />
    </section>
    <div className="documents-layout">
      <section className="page-card document-sidebar"><ColumnHeader eyebrow="MANUALS" title="维修资料" />
        <p className="section-note">选择一个版本，右侧查看处理状态和切块。资料有更新时，在它下面上传新版本。</p>
        {list.isPending && <LoadingState />}{list.error && <ErrorState error={list.error} onRetry={() => list.refetch()} />}
        {list.data && !groups.length && <EmptyState title="还没有资料">在上方上传第一份 Markdown 资料。</EmptyState>}
        <div className="document-list reference-list">{groups.map(group => <div key={group.documentId} className="reference-group">
          <div className="reference-group-head">
            <span><strong>{group.title}</strong><small>{group.documentId}</small></span>
            <button type="button" className="secondary small" aria-expanded={newVersionOf === group.documentId}
              onClick={() => setNewVersionOf(newVersionOf === group.documentId ? null : group.documentId)}>上传新版本</button>
          </div>
          {newVersionOf === group.documentId && <NewVersionForm title={group.title} onClose={() => setNewVersionOf(null)} />}
          {group.versions.map(v => <button type="button" key={v.version}
            className={selected?.documentId === v.document_id && selected.version === v.version ? 'selected' : ''}
            onClick={() => setSelected({ documentId: v.document_id, version: v.version })}>
            <span>第 {v.version} 版 <StatusBadge value={statusLabel[v.status] ?? v.status} tone={statusTone(v.status)} /></span>
            <small>{v.chunk_count !== null ? `${v.chunk_count} 块` : '尚未切块'} · {v.created_at.slice(0, 10)}</small>
          </button>)}
        </div>)}</div>
      </section>
      <section className="page-card document-detail"><ColumnHeader eyebrow="VERSION" title="版本与切块" />
        {!selected && <EmptyState title="尚未选择资料">选择左侧的某个版本，查看处理状态和切块结果。</EmptyState>}
        {selected && !current && list.data && <EmptyState title="找不到这个版本">列表里已没有它，请重新选择。</EmptyState>}
        {current && <>
          <h3>{current.title} · 第 {current.version} 版</h3>
          <div className="badge-row">
            <StatusBadge value={statusLabel[current.status] ?? current.status} tone={statusTone(current.status)} />
            <StatusBadge value={current.source_kind === 'upload' ? '页面上传' : '脚本导入'} />
            {current.chunk_count !== null && <StatusBadge value={`${current.chunk_count} 块`} />}
            <StatusBadge value={current.vector_fingerprint ? `向量 ${current.vector_fingerprint}` : '没有向量'} tone={current.vector_fingerprint ? 'good' : 'warn'} />
          </div>
          {current.status === 'failed' && <div className="callout" role="alert">处理失败：<code>{current.error_code}</code>。修正后重新上传同一份内容即可重试。</div>}
          {isWorking(current.status) && <LoadingState label="后台正在切块、计算向量" />}
          <dl className="version-meta">
            <dt>资料编号</dt><dd>{current.document_id}</dd>
            <dt>字数</dt><dd>{current.chars}</dd>
            <dt>适用车型</dt><dd>（后端改完后显示）</dd>
            <dt>目前用于</dt><dd>{current.bound_areas.length ? current.bound_areas.map(label).join('；') : '—'}</dd>
            <dt>必带章节</dt><dd>{current.always_include.length ? current.always_include.join('；') : '无'}</dd>
          </dl>
          {current.status === 'ready' && <>
            <div className="chunk-toolbar"><h3>切块（{chunks.data?.items.length ?? '…'}）</h3>
              <label className="inline-check"><input type="checkbox" checked={onlySearchable} onChange={e => setOnlySearchable(e.target.checked)} />只看参与检索的</label></div>
            {chunks.isPending && <LoadingState />}{chunks.error && <ErrorState error={chunks.error} onRetry={() => chunks.refetch()} />}
            {shownChunks.map(chunk => <article className="chunk" key={chunk.ordinal}>
              <small>#{chunk.ordinal} · {chunk.section}{chunk.subsection ? ` › ${chunk.subsection}` : ''}</small>
              <div className="badge-row">
                {!chunk.searchable && <StatusBadge value="导航章节，不参与检索" tone="warn" />}
                {chunk.searchable && <StatusBadge value={chunk.has_vector ? '有向量' : '缺向量'} tone={chunk.has_vector ? 'good' : 'bad'} />}
                {chunk.identifiers.map(code => <StatusBadge key={code} value={code} />)}
              </div>
              <details><summary>正文（{chunk.text.length} 字）</summary><p>{chunk.text}</p></details>
            </article>)}
          </>}
        </>}
      </section>
    </div>
  </div>;
}

const PREVIEW_NOTE = '样式预览：上传要等后端改成"按车型匹配"后才启用。';

/** A new manual: the file, which vehicle it applies to, and its title. Nothing tied to templates. */
function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [content, setContent] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [title, setTitle] = useState('');
  const [vehicle, setVehicle] = useState({ brand: '', model: '', yearFrom: '', yearTo: '', engineCode: '' });
  const [always, setAlways] = useState<string[]>([]);
  const headings = useMemo(() => sectionHeadings(content), [content]);

  const chooseFile = async (next: File | null) => {
    setFile(next); setAlways([]);
    setContent(next ? await next.text() : '');
    if (next) { setDocumentId(referenceIdFrom(next.name)); setTitle(next.name.replace(/\.[^.]+$/, '')); }
  };
  const field = (key: keyof typeof vehicle) => ({
    value: vehicle[key], onChange: (e: React.ChangeEvent<HTMLInputElement>) => setVehicle({ ...vehicle, [key]: e.target.value }),
  });
  const toggleHeading = (heading: string) => setAlways(prev => prev.includes(heading) ? prev.filter(h => h !== heading) : [...prev, heading]);
  const problems = [
    !file && '请选择 Markdown 文件',
    file && !headings.length && '文件里没有 "## " 二级标题，无法按章节切块',
    content.length > MAX_REFERENCE_CHARS && `资料超过 ${MAX_REFERENCE_CHARS} 字`,
    !title.trim() && '请填写标题',
    !REFERENCE_ID.test(documentId) && '资料编号只能用小写字母、数字和连字符（2～100 个字符）',
    !(vehicle.brand.trim() && vehicle.model.trim()) && '请填写适用车型（至少品牌和车型）',
  ].filter(Boolean) as string[];

  return <div className="upload-form">
    <p className="section-note">上传 Markdown 资料并写明适用车型。后台自动切块、计算向量；分析时按病例的车型找资料，再按题目检索章节。</p>
    <div className="upload-row three">
      <label>Markdown 文件<input type="file" accept=".md,.markdown" onChange={e => chooseFile(e.target.files?.[0] ?? null)} /></label>
      <label>标题<input value={title} maxLength={200} onChange={e => setTitle(e.target.value)} /></label>
      <label>资料编号<input value={documentId} maxLength={100} placeholder="选文件后自动生成" onChange={e => setDocumentId(e.target.value)} /></label>
    </div>
    <fieldset className="choice-group"><legend>适用车型 *</legend>
      <div className="vehicle-row">
        <label>品牌<input {...field('brand')} placeholder="如 大众" /></label>
        <label>车型<input {...field('model')} placeholder="如 探岳" /></label>
        <label>年款从<input {...field('yearFrom')} inputMode="numeric" placeholder="如 2019" /></label>
        <label>年款到<input {...field('yearTo')} inputMode="numeric" placeholder="不填表示至今" /></label>
        <label>发动机代码<input {...field('engineCode')} placeholder="如 DKVB" /></label>
      </div>
    </fieldset>
    {headings.length > 0 && <fieldset className="choice-group"><legend>必带章节（可选：每次分析都发给 AI）</legend>
      <div className="heading-choices">{headings.map(h => <label className="inline-check" key={h}><input type="checkbox" checked={always.includes(h)} onChange={() => toggleHeading(h)} />{h.replace(/^## +/, '')}</label>)}</div>
    </fieldset>}
    <div className="upload-actions">
      <button type="button" disabled title={PREVIEW_NOTE}>上传并处理</button>
      <span className="muted">{PREVIEW_NOTE}</span>
      {file && problems.length > 0 && <ul className="inline-error">{problems.map(p => <li key={p}>{p}</li>)}</ul>}
    </div>
  </div>;
}

/** A new version of an existing manual: only the file; its number, title and vehicle carry over. */
function NewVersionForm({ title, onClose }: { title: string; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  return <div className="new-version-form">
    <label>{title} 的新版本（Markdown）<input type="file" accept=".md,.markdown" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
    <div className="upload-actions">
      <button type="button" disabled title={PREVIEW_NOTE}>上传新版本{file ? `：${file.name}` : ''}</button>
      <button type="button" className="text-button" onClick={onClose}>取消</button>
    </div>
  </div>;
}
