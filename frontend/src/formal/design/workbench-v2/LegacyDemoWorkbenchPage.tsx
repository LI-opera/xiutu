import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api-client';
import { ErrorState, LoadingState } from '../../components/States';
import { type DiagnosisView, type ObservationList, type ObservationView, type ProtocolDecision } from '../../diagnosis/types';
import type { CaseSnapshot } from '../../types';
import type { AreaDef, AssetDef, QuestionBlock, TopicCard } from './historicalTopicTypes';
import { SavedVehicleProfile } from './FormalVehicleProfile';
import './workbench-v2-prototype.css';
import './workbench-v2-content.css';
import './formal-workbench-v2.css';

type Topic = { topic_id: string; version: string; synthetic: true; formal_usable: false; areas: AreaDef[]; cards: TopicCard[]; questions: QuestionBlock[]; assets: AssetDef[] };
type Writable = { check_id: string; formal_option_id: string; question_id: string; option_id: string };
type View = { case: CaseSnapshot; diagnosis: DiagnosisView; observations: ObservationList; topic: Topic; writable: Writable[]; view: {
  areas: Array<{ area_id: string; priority: number; recorded_questions: number; total_questions: number; recorded_question_ids: string[]; status: string; needs_review: boolean }>;
  current_check_id: string | null; active_question_id: string | null;
  synthesis: { confirmed_facts: Array<{ observation_id: string; question_id: string; option_id: string; label: string; outcome: string }>; issues: Array<{ observation_id: string; question_id: string; option_id: string; label: string; outcome: string }>; pending_area_ids: string[]; current_explanation: string | null; supporting_observation_id: string | null };
} };
type ActiveStep = NonNullable<DiagnosisView['current_step']>;
const activeQuestion: Record<string, string> = { 'CHK-02': 'PRS-02', 'CHK-03': 'PRS-11', 'CHK-04': 'AIR-07', 'CHK-05': 'AIR-15', 'CHK-06': 'RET-01', 'CHK-07': 'RET-04' };
const safetyLabels: Record<string, string> = { none: '未发现/无', caution: '需要谨慎', stop_now: '立即停止检查', unavailable: '无法判断' };
const conditionLabels: Record<string, string> = { acceleration: '加速时', high_load: '高负荷时', intermittent: '间歇出现', unknown: '未知' };
const safetyFromObservation = (observation: ObservationView | undefined) => {
  if (!observation) return null;
  const payload = payloadOf(observation);
  if (observation.kind === 'unavailable') return String(payload.reason ?? '').includes('立即停止') ? 'stop_now' : 'unavailable';
  const note = String((payload.protocol_fields as Record<string, unknown> | undefined)?.symptom_note ?? '');
  return Object.keys(safetyLabels).find(key => note.includes(`安全风险：${safetyLabels[key]}`)) ?? null;
};
const payloadOf = (item: ObservationView) => item.payload as Record<string, unknown>;
const currentProtocol = (step: ActiveStep | null | undefined): ProtocolDecision | null => ((step?.validation as { protocol?: ProtocolDecision } | undefined)?.protocol ?? null);
function Question({ view, question, open, onToggle, onAsset }: { view: View; question: QuestionBlock; open: boolean; onToggle: () => void; onAsset: (id: string) => void }) {
  const history = view.observations.items.filter(item => payloadOf(item).topic_question_id === question.id);
  const current = history.find(item => item.effective);
  const step = view.diagnosis.current_step;
  const checkId = currentProtocol(step)?.next_check_id;
  const isMeasurementStep = ['CHK-02', 'CHK-03'].includes(checkId ?? '') && activeQuestion[checkId ?? ''] === question.id;
  const active = activeQuestion[checkId ?? ''] === question.id && (isMeasurementStep || Boolean(view.writable.find(item => item.check_id === checkId && item.question_id === question.id)));
  const savedLabel = current ? question.options.find(item => item.id === payloadOf(current).topic_option_id)?.label ?? String(payloadOf(current).option_label ?? '已保存') : null;
  return <article className={`prototype-action-card ${current ? 'done' : ''} ${active ? 'current' : ''} ${open ? 'open' : ''}`}>
    <button type="button" className="prototype-action-summary" onClick={onToggle} aria-expanded={open}><span className="prototype-action-index">{current ? '✓' : question.id}</span><span><b>{question.title}</b><small>{question.purpose}</small></span><span className="prototype-action-status">{current ? '历史记录' : active ? '归档待输入' : '只读'}</span><span>{open ? '⌃' : '⌄'}</span></button>
    {open && <div className="prototype-action-detail"><div className="prototype-question-guidance"><p><b>检查目的</b>{question.purpose}</p><p><b>操作说明</b>{question.instructions}</p></div>
      {question.assetIds.length > 0 && <div className="prototype-asset-links">{question.assetIds.map(id => { const asset = view.topic.assets.find(entry => entry.id === id); return asset && <button key={id} type="button" onClick={() => onAsset(id)}>查看{asset.title}</button>; })}</div>}
      {current && <div className="prototype-record-result"><p className="prototype-recorded">当前有效事实：{savedLabel}</p><small>正式病例记录 · revision {current.created_revision}</small></div>}
      {history.filter(item => !item.effective).map(item => <p className="prototype-history-flag" key={item.id}>旧记录（已更正）· revision {item.created_revision}：{question.options.find(option => option.id === payloadOf(item).topic_option_id)?.label ?? String(payloadOf(item).option_label ?? '已记录')}</p>)}
      {!current && history.length > 0 && <p className="prototype-locked-note">本专题问题的原记录已被更正；当前有效观察和下一步以服务端重新计算为准，旧记录仅供追溯。</p>}
      {!current && active && step && <p className="prototype-locked-note">此历史病例的待输入步骤已归档，仅供查看。</p>}
      {!current && !active && history.length === 0 && <p className="prototype-locked-note">此项归档时没有已保存记录。</p>}
    </div>}
  </article>;
}

