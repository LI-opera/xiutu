import { Fragment, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, idempotencyKey } from '../lib/api-client';
import { ColumnHeader } from '../components/ColumnHeader';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/States';
import {
  groupReferences, isWorking, MAX_REFERENCE_CHARS, REFERENCE_ID, referenceIdFrom, sectionHeadings,
  statusLabel, statusTone, suggestions, vehicleText,
} from '../lib/references';
import type {
  KnownVehicles, ReferenceChunkList, ReferenceItem, ReferenceList, ReferenceUpload, ReferenceUploadResult,
  ReferenceVersionUpload,
} from '../lib/types';

export function ReferencesPage() {
  const client = useQueryClient();
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [newVersionOf, setNewVersionOf] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ['area-references'],
    queryFn: ({ signal }) => apiClient.request<ReferenceList>('/area-references', { signal }),
    refetchInterval: q => (q.state.data?.items.some(item => isWorking(item.status)) ? 1_500 : false),
  });
  const groups = useMemo(() => groupReferences(list.data?.items ?? []), [list.data]);
  const needle = query.trim().toLowerCase();
  const shown = groups.filter(g => !needle || g.title.toLowerCase().includes(needle) || g.documentId.includes(needle)
    || vehicleText(g.versions[0].vehicle).toLowerCase().includes(needle));
  const uploaded = (result: ReferenceUploadResult) => {
    client.invalidateQueries({ queryKey: ['area-references'] });
    setExpanded(result.document_id);
  };

  return <div className="references-page">
    <section className="page-card upload-card"><ColumnHeader eyebrow="UPLOAD" title="上传资料" />
      <UploadForm onUploaded={uploaded} />
    </section>
    <section className="page-card reference-card">
      <ColumnHeader eyebrow="MANUALS" title="维修资料" action={
        <input className="reference-search" type="search" aria-label="搜索资料" placeholder="搜索名称、编号或车型"
          value={query} onChange={e => setQuery(e.target.value)} />} />
      {list.isPending && <LoadingState />}{list.error && <ErrorState error={list.error} onRetry={() => list.refetch()} />}
      {list.data && !groups.length && <EmptyState title="还没有资料">在上方上传第一份 Markdown 资料。</EmptyState>}
      {list.data && groups.length > 0 && !shown.length && <EmptyState title="没有匹配的资料">换个关键词试试。</EmptyState>}
      {shown.length > 0 && <table className="reference-table">
        <thead><tr><th>资料名称</th><th className="optional">适用车型</th><th>版本</th><th>状态</th><th className="optional">块数</th><th className="optional">更新日期</th><th aria-label="操作" /></tr></thead>
        <tbody>{shown.map(group => {
          const latest = group.versions[0];
          const open = expanded === group.documentId;
          return <Fragment key={group.documentId}>
            <tr className={open ? 'open' : ''}>
              <td><button type="button" className="row-toggle" aria-expanded={open} onClick={() => setExpanded(open ? null : group.documentId)}>
                <span aria-hidden="true">{open ? '▾' : '▸'}</span>
                <span><strong>{group.title}</strong><small>{group.documentId}</small></span>
              </button></td>
              <td className="optional">{vehicleText(latest.vehicle)}</td>
              <td>第 {latest.version} 版</td>
              <td><StatusBadge value={statusLabel[latest.status] ?? latest.status} tone={statusTone(latest.status)} /></td>
              <td className="optional">{latest.chunk_count ?? '—'}</td>
              <td className="optional">{latest.updated_at.slice(0, 10)}</td>
              <td><button type="button" className="secondary small" aria-expanded={newVersionOf === group.documentId}
                onClick={() => setNewVersionOf(newVersionOf === group.documentId ? null : group.documentId)}>上传新版本</button></td>
            </tr>
            {newVersionOf === group.documentId && <tr className="reference-expanded"><td colSpan={7}>
              <NewVersionForm documentId={group.documentId} title={group.title}
                onClose={() => setNewVersionOf(null)} onUploaded={result => { setNewVersionOf(null); uploaded(result); }} />
            </td></tr>}
            {open && <tr className="reference-expanded"><td colSpan={7}><ReferenceDetail versions={group.versions} /></td></tr>}
          </Fragment>;
        })}</tbody>
      </table>}
    </section>
  </div>;
}

