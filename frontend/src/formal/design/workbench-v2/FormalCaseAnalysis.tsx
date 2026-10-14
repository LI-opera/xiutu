import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient, errorText } from '../../api-client';

type Excerpt = { id: string; source_ref: string; kind: string; text: string; page: number | null; locator?: string; section: string; file_sha256: string; asset_ids: string[] };
const sourceLocation = (source: Excerpt) => source.locator ?? `PDF 第 ${source.page} 页`;
type Direction = { type?: 'observed_pattern' | 'technical_cause'; title: string; basis_observation_ids: string[]; counter_observation_ids?: string[]; source_ids: string[]; editorial_rule_ids?: string[]; limit: string };
type Step = { kind: 'check' | 'conditional_action' | 'handoff' | 'record'; action_id?: string | null; action: string; reason?: string | null; recheck_reason?: string | null; prerequisites?: string | null; basis_observation_ids: string[]; missing_question_ids?: string[]; question_ids?: string[]; source_ids: string[]; retest?: string | null; stop_condition?: string | null };
type QuestionTarget = { question_id: string; name: string; target_question_id: string | null };
type Advice = { summary: string; supported_directions: Direction[]; unconfirmed_directions: string[]; steps: Step[]; retest_plan: string | null; uncertainty: string; safety_notice: string | null; publication?: { contract_version: string; state: 'complete' | 'partial'; rejected_sections: Array<{ field_path: string; rule_id: string; reason: string }>; safety_source_ids?: string[] } };
type Analysis = { id: string; status: string; input_revision: number; current_revision: number; stale: boolean; generation: string; mode: string; provider: string; model: string; allowed_scope: string; content: Advice | null; error_code: string | null; error_message?: string | null; basis: { observation_ids: string[]; observations: Array<{ id: string; question_id: string; question: string; option_labels: string[]; fields?: Record<string, { value: unknown; unit?: string }> }>; sources: Excerpt[]; questions?: Array<{ id: string; title: string; answer_kind: string; target_question_id: string | null }>; editorial_cards: Array<{ id: string; title: string; text: string }>; editorial_rules?: Array<{ id: string; question_id: string; value: number; unit: string; kind: string }>; images: Array<{ id: string; title: string; file: string; model_read_image: boolean }>; supported_action_ids?: string[]; unresolved_questions?: QuestionTarget[]; missing_body_source_refs: string[] }; post_analysis_retest: Array<{ id: string }>; linked_treatments: string[]; current_retest: Record<string, { reason: string; option_id: string | null }> };
type AnalysisList = { gate: { allowed: boolean; reason: string; missing_question_ids: string[]; missing_questions?: QuestionTarget[] }; configuration: { mode: string; enabled: boolean; provider: string; model: string; paid: boolean; input_char_limit: number; max_output_tokens: number; max_real_calls_per_request: number }; preview: { excerpts: Excerpt[]; missing_body_source_refs: string[]; editorial_card_count: number; image_references: Array<{ id: string; title: string }> } | null; items: Analysis[] };

type OpenAdvice = {
  summary: string;
  directions: Array<{ title: string; explanation?: string | null; basis_observation_ids: string[]; counter_observation_ids: string[]; source_ids: string[] }>;
  missing: Array<{ question_id: string; missing: string; reason?: string | null; suggestion?: string | null }>;
  steps: OpenStep[];
  conditional_branches?: Array<{ trigger: string; reason?: string | null; steps: OpenStep[] }>;
  precautions: string[]; verification?: string | null; if_unresolved?: string | null; uncertainty?: string | null;
};
type OpenStep = { kind: 'check' | 'repair' | 'record' | 'handoff'; action: string; reason?: string | null; prerequisites?: string | null; retest?: string | null; stop_condition?: string | null; question_ids: string[]; basis_observation_ids: string[]; source_ids: string[] };

