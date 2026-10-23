import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient, errorText } from '../lib/api-client';

type Round = { id: string; area_id: string; repair_action: string; repair_note: string;
  pre_repair_revision: number; retest_condition: string | null; retest_outcome: string | null;
  retest_evidence: string | null; next_area_id: string | null; created_at: string; retested_at: string | null };
type Snapshot = { revision: number; areas: Record<string, string>; rounds: Round[] };
type Field = { id: string; label: string; type: string; unit?: string | null; allowed_when_options?: string[] };
type Question = { id: string; area_id: string | null; cardId: string; title: string; answer_kind: string;
  options?: Array<{ id: string; label: string; outcome: string }>; fields?: Field[];
  capture?: { batch_id_required?: boolean } | null };
type Props = { caseId: string; areaId: string; revision: number;
  questions: Question[]; cards: Array<{ id: string; title: string }>;
  observations: Array<{ effective: boolean; question_id: string; payload?: { option_ids: string[] } }>;
  onArea: (id: string) => void; onChanged: () => void };
// A re-check answers the original question again; it is saved as a real record, not free text.
type Recheck = { option: string; fields: Record<string, string>; note: string };
const conditions = { same: '与故障发生时可比', different: '工况不同', unavailable: '无法复现或比较' };
const outcomes = { resolved: '原问题未再出现', persists: '原问题仍存在', uncertain: '结果尚不确定' };

function Choices({ label, items, value, onChange, disabled = false }: { label: string; items: Record<string, string>; value: string; onChange: (value: string) => void; disabled?: boolean }) {
  return <div className="prototype-result-grid" role="group" aria-label={label}>{Object.entries(items).map(([id, title]) =>
    <button key={id} type="button" aria-pressed={value === id} className={value === id ? 'selected' : ''} disabled={disabled} onClick={() => onChange(id)}>{title}</button>)}</div>;
}

