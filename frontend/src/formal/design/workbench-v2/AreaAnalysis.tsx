import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient, errorText } from '../../api-client';

type Reference = { id: string; version: string; title: string; body: string; content_hash: string; provenance: { coverage: string } };
type Step = { title?: string; kind?: "check" | "repair" | "record" | "handoff"; action: string; reason?: string; prerequisites?: string; retest?: string; stop_condition?: string; question_ids: string[]; source_ids: string[]; basis_observation_ids: string[] };
type Result = { summary: string; directions: Array<{ title: string; explanation?: string; source_ids: string[]; basis_observation_ids: string[] }>;
  missing: Array<{ question_id: string; missing: string; reason?: string; suggestion?: string }>;
  steps: Step[]; conditional_branches: Array<{ trigger: string; reason?: string; steps: Step[] }>;
  precautions: string[]; verification?: string; if_unresolved?: string; uncertainty?: string };
type Attempt = { id: string; status: string; input_revision: number; stale: boolean; model: string; error_code: string | null; created_at: string;
  result: Result | null; documents: Reference[]; questions: Array<{ id: string; title: string }>;
  observations: Array<{ id: string; question_id: string; question: string; option_labels: string[]; fields: Record<string, unknown> }>;
  usage: { input_tokens?: number; output_tokens?: number; total_tokens?: number } | null };
type Analysis = { area?: { id: string; title: string }; areas?: Array<{ id: string; title: string; document_ids: string[]; observation_ids: string[]; unknown_question_ids: string[] }>;
  revision: number; available: boolean; documents: Reference[];
  observations: Attempt['observations'];
  recorded: number; unknown: number; max_output_tokens: number; history: Attempt[] };

function References({ items }: { items: Reference[] }) {
  return <>{items.map(item => <details key={`${item.id}:${item.version}`} className="formal-area-reference">
    <summary>{item.title} · 版本 {item.version}</summary><p>{item.provenance.coverage}；本次发送文字正文，未发送图片。</p>
    <pre>{item.body}</pre>
  </details>)}</>;
}