export function OpenGuidanceResult({ analysis, onQuestion, onAsset }: { analysis: Analysis; onQuestion: (id: string) => void; onAsset: (id: string) => void; }) {
  const [referenceImage, setReferenceImage] = useState<string | null>(null);
  const selectedImage = analysis.basis.images.find(item => item.id === referenceImage);
  const content = analysis.content as unknown as OpenAdvice;
  const isV2 = analysis.content?.publication?.contract_version === 'case-advice-open-c19-v2';
  const facts = new Map(analysis.basis.observations.map(item => [item.id, item]));
  const sources = new Map(analysis.basis.sources.map(item => [item.id, item]));
  const questions = new Map((analysis.basis.questions ?? []).map(item => [item.id, item]));
  const questionLink = (id: string) => {
    const item = questions.get(id);
    return item?.target_question_id
      ? <button type="button" className="prototype-button subtle" onClick={() => onQuestion(item.target_question_id!)}>前往{item.title}（{id}）</button>
      : <span role="status">{item ? `接诊继承项需在病例信息中核对（${id}）` : `无法定位对应问题（${id}）`}</span>;
  };
  const basis = (factIds: string[], sourceIds: string[]) => factIds.length + sourceIds.length > 0 && <details className="formal-v2-advice-basis"><summary>查看依据</summary>
    {factIds.map((id, index) => { const fact = facts.get(id); return <p key={`${id}-${index}`}>{fact ? <><button type="button" className="prototype-button subtle" onClick={() => onQuestion(fact.question_id)}>{fact.question}</button>：{fact.option_labels.join('、') || '已记录数值或说明'}</> : `观察引用未匹配（${id}）`}</p>; })}
    {sourceIds.map((id, index) => { const source = sources.get(id); return <div key={`${id}-${index}`}>{source ? <><b>{source.section} · {sourceLocation(source)}</b><p style={{ whiteSpace: 'pre-wrap' }}>{source.text}</p><small>资料版本：{source.source_ref} · SHA-256：{source.file_sha256}</small>{source.asset_ids.map(assetId => { const image = analysis.basis.images.find(item => item.id === assetId); return image && <button type="button" key={assetId} className="prototype-button subtle" onClick={() => assetId.startsWith('AIR-REF-') ? setReferenceImage(assetId) : onAsset(assetId)}>查看图示：{image.title}（模型未读取图片）</button>; })}</> : <p>资料引用未匹配（{id}）</p>}</div>; })}
  </details>;
  const renderSteps = (steps: OpenStep[]) => <ol className="formal-v2-guidance-list">{steps.map((item, index) => <li key={index}><span className="formal-v2-guidance-step-kind">建议步骤</span><h4>{item.action}</h4>{item.reason && <p>{item.reason}</p>}{item.prerequisites && <p>执行条件：{item.prerequisites}</p>}{item.stop_condition && <p className="formal-v2-guidance-stop">停止／转向：{item.stop_condition}</p>}{item.retest && <p>完成后核对：{item.retest}</p>}{item.question_ids.map(id => <p key={id}>{questionLink(id)}</p>)}{basis(item.basis_observation_ids, item.source_ids)}</li>)}</ol>;
  return <div className="formal-v2-guidance">
    <div className="formal-v2-guidance-meta"><span>本次结果来源：{analysis.mode === 'real' ? `真实模型生成 · ${analysis.provider} / ${analysis.model}` : '模型替身测试 · 非真实 AI 生成'}</span><span>记录版本 {analysis.input_revision}{analysis.stale ? ' · 已过期' : ''}</span></div>
    <p className="formal-v2-guidance-demo">模拟病例，非实车检查结果；建议不等于已实施处理或最终维修报告。</p>
    <p>根据当前记录与提供资料生成，需结合现场及原始资料核对。</p>
    <section className="formal-v2-guidance-judgment"><h3>当前判断</h3><p className="formal-v2-guidance-lead">{content.summary}</p>{content.directions.map((item, index) => <div key={index}><b>{item.title}</b>{item.explanation && <p>{item.explanation}</p>}{basis([...item.basis_observation_ids, ...item.counter_observation_ids], item.source_ids)}</div>)}</section>
    {content.missing.length > 0 && <section><h3>建议补充检查</h3><p>以下项目用于进一步判断，可按现场情况选择，不要求全部完成。</p><ul className="formal-v2-guidance-list">{content.missing.map((item, index) => <li key={index}><b>{item.missing}</b>{item.reason && <p>{item.reason}</p>}{item.suggestion && <p>{item.suggestion}</p>}{questionLink(item.question_id)}</li>)}</ul></section>}
    {isV2 ? <>
      {content.steps.length > 0 && <section><h3>当前建议</h3>{renderSteps(content.steps)}</section>}
      {(content.conditional_branches ?? []).length > 0 && <section><h3>确认异常后的处理</h3><p>以下为条件分支；只有确认标题所述异常后才考虑执行。</p>{content.conditional_branches!.map((branch, index) => <details key={index} className="formal-v2-guidance-details"><summary>若发现：{branch.trigger}</summary>{branch.reason && <p>{branch.reason}</p>}{renderSteps(branch.steps)}</details>)}</section>}
    </> : content.steps.length > 0 && <section><h3>按顺序的处理指导</h3>{renderSteps(content.steps)}</section>}
    {content.precautions.length > 0 && <section><h3>注意事项</h3><ul>{content.precautions.map((item, index) => <li key={index}>{item}</li>)}</ul></section>}
    {content.verification && <section><h3>处理后如何验证</h3><p>{content.verification}</p><p>这是未来核对要求，不代表复检已经完成。</p></section>}
    {content.if_unresolved && <section><h3>仍未解决时</h3><p>{content.if_unresolved}</p></section>}
    {content.uncertainty && <p>尚不确定：{content.uncertainty}</p>}
    <details className="formal-v2-guidance-details"><summary>技术详情</summary><p>分析 ID：{analysis.id}</p><p>无效引用仅影响对应链接；系统未对 AI 技术结论进行内容审核。</p></details>
    {selectedImage && selectedImage.file.startsWith('/workbench-v2-assets/') && <div className="prototype-asset-backdrop" onClick={() => setReferenceImage(null)}><div className="prototype-asset-viewer" onClick={event => event.stopPropagation()}><header><b>{selectedImage.title}（模型未读取图片）</b><button type="button" onClick={() => setReferenceImage(null)}>关闭</button></header><div className="prototype-asset-stage"><img src={selectedImage.file} alt={selectedImage.title} /></div></div></div>}
  </div>;
}

