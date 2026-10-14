import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient, errorText } from '../../api-client';

type Round = { id: string; area_id: string; repair_action: string; repair_note: string;
  pre_repair_revision: number; retest_condition: string | null; retest_outcome: string | null;
  retest_evidence: string | null; next_area_id: string | null; created_at: string; retested_at: string | null };
type Snapshot = { revision: number; areas: Record<string, string>; rounds: Round[] };
type Question = { id: string; area_id: string | null; cardId: string; title: string; answer_kind: string; options?: Array<{ id: string; label: string; outcome: string }> };
type Props = { caseId: string; areaId: string; revision: number;
  questions: Question[]; cards: Array<{ id: string; title: string }>;
  observations: Array<{ effective: boolean; question_id: string; payload?: { option_ids: string[] } }>;
  onArea: (id: string) => void; onChanged: () => void };
const conditions = { same: '与故障发生时可比', different: '工况不同', unavailable: '无法复现或比较' };
const changes = { improved: '已改善', persists: '仍有异常', uncertain: '尚不能判断' };
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
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparisons, setComparisons] = useState<Record<string, string>>({});
  const [nextArea, setNextArea] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['template-repairs', caseId, revision],
    queryFn: ({ signal }) => apiClient.request<Snapshot>(`/cases/${caseId}/template-repairs`, { signal }) });
  const data = query.data;
  const rounds = data?.rounds.filter(item => item.area_id === areaId) ?? [];
  const latest = rounds[0];
  const pending = latest && !latest.retested_at ? latest : undefined;
  const roundIdentity = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!data) return;
    const identity = `${latest?.id ?? 'new'}:${latest?.retested_at ?? 'pending'}`;
    if (roundIdentity.current !== undefined && roundIdentity.current !== identity) {
      setAction(''); setNote(''); setCondition(''); setOutcome(''); setEvidence('');
      setAnswers({}); setSelectedIds([]); setComparisons({}); setNextArea(''); setError('');
      setOpen(null);
    }
    roundIdentity.current = identity;
  }, [data, latest?.id, latest?.retested_at, pending]);
  const effectiveRecords = new Map(observations.filter(item => item.effective).map(item => [item.question_id, item]));
  const recordedIds = new Set(effectiveRecords.keys());
  const availableTargets = questions.filter(q => q.area_id === areaId && recordedIds.has(q.id) && q.answer_kind !== 'automatic_derived');
  const resultFor = (q: Question) => {
    const ids = effectiveRecords.get(q.id)?.payload?.option_ids ?? [];
    const options = ids.map(id => q.options?.find(option => option.id === id));
    const hasUnknown = !options.length || options.some(option => !option || !['normal', 'recovered', 'abnormal'].includes(option.outcome));
    const group = options.some(option => option?.outcome === 'abnormal') ? 'abnormal' : hasUnknown ? 'uncertain' : 'normal';
    return { group, label: options.map(option => option?.label ?? '结果待确认').join('、') || '已保存记录，结果待确认' };
  };
  const candidateGroups = [
    { id: 'abnormal', title: '本次异常项 · 优先复检' },
    { id: 'uncertain', title: '无法检查或待确认项' },
    { id: 'normal', title: '正常或已完成记录项 · 按需添加' },
  ].map(group => ({ ...group, items: availableTargets.filter(q => resultFor(q).group === group.id) }));
  const targets = availableTargets.filter(q => selectedIds.includes(q.id));
  const groups = cards.map(card => ({ ...card, questions: targets.filter(q => q.cardId === card.id) })).filter(group => group.questions.length);
  const written = targets.filter(q => answers[q.id]?.trim());
  // Keep the existing round API; persist human-readable new evidence, never old answers.
  const recordedEvidence = [...written.map(q => `${q.title}${comparisons[q.id] ? `\n复检变化：${changes[comparisons[q.id] as keyof typeof changes]}` : ''}\n处理后新记录：${answers[q.id].trim()}`), evidence.trim()].filter(Boolean).join('\n\n');
  const unverified = targets.filter(q => !answers[q.id]?.trim());
  const evidenceText = recordedEvidence && unverified.length
    ? `${recordedEvidence}\n\n本轮已选但尚未取得新记录：\n${unverified.map(q => q.title).join('\n')}`
    : recordedEvidence;
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
      setAction(''); setNote(''); setCondition(''); setOutcome(''); setAnswers({}); setSelectedIds([]); setComparisons({}); setEvidence(''); setNextArea(''); setOpen(null);
      await query.refetch(); onChanged();
    } catch (cause) { setError(errorText(cause)); await query.refetch(); onChanged(); }
    finally { setBusy(false); }
  };
  const saveRetest = async () => {
    if (!data || !pending || busy || !condition || !outcome || !evidenceText || evidenceText.length > 4000) return;
    setBusy(true); setError('');
    try {
      await apiClient.request(`/cases/${caseId}/template-repairs/${pending.id}/retest`, { method: 'POST', body: {
        expected_revision: revision, retest_condition: condition, retest_outcome: outcome,
        retest_evidence: evidenceText, next_area_id: outcome === 'resolved' && condition === 'same' ? null : nextArea || null } });
      setAnswers({}); setSelectedIds([]); setComparisons({}); setEvidence(''); setCondition(''); setOutcome(''); setNextArea(''); setOpen(null);
      await query.refetch(); onChanged();
    } catch (cause) { setError(errorText(cause)); await query.refetch(); onChanged(); }
    finally { setBusy(false); }
  };
  return <section className="prototype-retest formal-template-retest">
    <div className="prototype-section-title"><div><p className="prototype-eyebrow">S6 · REPAIR & RETEST</p><h2>维修处理与独立复检</h2></div></div>
    <p>实际处理和独立复检分轮保存，不覆盖维修前数据。当前区域：<strong>{data?.areas[areaId] ?? '正在读取'}</strong>（跟随上方区域选择）。</p>
    {query.isPending && <p>正在读取处理记录…</p>}{query.error && <p role="alert">{errorText(query.error)}</p>}
    {pending && <div className="formal-retest-current"><b>本轮已完成的处理</b><p>{pending.repair_action}</p>{pending.repair_note && <p>{pending.repair_note}</p>}</div>}
    {data && <div className="prototype-intake-grid">
      <article><h3>维修处理记录</h3>
        {row('repair', `本轮对${data.areas[areaId]}做了什么处理`, '实际完成后记录，不自动采用 AI 建议。', pending ? '已记录 · 待复检' : '可记录', '区分建议与实际处理。', '填写实际动作并保存，建立本区域的新轮次。', pending ? <p className="prototype-recorded">已保存：{pending.repair_action}。请先完成本轮复检。</p> :
          <div className="formal-template-retest-fields"><label>实际处理动作<textarea value={action} disabled={busy} onChange={e => setAction(e.target.value)} maxLength={4000} placeholder="填写实际处理的部位、动作和范围" /></label>
            <label>补充说明（可选）<textarea value={note} disabled={busy} onChange={e => setNote(e.target.value)} maxLength={4000} /></label>
            <button type="button" className="prototype-button" disabled={busy || !action.trim()} onClick={() => void saveRepair()}>保存实际处理，进入复检</button></div>)}
      </article>
      <article><h3>复检工况</h3>
        {row('condition', '处理后工况与故障发生时是否可比', '根据本次实际复检选择，不预填答案。', condition ? '待保存' : retestStatus, '确认处理前后的结果能否比较。', '先保存实际处理，再选择新检查的工况。',
          <><Choices label="复检工况" items={conditions} value={condition} onChange={setCondition} disabled={!canRetest} />{!pending && <p>{latest?.retested_at ? `最近一次：${conditions[latest.retest_condition as keyof typeof conditions]}` : '先记录实际处理，再填写独立复检。'}</p>}</>)}
      </article>
      <article className="formal-retest-scope"><h3>选择本轮复检项目</h3>
        <p>选择与本次处理有关的检查项，不必重新填写整个区域。</p>
        {candidateGroups.filter(group => group.items.length).map(group => {
          const items = <div className="formal-retest-targets">{group.items.map(q =>
            <label key={q.id}><input type="checkbox" aria-label={q.title.replace(/^[A-Z]+-\d+\s*[·：]\s*/, '')} checked={selectedIds.includes(q.id)} disabled={!canRetest}
              onChange={e => setSelectedIds(previous => e.target.checked ? [...previous, q.id] : previous.filter(id => id !== q.id))} />
              <span>{q.title.replace(/^[A-Z]+-\d+\s*[·：]\s*/, '')}<small>本次记录：{resultFor(q).label}</small></span></label>)}</div>;
          return group.id === 'normal'
            ? <details key={group.id} className="formal-retest-candidates"><summary>{group.title}（{group.items.length} 项，已选 {group.items.filter(q => selectedIds.includes(q.id)).length} 项）</summary>{items}</details>
            : <section key={group.id} className="formal-retest-candidates" aria-label={group.title}><h4>{group.title}（{group.items.length} 项）</h4>{items}</section>;
        })}
        {!availableTargets.length && <p>本区域暂无可关联的检查项，可在下方直接记录新证据。</p>}
        <p>{pending ? `已选择 ${targets.length} 项，可随时调整；其他处理对象可在补充证据中记录。` : '保存实际处理后，选择需要复查的项目。'}</p>
      </article>
      {groups.map(group => <article key={group.id}><h3>{group.title} · 处理后复检</h3>
        {group.questions.map(q => row(`check:${q.id}`, q.title.replace(/^[A-Z]+-\d+\s*[·：]\s*/, ''), '来自本区域已保存的检查项，重新记录处理后的结果。', answers[q.id]?.trim() ? (changes[comparisons[q.id] as keyof typeof changes] ?? '已填写 · 待保存') : retestStatus,
          '取得处理后的新证据，与维修前记录分开保存。', '按实际需要复查；未填写的项目不会自动记为正常。',
          <><Choices label={`${q.title}：复检变化`} items={changes} value={comparisons[q.id] ?? ''}
            onChange={value => setComparisons(previous => ({ ...previous, [q.id]: value }))} disabled={!canRetest} />
          <label className="prototype-note-field">处理后新记录<textarea aria-label={`${q.title}：处理后新记录`} disabled={!canRetest} value={answers[q.id] ?? ''} maxLength={4000} onChange={e => setAnswers(previous => ({ ...previous, [q.id]: e.target.value }))} placeholder="填写本次新现象、读数与单位，或无法复查的原因" /></label></>))}
      </article>)}
      <article><h3>复检结果与新证据</h3>
        {row('result', '本轮处理后，原问题是否仍存在', '按实际结果记录，不因填写完毕就认定解决。', outcome ? '待保存' : retestStatus, '记录本轮结果与后续排查方向。', '至少填写一项新证据；点击保存后，本轮工况与所有新记录一起保存。',
          <div className="formal-template-retest-fields"><Choices label="复检结果" items={outcomes} value={outcome} onChange={setOutcome} disabled={!canRetest} />
            <label>{targets.length ? '其他新证据／补充说明' : '处理后新证据'}<textarea disabled={!canRetest} value={evidence} onChange={e => setEvidence(e.target.value)} maxLength={4000} placeholder="记录新症状、故障码、测量值或无法比较的原因" /></label>
            {!(outcome === 'resolved' && condition === 'same') && <label>下一排查区域（可选）<select value={nextArea} disabled={!canRetest} onChange={e => setNextArea(e.target.value)}><option value="">暂不指定</option>{Object.entries(data.areas).filter(([id]) => id !== areaId).map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select></label>}
            <p>本轮选中 {targets.length} 项，已填写 {written.length} 项，尚未填写 {targets.length - written.length} 项。未填写不代表正常。</p>
            {written.length > 0 && <div className="formal-retest-review"><b>本次将保存</b><ul>{written.map(q => <li key={q.id}>{q.title}：{changes[comparisons[q.id] as keyof typeof changes] ?? '未标注变化'}<p>{answers[q.id]}</p></li>)}</ul></div>}
            {evidenceText.length > 4000 && <p role="alert">本轮新证据共 {evidenceText.length} 字，超过 4000 字保存上限，请精简后保存。</p>}
            <button type="button" className="prototype-button" disabled={!canRetest || !condition || !outcome || !evidenceText || evidenceText.length > 4000} onClick={() => void saveRetest()}>保存本轮独立复检</button>
            {canRetest && (!condition || !outcome || !evidenceText) && <small>请选择复检工况、结果，并填写新证据。</small>}
          </div>)}
      </article>
      {latest?.retested_at && <article><h3>结果与转区</h3>{row('decision', '查看本轮已保存结果', '根据实际保存的复检结果继续。', '已保存', '保留本轮判断依据。', '转向另一区域只改变浏览位置。', <>
        <p>{conditions[latest.retest_condition as keyof typeof conditions]} · {outcomes[latest.retest_outcome as keyof typeof outcomes]}</p>
        <p className="formal-template-retest-evidence">{latest.retest_evidence}</p>
        <p>{latest.retest_outcome === 'resolved' && latest.retest_condition === 'same' ? '本轮记录为可比工况下原问题未再出现，可结束本轮；不等于最终维修报告。' : '尚未在可比工况下确认解决，可继续排查。'}</p>
        {latest.next_area_id && <button type="button" className="prototype-button subtle" onClick={() => onArea(latest.next_area_id!)}>前往{data.areas[latest.next_area_id]}</button>}</>)}</article>}
      {rounds.length > 0 && <article><h3>本区历史轮次</h3>{rounds.map((item, index) => row(`history:${item.id}`, `第 ${rounds.length - index} 轮 · ${data.areas[areaId]}`, new Date(item.created_at).toLocaleString('zh-CN'), item.retested_at ? '已复检' : '待复检', '保留每次实际处理与独立复检。', '历史只读，不覆盖处理前观察。', <>
        <p>实际处理：{item.repair_action}</p>{item.repair_note && <p>{item.repair_note}</p>}
        {item.retested_at ? <><p>{conditions[item.retest_condition as keyof typeof conditions]} · {outcomes[item.retest_outcome as keyof typeof outcomes]}</p><p className="formal-template-retest-evidence">{item.retest_evidence}</p></> : <p>等待本轮独立复检。</p>}</>))}</article>}
    </div>}
    {error && <p role="alert" className="formal-v2-profile-error">{error}</p>}
  </section>;
}