function Advice({ item, onQuestion }: { item: Attempt; onQuestion: (id: string) => void }) {
  const result = item.result;
  const questions = new Map(item.questions.map(q => [q.id, q.title]));
  const questionLink = (id: string) => questions.has(id)
    ? <button className="prototype-button subtle" type="button" key={id} onClick={() => onQuestion(id)}>前往 {questions.get(id)}</button>
    : null;
  const questionLinks = (ids: string[]) => {
    const matched = [...new Set(ids)].filter(id => questions.has(id));
    if (!matched.length) return null;
    return <details className="formal-v2-guidance-details"><summary>相关检查项（{matched.length}）</summary>
      {matched.map(id => <p key={id}>{questionLink(id)}</p>)}
    </details>;
  };
  const steps = (entries: Step[]) => <ol className="formal-v2-guidance-list formal-action-cards">{entries.map((step, index) => <li key={index}>
    <div className="formal-action-heading"><span className="formal-action-number" aria-hidden="true">{index + 1}</span><div>
      <span className="formal-v2-guidance-step-kind">{({ check: "检查确认", repair: "处理建议", record: "补充记录", handoff: "专业交接" } as const)[step.kind ?? "check"]}</span>
      <h4>{step.title || step.action}</h4>
    </div></div>
    {step.prerequisites && <p className="formal-action-condition"><b>执行条件：</b>{step.prerequisites}</p>}
    {step.stop_condition && <p className="formal-v2-guidance-stop"><b>停止／转向：</b>{step.stop_condition}</p>}
    {step.title && <p className="formal-action-body">{step.action}</p>}
    {step.retest && <div className="formal-action-retest"><b>完成后核对</b><p>{step.retest}</p></div>}
    <div className="formal-action-extras">
      {questionLinks(step.question_ids)}
    </div>
  </li>)}</ol>;
  return <article className="formal-area-result formal-v2-guidance">
    {item.stale && <p className="formal-v2-advice-stale">本次输入、资料或分析要求已更新，旧建议仅供回看；可重新发起分析。</p>}
    {item.status !== 'completed' && <p role="status">{item.status === 'running' ? '正在生成，请勿重复提交。'
      : item.status === 'unknown' ? '请求结果尚未确认，不会自动重发。' : `生成失败：${item.error_code ?? '未知错误'}。未自动重试。`}</p>}
    {result && <>
      <section className="formal-v2-guidance-judgment"><h3>当前判断</h3><p className="formal-v2-guidance-lead">{result.summary}</p>
      </section>
      {result.precautions.length > 0 && <section className="formal-advice-cautions" aria-label="操作提醒">
        <h3>操作提醒</h3><ul>{result.precautions.map((text, i) => <li key={i}>{text}</li>)}</ul>
      </section>}
      {result.steps.length > 0 && <section><h3>现在怎么做</h3>{steps(result.steps)}</section>}
      {(result.verification || result.conditional_branches.length > 0 || result.if_unresolved) && <section className="formal-advice-followup">
        <h3>处理后的复检与后续安排</h3>
        {result.verification && <div className="formal-advice-verification"><h4>先确认处理效果</h4><p>{result.verification}</p></div>}
        {result.conditional_branches.length > 0 && <div className="formal-advice-branches">
          <h4>满足条件后，再继续</h4>
          {result.conditional_branches.map((branch, i) => <details key={i} className="formal-advice-row">
            <summary><span className="formal-advice-row-label">条件 {i + 1}</span><span>{branch.trigger}</span></summary>
            <div className="formal-advice-row-body">{branch.reason && <p>{branch.reason}</p>}{steps(branch.steps)}</div>
          </details>)}
        </div>}
        {result.if_unresolved && <details className="formal-advice-row"><summary>仍未解决时，如何继续</summary><div className="formal-advice-row-body"><p>{result.if_unresolved}</p></div></details>}
      </section>}
      {(result.missing.length > 0 || result.directions.length > 0 || result.uncertainty) && <details className="formal-advice-supplement">
        <summary><span>待确认与补充说明</span>{result.missing.length > 0 && <span className="formal-advice-count">{result.missing.length} 项待确认</span>}</summary>
        <div className="formal-advice-row-body">
          {result.missing.length > 0 && <section><h4>还需要确认什么</h4>
            {result.missing.map((missing, i) => <details key={i} className="formal-advice-row">
              <summary>{missing.missing}</summary><div className="formal-advice-row-body">
                {missing.suggestion && <p><b>如何确认：</b>{missing.suggestion}</p>}
                {missing.reason && <p className="formal-advice-muted"><b>影响：</b>{missing.reason}</p>}
                {questionLink(missing.question_id)}
              </div>
            </details>)}
          </section>}
          {result.directions.length > 0 && <section><h4>其他解释</h4>
            {result.directions.map((direction, i) => <details key={i} className="formal-advice-row"><summary>{direction.title}</summary>
              {direction.explanation && <div className="formal-advice-row-body"><p>{direction.explanation}</p></div>}
            </details>)}
          </section>}
          {result.uncertainty && <section className="formal-advice-uncertainty"><h4>仍有不确定的地方</h4><p>{result.uncertainty}</p></section>}
        </div>
      </details>}
    </>}

  </article>;
}