/** One manual opened in the table: the chosen version (latest by default), its details and chunks. */
function ReferenceDetail({ versions }: { versions: ReferenceItem[] }) {
  const [version, setVersion] = useState<string | null>(null);
  const [onlySearchable, setOnlySearchable] = useState(true);
  const current = versions.find(v => v.version === version) ?? versions[0];
  const chunks = useQuery({
    queryKey: ['area-reference-chunks', current.document_id, current.version],
    queryFn: ({ signal }) => apiClient.request<ReferenceChunkList>(
      `/area-references/${encodeURIComponent(current.document_id)}/versions/${encodeURIComponent(current.version)}/chunks`, { signal }),
    enabled: current.status === 'ready',
  });
  const shownChunks = (chunks.data?.items ?? []).filter(c => !onlySearchable || c.searchable);
  return <div className="reference-detail">
    <div className="detail-head">
      <h3>第 {current.version} 版</h3>
      <div className="badge-row">
        <StatusBadge value={statusLabel[current.status] ?? current.status} tone={statusTone(current.status)} />
        <StatusBadge value={current.source_kind === 'upload' ? '页面上传' : '脚本导入'} />
        <StatusBadge value={current.vector_fingerprint ? `向量 ${current.vector_fingerprint}` : '没有向量'} tone={current.vector_fingerprint ? 'good' : 'warn'} />
      </div>
      {versions.length > 1 && <div className="history" role="group" aria-label="历史版本"><span className="muted">全部版本：</span>
        {versions.map(v => <button type="button" key={v.version} className={`text-button${v.version === current.version ? ' current' : ''}`}
          aria-pressed={v.version === current.version} onClick={() => setVersion(v.version)}>第 {v.version} 版</button>)}</div>}
    </div>
    {current.status === 'failed' && <div className="callout" role="alert">处理失败：<code>{current.error_code}</code>。修正后重新上传同一份内容即可重试。</div>}
    {isWorking(current.status) && <LoadingState label="后台正在切块、计算向量" />}
    <dl className="detail-grid">
      <div><dt>适用车型</dt><dd>{vehicleText(current.vehicle)}</dd></div>
      <div><dt>字数</dt><dd>{current.chars}</dd></div>
      <div><dt>上传时间</dt><dd>{current.created_at.slice(0, 16).replace('T', ' ')}</dd></div>
      <div><dt>必带章节</dt><dd>{current.always_include.length ? current.always_include.map(h => h.replace(/^## +/, '')).join('；') : '无'}</dd></div>
    </dl>
    {current.status === 'ready' && <details className="chunk-panel">
      <summary>切块（{current.chunk_count ?? chunks.data?.items.length ?? '…'}）</summary>
      <label className="inline-check"><input type="checkbox" checked={onlySearchable} onChange={e => setOnlySearchable(e.target.checked)} />只看参与检索的</label>
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
    </details>}
  </div>;
}

const resultText = (result: ReferenceUploadResult) => result.reused
  ? `这份内容已经是第 ${result.version} 版${result.status === 'queued' ? '，已重新排队处理' : ''}。`
  : `已受理为第 ${result.version} 版，后台正在处理。`;

/** A new manual: the file, its title and the vehicle it applies to. Nothing tied to templates. */
function UploadForm({ onUploaded }: { onUploaded: (result: ReferenceUploadResult) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [content, setContent] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [title, setTitle] = useState('');
  const [vehicle, setVehicle] = useState({ brand: '', model: '', year: '', engineCode: '' });
  const [always, setAlways] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const headings = useMemo(() => sectionHeadings(content), [content]);
  const known = useQuery({
    queryKey: ['area-reference-vehicles'],
    queryFn: ({ signal }) => apiClient.request<KnownVehicles>('/area-references/vehicles', { signal }),
  });
  const vehicles = known.data?.vehicles ?? [];

  const upload = useMutation({
    mutationFn: () => {
      const body: ReferenceUpload = {
        document_id: documentId, title: title.trim(), filename: file?.name ?? '', content, always_include: always,
        vehicle: { brand: vehicle.brand.trim(), model: vehicle.model.trim(), year: Number(vehicle.year), engine_code: vehicle.engineCode.trim() },
      };
      return apiClient.request<ReferenceUploadResult>('/area-references', { method: 'POST', body, idempotencyKey: idempotencyKey('reference'), timeoutMs: 60_000 });
    },
    onSuccess: result => { setMessage(resultText(result)); onUploaded(result); },
  });
  const chooseFile = async (next: File | null) => {
    setFile(next); setAlways([]); setMessage(''); upload.reset();
    setContent(next ? await next.text() : '');
    if (next) { setDocumentId(referenceIdFrom(next.name)); setTitle(next.name.replace(/\.[^.]+$/, '')); }
  };
  const field = (key: keyof typeof vehicle) => ({
    value: vehicle[key], onChange: (e: React.ChangeEvent<HTMLInputElement>) => setVehicle({ ...vehicle, [key]: e.target.value }),
  });
  const toggleHeading = (heading: string) => setAlways(prev => prev.includes(heading) ? prev.filter(h => h !== heading) : [...prev, heading]);
  const year = Number(vehicle.year);
  const problems = [
    !file && '请选择 Markdown 文件',
    file && !headings.length && '文件里没有 "## " 二级标题，无法按章节切块',
    content.length > MAX_REFERENCE_CHARS && `资料超过 ${MAX_REFERENCE_CHARS} 字`,
    !title.trim() && '请填写标题',
    !REFERENCE_ID.test(documentId) && '资料编号只能用小写字母、数字和连字符（2～100 个字符）',
    !(vehicle.brand.trim() && vehicle.model.trim() && vehicle.engineCode.trim()) && '请填写适用车型的品牌、车型和发动机代码',
    !(Number.isInteger(year) && year >= 1950 && year <= 2100) && '请填写年款（如 2019）',
  ].filter(Boolean) as string[];

  return <div className="upload-form">
    <p className="section-note">上传 Markdown 资料并写明适用车型。后台自动切块、计算向量；分析时只读这台车的资料，再按区域和题目检索章节。</p>
    <div className="upload-row three">
      <label>Markdown 文件<input type="file" accept=".md,.markdown" onChange={e => chooseFile(e.target.files?.[0] ?? null)} /></label>
      <label>标题<input value={title} maxLength={200} onChange={e => setTitle(e.target.value)} /></label>
      <label>资料编号<input value={documentId} maxLength={100} placeholder="选文件后自动生成" onChange={e => setDocumentId(e.target.value)} /></label>
    </div>
    <fieldset className="choice-group"><legend>适用车型 *</legend>
      <div className="vehicle-row">
        <label>品牌<input {...field('brand')} list="vehicle-brands" placeholder="如 大众" /></label>
        <label>车型<input {...field('model')} list="vehicle-models" placeholder="如 探岳" /></label>
        <label>年款<input {...field('year')} list="vehicle-years" inputMode="numeric" placeholder="如 2019" /></label>
        <label>发动机代码<input {...field('engineCode')} list="vehicle-engines" placeholder="如 DKVB" /></label>
      </div>
      <datalist id="vehicle-brands">{suggestions(vehicles, 'brand').map(v => <option key={v} value={v} />)}</datalist>
      <datalist id="vehicle-models">{suggestions(vehicles, 'model').map(v => <option key={v} value={v} />)}</datalist>
      <datalist id="vehicle-years">{suggestions(vehicles, 'year').map(v => <option key={v} value={v} />)}</datalist>
      <datalist id="vehicle-engines">{suggestions(vehicles, 'engine_code').map(v => <option key={v} value={v} />)}</datalist>
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

/** A new version of an existing manual: only the file; its title, vehicle and sections carry over. */
function NewVersionForm({ documentId, title, onClose, onUploaded }: {
  documentId: string; title: string; onClose: () => void; onUploaded: (result: ReferenceUploadResult) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [content, setContent] = useState('');
  const headings = useMemo(() => sectionHeadings(content), [content]);
  const upload = useMutation({
    mutationFn: () => {
      const body: ReferenceVersionUpload = { filename: file?.name ?? '', content };
      return apiClient.request<ReferenceUploadResult>(`/area-references/${encodeURIComponent(documentId)}/versions`,
        { method: 'POST', body, idempotencyKey: idempotencyKey('reference-version'), timeoutMs: 60_000 });
    },
    onSuccess: onUploaded,
  });
  const chooseFile = async (next: File | null) => {
    setFile(next); upload.reset();
    setContent(next ? await next.text() : '');
  };
  const problem = file && !headings.length ? '文件里没有 "## " 二级标题，无法按章节切块'
    : content.length > MAX_REFERENCE_CHARS ? `资料超过 ${MAX_REFERENCE_CHARS} 字` : '';
  return <div className="new-version-form">
    <label>{title} 的新版本（Markdown）<input type="file" accept=".md,.markdown" onChange={e => chooseFile(e.target.files?.[0] ?? null)} /></label>
    <p className="muted">标题、适用车型和必带章节沿用上一版；处理完成后，分析改读新版本。</p>
    {problem && <p className="inline-error">{problem}</p>}
    <div className="upload-actions">
      <button type="button" disabled={!file || !!problem || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? '正在上传' : '上传新版本'}</button>
      <button type="button" className="text-button" onClick={onClose}>取消</button>
    </div>
    {upload.error && <ErrorState error={upload.error} />}
  </div>;
}