// Changing the upstream area remounts the draft, so no answer can cross areas or cases.
export function TemplateRepairRetest(props: Props) {
  return <RepairArea key={`${props.caseId}:${props.areaId}`} {...props} />;
}
function RepairArea({ caseId, areaId, revision, questions, cards, observations, onArea, onChanged }: Props) {
  const [action, setAction] = useState('');
  const [note, setNote] = useState('');
  const [condition, setCondition] = useState('');
  const [outcome, setOutcome] = useState('');
  const [evidence, setEvidence] = useState('');
  const [rechecks, setRechecks] = useState<Record<string, Recheck>>({});
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [nextArea, setNextArea] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['template-repairs', caseId, revision],
    queryFn: ({ signal }) => apiClient.request<Snapshot>(`/cases/${caseId}/template-repairs`, { signal }),
    // Keep the section on screen while a new revision loads; unmounting it shrank the page
    // and the browser jumped up to the AI analysis after every save.
    placeholderData: (previous, previousQuery) => previousQuery?.queryKey[1] === caseId ? previous : undefined });
  const stepTwo = useRef<HTMLElement>(null);
  const justSavedRepair = useRef(false);
  const data = query.data;
  const rounds = data?.rounds.filter(item => item.area_id === areaId) ?? [];
  const latest = rounds[0];
  const pending = latest && !latest.retested_at ? latest : undefined;
  const roundIdentity = useRef<string | undefined>(undefined);
  const clearRetest = () => { setCondition(''); setOutcome(''); setEvidence(''); setRechecks({}); setSelectedIds([]); setNextArea(''); setOpen(null); };
  useEffect(() => {
    if (!data) return;
    const identity = `${latest?.id ?? 'new'}:${latest?.retested_at ?? 'pending'}`;
    if (roundIdentity.current !== undefined && roundIdentity.current !== identity) {
      setAction(''); setNote(''); setError(''); clearRetest();
      if (justSavedRepair.current && pending) {
        // Continue where the user is: open the first retest item instead of leaving them to scroll.
        setOpen('condition');
        stepTwo.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
      }
      justSavedRepair.current = false;
    }
    roundIdentity.current = identity;
  }, [data, latest?.id, latest?.retested_at, pending]);
  const effectiveRecords = new Map(observations.filter(item => item.effective).map(item => [item.question_id, item]));
  const recordedIds = new Set(effectiveRecords.keys());
  const areaRecorded = questions.filter(q => q.area_id === areaId && recordedIds.has(q.id) && q.answer_kind !== 'automatic_derived');
  // Readings captured as one batch are compared together; a single re-entry would mix time points.
  const batchOnly = areaRecorded.filter(q => q.capture?.batch_id_required);
  const availableTargets = areaRecorded.filter(q => !q.capture?.batch_id_required);
  const labelsFor = (q: Question, ids: string[]) => ids.map(id => q.options?.find(option => option.id === id)?.label ?? '结果待确认').join('、');
  const resultFor = (q: Question) => {
    const ids = effectiveRecords.get(q.id)?.payload?.option_ids ?? [];
    const options = ids.map(id => q.options?.find(option => option.id === id));
    const hasUnknown = !options.length || options.some(option => !option || !['normal', 'recovered', 'abnormal'].includes(option.outcome));
    const group = options.some(option => option?.outcome === 'abnormal') ? 'abnormal' : hasUnknown ? 'uncertain' : 'normal';
    return { group, label: labelsFor(q, ids) || '已保存记录，结果待确认' };
  };
  const candidateGroups = [
    { id: 'abnormal', title: '本次异常项 · 优先复检' },
    { id: 'uncertain', title: '无法检查或待确认项' },
    { id: 'normal', title: '正常或已完成记录项 · 按需添加' },
  ].map(group => ({ ...group, items: availableTargets.filter(q => resultFor(q).group === group.id) }));
  const targets = availableTargets.filter(q => selectedIds.includes(q.id));
  const groups = cards.map(card => ({ ...card, questions: targets.filter(q => q.cardId === card.id) })).filter(group => group.questions.length);
  const shortTitle = (q: Question) => q.title.replace(/^[A-Z]+-\d+\s*[·：]\s*/, '');
  const optionOf = (q: Question, id?: string) => q.options?.find(option => option.id === id);
  const fieldsFor = (q: Question, optionId?: string) => {
    const option = optionOf(q, optionId);
    if (!option || option.outcome === 'unavailable') return [];
    return (q.fields ?? []).filter(field => !field.allowed_when_options || field.allowed_when_options.includes(option.id));
  };
  const update = (id: string, change: Partial<Recheck>) => setRechecks(previous => ({ ...previous, [id]: { ...(previous[id] ?? { option: '', fields: {}, note: '' }), ...change } }));
  const written = targets.filter(q => rechecks[q.id]?.option);
  const unverified = targets.filter(q => !rechecks[q.id]?.option);
  const describe = (q: Question) => {
    const item = rechecks[q.id];
    const values = fieldsFor(q, item.option).filter(field => item.fields[field.id]?.trim()).map(field => `${field.label} ${item.fields[field.id].trim()}${field.unit ? ` ${field.unit}` : ''}`);
    return [`${q.title}`, `处理前：${resultFor(q).label}`, `处理后：${optionOf(q, item.option)?.label ?? ''}${values.length ? `（${values.join('，')}）` : ''}`, item.note.trim() && `说明：${item.note.trim()}`].filter(Boolean).join('\n');
  };
  // The round keeps a readable summary; the re-checked answers themselves are saved as records.
  const recordedEvidence = [...written.map(describe), evidence.trim()].filter(Boolean).join('\n\n');
  const evidenceText = recordedEvidence && unverified.length
    ? `${recordedEvidence}\n\n本轮已选但尚未取得新记录：\n${unverified.map(q => q.title).join('\n')}`
    : recordedEvidence;
  const recheckBody = written.map(q => {
    const item = rechecks[q.id];
    const unavailable = optionOf(q, item.option)?.outcome === 'unavailable';
    return { question_id: q.id, option_ids: [item.option],
      fields: Object.fromEntries(fieldsFor(q, item.option).filter(field => item.fields[field.id]?.trim()).map(field =>
        [field.id, { value: field.type === 'number' ? Number(item.fields[field.id]) : item.fields[field.id].trim(), unit: field.unit ?? null }])),
      note: unavailable ? '' : item.note.trim(), unavailable_reason: unavailable ? item.note.trim() : '' };
  });
  const retestStatus = pending ? '待记录' : latest ? '本轮已复检' : '先记录处理';
  const canRetest = Boolean(pending) && !busy;
  const row = (id: string, title: string, description: string, status: string, purpose: string, instruction: string, body: ReactNode) =>
    <article key={id} className={`prototype-action-card${open === id ? ' open' : ''}`}>
      <button type="button" className="prototype-action-summary" aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)}>
        <span className="prototype-action-index">{id.startsWith('check:') ? targets.findIndex(q => `check:${q.id}` === id) + 1 : '·'}</span>
        <span><b>{title}</b><small>{description}</small></span><span className="prototype-action-status">{status}</span><span aria-hidden="true">{open === id ? '⌃' : '⌄'}</span>
      </button>
      {open === id && <div className="prototype-action-detail"><div className="prototype-question-guidance"><p><b>记录目的</b>{purpose}</p><p><b>操作说明</b>{instruction}</p></div>{body}</div>}
    </article>;
  const saveRepair = async () => {
    if (!data || busy || !action.trim()) return;
    setBusy(true); setError('');
    try {
      await apiClient.request(`/cases/${caseId}/template-repairs`, { method: 'POST', body: {
        expected_revision: revision, area_id: areaId, repair_action: action.trim(), repair_note: note.trim() } });
      setAction(''); setNote(''); clearRetest();
      justSavedRepair.current = true;
      await query.refetch(); onChanged();
    } catch (cause) { justSavedRepair.current = false; setError(errorText(cause)); await query.refetch(); onChanged(); }
    finally { setBusy(false); }
  };
  const saveRetest = async () => {
    if (!data || !pending || busy || !condition || !outcome || !evidenceText || evidenceText.length > 4000) return;
    setBusy(true); setError('');
    try {
      await apiClient.request(`/cases/${caseId}/template-repairs/${pending.id}/retest`, { method: 'POST', body: {
        expected_revision: revision, retest_condition: condition, retest_outcome: outcome,
        retest_evidence: evidenceText, next_area_id: outcome === 'resolved' && condition === 'same' ? null : nextArea || null,
        observations: recheckBody } });
      clearRetest();
      await query.refetch(); onChanged();
    } catch (cause) { setError(errorText(cause)); await query.refetch(); onChanged(); }
    finally { setBusy(false); }
  };
  return <section className="prototype-retest formal-template-retest">
    <div className="prototype-section-title"><div><p className="prototype-eyebrow">S6 · REPAIR & RETEST</p><h2>维修处理与独立复检</h2></div></div>
    <p>先保存实际处理，再做独立复检；复检的工况、项目和结果一起保存。处理前的记录保留在历史中，不会被覆盖。当前区域：<strong>{data?.areas[areaId] ?? '正在读取'}</strong>（跟随上方区域选择）。</p>
    {query.isPending && <p>正在读取处理记录…</p>}{query.error && <p role="alert">{errorText(query.error)}</p>}
    {data && <div className="prototype-intake-grid">
      <article className="formal-retest-step"><h3>第 1 步 · 实际处理</h3>
        {row('repair', `本轮对${data.areas[areaId]}做了什么处理`, '实际完成后记录，不自动采用 AI 建议。', pending ? '已记录 · 待复检' : '可记录', '区分建议与实际处理。', '只写做了什么；处理后的确认和测量放到第 2 步复检里。', pending ? <p className="prototype-recorded">已保存：{pending.repair_action}。请在第 2 步完成本轮复检。</p> :
          <div className="formal-template-retest-fields"><label>实际处理动作<textarea value={action} disabled={busy} onChange={e => setAction(e.target.value)} maxLength={4000} placeholder="填写实际处理的部位、动作和范围" /></label>
            <label>补充说明（可选）<textarea value={note} disabled={busy} onChange={e => setNote(e.target.value)} maxLength={4000} /></label>
            <button type="button" className="prototype-button" disabled={busy || !action.trim()} onClick={() => void saveRepair()}>保存实际处理，进入复检</button></div>)}
      </article>
      <article ref={stepTwo} className="formal-retest-step" aria-label="第 2 步 · 独立复检"><h3>第 2 步 · 独立复检</h3>
        <p>{pending ? '按顺序填写：复检工况 → 重新检查的项目 → 原问题是否仍存在，最后一起保存。' : latest?.retested_at ? '本轮复检已保存；如再次处理，请先在第 1 步建立新轮次。' : '先在第 1 步保存实际处理，再填写复检。'}</p>
        {!pending && latest?.retested_at && <section className="formal-retest-conclusion" aria-label="本轮复检结论">
          <p><b>{conditions[latest.retest_condition as keyof typeof conditions]} · {outcomes[latest.retest_outcome as keyof typeof outcomes]}</b></p>
          <p>{latest.retest_outcome === 'resolved' && latest.retest_condition === 'same' ? '可比工况下原问题未再出现，本轮可以结束；这不等于最终维修报告。如需 AI 根据处理结果给出下一步，请在 AI 分析中重新发起。' : '尚未在可比工况下确认解决，可继续排查或重新发起 AI 分析。'}</p>
          <p className="formal-template-retest-evidence">{latest.retest_evidence}</p>
          {latest.next_area_id && <button type="button" className="prototype-button subtle" onClick={() => onArea(latest.next_area_id!)}>前往{data.areas[latest.next_area_id]}</button>}
        </section>}
        {pending && <>
        {row('condition', '① 处理后工况与故障发生时是否可比', '根据本次实际复检选择，不预填答案。', condition ? '待保存' : retestStatus, '确认处理前后的结果能否比较。', '间歇性故障需在原故障工况下复检，结果才能说明是否解决。',
          <><Choices label="复检工况" items={conditions} value={condition} onChange={setCondition} disabled={!canRetest} /></>)}
        <div className="formal-retest-scope"><h4>② 选择本轮复检项目</h4>
          <p>选择与本次处理有关的检查项，重新回答原问题；保存后会成为新的检查记录，处理前的结果仍保留在历史中。</p>
          {candidateGroups.filter(group => group.items.length).map(group => {
            const items = <div className="formal-retest-targets">{group.items.map(q =>
              <label key={q.id}><input type="checkbox" aria-label={shortTitle(q)} checked={selectedIds.includes(q.id)} disabled={!canRetest}
                onChange={e => setSelectedIds(previous => e.target.checked ? [...previous, q.id] : previous.filter(id => id !== q.id))} />
                <span>{shortTitle(q)}<small>本次记录：{resultFor(q).label}</small></span></label>)}</div>;
            return group.id === 'normal'
              ? <details key={group.id} className="formal-retest-candidates"><summary>{group.title}（{group.items.length} 项，已选 {group.items.filter(q => selectedIds.includes(q.id)).length} 项）</summary>{items}</details>
              : <section key={group.id} className="formal-retest-candidates" aria-label={group.title}><h4>{group.title}（{group.items.length} 项）</h4>{items}</section>;
          })}
          {!availableTargets.length && <p>本区域暂无可重新记录的检查项，可在下方直接记录新证据。</p>}
          {batchOnly.length > 0 && <small>成组采集的读数（{batchOnly.map(shortTitle).join('、')}）需整组重新采集，暂不支持单项重录，请写入下方新证据。</small>}
          <p>已选择 {targets.length} 项。</p>
        </div>
        {groups.map(group => <div key={group.id} className="formal-retest-group"><h4>{group.title} · 处理后重新记录</h4>
          {group.questions.map(q => {
            const item = rechecks[q.id];
            return row(`check:${q.id}`, shortTitle(q), `处理前：${resultFor(q).label}`, item?.option ? `处理后：${optionOf(q, item.option)?.label}` : retestStatus,
              '取得处理后的新结果，作为新记录保存。', '按实际复查结果选择；未选择的项目不会自动记为正常。',
              <div className="formal-template-retest-fields">
                <Choices label={`${q.title}：处理后结果`} items={Object.fromEntries((q.options ?? []).map(option => [option.id, option.label]))} value={item?.option ?? ''}
                  onChange={value => update(q.id, { option: value, fields: {} })} disabled={!canRetest} />
                {fieldsFor(q, item?.option).map(field => <label key={field.id}>{field.label}{field.unit ? ` · ${field.unit}` : ''}
                  <input aria-label={`${q.title}：${field.label}`} type={field.type === 'number' ? 'number' : 'text'} step={field.type === 'number' ? 'any' : undefined} disabled={!canRetest}
                    value={item?.fields[field.id] ?? ''} onChange={e => update(q.id, { fields: { ...(item?.fields ?? {}), [field.id]: e.target.value } })} /></label>)}
                <label className="prototype-note-field">补充说明（可选）<textarea aria-label={`${q.title}：补充说明`} disabled={!canRetest} value={item?.note ?? ''} maxLength={2000} onChange={e => update(q.id, { note: e.target.value })} placeholder="新现象、读数来源，或无法复查的原因" /></label>
              </div>);
          })}
        </div>)}
        {row('result', '③ 本轮处理后，原问题是否仍存在', '按实际结果记录，不因填写完毕就认定解决。', outcome ? '待保存' : retestStatus, '记录本轮结果与后续排查方向。', '点击保存后，工况、重新记录的项目和结果一起保存。',
          <div className="formal-template-retest-fields"><Choices label="复检结果" items={outcomes} value={outcome} onChange={setOutcome} disabled={!canRetest} />
            <label>{targets.length ? '其他新证据／补充说明' : '处理后新证据'}<textarea disabled={!canRetest} value={evidence} onChange={e => setEvidence(e.target.value)} maxLength={4000} placeholder="记录新症状、故障码、测量值或无法比较的原因" /></label>
            {!(outcome === 'resolved' && condition === 'same') && <label>下一排查区域（可选）<select value={nextArea} disabled={!canRetest} onChange={e => setNextArea(e.target.value)}><option value="">暂不指定</option>{Object.entries(data.areas).filter(([id]) => id !== areaId).map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select></label>}
            <p>本轮选中 {targets.length} 项，已重新记录 {written.length} 项，尚未记录 {targets.length - written.length} 项。未记录不代表正常。</p>
            {written.length > 0 && <div className="formal-retest-review"><b>本次将保存为新记录</b><ul>{written.map(q => <li key={q.id}>{shortTitle(q)}：{resultFor(q).label} → {optionOf(q, rechecks[q.id].option)?.label}</li>)}</ul></div>}
            {evidenceText.length > 4000 && <p role="alert">本轮新证据共 {evidenceText.length} 字，超过 4000 字保存上限，请精简后保存。</p>}
            <button type="button" className="prototype-button" disabled={!canRetest || !condition || !outcome || !evidenceText || evidenceText.length > 4000} onClick={() => void saveRetest()}>保存本轮独立复检</button>
            {canRetest && (!condition || !outcome || !evidenceText) && <small>请选择复检工况、结果，并至少重新记录一项或填写新证据。</small>}
          </div>)}
        </>}
      </article>
      {rounds.length > 0 && <article className="formal-retest-step"><h3>本区历史轮次</h3>{rounds.map((item, index) => row(`history:${item.id}`, `第 ${rounds.length - index} 轮 · ${data.areas[areaId]}`, new Date(item.created_at).toLocaleString('zh-CN'), item.retested_at ? '已复检' : '待复检', '保留每次实际处理与独立复检。', '历史只读，不覆盖处理前观察。', <>
        <p>实际处理：{item.repair_action}</p>{item.repair_note && <p>{item.repair_note}</p>}
        {item.retested_at ? <><p>{conditions[item.retest_condition as keyof typeof conditions]} · {outcomes[item.retest_outcome as keyof typeof outcomes]}</p><p className="formal-template-retest-evidence">{item.retest_evidence}</p></> : <p>等待本轮独立复检。</p>}</>))}</article>}
    </div>}
    {error && <p role="alert" className="formal-v2-profile-error">{error}</p>}
  </section>;
}