export function AreaAnalysis({ caseId, areaId, revision, onQuestion }: { caseId: string; areaId?: string; revision: number; onQuestion: (id: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const combined = !areaId;
  const endpoint = areaId ? `/cases/${caseId}/areas/${areaId}/analysis` : `/cases/${caseId}/matched-areas/analysis`;
  const query = useQuery({ queryKey: ['area-analysis', caseId, areaId ?? 'matched', revision],
    queryFn: ({ signal }) => apiClient.request<Analysis>(endpoint, { signal }),
    refetchInterval: q => q.state.data?.history.some(h => h.status === 'running') ? 2500 : false });
  const repairQuery = useQuery({ queryKey: ['template-repairs', caseId],
    queryFn: ({ signal }) => apiClient.request<{ rounds: Array<{ created_at: string; retested_at: string | null }> }>(`/cases/${caseId}/template-repairs`, { signal }) });
  const data = query.data;
  const current = data?.history.find(item => !item.stale);
  const postAdviceTreatment = Boolean(data?.history[0] && repairQuery.data?.rounds.some(item =>
    new Date(item.created_at).getTime() > new Date(data.history[0].created_at).getTime() ||
    Boolean(item.retested_at && new Date(item.retested_at).getTime() > new Date(data.history[0].created_at).getTime())));
  const retryableFailure = current?.status === 'failed';
  const blockedByAttempt = Boolean(current && !retryableFailure);
  const submit = async () => {
    if (busy || !data) return;
    setBusy(true); setError('');
    try {
      await apiClient.request(endpoint, {
        method: 'POST', body: { expected_revision: revision }, timeoutMs: 135000,
      });
    } catch (e) { setError(errorText(e)); }
    finally { await query.refetch(); setBusy(false); }
  };
  return <section className="prototype-synthesis formal-area-analysis">
    <div className="prototype-section-title split"><div><p className="prototype-eyebrow">CASE ADVICE · FROZEN SERVER SNAPSHOT</p><h2>AI 分析建议</h2></div><span className="prototype-synthesis-badge">{data?.history[0]?.status === 'completed' ? '本次结果：真实模型生成' : '当前请求：真实 AI'}</span></div>
    {query.isPending && <p>正在读取区域资料与分析记录…</p>}
    {query.error && <p role="alert">{errorText(query.error)}</p>}
    {data && <><p>{combined ? `本次只综合 ${data.areas?.length ?? 0} 个已有检查记录的区域及其对应资料；其余匹配区域暂不发送。` : `本次分析区域：${data.area?.title ?? '当前区域'}。`}未检查的保留为未知；建议不会自动写入维修事实。</p>
      {combined && !data.areas?.length && <p>尚无已保存检查记录的区域，请先记录至少一项检查结果。</p>}
      {(data.areas?.some(area => !area.document_ids.length) || (!combined && !data.documents.length)) && <p>参与分析的区域尚未关联资料。</p>}
      {!data.available && <p>当前未配置真实模型连接，尚未发起请求。</p>}
      {postAdviceTreatment && <p className="formal-v2-advice-stale">下方建议生成后又记录了实际处理或复检；这些新记录未发送给本次 AI，原建议不能视为处理后的新判断。</p>}
      <button type="button" className="prototype-button" disabled={busy || blockedByAttempt || !data.available || !data.documents.length || (combined && !data.areas?.length) || Boolean(data.areas?.some(area => !area.document_ids.length))} onClick={() => void submit()}>
        {busy ? '正在请求真实 AI…' : retryableFailure ? '重新分析（上次失败，需手动点击）' : current?.status === 'completed' ? '分析已完成' : current?.status === 'running' ? '正在生成分析…' : current ? '请求结果待确认' : combined ? `综合分析 ${data.areas?.length ?? 0} 个有记录区域（真实 AI）` : '分析本区域（真实 AI）'}</button>
      {error && <p role="alert">{error}</p>}
      {data.history[0] && <Advice item={data.history[0]} onQuestion={onQuestion} />}

      <details className="formal-area-input-preview"><summary>本次将发送的资料与记录（{data.documents.length} 份资料，{data.recorded} 条记录）</summary>
        <p>未记录 {data.unknown} 项；输出上限 {data.max_output_tokens} tokens。</p>
        {combined && data.areas?.map(area => <div key={area.id} className="formal-area-input-group"><h3>{area.title} · {area.observation_ids.length} 条记录 · {area.document_ids.length} 份资料</h3>
          <References items={data.documents.filter(doc => area.document_ids.includes(doc.id))} />
          {data.observations.filter(o => area.observation_ids.includes(o.id)).map(o => <div key={o.id}><p>{o.question}：{o.option_labels.join('、')}</p>
            {Object.keys(o.fields).length > 0 && <pre>{JSON.stringify(o.fields, null, 2)}</pre>}</div>)}
          {area.unknown_question_ids.length > 0 && <p>未记录 {area.unknown_question_ids.length} 项，发送为未知。</p>}</div>)}
        {!combined && <><References items={data.documents} />{data.observations.map(o => <div key={o.id}><p>{o.question}：{o.option_labels.join('、')}</p>
          {Object.keys(o.fields).length > 0 && <pre>{JSON.stringify(o.fields, null, 2)}</pre>}</div>)}</>}
      </details>
    </>}
  </section>;
}