export function LegacyDemoWorkbenchPage({ caseId }: { caseId: string }) {
  const initialSelectionRef = useRef<string | null>(null);
  const [selectedArea, setSelectedArea] = useState('boost-air');
  const [selectedCard, setSelectedCard] = useState('air-connector');
  const [openQuestion, setOpenQuestion] = useState<string | null>('AIR-07');
  const [assetId, setAssetId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const query = useQuery({ queryKey: ['formal-workbench-v2', caseId], queryFn: ({ signal }) => apiClient.request<View>(`/cases/${caseId}/workbench-v2`, { signal, timeoutMs: 20_000 }), refetchInterval: result => result.state.data?.case.status === 'analyzing' || Boolean(result.state.data?.case.active_run) ? 1000 : false, staleTime: 0 });
  const view = query.data;
  const onRefresh = () => { void query.refetch(); };
  useEffect(() => { setSelectedArea('boost-air'); setSelectedCard('air-connector'); setOpenQuestion('AIR-07'); initialSelectionRef.current = null; }, [caseId]);
  const routeCheck = currentProtocol(view?.diagnosis.current_step)?.next_check_id;
  const topicVersion = view?.topic.version;
  useEffect(() => {
    const questionId = activeQuestion[routeCheck ?? ''];
    const question = view?.topic.questions.find(item => item.id === questionId);
    const card = view?.topic.cards.find(item => item.id === question?.cardId);
    if (question && card) {
      setOpenQuestion(question.id);
      if (card.areaId) setSelectedArea(card.areaId);
      setSelectedCard(card.id);
    }
  }, [caseId, routeCheck, topicVersion]);
  const firstAreaId = view?.view.areas.reduce<{ area_id: string; priority: number } | null>((first, area) => !first || area.priority < first.priority ? area : first, null)?.area_id;
  const confirmedIntakeId = view?.observations.items.find(observation => observation.effective && payloadOf(observation).check_id === 'CHK-01')?.id;
  useEffect(() => {
    if (!firstAreaId || !confirmedIntakeId || activeQuestion[routeCheck ?? '']) return;
    const selectionKey = `${caseId}:${confirmedIntakeId}`;
    if (initialSelectionRef.current === selectionKey) return;
    const firstCard = view?.topic.areas.find(entry => entry.id === firstAreaId)?.componentIds[0];
    if (firstCard) { initialSelectionRef.current = selectionKey; setSelectedArea(firstAreaId); setSelectedCard(firstCard); setOpenQuestion(null); }
  }, [caseId, confirmedIntakeId, firstAreaId, routeCheck, view?.topic.areas]);
  const questionMap = useMemo(() => new Map(view?.topic.questions.map(question => [question.id, question]) ?? []), [view?.topic.questions]);
  if (query.isPending) return <LoadingState label="正在从服务端恢复 V2 病例" />;
  if (query.error || !view) return <ErrorState error={query.error ?? new Error('病例数据不完整')} onRetry={onRefresh} />;
  const { topic, case: item, diagnosis, observations } = view;
  const area = topic.areas.find(entry => entry.id === selectedArea) ?? topic.areas[0];
  const cards = topic.cards.filter(card => card.areaId === area.id);
  const card = cards.find(entry => entry.id === selectedCard) ?? cards[0];
  const step = diagnosis.current_step;
  const protocol = currentProtocol(step);
  const currentCheck = protocol?.next_check_id;
  const effective = observations.items.filter(observation => observation.effective);
  const symptomObservation = effective.find(observation => payloadOf(observation).check_id === 'CHK-01');
  const symptomFields = symptomObservation ? payloadOf(symptomObservation).protocol_fields as Record<string, unknown> | undefined : undefined;
  const unavailableReason = symptomObservation?.kind === 'unavailable' ? String(payloadOf(symptomObservation).reason ?? '') : '';
  const symptomCondition = typeof symptomFields?.symptom_conditions === 'string' ? symptomFields.symptom_conditions : Object.keys(conditionLabels).find(key => unavailableReason.includes(`症状发生工况：${conditionLabels[key]}`)) ?? null;
  const safetyGate = safetyFromObservation(symptomObservation);
  const intakeConfirmed = Boolean(symptomObservation);
  const intakeStopped = symptomObservation?.kind === 'unavailable';
  const topicFacts = effective.filter(observation => typeof payloadOf(observation).topic_question_id === 'string');
  const summary = view.view.synthesis;
  const currentAsset = topic.assets.find(asset => asset.id === assetId);
  const activeTopicQuestion = activeQuestion[currentCheck ?? ''];
  return <div className="prototype-v2 formal-workbench-v2">
    <div className="prototype-warning"><span>◇</span><b>历史病例 · 只读</b><span>保留原有接诊、检查与分析记录；不再提交或更正</span></div>
    <header className="prototype-case-header"><div><p className="prototype-eyebrow">XIUTU · FORMAL DIAGNOSTIC WORKBENCH V2</p><h1>{item.vehicle.model} · {item.vehicle.engine_code} 诊断工作台</h1><p>{item.fault_description}</p></div><div className="prototype-header-actions"><Link className="prototype-button subtle" to="/history">返回病例列表</Link><Link className="prototype-button subtle" to={`/workbench/${caseId}?legacy=1`}>查看区域视图</Link><button className="prototype-button subtle" onClick={onRefresh}>刷新病例</button></div></header>
    <main>
      <SavedVehicleProfile key={caseId} item={item} caseId={caseId} topicVersion={topic.version} symptomCondition={symptomCondition} safetyGate={safetyGate} />
      <section className="prototype-intake"><div className="prototype-section-title"><div><p className="prototype-eyebrow">S0 · INTAKE</p><h2>接诊信息</h2></div></div><div className="prototype-intake-summary"><span>{item.vehicle.model} · {item.vehicle.engine_code}</span><span>{item.fault_description}</span><span>当前读取故障码：{item.fault_codes.join('、') || '未读取'}</span><b>{intakeConfirmed ? intakeStopped ? '已暂停检查，等待安全交接' : '接诊信息已确认' : '等待上方确认'}</b></div>{item.status === 'analyzing' && <p role="status">已保存，服务端正在重新计算下一步…</p>}</section>
      {!intakeConfirmed && <p className="formal-v2-intake-prompt">此病例归档时尚未确认接诊信息；原有待输入状态已保留。</p>}
      {intakeStopped && <p className="formal-v2-intake-prompt">已记录安全边界不明确或需立即停止；不生成负荷检查建议。<Link to={`/workbench/${caseId}?legacy=1`}>查看服务端保守交接</Link></p>}
      {intakeConfirmed && !intakeStopped && <>
      <section className="prototype-area-section">
        <div className="prototype-section-title split"><div><p className="prototype-eyebrow">S1—S5 · DIAGNOSTIC AREAS</p><h2>建议排查区域</h2></div><p>区域状态与进度由服务端投影；当前建议不会清空其他区域记录。</p></div>
        <div className="prototype-area-grid">{[...topic.areas].sort((left, right) => (view.view.areas.find(item => item.area_id === left.id)?.priority ?? 99) - (view.view.areas.find(item => item.area_id === right.id)?.priority ?? 99)).map(entry => {
          const state = view.view.areas.find(item => item.area_id === entry.id)!;
          const done = state.recorded_questions, total = state.total_questions;
          return <button key={entry.id} className={`prototype-area-card ${selectedArea === entry.id ? 'selected' : ''}`} onClick={() => { setSelectedArea(entry.id); setSelectedCard(entry.componentIds[0]); setOpenQuestion(null); }}>
            <span className="prototype-area-top"><span className="prototype-area-icon">{done === total ? '✓' : entry.icon}</span><span>当前优先级 {state.priority}</span></span>
            <strong>{entry.title}</strong><span className="prototype-area-components">{topic.cards.filter(card => card.areaId === entry.id).map(card => card.title).join(' · ')}</span>
            <span className="prototype-progress"><i><i style={{ width: `${total ? done / total * 100 : 0}%` }} /></i><b>{done}/{total} 问题</b></span>
            <span className="prototype-status">{state.needs_review ? '已有记录 · 更正后需复核' : done ? '存在服务端检查记录' : '可查看专题内容'}</span><small>完成记录不等于部件正常。</small>
          </button>;
        })}</div>
      </section>
      <section className="prototype-workspace">
        <aside className="prototype-component-list"><p className="prototype-eyebrow">CURRENT SYSTEM</p><h2>{area.title}</h2><p>{area.description}</p><div>{cards.map(entry => { const done = entry.questionIds.filter(id => topicFacts.some(observation => payloadOf(observation).topic_question_id === id)).length; return <button key={entry.id} className={entry.id === card.id ? 'selected' : ''} onClick={() => { setSelectedCard(entry.id); setOpenQuestion(null); }}><span className="prototype-component-icon">{done === entry.questionIds.length ? '✓' : entry.icon}</span><span><b>{entry.title}</b><small>{done}/{entry.questionIds.length} · 服务端记录</small></span><span>›</span></button>; })}</div></aside>
        <div className="prototype-action-workspace">
          <div className="prototype-action-heading"><div><p className="prototype-eyebrow">QUESTION BLOCKS</p><h2>{card.title}</h2><p>{card.location} · {card.why}</p></div><span className="prototype-component-chip">{card.questionIds.length} 个问题块</span></div>
          <div className="prototype-long-card"><b>为什么检查</b><p>{card.why}</p><b>位置与边界</b><p>{card.location}。{card.safety}</p><div className="prototype-asset-links">{card.assetIds.map(id => { const asset = topic.assets.find(entry => entry.id === id); return asset && <button type="button" key={id} onClick={() => setAssetId(id)}>查看{asset.title}</button>; })}</div></div>
          {activeTopicQuestion && !card.questionIds.includes(activeTopicQuestion) && <p className="formal-v2-current-hint">归档时的待输入任务位于 {questionMap.get(activeTopicQuestion)?.title}；仅供追溯。</p>}
          <div className="prototype-action-list">{card.questionIds.map(id => { const question = questionMap.get(id); return question && <Question key={id} view={view} question={question} open={openQuestion === id} onToggle={() => setOpenQuestion(openQuestion === id ? null : id)} onAsset={setAssetId} />; })}</div>
        </div>
      </section>
      <section className="prototype-synthesis">
        <div className="prototype-section-title"><div><p className="prototype-eyebrow">DIAGNOSTIC SYNTHESIS</p><h2>综合诊断分析</h2></div><span className="prototype-synthesis-badge">只依据服务端有效观察</span></div>
        <div className="prototype-synthesis-grid four">
          <article><h3>已确认事实</h3>{summary.confirmed_facts.length ? summary.confirmed_facts.map(fact => <p key={fact.observation_id}>{questionMap.get(fact.question_id)?.title}：{fact.label}</p>) : <p>专题事实尚未记录。</p>}</article>
          <article><h3>已发现问题</h3>{summary.issues.length ? summary.issues.map(fact => <p key={fact.observation_id}>{questionMap.get(fact.question_id)?.title}：{fact.label}</p>) : <p>没有已保存的专题异常。未检查不等于正常。</p>}</article>
          <article><h3>尚待排查</h3>{summary.pending_area_ids.map(id => <p key={id}>{topic.areas.find(entry => entry.id === id)?.title}：尚无正式专题记录</p>)}</article>
          <article><h3>当前解释</h3><p>{summary.current_explanation ?? '当前没有可继续的受控步骤；请查看已保存事实和报告门禁。'}</p><small>服务端路由引用：{summary.supporting_observation_id ?? '接诊快照/冻结协议'}。最终报告门禁保持原规则。</small></article>
        </div>
        <details className="formal-v2-history"><summary>查看诊断记录与更正历史</summary>{observations.items.map(observation => { const payload = payloadOf(observation); const question = questionMap.get(String(payload.topic_question_id ?? '')); const option = question?.options.find(entry => entry.id === payload.topic_option_id); return <article key={observation.id}><b>{question?.title ?? '受控接诊与检查'} · {option?.label ?? String(payload.option_label ?? '已记录')}</b><span>{observation.effective ? '当前有效' : '已被更正'} · 第 {observation.created_revision} 次病例修订</span>{observation.correction_reason && <small>更正原因：{observation.correction_reason}</small>}<details><summary>技术详情</summary><code>{String(payload.topic_question_id ?? payload.check_id ?? '')} / {String(payload.topic_option_id ?? payload.option_id ?? '')}</code></details></article>; })}</details>
      </section>
      <section className="prototype-ai-analysis"><div className="prototype-section-title"><div><p className="prototype-eyebrow">AI ANALYSIS · FORMAL BOUNDARY</p><h2>AI 分析</h2></div></div><p>正式病例暂未接通模型建议的授权、审阅和记录契约。此处不调用原型 DeepSeek 接口，也不会把 AI 输出写成有效观察或绕过报告门禁。</p><button className="prototype-button" disabled>AI 分析 · 待正式接入</button></section>
      <section className="prototype-retest"><div className="prototype-section-title"><div><p className="prototype-eyebrow">S6 · REPAIR & RETEST</p><h2>维修处理与独立复检</h2></div></div><p>本节仅展示历史记录。</p><div className="prototype-intake-grid">{topic.cards.filter(entry => entry.stage === 'S6').map(entry => <article key={entry.id}><h3>{entry.title}</h3>{entry.questionIds.map(id => { const question = questionMap.get(id); return question && <Question key={id} view={view} question={question} open={openQuestion === id} onToggle={() => setOpenQuestion(openQuestion === id ? null : id)} onAsset={setAssetId} />; })}</article>)}</div><details><summary>最终报告门禁</summary><p>{item.report_gate?.available ? '原有报告门禁允许' : '原有报告门禁尚未允许；本页演示小结不是最终报告。'}</p></details></section>
      </>}
    </main><footer>修途正式病例 V2 体验 · synthetic / DEMO / formal_usable=false · 专题静态内容与病例服务端事实严格分离</footer>
    {currentAsset && <div className="prototype-asset-backdrop" onClick={() => setAssetId(null)}><div className="prototype-asset-viewer" onClick={event => event.stopPropagation()}><header><div><b>{currentAsset.title}</b><small>{currentAsset.description} · 合成资料包</small></div><button onClick={() => setAssetId(null)}>关闭</button></header><div className="prototype-asset-stage"><img src={currentAsset.file} alt={currentAsset.title} style={{ width: `${zoom}%` }} /></div><footer><label>缩放 <input type="range" min="60" max="220" value={zoom} onChange={event => setZoom(Number(event.target.value))} /></label></footer></div></div>}
  </div>;
}
