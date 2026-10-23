import { TemplateCaseLifecycle } from './TemplateCaseLifecycle';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiClient, ApiError, errorText, idempotencyKey } from '../lib/api-client';
import { ErrorState, LoadingState } from '../components/States';
import type { CaseSnapshot } from '../lib/types';
import { AreaAnalysis } from './AreaAnalysis';
import { TemplateRepairRetest } from './TemplateRepairRetest';
import { MatchedVehicleForm } from './MatchedVehicleIntake';
import './workbench-base.css';
import './workbench-content.css';
import './workbench.css';

type Option = { id: string; label: string; outcome: string };
type Field = { id: string; label: string; type: string; unit?: string; required_when_recorded?: boolean };
type Question = { id: string; stage: string; cardId: string; area_id: string | null; title: string; purpose: string; instructions: string; answer_kind: string; phase: string; options: Option[]; fields: Field[]; assetIds: string[]; capture?: { batch_kind: string; batch_id_required: boolean } | null; prerequisites: { refs: string[]; when: string }; execution_conditions?: { bypass_options: string[] } };
type Card = { id: string; stage: string; areaId?: string; title: string; icon: string; location: string; why: string; safety: string; questionIds: string[]; assetIds: string[] };
type Area = { id: string; title: string; icon: string; description: string; initialPriority: number; componentIds: string[] };
type AreaRanking = { status: 'not_requested' | 'running' | 'completed' | 'failed'; source: 'template' | 'ai'; order: string[]; reasons: Record<string, string>; available: boolean; error_code: string | null; model: string | null; requested_at: string | null; finished_at: string | null };
type Observation = { id: string; question_id: string; round_id: string | null; payload: { option_ids: string[]; fields: Record<string, { value: string | number; unit: string | null }>; note: string; unavailable_reason: string; batch_id: string | null }; created_revision: number; effective: boolean; correction_reason?: string | null };
type Calculation = { question_id: string; option_id: string | null; reason: string; basis_observation_ids: string[]; detail: Record<string, unknown> };
type ConditionBlocker = { ref: string; expected: string[]; actual: string; reason: string };
type View = { case: CaseSnapshot; topic: { version: string; questions: Question[]; cards: Card[]; areas: Area[]; assets: Array<{ id: string; title: string; description: string; file: string }> }; plan: { required_question_ids: string[]; expanded_area_ids: string[]; capture_batches: Record<string, string>; rounds: Array<{ id: string; batch_id: string }> ; intake: { symptom_condition: string; safety_gate: string } }; observations: Observation[]; view: { question_states: Record<string, { status: string; option_ids: string[]; observation_id: string | null; calculation: Calculation | null; required: boolean; focused?: boolean; condition_blockers?: ConditionBlocker[] }>; derived: Record<string, Calculation>; areas: Array<{ area_id: string; priority: number; recorded: number; required: number; missing: string[]; unavailable: number; abnormal: number; recommendation: string }>; synthesis: { facts: Array<{ question_id: string; option_ids: string[] }>; issues: Array<{ question_id: string; option_ids: string[] }>; unavailable: Array<{ question_id: string; option_ids: string[] }>; conflicts: Array<{ id: string; reason: string; question_ids?: string[] }>; missing_question_ids: string[]; next_step: string }; ai_readiness: { ready_for_first_advice: boolean; repair_conclusion_supported: boolean; reasons: string[]; advice_scope?: string; evidence?: { raw_required_responded: boolean; derived_computable: boolean; evidence_sufficient: boolean } }; active_round_id: string | null } };

type Draft = { selected: string[]; fields: Record<string, string>; unavailableReason: string };
type SaveStatus = { phase: 'idle' | 'dirty' | 'saving' | 'saved' | 'failed' | 'conflict'; message?: string };
type SaveOutcome = 'saved' | 'unchanged' | 'incomplete' | 'failed';
const JumpToQuestion = createContext<(id: string) => void>(() => {});
const fromSaved = (existing?: Observation): Draft => ({ selected: existing?.payload.option_ids ?? [], fields: Object.fromEntries(Object.entries(existing?.payload.fields ?? {}).map(([id, value]) => [id, String(value.value)])), unavailableReason: existing?.payload.unavailable_reason === '原因未提供' ? '' : existing?.payload.unavailable_reason ?? '' });
const currentObservation = (data: View, question: Question) =>
  data.observations.find(item => item.effective && item.question_id === question.id);