function rejectedLabel(field: string, rule: string) {
  if (field.startsWith('retest_plan')) return '处理后验证方案';
  if (field.startsWith('supported_directions')) return '一条故障方向';
  if (field.startsWith('steps')) {
    if (rule.startsWith('action.') || rule.includes('operation')) return '一条现场操作建议';
    return '一条处理或交接建议';
  }
  return '一段分析说明';
}

function rejectedExplanation(field: string, rule: string) {
  if (field.startsWith('retest_plan')) return '缺少可适用的复检依据，本次不提供该复检步骤。';
  if (rule === 'action.known' || rule.includes('operation')) return '当前冻结资料未支持该现场操作，因此没有把它作为可执行步骤展示。';
  if (rule.includes('source')) return '所引资料不能支持这一建议的适用范围。';
  if (rule.includes('fact') || rule.includes('reference')) return '缺少有效病例事实或引用。';
  return '该部分未通过事实、资料或适用条件核对。';
}

function GuidanceResult({ analysis, onQuestion, onAsset }: { analysis: Analysis; onQuestion: (id: string) => void; onAsset: (id: string) => void }) {
  const content = analysis.content;
  if (!content) return null;
  const facts = new Map(analysis.basis.observations.map(item => [item.id, item]));
  const sources = new Map(analysis.basis.sources.map(item => [item.id, item]));
  const questions = new Map(analysis.basis.unresolved_questions?.map(item => [item.question_id, item]) ?? []);
  const first = content.supported_directions[0];
  const records = content.steps.filter(item => item.kind === 'record');
  const operations = content.steps.filter(item => item.kind === 'check' || item.kind === 'conditional_action');
  const handoffs = content.steps.filter(item => item.kind === 'handoff');
  const treatment = operations.find(item => item.kind === 'conditional_action');
  const fieldNames: Record<string, string> = { hpa: '压力', rpm: '转速', load: '负荷', target: '目标压力', actual: '实际压力', pressureBar: '检漏压力', captured_at: '采集时间', gear: '挡位/工况', location: '位置' };
  const showFact = (id: string) => {
    const fact = facts.get(id);
    if (!fact) return null;
    const values = Object.entries(fact.fields ?? {}).filter(([, item]) => item.value !== null && item.value !== undefined && item.value !== '').map(([key, item]) => `${fieldNames[key] ?? key} ${String(item.value)} ${item.unit ?? ''}`.trim());
    return <li key={id}><button type="button" className="prototype-button subtle" onClick={() => onQuestion(fact.question_id)}>{fact.question.replace(/^[A-Z]+-\d+\s*[·：]?\s*/, '')}</button><span> {[...fact.option_labels, ...values].join('；') || '已记录'}</span></li>;
  };
  const evidence = (factIds: string[], sourceIds: string[], missingIds: string[] = []) => factIds.length + sourceIds.length + missingIds.length ? <details className="formal-v2-advice-basis"><summary>查看依据</summary>
    {factIds.length > 0 && <ul>{factIds.map(showFact)}</ul>}
    {missingIds.map(id => { const target = questions.get(id); return <p key={id}><button type="button" className="prototype-button subtle" disabled={!target?.target_question_id} onClick={() => target?.target_question_id && onQuestion(target.target_question_id)}>待补：{target?.name ?? id}</button></p>; })}
    {sourceIds.map(id => { const source = sources.get(id); return <div key={id}><b>{source ? `${source.section} · 手册第 ${source.page} 页` : '来源正文未提供'}</b><p>{source?.text ?? '此来源不在冻结快照中'}</p></div>; })}
  </details> : null;
  const imagesFor = (sourceIds: string[]) => [...new Set(sourceIds.flatMap(id => sources.get(id)?.asset_ids ?? []))].map(id => analysis.basis.images.find(item => item.id === id)).filter((item): item is Analysis['basis']['images'][number] => Boolean(item));
  const editorialFor = (ids: string[]) => ids.map(id => { const rule = analysis.basis.editorial_rules?.find(item => item.id === id); return rule ? <p key={id}>专题演示规则：{rule.value} {rule.unit}（非厂家判断或操作标准）</p> : null; });
  return <div className="formal-v2-guidance">
    <div className="formal-v2-guidance-meta"><span>本次结果来源：{analysis.mode === 'real' ? `真实模型生成 · ${analysis.provider} / ${analysis.model}` : '模型替身测试 · 非真实 AI 生成'}</span><span>记录版本 {analysis.input_revision}{analysis.stale ? ' · 已过期' : ''}</span></div>
    <p className="formal-v2-guidance-demo">模拟病例，非实车检查结果；建议不等于已实施处理或最终维修报告。</p>
    <section className="formal-v2-guidance-judgment"><h3>当前判断</h3><p className="formal-v2-guidance-lead">{content.summary}</p>{first && <><p><b>优先方向：</b>{first.title}</p>{first.basis_observation_ids.length > 0 && <><b>关键支持事实</b><ul>{first.basis_observation_ids.slice(0, 4).map(showFact)}</ul></>}{Boolean(first.counter_observation_ids?.length) && <><b>帮助区分其他方向的记录</b><ul>{first.counter_observation_ids?.slice(0, 3).map(showFact)}</ul></>}</>}
      {content.publication?.state === 'partial' && <div className="formal-v2-guidance-partial" role="status"><b>部分内容未获支持；下方只显示可独立成立的指导。</b><ul>{content.publication.rejected_sections.map((item, index) => <li key={`${item.field_path}-${index}`}>{rejectedLabel(item.field_path, item.rule_id)}：{rejectedExplanation(item.field_path, item.rule_id)}</li>)}</ul></div>}
      {first && evidence(first.basis_observation_ids.concat(first.counter_observation_ids ?? []), first.source_ids)}{first && editorialFor(first.editorial_rule_ids ?? [])}
    </section>
    {records.length > 0 && <section><h3>处理前必要确认</h3><ul className="formal-v2-guidance-list">{records.map((step, index) => <li key={index}><b>{step.action}</b><p>{step.recheck_reason ?? step.reason}</p>{step.question_ids?.map(id => { const target = questions.get(id); const existing = analysis.basis.observations.find(item => item.question_id === id); return <button type="button" key={id} className="prototype-button subtle" onClick={() => onQuestion(target?.target_question_id ?? id)}>前往{target?.name ?? existing?.question.replace(/^[A-Z]+-\d+\s*[·：]?\s*/, '') ?? '对应问题'}</button>; })}{evidence(step.basis_observation_ids, step.source_ids, step.missing_question_ids)}</li>)}</ul></section>}
       {operations.length > 0 && <section><h3>按顺序的处理指导</h3><ol className="formal-v2-guidance-list">{operations.map((step, index) => <li key={index}><span className="formal-v2-guidance-step-kind">{step.kind === 'conditional_action' ? '条件性处理 · 尚未执行' : '处理前检查 · 仅限本步'}</span><h4>{step.action}</h4>{step.prerequisites && <p><b>执行前提：</b>{step.prerequisites}</p>}{step.kind === 'check' && step.retest && <p><b>完成后记录：</b>{step.retest}</p>}{step.stop_condition && <p className="formal-v2-guidance-stop"><b>本步停止／转向：</b>{step.stop_condition}</p>}{imagesFor(step.source_ids).map(image => <button type="button" key={image.id} className="prototype-button subtle" onClick={() => onAsset(image.id)}>查看相关图示：{image.title}（模型未读取图片）</button>)}{evidence(step.basis_observation_ids, step.source_ids)}</li>)}</ol></section>}
    {handoffs.length > 0 && <section><h3>异常分支与交接</h3><ul className="formal-v2-guidance-list">{handoffs.map((step, index) => <li key={index}><b>{step.action}</b>{step.reason && <p>{step.reason}</p>}{evidence(step.basis_observation_ids, step.source_ids, step.missing_question_ids)}</li>)}</ul></section>}
    {treatment?.retest || content.retest_plan || content.publication?.rejected_sections.some(item => item.field_path.startsWith('retest_plan')) ? <section><h3>处理后如何验证</h3><p>{treatment?.retest ?? content.retest_plan ?? '复检方案未获资料支持，当前不提供可执行复检步骤。'}</p><p>处理前记录不被复检覆盖；尚未实施的步骤不显示为已完成。</p>{treatment && evidence(treatment.basis_observation_ids, treatment.source_ids)}</section> : null}
    <details className="formal-v2-guidance-details"><summary>其他方向、不确定性与技术详情</summary>{content.supported_directions.slice(1).map((direction, index) => <div key={index}><b>{direction.title}</b><p>{direction.limit}</p>{evidence(direction.basis_observation_ids.concat(direction.counter_observation_ids ?? []), direction.source_ids)}{editorialFor(direction.editorial_rule_ids ?? [])}</div>)}{content.unconfirmed_directions.length > 0 && <><h4>尚不能确认</h4><ul>{content.unconfirmed_directions.map((item, index) => <li key={index}>{item}</li>)}</ul></>}<p>{content.uncertainty}</p>{content.safety_notice && <p>{content.safety_notice}</p>}{content.publication?.rejected_sections.map((item, index) => <p key={index}>未发布：{item.field_path} / {item.rule_id} · {item.reason}</p>)}<p>契约：{content.publication?.contract_version ?? '旧版'}；分析 ID：{analysis.id}</p><p>引用 ID 与完整冻结来源见各段“查看依据”；编辑性演示数值不是厂家判断标准。</p></details>
    {analysis.linked_treatments.length > 0 && <p>已关联实际处理记录 {analysis.linked_treatments.length} 条；处理后复检仍须单独记录。</p>}{analysis.post_analysis_retest.length > 0 && <p>分析后有 {analysis.post_analysis_retest.length} 个独立复检轮次。</p>}
  </div>;
}

