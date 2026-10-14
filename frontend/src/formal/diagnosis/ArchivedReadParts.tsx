import { useQueries } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import { ErrorState, StatusBadge } from '../components/States';
import { asStepCandidate, referencesOf, type DiagnosisView, type EvidenceView, type ProtocolDecision, type StepCandidate } from './types';

function ClaimLine({ label, value }: { label: string; value?: { text?: string } | null }) {
  if (!value?.text) return null;
  return <div className="claim-line"><b>{label}</b><span>{value.text}</span></div>;
}

export function CurrentStep({ candidate, protocol, onEvidence }: { candidate: StepCandidate; protocol?: ProtocolDecision | null; onEvidence: (ids: string[]) => void }) {
  const refs = referencesOf(candidate);
  const display = protocol?.presentation;
  return <article className="current-step">
    <p className="kicker">{display?.progress_phase ?? '当前任务'} · DKVB/P0299 保守模式演示</p><h2>{display?.task_title ?? display?.task_summary ?? candidate.title}</h2>
    <section><h3>当前问题</h3><p>{display?.question ?? display?.why_summary ?? candidate.purpose.text}</p></section>
    <section><h3>为什么要确认</h3><p>{display?.why_summary ?? candidate.purpose.text}</p></section>
    <section><h3>操作步骤</h3><ol>{(display?.operation_steps ?? candidate.actions?.map(x => x.text) ?? []).map((text, i) => <li key={i}>{text}</li>)}</ol></section>
    {display?.record_summary && <div className="callout"><b>本步记录</b><p>{display.record_summary}</p></div>}
    <div className="callout"><b>归档时的后续预览</b><p>{display?.outcome_preview ?? display?.completion_explanation ?? '原流程会在保存观察后由服务端选择下一步。'}</p></div>
    {!!candidate.interpretation?.length && <div className="callout"><b>解释边界</b><ul>{candidate.interpretation.map((x, i) => <li key={i}>{x.text}</li>)}</ul></div>}
    <section className="evidence-digest"><h3>资料依据摘要</h3>{display?.evidence_kind && <p><b>依据性质：</b>{display.evidence_kind}</p>}<p>{display?.evidence_summary ?? '当前说明来自病例冻结的受控资料。'}</p><p><b>适用范围：</b>{display?.evidence_scope ?? '当前病例冻结资料范围。'}</p><p><b>限制：</b>{display?.evidence_limitations ?? '不能脱离适配范围解释。'}</p>{refs.length > 0 && <button type="button" className="secondary" onClick={() => onEvidence(refs.map(ref => ref.evidence_id))}>查看资料原文与出处</button>}</section>
    <details><summary>技术详情</summary><ClaimLine label="组件" value={{ text: candidate.component_key }} /><ClaimLine label="位置" value={candidate.location} /><code>{protocol?.next_check_id}</code></details>
  </article>;
}

export function EvidenceDrawer({ evidenceIds, onClose }: { evidenceIds: string[]; onClose: () => void }) {
  const queries = useQueries({ queries: evidenceIds.map(id => ({ queryKey: ['evidence', id], queryFn: ({ signal }) => apiClient.request<EvidenceView>(`/evidence/${id}`, { signal }) })) });
  if (!evidenceIds.length) return null;
  return <aside className="evidence-drawer" aria-label="检查依据"><div className="drawer-head"><h2>资料原文与出处</h2><button type="button" className="secondary" onClick={onClose}>关闭</button></div>
    <p className="section-note">以下条目来自病例冻结的同一受控资料范围；重复引用在这里合并展示。</p>
    {queries.some(query => query.isPending) && <p>正在读取授权来源…</p>}
    {queries.map((query, index) => query.error ? <ErrorState key={evidenceIds[index]} error={query.error} onRetry={() => query.refetch()} /> : query.data ? <article className="evidence-source" key={query.data.evidence_id}><h3>DKVB/P0299 受控演示资料</h3><div className="badge-row"><StatusBadge value={query.data.synthetic ? '合成演示来源' : '待核实非虚构'} tone="warn" /><StatusBadge value={(query.data.current_validity as { valid?: boolean }).valid ? '当前有效' : '来源失效'} tone={(query.data.current_validity as { valid?: boolean }).valid ? 'good' : 'bad'} /></div><p><b>支持关系：</b>支持当前检查的方法、位置、工况或可记录结果；具体原文见定位快照。</p><dl className="version-meta"><dt>资料形式</dt><dd>{query.data.source_access.kind === 'pdf' ? 'PDF 原件' : '受控整理文本'}</dd><dt>定位</dt><dd>{query.data.source_access.page !== null ? `物理页 ${query.data.source_access.page}` : '章节/字符定位见技术详情'}</dd></dl>{query.data.source_access.content_url && <a className="button-link" href={query.data.source_access.content_url} target="_blank" rel="noreferrer">打开原文与定位</a>}<details><summary>原文摘要与定位</summary><pre>{JSON.stringify(query.data.snapshot, null, 2)}</pre></details></article> : null)}
  </aside>;
}

export function stepFrom(view: DiagnosisView | undefined) {
  return view?.current_step ? asStepCandidate(view.current_step.candidate as Record<string, unknown>) : null;
}
