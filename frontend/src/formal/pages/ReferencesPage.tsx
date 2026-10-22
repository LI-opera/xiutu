import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, idempotencyKey } from '../api-client';
import { ColumnHeader } from '../components/ColumnHeader';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/States';
import {
  groupReferences, isWorking, MAX_REFERENCE_CHARS, REFERENCE_ID, referenceIdFrom, sectionHeadings,
  statusLabel, statusTone, targetKey,
} from '../references';
import type { AreaTarget, ReferenceChunkList, ReferenceList, ReferenceTargets, ReferenceUpload, ReferenceUploadResult } from '../types';

type Selected = { documentId: string; version: string };

function areaNames(targets: ReferenceTargets | undefined) {
  const names = new Map<string, string>();
  targets?.templates.forEach(t => t.areas.forEach(a => names.set(
    targetKey({ template_id: t.template_id, template_version: t.version, area_id: a.id }), `${t.title} v${t.version} · ${a.title}`)));
  return names;
}

export function ReferencesPage() {
  const client = useQueryClient();
  const [selected, setSelected] = useState<Selected | null>(null);
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
      <UploadPanel targets={targets.data} targetsError={targets.error} groups={groups.map(g => ({ id: g.documentId, title: g.title }))}
        onUploaded={result => { setSelected({ documentId: result.document_id, version: result.version }); client.invalidateQueries({ queryKey: ['area-references'] }); }} />
    </section>
    <div className="documents-layout">
    <section className="page-card document-sidebar"><ColumnHeader eyebrow="MANUALS" title="维修资料" />
      <p className="section-note">AI 分析按区域读取这里的资料。选择一个版本，右侧查看处理状态和切块。</p>
      {list.isPending && <LoadingState />}{list.error && <ErrorState error={list.error} onRetry={() => list.refetch()} />}
      {list.data && !groups.length && <EmptyState title="还没有资料">在上方上传第一份 Markdown 资料。</EmptyState>}
      <div className="document-list reference-list">{groups.map(group => <div key={group.documentId} className="reference-group">
        <strong>{group.title}</strong><small>{group.documentId}</small>
        {group.versions.map(v => <button type="button" key={v.version}
          className={selected?.documentId === v.document_id && selected.version === v.version ? 'selected' : ''}
          onClick={() => setSelected({ documentId: v.document_id, version: v.version })}>
          <span>第 {v.version} 版 <StatusBadge value={statusLabel[v.status] ?? v.status} tone={statusTone(v.status)} /></span>
          <small>{v.bound_areas.length ? `用于 ${v.bound_areas.length} 个区域` : '未用于区域'}{v.chunk_count !== null ? ` · ${v.chunk_count} 块` : ''}</small>
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
          <dt>正在使用的区域</dt><dd>{current.bound_areas.length ? current.bound_areas.map(label).join('；') : '无（处理完成前不会切换；或已被更新的版本取代）'}</dd>
          <dt>上传时选择的区域</dt><dd>{current.requested_areas.length ? current.requested_areas.map(label).join('；') : '—'}</dd>
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

function UploadPanel({ targets, targetsError, groups, onUploaded }: {
  targets: ReferenceTargets | undefined; targetsError: unknown;
  groups: { id: string; title: string }[]; onUploaded: (result: ReferenceUploadResult) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [content, setContent] = useState('');
  const [existing, setExisting] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [title, setTitle] = useState('');
  const [areas, setAreas] = useState<Map<string, AreaTarget>>(new Map());
  const [always, setAlways] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const headings = useMemo(() => sectionHeadings(content), [content]);

  const chooseFile = async (next: File | null) => {
    setFile(next); setMessage(''); setAlways([]); upload.reset();
    const text = next ? await next.text() : '';
    setContent(text);
    if (next && !existing) {
      setDocumentId(referenceIdFrom(next.name));
      setTitle(next.name.replace(/\.[^.]+$/, ''));
    }
  };
  const chooseExisting = (id: string) => {
    setExisting(id);
    const group = groups.find(g => g.id === id);
    if (group) { setDocumentId(group.id); setTitle(group.title); }
    else if (file) { setDocumentId(referenceIdFrom(file.name)); setTitle(file.name.replace(/\.[^.]+$/, '')); }
  };
  const toggleArea = (target: AreaTarget) => setAreas(prev => {
    const next = new Map(prev); const key = targetKey(target);
    if (next.has(key)) next.delete(key); else next.set(key, target);
    return next;
  });
  const toggleHeading = (heading: string) => setAlways(prev => prev.includes(heading) ? prev.filter(h => h !== heading) : [...prev, heading]);

  const problems = [
    !file && '请选择 Markdown 文件',
    file && !headings.length && '文件里没有 "## " 二级标题，无法按章节切块',
    content.length > MAX_REFERENCE_CHARS && `资料超过 ${MAX_REFERENCE_CHARS} 字`,
    !REFERENCE_ID.test(documentId) && '资料编号只能用小写字母、数字和连字符（2～100 个字符）',
    !title.trim() && '请填写标题',
    !areas.size && '请至少选择一个区域',
  ].filter(Boolean) as string[];

  const upload = useMutation({
    mutationFn: () => {
      const body: ReferenceUpload = {
        document_id: documentId, title: title.trim(), filename: file?.name ?? '', content,
        areas: [...areas.values()], always_include: always,
      };
      return apiClient.request<ReferenceUploadResult>('/area-references', { method: 'POST', body, idempotencyKey: idempotencyKey('reference'), timeoutMs: 60_000 });
    },
    onSuccess: result => {
      setMessage(result.reused
        ? `这份内容已经是第 ${result.version} 版${result.status === 'queued' ? '，已重新排队处理' : ''}；所选区域已合并。`
        : `已受理为第 ${result.version} 版，后台正在处理。`);
      onUploaded(result);
    },
  });

  return <div className="upload-form">
    <p className="section-note">上传 Markdown 后，后台自动切块、计算向量；处理完成后，所选区域改用这份资料。</p>
    <div className="upload-row">
      <label>Markdown 文件<input type="file" accept=".md,.markdown" onChange={e => chooseFile(e.target.files?.[0] ?? null)} /></label>
      <label>新资料还是新版本<select value={existing} onChange={e => chooseExisting(e.target.value)}>
        <option value="">新资料</option>
        {groups.map(g => <option key={g.id} value={g.id}>{g.title} 的新版本</option>)}
      </select></label>
      <label>资料编号<input value={documentId} disabled={!!existing} maxLength={100} onChange={e => setDocumentId(e.target.value)} /></label>
      <label>标题<input value={title} maxLength={200} onChange={e => setTitle(e.target.value)} /></label>
    </div>
    <fieldset className="choice-group"><legend>用于哪些区域 *</legend>
      {targetsError ? <ErrorState error={targetsError} /> : null}
      <div className="target-columns">{targets?.templates.map(t => <div className="target-column" key={`${t.template_id}@${t.version}`}>
        <small>{t.title} · 第 {t.version} 版模板</small>
        {t.areas.map(a => {
          const target = { template_id: t.template_id, template_version: t.version, area_id: a.id };
          return <label className="inline-check" key={a.id}><input type="checkbox" checked={areas.has(targetKey(target))} onChange={() => toggleArea(target)} />{a.title}</label>;
        })}
      </div>)}</div>
    </fieldset>
    {headings.length > 0 && <fieldset className="choice-group"><legend>必带章节（可选：每次分析都发给 AI）</legend>
      <div className="heading-choices">{headings.map(h => <label className="inline-check" key={h}><input type="checkbox" checked={always.includes(h)} onChange={() => toggleHeading(h)} />{h.replace(/^## +/, '')}</label>)}</div>
    </fieldset>}
    <div className="upload-actions">
      <button type="button" disabled={problems.length > 0 || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? '正在上传' : '上传并处理'}</button>
      {file && problems.length > 0 && <ul className="inline-error">{problems.map(p => <li key={p}>{p}</li>)}</ul>}
      {message && <p role="status">{message}</p>}
    </div>
    {upload.error && <ErrorState error={upload.error} />}
  </div>;
}
