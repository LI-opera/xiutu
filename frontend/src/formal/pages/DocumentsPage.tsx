import { useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiError, idempotencyKey } from '../api-client';
import { ColumnHeader } from '../components/ColumnHeader';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/States';
import { displayBytes, documentInput, emptyMaterialDraft, type MaterialDraft } from '../state';
import type { ChunkList, ClientConfig, DocumentList, ReviewInput, ReviewResponse, SearchInput, SearchResponse, UploadResponse, VersionResponse } from '../types';

const pending = new Set(['pending', 'parsing']);
const indexPending = new Set(['index_pending', 'building']);
const statusTone = (value: string): 'neutral' | 'good' | 'warn' | 'bad' => value === 'ready' || value === 'approved' || value === 'review_pending' ? 'good' : value === 'failed' || value === 'rejected' || value === 'revoked' ? 'bad' : value === 'pending' || value === 'parsing' || value === 'index_pending' || value === 'building' || value === 'needs_ocr' ? 'warn' : 'neutral';

export function DocumentsPage() {
  const client = useQueryClient();
  const [selected, setSelected] = useState<{ documentId: string; versionId: string } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [draft, setDraft] = useState<MaterialDraft>(emptyMaterialDraft);
  const [uploadMessage, setUploadMessage] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [reviewDecision, setReviewDecision] = useState<'approved' | 'rejected' | 'revoked'>('approved');
  const [reviewSource, setReviewSource] = useState<'unknown' | 'verified'>('unknown');
  const [reviewLicense, setReviewLicense] = useState<'unknown' | 'private_use' | 'permitted'>('unknown');
  const [queryText, setQueryText] = useState('');
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searchError, setSearchError] = useState<unknown>(null);
  const [searchPending, setSearchPending] = useState(false);
  const searchEpoch = useRef(0);
  const searchAbort = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const selectedRef = useRef(selected);
  const queryTextRef = useRef(queryText);
  selectedRef.current = selected;
  queryTextRef.current = queryText;

  const config = useQuery({ queryKey: ['client-config'], queryFn: () => apiClient.request<ClientConfig>('/client-config') });
  const documents = useInfiniteQuery({
    queryKey: ['documents'],
    initialPageParam: null as string | null,
    queryFn: ({ signal, pageParam }) => apiClient.request<DocumentList>(`/documents?limit=50${pageParam !== null ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`, { signal }),
    getNextPageParam: (lastPage, pages) => {
      const cursor = lastPage.next_cursor;
      if (cursor === null || pages.slice(0, -1).some(page => page.next_cursor === cursor)) return undefined;
      return cursor;
    },
  });
  const documentItems = useMemo(() => {
    const byId = new Map<string, DocumentList['items'][number]>();
    documents.data?.pages.forEach(page => page.items.forEach(item => { if (!byId.has(item.id)) byId.set(item.id, item); }));
    return [...byId.values()];
  }, [documents.data]);
  const version = useQuery({
    queryKey: ['document-version', selected?.documentId, selected?.versionId],
    queryFn: ({ signal }) => apiClient.request<VersionResponse>(`/documents/${selected!.documentId}/versions/${selected!.versionId}`, { signal }),
    enabled: !!selected,
    refetchInterval: query => {
      const item = query.state.data;
      return item && (pending.has(item.parse_status) || indexPending.has(item.index_status)) ? 1_200 : false;
    },
  });
  const chunks = useInfiniteQuery({
    queryKey: ['document-chunks', selected?.documentId, selected?.versionId],
    initialPageParam: null as number | null,
    queryFn: ({ signal, pageParam }) => apiClient.request<ChunkList>(`/documents/${selected!.documentId}/versions/${selected!.versionId}/chunks?limit=100${pageParam !== null ? `&cursor=${encodeURIComponent(String(pageParam))}` : ''}`, { signal }),
    getNextPageParam: (lastPage, pages) => {
      const cursor = lastPage.next_cursor;
      if (cursor === null || pages.slice(0, -1).some(page => page.next_cursor === cursor)) return undefined;
      return cursor;
    },
    enabled: !!selected && !!version.data && !pending.has(version.data.parse_status),
  });
  const chunkItems = useMemo(() => {
    const byOrdinal = new Map<number, ChunkList['items'][number]>();
    chunks.data?.pages.forEach(page => page.items.forEach(item => { if (!byOrdinal.has(item.ordinal)) byOrdinal.set(item.ordinal, item); }));
    return [...byOrdinal.values()];
  }, [chunks.data]);
  const source = useQuery({
    queryKey: ['document-source', selected?.documentId, selected?.versionId],
    queryFn: ({ signal }) => apiClient.request<string>(`/documents/${selected!.documentId}/versions/${selected!.versionId}/content`, { signal, response: 'text' }),
    enabled: false,
  });

  const upload = useMutation({
    mutationFn: async () => {
      if (!file || !draft.nature) throw new Error('请选择文件并明确资料性质。');
      if (config.data && file.size > config.data.upload_max_bytes) throw new ApiError(413, 'UPLOAD_TOO_LARGE', '所选文件超过服务端允许大小', null, { size: file.size, limit: config.data.upload_max_bytes }, false);
      const form = new FormData(); form.set('file', file); form.set('metadata', JSON.stringify(documentInput(draft)));
      return apiClient.request<UploadResponse>('/documents', { method: 'POST', body: form, idempotencyKey: idempotencyKey('upload'), timeoutMs: 60_000 });
    },
    onSuccess: result => {
      invalidateSearch();
      setSelected({ documentId: result.document_id, versionId: result.version_id });
      setUploadMessage(result.reused ? '服务端复用了相同哈希与元数据版本。' : '上传已受理，正在读取真实解析状态。');
      client.invalidateQueries({ queryKey: ['documents'] });
    },
  });
  const review = useMutation({
    mutationFn: () => {
      const metadata = (version.data?.metadata ?? {}) as Record<string, unknown>;
      const original = (metadata.scope ?? {}) as ReviewInput['scope'];
      const body: ReviewInput = { decision: reviewDecision, scope: original, source_status: reviewSource, license_status: reviewLicense, review_note: reviewNote };
      return apiClient.request<ReviewResponse>(`/documents/${selected!.documentId}/versions/${selected!.versionId}/review`, { method: 'POST', body, idempotencyKey: idempotencyKey('review') });
    },
    onSuccess: () => { setReviewNote(''); client.invalidateQueries({ queryKey: ['document-version', selected?.documentId, selected?.versionId] }); },
  });
  type SearchAttempt = {
    documentId: string;
    versionId: string;
    query: string;
    generation: number;
    controller: AbortController;
    body: SearchInput;
  };
  const currentSearch = (attempt: SearchAttempt) => {
    const current = selectedRef.current;
    return mounted.current && searchEpoch.current === attempt.generation && current?.documentId === attempt.documentId && current.versionId === attempt.versionId && queryTextRef.current === attempt.query;
  };
  const search = useMutation({
    mutationFn: (attempt: SearchAttempt) => apiClient.request<SearchResponse>('/evidence/search', { method: 'POST', body: attempt.body, signal: attempt.controller.signal }),
    onSuccess: (result, attempt) => { if (currentSearch(attempt)) setSearchResult(result); },
    onError: (error, attempt) => { if (currentSearch(attempt)) setSearchError(error); },
    onSettled: (_result, _error, attempt) => { if (currentSearch(attempt)) setSearchPending(false); },
  });
  function invalidateSearch() {
    searchEpoch.current += 1;
    searchAbort.current?.abort();
    searchAbort.current = null;
    setSearchPending(false);
    setSearchError(null);
    setSearchResult(null);
    search.reset();
  }
  const runSearch = () => {
    if (!selected || !version.data || !queryText.trim()) return;
    searchAbort.current?.abort();
    const controller = new AbortController();
    const generation = searchEpoch.current + 1;
    searchEpoch.current = generation;
    searchAbort.current = controller;
    const metadata = (version.data.metadata ?? {}) as Record<string, unknown>;
    const scope = (metadata.scope ?? {}) as Record<string, unknown>;
    const attempt: SearchAttempt = {
      documentId: selected.documentId,
      versionId: selected.versionId,
      query: queryText,
      generation,
      controller,
      body: { query: queryText, vehicle_scope: { model: scope.model as string | null, year: scope.year_from as number | null, engine_family: scope.engine_family as string | null, engine_code: scope.engine_code as string | null }, top_k: 5 },
    };
    setSearchPending(true);
    setSearchError(null);
    setSearchResult(null);
    search.mutate(attempt);
  };
  const uploadError = useMemo(() => file && config.data && file.size > config.data.upload_max_bytes ? `文件 ${file.name} 为 ${displayBytes(file.size)}，超过允许的 ${displayBytes(config.data.upload_max_bytes)}。` : '', [file, config.data]);
  const metadata = (version.data?.metadata ?? {}) as Record<string, unknown>;
  const isSynthetic = metadata.synthetic === true;
  useEffect(() => {
    setReviewSource(metadata.source_status === 'verified' ? 'verified' : 'unknown');
    setReviewLicense(['private_use', 'permitted'].includes(String(metadata.license_status)) ? metadata.license_status as typeof reviewLicense : 'unknown');
    setReviewNote('');
  }, [selected?.versionId, metadata.source_status, metadata.license_status]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      searchEpoch.current += 1;
      searchAbort.current?.abort();
    };
  }, []);

  const selectFile = (next: File | null) => {
    setFile(next); setDraft({ ...emptyMaterialDraft(), title: next?.name.replace(/\.[^.]+$/, '') ?? '' });
    setUploadMessage(''); upload.reset();
  };
  const selectDocument = (documentId: string, versionId: string) => {
    if (selected) client.removeQueries({ queryKey: ['document-source', selected.documentId, selected.versionId], exact: true });
    invalidateSearch();
    setSelected({ documentId, versionId });
  };

  return <div className="documents-layout">
    <section className="page-card document-sidebar"><ColumnHeader eyebrow="MATERIALS" title="资料中心" />
      <p className="section-note">选择已有资料或上传新版本。页面只显示服务端真实状态。</p>
      {documents.isPending && <LoadingState />}{documents.error && !documents.data && <ErrorState error={documents.error} onRetry={() => documents.refetch()} />}
      <div className="document-list">{documentItems.map(item => <button type="button" className={selected?.documentId === item.id ? 'selected' : ''} disabled={!item.latest_version_id} key={item.id} onClick={() => item.latest_version_id && selectDocument(item.id, item.latest_version_id)}><strong>{item.title}</strong><small>{item.source_kind} · {item.latest_version_id ? '有版本' : '无版本'}</small></button>)}</div>
      {documents.error && documents.data && <ErrorState error={documents.error} onRetry={() => documents.fetchNextPage()} />}
      {documents.hasNextPage && <button type="button" className="secondary" disabled={documents.isFetchingNextPage} onClick={() => documents.fetchNextPage()}>{documents.isFetchingNextPage ? '正在加载更多资料' : '加载更多资料'}</button>}
      <details className="upload-panel" open><summary>上传资料</summary>
        <label>Markdown / PDF<input type="file" accept=".md,.markdown,.pdf" onChange={e => selectFile(e.target.files?.[0] ?? null)} /></label>
        <p>服务端实际上限：{config.data ? displayBytes(config.data.upload_max_bytes) : '读取中'}{file && <> · 当前 {displayBytes(file.size)}</>}</p>
        {uploadError && <p role="alert" className="inline-error">{uploadError}</p>}
        <label>资料性质 *<select value={draft.nature} onChange={e => setDraft({ ...draft, nature: e.target.value as MaterialDraft['nature'] })}><option value="">必须明确选择</option><option value="synthetic">虚构/合成测试资料</option><option value="nonfiction">非虚构来源，尚待核实</option></select></label>
        <label>标题<input value={draft.title} maxLength={300} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label>
        <label>来源说明（未知可留空）<textarea value={draft.sourceReference} onChange={e => setDraft({ ...draft, sourceReference: e.target.value })} /></label>
        <div className="mini-grid"><label>车型<input value={draft.model} onChange={e => setDraft({ ...draft, model: e.target.value })} /></label><label>起始年款<input inputMode="numeric" value={draft.yearFrom} onChange={e => setDraft({ ...draft, yearFrom: e.target.value })} /></label><label>结束年款<input inputMode="numeric" value={draft.yearTo} onChange={e => setDraft({ ...draft, yearTo: e.target.value })} /></label><label>发动机系列<input value={draft.engineFamily} onChange={e => setDraft({ ...draft, engineFamily: e.target.value })} /></label><label>发动机代码<input value={draft.engineCode} onChange={e => setDraft({ ...draft, engineCode: e.target.value })} /></label></div>
        <p className="muted">未知字段保持空值；非虚构不等于来源、许可或适配已核实。</p>
        <button type="button" disabled={!file || !draft.nature || !draft.title.trim() || !!uploadError || upload.isPending} onClick={() => upload.mutate()}>上传并读取状态</button>
        {uploadMessage && <p role="status">{uploadMessage}</p>}{upload.error && <ErrorState error={upload.error} />}
      </details>
    </section>
    <section className="page-card document-detail"><ColumnHeader eyebrow="VERSION" title="版本、审核与索引" />
      {!selected && <EmptyState title="尚未选择资料">选择已有资料或成功上传后，这里显示真实版本状态。</EmptyState>}
      {version.isPending && selected && <LoadingState label="正在读取版本" />}{version.error && <ErrorState error={version.error} onRetry={() => version.refetch()} />}
      {version.data && <><div className="badge-row"><StatusBadge value={`解析 ${version.data.parse_status}`} tone={statusTone(version.data.parse_status)} /><StatusBadge value={`审核 ${version.data.review_status}`} tone={statusTone(version.data.review_status)} /><StatusBadge value={`索引 ${version.data.index_status}`} tone={statusTone(version.data.index_status)} /><StatusBadge value={isSynthetic ? 'synthetic' : '非虚构待核实'} tone={isSynthetic ? 'warn' : 'neutral'} /><StatusBadge value={`formal_usable=${String(version.data.formal_usable)}`} tone={version.data.formal_usable ? 'good' : 'warn'} /></div>
        <dl className="version-meta"><dt>版本</dt><dd>{selected!.versionId}</dd><dt>SHA256</dt><dd>{version.data.sha256}</dd><dt>页面</dt><dd>{version.data.page_count ?? '未知'}</dd><dt>索引资格</dt><dd>{version.data.index_exclusion ?? (version.data.index_status === 'ready' ? '服务端已标记 ready' : '无明确排除原因')}</dd></dl>
        {version.data.parse_status === 'needs_ocr' && <div className="callout">此 PDF 缺少可用文字层，需要 OCR。本包只显示缺项，不执行 OCR。</div>}
        <details><summary>资料声明与审核历史</summary><pre>{JSON.stringify({ metadata: version.data.metadata, review_history: version.data.review_history, parse_error: version.data.parse_error, page_issues: version.data.page_issues, index_error: version.data.index_error }, null, 2)}</pre></details>
        <div className="review-box"><h3>人工审核</h3><div className="mini-grid"><label>决定<select value={reviewDecision} onChange={e => setReviewDecision(e.target.value as typeof reviewDecision)}><option value="approved">批准</option><option value="rejected">拒绝</option><option value="revoked">撤销</option></select></label><label>来源核实<select value={reviewSource} onChange={e => setReviewSource(e.target.value as typeof reviewSource)}><option value="unknown">未知/未核实</option><option value="verified">已核实</option></select></label><label>许可状态<select value={reviewLicense} onChange={e => setReviewLicense(e.target.value as typeof reviewLicense)}><option value="unknown">未知</option><option value="private_use">仅私用</option><option value="permitted">已获许可</option></select></label></div><p className="muted">这些值只由本次人工审核明确选择；文件名和上传性质不会自动把它们改为已核实。</p><label>审核说明<textarea value={reviewNote} maxLength={4000} onChange={e => setReviewNote(e.target.value)} /></label><button type="button" disabled={!reviewNote.trim() || review.isPending || !['review_pending', 'needs_ocr'].includes(version.data.parse_status)} onClick={() => review.mutate()}>提交真实审核决定</button>{review.error && <ErrorState error={review.error} />}</div>
        <div className="actions"><button type="button" className="secondary" disabled={version.data.mime === 'application/pdf'} onClick={() => source.refetch()}>{version.data.mime === 'application/pdf' ? 'PDF 使用原件链接' : '查看原文'}</button><a className="button-link" href={`/api/v2/documents/${selected!.documentId}/versions/${selected!.versionId}/content`} target="_blank" rel="noreferrer">打开/下载不可变原件</a></div>
        {source.isFetching && <LoadingState label="正在读取原文" />}{source.error && <ErrorState error={source.error} />}{source.data && <pre className="source-preview">{source.data}</pre>}
        <h3>解析切块</h3>{chunks.isPending && <LoadingState />}{chunks.error && !chunks.data && <ErrorState error={chunks.error} onRetry={() => chunks.refetch()} />}{chunkItems.map(chunk => <article className="chunk" key={chunk.ordinal}><small>#{chunk.ordinal} · {chunk.heading_path.join(' / ') || '无标题'} · {chunk.page_start ? `p.${chunk.page_start}` : '无页码'}</small><p>{chunk.text}</p></article>)}
        {chunks.error && chunks.data && <ErrorState error={chunks.error} onRetry={() => chunks.fetchNextPage()} />}
        {chunks.hasNextPage && <button type="button" className="secondary" disabled={chunks.isFetchingNextPage} onClick={() => chunks.fetchNextPage()}>{chunks.isFetchingNextPage ? '正在加载更多切块' : '加载更多切块'}</button>}
        <div className="trial-search"><h3>合格资料试搜</h3><label>问题<input value={queryText} maxLength={2000} onChange={e => { invalidateSearch(); setQueryText(e.target.value); }} /></label><button type="button" disabled={!queryText.trim() || version.data.index_status !== 'ready'} onClick={runSearch}>{searchPending ? '重新检索' : '调用真实检索'}</button>{searchError !== null && <ErrorState error={searchError} />}
          {searchResult && !searchResult.chunks.length && <EmptyState title="没有合格命中">服务端未返回符合当前适配和资格的片段。</EmptyState>}{searchResult?.chunks.map((item, i) => <pre className="search-hit" key={i}>{JSON.stringify(item, null, 2)}</pre>)}{searchResult && <details><summary>排除项与检索轨迹</summary><pre>{JSON.stringify({ excluded: searchResult.excluded, trace: searchResult.trace }, null, 2)}</pre></details>}
        </div>
      </>}
    </section>
  </div>;
}