export function FormalCaseAnalysis({ caseId, revision, onQuestion, onAsset }: { caseId: string; revision: number; onQuestion: (id: string) => void; onAsset: (id: string) => void }) {
  const query = useQuery({ queryKey: ['case-analyses', caseId, revision], queryFn: ({ signal }) => apiClient.request<AnalysisList>(`/cases/${caseId}/analyses`, { signal, timeoutMs: 20_000 }), refetchInterval: response => response.state.data?.items.some(item => ['queued', 'running'].includes(item.status)) ? 1500 : false });
  const data = query.data;
  const latest = data?.items[0];
  const unresolved = latest?.basis.unresolved_questions ?? [];
  const isOpen = ['case-advice-open-c19-v1', 'case-advice-open-c19-v2'].includes(latest?.content?.publication?.contract_version ?? '');
  const controlledRetest = latest?.content?.steps.find(step => step.kind === 'conditional_action' && step.action_id && step.retest)?.retest;
  const questionLinks = (items: QuestionTarget[]) => items.length > 0 && <ul className="formal-v2-advice-missing-list">{items.map(item => <li key={item.question_id}><button type="button" className="prototype-button subtle" disabled={!item.target_question_id} onClick={() => item.target_question_id && onQuestion(item.target_question_id)}>{item.name}（{item.question_id}）{item.target_question_id !== item.question_id && item.target_question_id ? ` → 原始问题 ${item.target_question_id}` : ''}</button></li>)}</ul>;
  const references = (facts: string[], sources: string[], missing: string[] = []) => facts.length + sources.length + missing.length === 0 ? null : <details className="formal-v2-advice-basis"><summary>查看事实、缺项与资料依据（{facts.length + sources.length + missing.length}）</summary>
    {facts.map(id => { const fact = latest?.basis.observations?.find(item => item.id === id); return <div key={id}><button type="button" className="prototype-button subtle" onClick={() => fact && onQuestion(fact.question_id)} disabled={!fact}>查看 {fact?.question_id ?? id} · {fact?.question ?? '观察记录'}</button>{fact && <span>　快照结果：{fact.option_labels.join('、') || '已记录数值或文本'}</span>}</div>; })}
    {missing.map(id => { const target = latest?.basis.unresolved_questions?.find(item => item.question_id === id); return <div key={`missing-${id}`}><button type="button" className="prototype-button subtle" disabled={!target?.target_question_id} onClick={() => target?.target_question_id && onQuestion(target.target_question_id)}>待补 {target?.name ?? id}（{id}）</button></div>; })}
    {sources.map(id => { const source = latest?.basis.sources.find(item => item.id === id); return <div key={id}><b>{source?.source_ref ?? id} · 第 {source?.page ?? '?'} 页</b><p>{source?.text ?? '来源正文不在当前快照'}</p></div>; })}
  </details>;
  return <section className="prototype-ai-analysis formal-v2-case-advice"><div className="prototype-section-title"><div><p className="prototype-eyebrow">CASE ADVICE · FROZEN SERVER SNAPSHOT</p><h2>AI 分析建议</h2></div><span className="prototype-synthesis-badge">当前请求模式：{data?.configuration.mode === 'stub' ? '模型替身（非真实 AI）' : data?.configuration.mode === 'real' ? '真实模型已配置' : '关闭'}</span></div>
    <p>综合区为服务端规则摘要；本区是另行生成的病例建议。synthetic / DEMO / formal_usable=false。</p>
    {query.error && <div role="alert">分析状态读取失败：{errorText(query.error)} <button type="button" onClick={() => { void query.refetch(); }}>重试</button></div>}
    {data && <><p>准备状态：{data.gate.reason}</p>{!latest?.content && questionLinks(data.gate.missing_questions ?? [])}
      {!data.configuration.enabled && <p>真实模型调用关闭。仅明确配置的开发实例可使用模型替身。</p>}
      {latest && <article className="formal-v2-advice-result">{latest.content?.publication?.contract_version === 'case-advice-proposal-c17-v1' || isOpen ? null : <h3>本次结果来源：{latest.generation}</h3>}<p>{isOpen ? `AI 分析建议已生成；基于记录版本 ${latest.input_revision}，当前版本 ${latest.current_revision}。` : latest.content?.publication?.contract_version === 'case-advice-proposal-c17-v1' ? `本次建议：${latest.content.publication.state === 'partial' ? '部分内容可用' : '已生成'}；基于记录版本 ${latest.input_revision}，当前版本 ${latest.current_revision}。` : `状态：${latest.status} · 基于记录版本 ${latest.input_revision}；当前版本 ${latest.current_revision}。`}</p>
        {latest.stale && <p className="formal-v2-advice-stale">基于较早记录，需重新分析；以下保留为历史建议，不代表当前病例事实。</p>}
        {latest.status === 'failed' && <p role="alert">{latest.error_message ?? '分析失败；病例记录未改变。'}若上次调用状态不确定，系统不会自动重试付费请求。</p>}
        {['queued', 'running'].includes(latest.status) && <p>任务进行中；仍可继续保存其他检查记录，完成后将按冻结版本显示。</p>}
        {latest.content && (isOpen ? <OpenGuidanceResult analysis={latest} onQuestion={onQuestion} onAsset={onAsset} /> : latest.content.publication?.contract_version === 'case-advice-proposal-c17-v1' ? <GuidanceResult analysis={latest} onQuestion={onQuestion} onAsset={onAsset} /> : <>{latest.content.publication && <p role="status"><b>{latest.content.publication.state === 'partial' ? '部分通过：仅展示独立通过的分析与建议' : '本次分析内容通过校验'}</b>；分析解释不代表操作获准，更不代表最终报告通过。{latest.content.publication.rejected_sections.length > 0 && <> 未发布 {latest.content.publication.rejected_sections.length} 项：{latest.content.publication.rejected_sections.map(item => `${item.field_path}（${item.reason}）`).join('；')}。</>}</p>}<p><b>本次情况概述：</b>{latest.content.summary}</p>
          <h4>有依据的观察方向（非确诊）</h4>{latest.content.supported_directions.length ? latest.content.supported_directions.map((direction, index) => <div key={index}><b>{direction.title}</b><p>{direction.limit}</p>{direction.editorial_rule_ids?.map(id => { const rule = latest.basis.editorial_rules?.find(item => item.id === id); return rule ? <p key={id}>编辑性演示规则 {id}：{rule.value} {rule.unit}（非厂家标准，不授权现场操作）</p> : null; })}{references(direction.basis_observation_ids, direction.source_ids)}</div>) : <p>暂无可单独发布的观察方向；未检查不等于已排除。</p>}
          <h4>尚不能确认</h4><ul>{latest.content.unconfirmed_directions.map((item, index) => <li key={index}>{item}</li>)}</ul>
           <h4>按顺序的记录、检查或交接建议</h4><ol>{latest.content.steps.map((step, index) => <li key={index}><b>{step.kind === 'record' ? '补充记录：' : step.kind === 'conditional_action' ? '资料支持的条件性处理（待执行）：' : step.action_id ? '资料支持的受控检查：' : '交接建议：'}{step.action}</b>{step.reason && <p>原因：{step.reason}</p>}{step.kind === 'record' && step.question_ids?.map(id => { const target = latest.basis.unresolved_questions?.find(item => item.question_id === id); return <button type="button" key={id} className="prototype-button subtle" onClick={() => onQuestion(target?.target_question_id ?? id)}>前往记录 {target?.name ?? id}（{id}）</button>; })}{step.prerequisites && <p>执行条件：{step.prerequisites}</p>}{step.retest && <p>复检：{step.retest}</p>}{step.stop_condition && <p>停止或交接：{step.stop_condition}</p>}{references(step.basis_observation_ids, step.source_ids, step.missing_question_ids)}</li>)}</ol>
          <p><b>处理后复检：</b>{latest.content.retest_plan ?? (latest.content.publication?.rejected_sections.some(item => item.field_path === 'retest_plan') ? '复检方案未获支持，当前未提供可执行复检步骤。' : controlledRetest ? '见上方资料支持的条件性处理步骤；尚未实施处理，尚无复检事实。' : '尚未实施处理，本次未提出处理后复检方案。')}</p><p><b>不确定性：</b>{latest.content.uncertainty}</p>{latest.content.safety_notice && <p>{latest.content.safety_notice}</p>}{latest.content.publication?.safety_source_ids?.length ? references([], latest.content.publication.safety_source_ids) : null}
          {latest.linked_treatments.length > 0 && <p>已关联实际处理记录 {latest.linked_treatments.length} 条；请在下方独立记录处理后的复检。</p>}
          {latest.post_analysis_retest.length > 0 && <p>分析后已有 {latest.post_analysis_retest.length} 个独立复检轮次。{Object.entries(latest.current_retest).map(([id, item]) => `${id}：${item.reason}`).join('；')}</p>}
          <details><summary>本次快照的来源与器件图</summary>{latest.basis.sources.map(item => <p key={item.id}>{item.source_ref} · 第 {item.page} 页：{item.text}</p>)}{latest.basis.images.map(item => <button type="button" key={item.id} onClick={() => onAsset(item.id)}>查看{item.title}（模型未读取图片）</button>)}{latest.basis.missing_body_source_refs.length > 0 && <p>未提供正文：{latest.basis.missing_body_source_refs.join('、')}</p>}</details>
          {latest.allowed_scope === 'supplement_or_handoff' && unresolved.length > 0 && <><h4>待补原始检查</h4><button type="button" className="prototype-button" onClick={() => unresolved[0].target_question_id && onQuestion(unresolved[0].target_question_id)} disabled={!unresolved[0].target_question_id}>前往补充检查</button>{questionLinks(unresolved)}</>}
        </>)}
      </article>}
      {data.items.length > 1 && <details className="formal-v2-advice-history"><summary>较早的病例建议（{data.items.length - 1}）</summary>{data.items.slice(1).map(item => <article key={item.id}><b>{item.generation} · revision {item.input_revision} · {item.stale ? '已过期' : item.status}</b>{item.content && (['case-advice-open-c19-v1', 'case-advice-open-c19-v2'].includes(item.content.publication?.contract_version ?? '') ? <OpenGuidanceResult analysis={item} onQuestion={onQuestion} onAsset={onAsset} /> : <><p>{item.content.summary}</p><ol>{item.content.steps.map((step, index) => <li key={index}>{step.action}<details><summary>条件、依据与复检</summary>{step.reason && <p>原因：{step.reason}</p>}{step.prerequisites && <p>执行条件：{step.prerequisites}</p>}<p>事实依据：{step.basis_observation_ids.join('、') || '无'}</p>{step.missing_question_ids?.length ? <p>待补问题：{step.missing_question_ids.join('、')}</p> : null}{step.source_ids.map(id => { const source = item.basis.sources.find(entry => entry.id === id); return <p key={id}>{source?.source_ref ?? id} · 第 {source?.page ?? '?'} 页：{source?.text}</p>; })}{step.retest && <p>复检：{step.retest}</p>}{step.stop_condition && <p>停止/交接：{step.stop_condition}</p>}</details></li>)}</ol></>)}{item.error_code && <p>{item.error_message ?? '分析失败；病例记录未改变。'}</p>}</article>)}</details>}
    </>}
  </section>;
}