const isUnavailable = (question: Question, selected: string[]) => selected.some(id => question.options.find(option => option.id === id)?.outcome === 'unavailable' || question.execution_conditions?.bypass_options.includes(id));
function visibleFields(question: Question, selected: string[]): Field[] {
  if (!selected.length || isUnavailable(question, selected)) return [];
  if (question.id === 'AIR-14' && !selected.includes('within_limit')) return [];
  if (question.id === 'AIR-15' && selected.includes('none')) return [];
  if (['PRS-02', 'PRS-03'].includes(question.id) && selected.includes('signal_missing')) return [];
  if (question.id === 'TUR-07' && selected.includes('none')) return [];
  if (['X-01', 'X-06'].includes(question.id) && selected.includes('none')) return [];
  return question.fields;
}
const needsManualSave = (question: Question, draft: Draft) => isUnavailable(question, draft.selected) || visibleFields(question, draft.selected).length > 0;
function normalizedAnswer(question: Question, draft: Draft) {
  const selected = question.options.filter(option => draft.selected.includes(option.id)).map(option => option.id);
  const unavailable = isUnavailable(question, selected);
  const fields = Object.fromEntries(visibleFields(question, selected).filter(field => draft.fields[field.id]?.trim()).map(field => [field.id, { value: field.type === 'number' ? Number(draft.fields[field.id]) : draft.fields[field.id].trim(), unit: field.unit ?? null }]));
  return { selected, fields, unavailableReason: unavailable ? draft.unavailableReason.trim() || '原因未提供' : '' };
}
function matchesSaved(question: Question, draft: Draft, existing?: Observation): boolean {
  if (!existing) return false;
  const answer = normalizedAnswer(question, draft);
  const savedFields = Object.fromEntries(visibleFields(question, answer.selected).filter(field => existing.payload.fields[field.id]).map(field => [field.id, existing.payload.fields[field.id]]));
  const savedSelected = question.options.filter(option => existing.payload.option_ids.includes(option.id)).map(option => option.id);
  return JSON.stringify(answer.selected) === JSON.stringify(savedSelected) &&
    JSON.stringify(answer.fields) === JSON.stringify(savedFields) &&
    answer.unavailableReason === (existing.payload.unavailable_reason || '');
}
function draftCheck(question: Question, draft: Draft): string | null {
  if (!draft.selected.length && question.answer_kind !== 'multi_choice') return '请选择结果。';
  if (!draft.selected.length) return null; // 空集合表示“未选择”，绝不视为“无此现象”。
  const unavailable = isUnavailable(question, draft.selected);
  if (unavailable) return null;
  const recorded = draft.selected.includes('recorded') || question.answer_kind === 'conditional_operation';
  for (const field of visibleFields(question, draft.selected)) {
    const value = draft.fields[field.id]?.trim() ?? '';
    if (recorded && field.required_when_recorded && !value) return `请填写${field.label}。`;
    if (value && field.type === 'number' && (!Number.isFinite(Number(value)) || Number(value) <= 0)) return `${field.label}需要正数。`;
  }
  return null;
}
function useAnswerSaving(caseId: string, data: View | undefined, refresh: () => Promise<View | undefined>, onCommitted: (id: string, view: View, token: number) => void, navigationToken: () => number) {
  const queryClient = useQueryClient();
  const dataRef = useRef<View | undefined>(data);
  const draftsRef = useRef<Record<string, Draft>>({});
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [statuses, setStatuses] = useState<Record<string, SaveStatus>>({});
  const timers = useRef<Record<string, number>>({});
  const queue = useRef<Promise<void>>(Promise.resolve());
  const pending = useRef<Partial<Record<string, Promise<SaveOutcome>>>>({});
  const autoPending = useRef(new Set<string>());
  const autoTokens = useRef<Record<string, number>>({});
  const attempts = useRef<Record<string, { fingerprint: string; key: string }>>({});
  const committedRef = useRef(onCommitted);
  committedRef.current = onCommitted;
  useEffect(() => {
    if (!data) return;
    if (dataRef.current && data.case.revision < dataRef.current.case.revision) {
      queryClient.setQueryData(['template-workbench', caseId], dataRef.current);
    } else dataRef.current = data;
  }, [caseId, data, queryClient]);
  const status = (id: string, phase: SaveStatus['phase'], message?: string) => setStatuses(old => ({ ...old, [id]: { phase, message } }));
  const save = (id: string, advance = false, token = navigationToken()): Promise<SaveOutcome> => {
    window.clearTimeout(timers.current[id]);
    // A second click while this question is in flight observes the same attempt.
    // In particular, a failed attempt must not silently turn into a new request.
    if (pending.current[id]) return pending.current[id];
    const task: Promise<SaveOutcome> = queue.current.catch(() => {}).then(async () => {
      const latest = dataRef.current;
      const question = latest?.topic.questions.find(item => item.id === id);
      const draft = draftsRef.current[id];
      if (!latest || !question || !draft) return 'unchanged';
      const incomplete = draftCheck(question, draft);
      if (incomplete) { status(id, 'dirty', incomplete); return 'incomplete'; }
      const existing = currentObservation(latest, question);
      if (matchesSaved(question, draft, existing)) {
        if (draftsRef.current[id] === draft) {
          const next = { ...draftsRef.current }; delete next[id]; draftsRef.current = next; setDrafts(next);
          autoPending.current.delete(id); status(id, 'saved');
        }
        return 'unchanged';
      }
      const normalized = normalizedAnswer(question, draft);
      const body = { expected_revision: latest.case.revision, topic_version: latest.topic.version, question_id: id, option_ids: normalized.selected, fields: normalized.fields, note: '', unavailable_reason: isUnavailable(question, normalized.selected) ? draft.unavailableReason.trim() : '', batch_id: question.capture?.batch_id_required ? latest.plan.capture_batches[question.capture.batch_kind] ?? null : null, round_id: null };
      const path = existing ? `/cases/${caseId}/topic-observations/${existing.id}/correct` : `/cases/${caseId}/topic-observations`;
      const fingerprint = JSON.stringify({ path, body });
      const attempt = attempts.current[id]?.fingerprint === fingerprint ? attempts.current[id] : { fingerprint, key: idempotencyKey('template-answer') };
      attempts.current[id] = attempt;
      status(id, 'saving');
      try {
        const response = await apiClient.request<{ view: View }>(path, { method: 'POST', body, idempotencyKey: attempt.key, timeoutMs: 20_000 });
        if (!dataRef.current || response.view.case.revision >= dataRef.current.case.revision) {
          dataRef.current = response.view;
          queryClient.setQueryData(['template-workbench', caseId], response.view);
        }
        if (attempts.current[id] === attempt) delete attempts.current[id];
        if (draftsRef.current[id] === draft) {
          const next = { ...draftsRef.current }; delete next[id]; draftsRef.current = next; setDrafts(next);
          autoPending.current.delete(id); status(id, 'saved');
          if (advance) committedRef.current(id, response.view, token);
          return 'saved';
        }
        status(id, 'dirty');
        if (autoPending.current.has(id)) {
          window.clearTimeout(timers.current[id]);
          timers.current[id] = window.setTimeout(() => { void save(id, question.answer_kind !== 'multi_choice', autoTokens.current[id]); }, question.answer_kind === 'multi_choice' ? 350 : 0);
        }
        return 'saved';
      } catch (failure) {
        const conflict = failure instanceof ApiError && failure.status === 409;
        status(id, conflict ? 'conflict' : 'failed', conflict ? '病例已在其他窗口改变；已保留本地选择。请同步后重试。' : errorText(failure));
        if (conflict) {
          delete attempts.current[id];
          const synced = await refresh();
          if (synced && (!dataRef.current || synced.case.revision >= dataRef.current.case.revision)) dataRef.current = synced;
        }
        return 'failed';
      }
    });
    pending.current[id] = task;
    queue.current = task.then(() => undefined, () => undefined);
    void task.then(() => { if (pending.current[id] === task) delete pending.current[id]; }, () => { if (pending.current[id] === task) delete pending.current[id]; });
    return task;
  };
  const change = (question: Question, existing: Observation | undefined, mutate: (draft: Draft) => Draft, autoSave: boolean | ((draft: Draft) => boolean)) => {
    const before = draftsRef.current[question.id] ?? fromSaved(existing);
    const after = mutate(before);
    if (JSON.stringify(before) === JSON.stringify(after)) return;
    delete attempts.current[question.id];
    const next = { ...draftsRef.current, [question.id]: after };
    draftsRef.current = next; setDrafts(next);
    status(question.id, 'dirty', draftCheck(question, after) ?? undefined);
    window.clearTimeout(timers.current[question.id]);
    const shouldAutoSave = typeof autoSave === 'function' ? autoSave(after) : autoSave;
    if (shouldAutoSave && !draftCheck(question, after)) {
      autoPending.current.add(question.id);
      autoTokens.current[question.id] = navigationToken();
      timers.current[question.id] = window.setTimeout(() => { void save(question.id, question.answer_kind !== 'multi_choice', autoTokens.current[question.id]); }, question.answer_kind === 'multi_choice' ? 350 : 0);
    } else autoPending.current.delete(question.id);
  };
  const finishMulti = async (id: string) => {
    const token = navigationToken();
    const latest = dataRef.current;
    const question = latest?.topic.questions.find(item => item.id === id);
    if (!latest || !question) return;
    const draft = draftsRef.current[id] ?? fromSaved(currentObservation(latest, question));
    if (!draft.selected.length) { status(id, 'dirty', '请选具体项目或“无此现象”后再进入下一项。'); return; }
    if (draftsRef.current[id] && needsManualSave(question, draft)) { status(id, 'dirty', '请先点击保存，再进入下一项。'); return; }
    if (draftsRef.current[id]) {
      const outcome = await save(id);
      if (outcome === 'failed' || outcome === 'incomplete' || draftsRef.current[id]) return;
    } else if (!currentObservation(latest, question)) return;
    const savedView = dataRef.current;
    if (savedView) committedRef.current(id, savedView, token);
  };
  useEffect(() => {
    const pending = Object.keys(drafts).length > 0;
    if (!pending) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    const links = (event: MouseEvent) => {
      const anchor = (event.target as Element | null)?.closest<HTMLAnchorElement>('a[href]');
      if (anchor && new URL(anchor.href).origin === location.origin && !window.confirm('仍有未提交的检查输入，确定离开吗？')) event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    document.addEventListener('click', links, true);
    return () => { window.removeEventListener('beforeunload', warn); document.removeEventListener('click', links, true); };
  }, [drafts]);
  useEffect(() => () => Object.values(timers.current).forEach(timer => window.clearTimeout(timer)), []);
  return { drafts, statuses, change, save, finishMulti, hasUnsaved: Object.keys(drafts).length > 0 };
}
type Autosave = ReturnType<typeof useAnswerSaving>;
function AnswerForm({ question, existing, autosave, blockers: pendingConditions }: { question: Question; existing?: Observation; autosave: Autosave; blockers: ConditionBlocker[] }) {
  const draft = autosave.drafts[question.id] ?? fromSaved(existing);
  const state = autosave.statuses[question.id] ?? { phase: existing ? 'saved' : 'idle' };
  const choose = (id: string) => autosave.change(question, existing, old => {
    if (question.answer_kind !== 'multi_choice') return { ...old, selected: [id] };
    const exclusive = new Set(['none', 'none_known']);
    const selected = old.selected.includes(id) ? old.selected.filter(item => item !== id) : exclusive.has(id) ? [id] : [...old.selected.filter(item => !exclusive.has(item)), id];
    return { ...old, selected };
  }, after => !needsManualSave(question, after));
  const unavailable = isUnavailable(question, draft.selected);
  const fields = visibleFields(question, draft.selected);
  const manual = needsManualSave(question, draft);
  const hasDraft = Boolean(autosave.drafts[question.id]);
  const validation = hasDraft ? draftCheck(question, draft) : null;
  return <div className="formal-v2-connected-form">
    <div className="prototype-result-grid">{question.options.map(option => <button type="button" key={option.id} aria-pressed={draft.selected.includes(option.id)} className={draft.selected.includes(option.id) ? 'selected' : ''} disabled={pendingConditions.length > 0 && !!question.execution_conditions && !question.execution_conditions.bypass_options.includes(option.id)} onClick={() => choose(option.id)}>{option.label}</button>)}</div>
    {fields.length > 0 && <div className="prototype-structured-fields">{fields.map(field => <label key={field.id}><span>{field.label}{field.required_when_recorded ? ' *' : ''}{field.unit ? ` · ${field.unit}` : ''}</span><input type={field.type === 'number' ? 'number' : 'text'} step={field.type === 'number' ? 'any' : undefined} value={draft.fields[field.id] ?? ''} onChange={event => autosave.change(question, existing, old => ({ ...old, fields: { ...old.fields, [field.id]: event.target.value } }), false)} /></label>)}</div>}
    {unavailable && <label className="formal-v2-reason">无法完成原因（可选；未填写时记录“原因未提供”）<textarea value={draft.unavailableReason} onChange={event => autosave.change(question, existing, old => ({ ...old, unavailableReason: event.target.value }), false)} maxLength={2000} /></label>}
    {question.capture?.batch_id_required && <small>使用服务端分配的采集批次；实际测量字段不会带入演示默认值。</small>}
    {manual && draft.selected.length > 0 && <button type="button" className="prototype-button formal-v2-save" onClick={() => { void autosave.save(question.id, question.answer_kind !== 'multi_choice'); }} disabled={state.phase === 'saving'}>保存</button>}
    {question.answer_kind === 'multi_choice' && <button type="button" className="prototype-button subtle formal-v2-next" onClick={() => { void autosave.finishMulti(question.id); }}>下一项</button>}
    {(state.phase === 'saving' || state.phase === 'failed' || state.phase === 'conflict' || (!hasDraft && (state.phase === 'saved' || existing))) && <p className="formal-v2-form-status" role="status">{state.phase === 'saving' ? '保存中…' : state.phase === 'failed' || state.phase === 'conflict' ? '保存失败' : '已保存'}</p>}
    {validation && <p className="formal-v2-validation">{validation}</p>}
    {(state.phase === 'failed' || state.phase === 'conflict') && <div className="formal-v2-error" role="alert"><p>{state.message}</p><button type="button" onClick={() => { void autosave.save(question.id, question.answer_kind !== 'multi_choice'); }}>重试</button></div>}
  </div>;
}

function QuestionCard({ data, question, open, toggle, autosave, showAsset }: { data: View; question: Question; open: boolean; toggle: () => void; autosave: Autosave; showAsset: (id: string) => void }) {
  const goToQuestion = useContext(JumpToQuestion);
  const state = data.view.question_states[question.id];
  const existing = currentObservation(data, question);
  const label = state.option_ids.map(id => question.options.find(o => o.id === id)?.label ?? id).join('、');
  const savePhase = autosave.statuses[question.id]?.phase;
  const summaryStatus = savePhase === 'saving' ? '保存中…' : savePhase === 'failed' || savePhase === 'conflict' ? '保存失败，重试' : autosave.drafts[question.id] ? '' : state.status === 'derived' ? '服务端计算' : state.status === 'inherited' ? '接诊已确认' : existing?.payload.option_ids.length ? '服务端已保存' : state.focused ? '建议关注' : '可记录';
  return <article id={`formal-question-${question.id}`} className={`prototype-action-card ${existing?.payload.option_ids.length ? 'done' : ''} ${open ? 'open' : ''}`}>
    <button type="button" className="prototype-action-summary" onClick={toggle} aria-expanded={open}><span className="prototype-action-index">{existing?.payload.option_ids.length ? '✓' : question.id}</span><span><b>{question.title}</b><small>{question.purpose}</small></span>{summaryStatus && <span className="prototype-action-status">{summaryStatus}</span>}<span>{open ? '⌃' : '⌄'}</span></button>
    {open && <div className="prototype-action-detail"><div className="prototype-question-guidance"><p><b>检查目的</b>{question.purpose}</p><p><b>操作说明</b>{question.instructions}</p></div>
      {question.assetIds.length > 0 && <div className="prototype-asset-links">{question.assetIds.map(id => { const asset = data.topic.assets.find(entry => entry.id === id); return asset && <button key={id} type="button" onClick={() => showAsset(id)}>查看{asset.title}</button>; })}</div>}
      {state.status === 'derived' && <div className="prototype-record-result"><b>自动派生：{label || '待补充/无法分类'}</b><p>{state.calculation?.reason}</p><small>依据已保存记录：{state.calculation?.basis_observation_ids.length ? state.calculation.basis_observation_ids.join('、') : '尚无完整输入'}。不会读取未提交草稿。</small></div>}
      {state.status === 'inherited' && <p className="prototype-record-result">接诊快照已确认：{label}。不要求再次填写。</p>}
      {state.status !== 'derived' && state.status !== 'inherited' && <>{existing?.payload.option_ids.length ? <p className="prototype-recorded">当前有效事实：{label}</p> : null}{(question.execution_conditions || question.prerequisites.refs.length > 0) && <p>执行条件：{question.execution_conditions ? '完成实际执行结果前，须满足下列已配置前提' : question.prerequisites.when.replace(/[。.!?]+$/, '')}。无法完成可直接记录，实际执行仍由服务端校验。</p>}{(state.condition_blockers?.length ?? 0) > 0 && <div className="prototype-locked-note" role="status">{state.condition_blockers?.map(item => <p key={item.ref}>{item.reason}。<button type="button" onClick={() => goToQuestion(item.ref)}>{item.ref === 'intake:safety_gate' ? '查看接诊安全信息' : `查看${item.ref}`}</button></p>)}<small>无法执行或安全停止仍可按实际情况记录；填写原因不会解锁执行结果。</small></div>}<AnswerForm question={question} existing={existing} autosave={autosave} blockers={state.condition_blockers ?? []} /></>}
    </div>}
  </article>;
}

function navigationBlock(view: View, question: Question): string | null {
  if (question.execution_conditions) return view.view.question_states[question.id]?.condition_blockers?.[0]?.reason ?? null;
  return null;
}

type SynthesisItem = { id: string; text: string; critical?: boolean; questionId?: string };
function SynthesisColumn({ title, items, empty, expanded, onToggle }: { title: string; items: SynthesisItem[]; empty: string; expanded: boolean; onToggle: () => void }) {
  const goToQuestion = useContext(JumpToQuestion);
  const contentRef = useRef<HTMLDivElement>(null);
  const [longText, setLongText] = useState(false);
  const textKey = items.map(item => `${item.id}:${item.text}`).join('\u0000');
  useEffect(() => {
    if (expanded) return;
    const check = () => {
      const overflow = [...(contentRef.current?.querySelectorAll<HTMLElement>('.formal-v2-synthesis-text') ?? [])]
        .some(node => node.scrollHeight > node.clientHeight + 2);
      setLongText(overflow);
    };
    check();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(check);
    if (contentRef.current) observer?.observe(contentRef.current);
    return () => observer?.disconnect();
  }, [expanded, textKey]);
  const isLongList = items.slice(3).some(item => !item.critical);
  const shown = expanded ? items : items.filter((item, index) => index < 3 || item.critical);
  return <article className="formal-v2-synthesis-column">
    <h3>{title} <small>{items.length} 条</small></h3>
    <div ref={contentRef}>{shown.length ? shown.map(item => <p key={item.id} className={`formal-v2-synthesis-text ${expanded ? '' : 'clamped'}`}>{item.questionId ? <button type="button" className="formal-v2-synthesis-question" onClick={() => goToQuestion(item.questionId!)}>{item.text}</button> : item.text}</p>) : <p>{empty}</p>}</div>
    {(isLongList || longText) && <button type="button" className="formal-v2-synthesis-toggle" aria-expanded={expanded} onClick={onToggle}>{expanded ? '收起' : isLongList ? `展开全部（共 ${items.length} 条）` : '查看全文'}</button>}
  </article>;
}

export function SynthesisGrid({ data, label, questionMap, templateBound = false, selectedAreaId }: { data: View; label: (id: string, options: string[]) => string; questionMap: Map<string, Question>; templateBound?: boolean; selectedAreaId?: string }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [showAllMatched, setShowAllMatched] = useState(templateBound);
  const previousAreaId = useRef(selectedAreaId);
  useEffect(() => {
    if (templateBound && previousAreaId.current !== selectedAreaId) setShowAllMatched(false);
    previousAreaId.current = selectedAreaId;
  }, [templateBound, selectedAreaId]);
  const toggle = (key: string) => setExpanded(current => ({ ...current, [key]: !current[key] }));
  const synthesis = data.view.synthesis;
  const matchedAreas = new Map(data.topic.areas.map(area => [area.id, area.title]));
  const currentAreaId = templateBound && !showAllMatched ? selectedAreaId : undefined;
  const inScope = (id: string) => {
    if (!templateBound) return true;
    const areaId = questionMap.get(id)?.area_id;
    return Boolean(areaId && matchedAreas.has(areaId) && (!currentAreaId || areaId === currentAreaId));
  };
  const areaPrefix = (id: string) => templateBound && showAllMatched ? `${matchedAreas.get(questionMap.get(id)?.area_id ?? '') ?? ''} · ` : '';
  const facts = synthesis.facts.filter(item => inScope(item.question_id)).map(item => ({ id: item.question_id, questionId: templateBound ? item.question_id : undefined, text: `${areaPrefix(item.question_id)}${label(item.question_id, item.option_ids)}` }));
  const issues = synthesis.issues.filter(item => inScope(item.question_id)).map(item => ({ id: item.question_id, questionId: templateBound ? item.question_id : undefined, text: `${areaPrefix(item.question_id)}${label(item.question_id, item.option_ids)}` }));
  const conflicts = [
    ...synthesis.conflicts.filter(item => !templateBound || Boolean(item.question_ids?.length && item.question_ids.every(id => {
      const areaId = questionMap.get(id)?.area_id;
      return areaId && matchedAreas.has(areaId);
    }) && item.question_ids.some(inScope))).map(item => ({ id: `conflict:${item.id}`, text: item.reason, critical: true, questionId: templateBound ? item.question_ids?.find(inScope) : undefined })),
    ...synthesis.unavailable.filter(item => inScope(item.question_id)).map(item => ({ id: `unavailable:${item.question_id}`, questionId: templateBound ? item.question_id : undefined, text: `${areaPrefix(item.question_id)}${questionMap.get(item.question_id)?.title ?? item.question_id}：无法完成/未知` })),
    ...synthesis.missing_question_ids.filter(inScope).map(id => ({ id: `missing:${id}`, questionId: templateBound ? id : undefined, text: `${areaPrefix(id)}${questionMap.get(id)?.title ?? id}：${templateBound ? '尚未记录' : '本轮待记录'}` })),
  ];
  const safetyReasons = data.view.ai_readiness.reasons.filter(reason => /安全|停止|危险|关键|冲突/.test(reason));
  const otherReasons = data.view.ai_readiness.reasons.filter(reason => !safetyReasons.includes(reason));
  const explanation = templateBound ? [
    { id: 'template-scope', text: `当前汇总${currentAreaId ? `“${matchedAreas.get(currentAreaId) ?? currentAreaId}”` : '全部匹配区域'}：已保存正常/事实 ${facts.length} 条、异常 ${issues.length} 条、冲突与缺项 ${conflicts.length} 条。点击条目可返回原题。` },
    { id: 'template-analysis', text: issues.length || conflicts.length ? '请核对上列异常、冲突或缺项；这些记录尚不能直接形成故障确诊或维修结论。' : '当前范围没有已记录异常；未检查不等于已排除故障。本栏不是 AI 诊断。' },
  ] : [
    ...safetyReasons.map((text, index) => ({ id: `safety:${index}`, text })),
    { id: 'next', text: synthesis.next_step },
    { id: 'readiness', text: `检查完成度：${data.view.ai_readiness.ready_for_first_advice ? data.view.ai_readiness.advice_scope === 'supplement_or_handoff' ? '关键证据仍需核对，不支持维修结论' : '本轮必需项已回应' : '尚有本轮必需缺项，可依据现有记录分析；未检查内容作为未知'}；本栏是服务端规则摘要，不是模型建议。` },
    ...otherReasons.map((text, index) => ({ id: `reason:${index}`, text })),
  ];
  return <>{templateBound && <div className="formal-v2-synthesis-scope"><button type="button" onClick={() => setShowAllMatched(value => !value)}>{showAllMatched ? '只看当前区域' : '查看全部匹配区域'}</button></div>}<div className="prototype-synthesis-grid four">
    <SynthesisColumn title="已确认事实" items={facts} empty="尚无已保存的检查事实。" expanded={Boolean(expanded.facts)} onToggle={() => toggle('facts')} />
    <SynthesisColumn title="已发现问题" items={issues} empty="未记录异常，不等于已经排除。" expanded={Boolean(expanded.issues)} onToggle={() => toggle('issues')} />
    <SynthesisColumn title="冲突与缺项" items={conflicts} empty="当前无已识别冲突或本轮缺项。" expanded={Boolean(expanded.conflicts)} onToggle={() => toggle('conflicts')} />
    <SynthesisColumn title="当前解释" items={explanation} empty="暂无服务端解释。" expanded={Boolean(expanded.explanation)} onToggle={() => toggle('explanation')} />
  </div></>;
}

export function TemplateWorkbenchPage({ caseId }: { caseId: string }) {
  const [areaId, setAreaId] = useState('boost-air');
  const [cardId, setCardId] = useState('air-intake');
  const [openQuestion, setOpenQuestion] = useState<string | null>(null);
  const [expandedQuestions, setExpandedQuestions] = useState<Set<string>>(() => new Set());
  const [assetId, setAssetId] = useState<string | null>(null);
  const [completionHint, setCompletionHint] = useState('');
  const [rankingBusy, setRankingBusy] = useState(false);
  const [rankingError, setRankingError] = useState('');
  const rankingOrderRef = useRef<string[]>([]);
  const navigation = useRef({ token: 0, areaId, cardId, openQuestion });
  navigation.current.areaId = areaId;
  navigation.current.cardId = cardId;
  navigation.current.openQuestion = openQuestion;
  useEffect(() => { navigation.current.token += 1; setCompletionHint(''); }, [areaId, cardId, openQuestion]);
  const toggleQuestion = (id: string) => {
    navigation.current.token += 1;
    const opening = !expandedQuestions.has(id);
    setExpandedQuestions(current => {
      const next = new Set(current);
      if (opening) next.add(id); else next.delete(id);
      return next;
    });
    setOpenQuestion(opening ? id : openQuestion === id ? null : openQuestion);
  };
  const advanceAfterSave = (id: string, view: View, token: number) => {
    const cursor = navigation.current;
    if (cursor.token !== token || cursor.openQuestion !== id) return;
    const current = view.topic.questions.find(question => question.id === id);
    if (!current) return;
    const scope = current.area_id ? view.topic.cards.filter(card => card.areaId === current.area_id) : view.topic.cards.filter(card => card.stage === current.stage);
    const cardIndex = scope.findIndex(card => card.id === current.cardId);
    for (let c = Math.max(cardIndex, 0); c < scope.length; c += 1) {
      const candidateIds = scope[c].questionIds;
      const start = c === cardIndex ? candidateIds.indexOf(id) + 1 : 0;
      for (const candidateId of candidateIds.slice(start)) {
        const question = view.topic.questions.find(item => item.id === candidateId);
        if (!question || ['automatic_derived'].includes(question.answer_kind) || ['saved', 'derived', 'inherited'].includes(view.view.question_states[candidateId]?.status)) continue;
        if (navigationBlock(view, question)) continue;
        navigation.current = { token: cursor.token + 1, areaId: cursor.areaId, cardId: scope[c].id, openQuestion: candidateId };
        setCardId(scope[c].id); setOpenQuestion(candidateId); setExpandedQuestions(open => new Set(open).add(candidateId)); setCompletionHint('');
        return;
      }
    }
    if (current.area_id) {
      const remaining = view.topic.questions.filter(question => question.area_id === current.area_id && view.view.question_states[question.id]?.status === 'unanswered' && question.answer_kind !== 'automatic_derived');
      const blocked = remaining.map(question => navigationBlock(view, question)).find(Boolean);
      const next = view.view.areas.filter(area => area.area_id !== current.area_id).sort((a, b) => {
        const order = rankingOrderRef.current;
        return (order.indexOf(a.area_id) < 0 ? a.priority : order.indexOf(a.area_id)) - (order.indexOf(b.area_id) < 0 ? b.priority : order.indexOf(b.area_id));
      })[0];
      setCompletionHint(`${remaining.length ? `本区仍有 ${remaining.length} 项未完成${blocked ? `；${blocked}` : ''}。` : '本区当前题目已记录。'}${next ? ` 下一建议区域：${view.topic.areas.find(area => area.id === next.area_id)?.title ?? next.area_id}。` : ''}`);
    }
  };
  const query = useQuery({ queryKey: ['template-workbench', caseId], queryFn: ({ signal }) => apiClient.request<View>(`/cases/${caseId}/workbench-v2`, { signal, timeoutMs: 20_000 }) });
  const data = query.data;
  const templateBinding = (data?.case.intake_snapshot as { template_binding?: { title: string; template_id: string; version: string }; workbench_flow?: string } | undefined)?.template_binding;
  const rankingQuery = useQuery({ queryKey: ['area-ranking', caseId], enabled: Boolean(templateBinding),
    queryFn: ({ signal }) => apiClient.request<AreaRanking>(`/cases/${caseId}/area-ranking`, { signal, timeoutMs: 20_000 }) });
  const ranking = rankingQuery.data;
  rankingOrderRef.current = ranking?.source === 'ai' ? ranking.order : [];
  const requestRanking = async () => {
    if (!data || rankingBusy) return;
    setRankingBusy(true); setRankingError('');
    try {
      await apiClient.request<AreaRanking>(`/cases/${caseId}/area-ranking`, {
        method: 'POST', body: { expected_revision: data.case.revision }, timeoutMs: 45_000,
      });
      await rankingQuery.refetch();
    } catch (error) {
      setRankingError(errorText(error));
      await rankingQuery.refetch();
    } finally { setRankingBusy(false); }
  };
  const refresh = () => { void query.refetch(); void rankingQuery.refetch(); };
  const autosave = useAnswerSaving(caseId, data, async () => (await query.refetch()).data, advanceAfterSave, () => navigation.current.token);
  const goToQuestion = (id: string) => {
    if (id === 'intake:safety_gate') {
      document.querySelector('.prototype-vehicle-basics')?.scrollIntoView({ block: 'start' });
      return;
    }
    const target = query.data?.topic.questions.find(item => item.id === id);
    if (!target) return;
    navigation.current.token += 1;
    if (target.area_id) setAreaId(target.area_id);
    setCardId(target.cardId);
    setOpenQuestion(id);
    setExpandedQuestions(current => new Set(current).add(id));
    // Explicit prerequisite link navigation only; successful saves never scroll.
    window.setTimeout(() => document.getElementById(`formal-question-${id}`)?.scrollIntoView({ block: 'start' }), 0);
  };
  if (query.isPending) return <LoadingState label="正在从服务端恢复专题病例" />;
  if (query.error || !data) return <ErrorState error={query.error ?? new Error('病例数据不完整')} onRetry={refresh} />;
  const area = data.topic.areas.find(entry => entry.id === areaId) ?? data.topic.areas[0];
  const areaOrder = ranking?.source === 'ai' ? ranking.order : data.topic.areas.map(entry => entry.id);
  const areaCards = [...data.topic.areas].sort((a, b) => areaOrder.indexOf(a.id) - areaOrder.indexOf(b.id));
  const rankingStatusText = rankingBusy ? '正在请求真实 AI 排序，请稍候；不要重复点击。'
    : rankingQuery.isPending ? '正在读取 AI 排序状态…'
    : rankingQuery.error ? 'AI 排序状态读取失败，请刷新病例。'
    : ranking?.status === 'completed' && ranking.source === 'ai'
      ? `真实 AI 排序已完成 · ${ranking.model ?? '模型未知'}${ranking.finished_at ? ` · ${new Date(ranking.finished_at).toLocaleString('zh-CN')}` : ''}。下方顺序与理由来自本次模型结果。`
    : ranking?.status === 'running' ? 'AI 排序请求已记录，正在等待结果；可点击“刷新病例”查看状态。'
    : ranking?.status === 'failed' ? `本次未得到可用的 AI 排序（${ranking.error_code ?? '原因未知'}）；下方为模板顺序，不会自动重试。`
    : ranking?.available ? '尚未请求 AI 排序；下方仍是模板顺序。点击绿色按钮才会发起一次真实模型调用。'
    : '尚未请求 AI 排序；当前实例未开放真实模型，下方仍是模板顺序。';
  const cards = data.topic.cards.filter(entry => entry.areaId === area.id);
  const card = cards.find(entry => entry.id === cardId) ?? cards[0];
  const currentAsset = data.topic.assets.find(asset => asset.id === assetId);
  const questionMap = new Map(data.topic.questions.map(question => [question.id, question]));
  const label = (qid: string, options: string[]) => `${questionMap.get(qid)?.title ?? qid}：${options.length ? options.map(id => questionMap.get(qid)?.options.find(option => option.id === id)?.label ?? id).join('、') : '未选择（不等于正常）'}`;
  return <JumpToQuestion.Provider value={goToQuestion}><div className="prototype-v2 formal-workbench-v2">
    <div className="prototype-warning"><span>◇</span><b>资料模板排查</b><span>按实际检查结果记录，处理与复检分别保存</span></div>
    <header className="prototype-case-header"><div><p className="prototype-eyebrow">XIUTU · FORMAL DIAGNOSTIC WORKBENCH V2</p><h1>{data.case.vehicle.model} · {data.case.vehicle.engine_code} 诊断工作台</h1></div><div className="prototype-header-actions"><Link className="prototype-button subtle" to="/history">返回病例列表</Link><button type="button" className="prototype-button subtle" onClick={refresh}>刷新病例</button></div></header>
    <main>
      <TemplateCaseLifecycle caseId={caseId} revision={data.case.revision} closed={Boolean((data.case.intake_snapshot as {case_lifecycle?:{closed?:boolean}})?.case_lifecycle?.closed)} onChanged={refresh} />
      <MatchedVehicleForm embedded initial={{
        brand: data.case.vehicle.brand ?? '', model: data.case.vehicle.model, year: String(data.case.vehicle.year ?? ''),
        engine: data.case.vehicle.engine_code ?? '', complaint: data.case.fault_description,
        codes: data.case.fault_codes.join('、'),
        condition: data.plan.intake.symptom_condition === 'unprovided' ? '' : data.plan.intake.symptom_condition,
        safety: data.plan.intake.safety_gate === 'unprovided' ? '' : data.plan.intake.safety_gate,
      }} />
      <section className="prototype-intake"><div className="prototype-section-title"><div><p className="prototype-eyebrow">S0 · INTAKE</p><h2>接诊信息</h2></div></div><div className="prototype-intake-summary"><span>{data.case.vehicle.model} · {data.case.vehicle.engine_code}</span><span>{data.case.fault_description}</span><span>当前读取故障码：{data.case.fault_codes.join('、')}</span><b>服务端已保存</b></div><details><summary>其他接诊问题</summary>{data.topic.cards.filter(entry => entry.stage === 'S0').flatMap(entry => entry.questionIds).map(id => { const question = questionMap.get(id); return question && <QuestionCard key={id} data={data} question={question} open={expandedQuestions.has(id)} toggle={() => toggleQuestion(id)} autosave={autosave} showAsset={setAssetId} />; })}</details></section>
      <section className="prototype-area-section"><div className="prototype-section-title split"><div><p className="prototype-eyebrow">S1—S5 · DIAGNOSTIC AREAS</p><h2>匹配的排查区域</h2></div></div><div className="formal-v2-ranking-controls"><button type="button" className="prototype-button" disabled={!ranking?.available || rankingBusy} onClick={() => { void requestRanking(); }}>{rankingBusy ? '正在请求 AI…' : ranking?.source === 'ai' ? '真实 AI 已排序' : '点击调用真实 AI 排序'}</button><p className="prototype-generated-status" role="status">{rankingStatusText}</p>{rankingError && <p className="formal-v2-profile-error" role="alert">{rankingError}</p>}</div><div className="prototype-area-grid">{areaCards.map((entry, index) => { const state = data.view.areas.find(item => item.area_id === entry.id)!; return <button type="button" key={entry.id} className={`prototype-area-card ${area.id === entry.id ? 'selected' : ''}`} onClick={() => { navigation.current.token += 1; setAreaId(entry.id); setCardId(entry.componentIds[0]); }}><span className="prototype-area-top"><span className="prototype-area-icon">{entry.icon}</span><span>{ranking?.source === 'ai' ? '建议优先级' : '区域'} {ranking?.source === 'ai' ? index + 1 : state.priority}</span></span><strong>{entry.title}</strong><span className="prototype-area-components">{entry.description}</span><span className="prototype-progress"><i><i style={{ width: `${state.required ? (state.required - state.missing.length) / state.required * 100 : 0}%` }} /></i><b>{state.recorded} 已记录 · {state.required} 可记录</b></span><span className="prototype-status">{ranking?.source === 'ai' ? ranking.reasons[entry.id] : state.recommendation}</span><small>异常 {state.abnormal} · 无法完成 {state.unavailable} · 缺项 {state.missing.length}</small></button>; })}</div></section>
      <section className="prototype-workspace"><aside className="prototype-component-list"><p className="prototype-eyebrow">CURRENT SYSTEM</p><h2>{area.title}</h2><div>{cards.map(entry => <button type="button" key={entry.id} className={entry.id === card.id ? 'selected' : ''} onClick={() => { navigation.current.token += 1; setCardId(entry.id); }}><span className="prototype-component-icon">{entry.icon}</span><span><b>{entry.title}</b><small>{entry.questionIds.filter(id => data.view.question_states[id]?.status === 'saved').length}/{entry.questionIds.length} · 服务端记录</small></span><span>›</span></button>)}</div></aside><div className="prototype-action-workspace"><div className="prototype-action-heading"><div><p className="prototype-eyebrow">QUESTION BLOCKS</p><h2>{card.title}</h2><p>{card.location} · {card.why}</p><div className="prototype-asset-links formal-v2-heading-assets">{card.assetIds.map(id => { const asset = data.topic.assets.find(entry => entry.id === id); return asset && <button type="button" key={id} onClick={() => setAssetId(id)}>查看{asset.title}</button>; })}</div></div><span className="prototype-component-chip">{card.questionIds.length} 个问题块</span></div><div className="prototype-action-list">{card.questionIds.map(id => { const question = questionMap.get(id); return question && <QuestionCard key={id} data={data} question={question} open={expandedQuestions.has(id)} toggle={() => toggleQuestion(id)} autosave={autosave} showAsset={setAssetId} />; })}</div>{completionHint && <p className="formal-v2-completion-hint" role="status">{completionHint}</p>}</div></section>
      <section className="prototype-synthesis"><div className="prototype-section-title"><div><p className="prototype-eyebrow">DIAGNOSTIC SYNTHESIS</p><h2>综合诊断分析</h2></div><span className="prototype-synthesis-badge">服务端规则摘要 · 非 AI</span></div><SynthesisGrid key={caseId} data={data} label={label} questionMap={questionMap} templateBound selectedAreaId={area.id} /><details className="formal-v2-history"><summary>查看完整记录与更正历史（{data.observations.length}）</summary>{data.observations.map(observation => <article key={observation.id}><b>{label(observation.question_id, observation.payload.option_ids)}</b><span>{observation.effective ? '当前有效' : '旧记录'} · revision {observation.created_revision}</span>{observation.payload.note && <small>原有备注：{observation.payload.note}</small>}{observation.payload.unavailable_reason && <small>无法完成原因：{observation.payload.unavailable_reason}</small>}{observation.correction_reason && <small>更正操作说明：{observation.correction_reason}</small>}</article>)}</details></section>
      <AreaAnalysis caseId={caseId} revision={data.case.revision} onQuestion={goToQuestion} />
      <TemplateRepairRetest caseId={caseId} areaId={area.id} revision={data.case.revision} questions={data.topic.questions} cards={data.topic.cards} observations={data.observations} onChanged={refresh} onArea={id => { const next = data.topic.areas.find(entry => entry.id === id); if (next) { setAreaId(id); setCardId(next.componentIds[0]); document.querySelector('.prototype-area-section')?.scrollIntoView({ block: 'start' }); } }} />
    </main><footer>修途工作台 · 编辑性资料模板 · 用户观察独立保存</footer>
    {currentAsset && <div className="prototype-asset-backdrop" onClick={() => setAssetId(null)}><div className="prototype-asset-viewer" onClick={event => event.stopPropagation()}><header><div><b>{currentAsset.title}</b><small>{currentAsset.description} · 合成专题资料</small></div><button onClick={() => setAssetId(null)}>关闭</button></header><div className="prototype-asset-stage"><img src={currentAsset.file} alt={currentAsset.title} /></div></div></div>}
  </div></JumpToQuestion.Provider>;
}
