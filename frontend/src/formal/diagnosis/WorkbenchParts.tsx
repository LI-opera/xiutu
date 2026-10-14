import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiClient, idempotencyKey } from '../api-client';
import { EmptyState, ErrorState, StatusBadge } from '../components/States';
import { consumeRunEvents } from './run-events';
import { codeText, observationSummary, runExplanation, statusText } from './presentation';
import { asStepCandidate, referencesOf, type DiagnosisArea, type DiagnosisView,
  type CorrectObservation, type EnqueuedAction, type EvidenceView, type FinalReportGate,
  type ObservationView, type ProtocolDecision, type ReportList, type RunSnapshot, type StepCandidate,
  type SubmitObservation } from './types';

const terminal = new Set(['succeeded', 'failed', 'cancelled', 'superseded', 'waiting_input']);

export function AreaTree({ areas, currentAreaId, selectedAreaId, busy, canActivate, onActivate, onSelect }: {
  areas: DiagnosisArea[]; currentAreaId?: string; selectedAreaId?: string; busy: boolean;
  canActivate: boolean; onActivate: (id: string) => void; onSelect: (id: string) => void;
}) {
  if (!areas.length) return <EmptyState title="尚无诊断区域">启动诊断后由服务端生成区域。</EmptyState>;
  return <div className="area-tree" role="tree" aria-label="诊断区域">
    {areas.map(area => <div key={area.id} role="treeitem" aria-current={area.id === currentAreaId} aria-selected={area.id === selectedAreaId} className={area.id === selectedAreaId ? 'area active' : 'area'}>
      {['completed', 'current'].includes(area.status) ? <button type="button" className="area-select" aria-pressed={area.id === selectedAreaId} onClick={() => onSelect(area.id)}><b>{area.title}</b><small>{area.component_key}</small></button> : <div><b>{area.title}</b><small>{area.component_key}</small></div>}
      <StatusBadge value={statusText(area.status)} tone={area.status === 'completed' ? 'good' : area.status === 'stale' ? 'bad' : 'warn'} />
      {area.status === 'pending' && canActivate && <button type="button" className="secondary" disabled={busy} onClick={() => onActivate(area.id)}>生成本区域检查</button>}
    </div>)}
  </div>;
}

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

export function ProtocolProgress({ protocol, observations = [] }: { protocol: ProtocolDecision; observations?: ObservationView[] }) {
  const display = protocol.presentation;
  if (!display) return null;
  const checkLabels: Record<string,string> = {'CHK-00':'接车确认','CHK-01':'症状与故障码','CHK-02':'静态数据可信度','CHK-03':'负荷增压记录','CHK-04':'空气路径外观','CHK-05':'局部泄漏定位','CHK-05-SUPPLEMENT':'补充定位','CHK-06':'模拟处理','CHK-07':'处理后复检','CHK-08':'调节机构观察','CHK-09':'受控执行','CHK-10':'交接说明','CHK-11':'最终复核'};
  const actualCompleted = [...new Set(observations.filter(item => item.effective).map(item => checkLabels[String((item.payload as Record<string, unknown>).check_id)]).filter(Boolean))];
  const phases = ['接诊','故障现象与数据确认','系统检查','处理与复检','小结或交接'];
  const currentPhase = display.progress_phase ?? '系统检查';
  const phaseIndex = Math.max(0, phases.indexOf(currentPhase));
  return <section className="protocol-progress" aria-label="当前保守流程进度"><div><p className="kicker">当前阶段</p><b>{currentPhase}</b><p>这是 synthetic 受控演示，不代表实车维修结论。</p></div><ol>{phases.map((label, index) => <li className={index < phaseIndex ? 'done' : index === phaseIndex ? 'current' : 'pending'} key={label}><span>{index < phaseIndex ? '已完成' : index === phaseIndex ? '正在进行' : '后续'}</span><b>{label}</b></li>)}</ol><details><summary>技术步骤与已保存检查</summary><code>{protocol.next_check_id}</code>{actualCompleted.length > 0 && <p>{actualCompleted.join(' → ')}</p>}</details></section>;
}

type SubmittedMeasurement = NonNullable<SubmitObservation['measurements']>[number];
type MeasurementDraft = { value: string; unit: SubmittedMeasurement['unit'] };
const decimalText = /^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,2})?$/;
const validDecimal = (value: string) => {
  const text = value.trim();
  if (!decimalText.test(text)) return false;
  const number = Number(text);
  return Number.isFinite(number) && Math.abs(number) <= 1e30;
};

export const fieldLabel = (value: string) => ({
  visual: '目视', touch: '触摸', leak_spray: '检漏喷剂', ultrasound: '超声设备',
  absent: '未出现', present: '仍存在', not_found: '未发现', localized: '已定位',
  inconclusive: '无法确定', completed: '已完成', incomplete: '未完成', none: '无',
  yes: '是', no: '否', unknown: '未知', secure: '牢固', loose: '松动', free: '活动正常',
  restricted: '受限', consistent: '一致', conflict: '冲突',
  acceleration: '加速时', high_load: '高负荷时', intermittent: '间歇出现',
}[value] ?? value);
const optionLabel = (id: string, fallback: string) => ({
  'leak.localized': '已发现明确漏点', 'leak.not_found': '未发现明确漏点',
  'leak.inconclusive': '结果不确定', 'supplement.localized': '已补充明确定位',
  'supplement.inconclusive': '仍然无法确定', 'repair.completed': '已完成处理',
  'repair.not_completed': '尚未完成处理',
  'intake.confirmed': '确认进入演示', 'profile.recorded': '保存接车信息',
  'static.compatible': '静态读数相容', 'static.abnormal': '静态读数异常',
  'static.ambiguous': '静态信息不足', 'air.seating_suspect': '接头就位可疑',
  'air.wall_damage': '管壁损伤', 'air.oil_trace_only': '仅有油迹', 'air.none': '未见异常',
  'control.continue': '观察支持继续', 'control.conflict': '观察存在冲突',
  'setup.not_run': '尚未运行', 'setup.needed': '条件未就绪', 'setup.completed': '完成合成设置',
  'setup.failed': '执行失败', 'handoff.acknowledged': '确认交接说明',
}[id] ?? fallback.replace(/^增压空气系统/, '').replace(/[。.]$/, ''));

function OutcomeButtons({ label, values, value, onChange }: { label: string; values: string[]; value?: string; onChange: (value: string) => void }) {
  return <fieldset className="outcome-field"><legend>{label}</legend><div className="outcome-buttons">{values.map(item => <button type="button" key={item} aria-pressed={value === item} className={value === item ? 'selected' : 'secondary'} onClick={() => onChange(item)}>{fieldLabel(item)}</button>)}</div></fieldset>;
}

export function ObservationForm({ caseId, revision, epoch, stepId, candidate, requiredConditions, protocol, priorRetest, priorControlSetup, onSubmitted, onConflict }: {
  caseId: string; revision: number; epoch: number; stepId: string; candidate: StepCandidate;
  requiredConditions: Record<string, string> | null; protocol?: ProtocolDecision | null; priorRetest?: ObservationView | null; priorControlSetup?: boolean; onSubmitted: (result: EnqueuedAction) => void;
  onConflict: () => void | Promise<void>;
}) {
  const [unavailable, setUnavailable] = useState(false);
  const [choice, setChoice] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [measurements, setMeasurements] = useState<Record<string, MeasurementDraft>>({});
  const [protocolFields, setProtocolFields] = useState<Record<string, string>>({});
  const [manualRetest, setManualRetest] = useState(false);
  const [presetId, setPresetId] = useState<string | null>(null);
  const keys = useRef(new Map<string, string>());
  const checkId = protocol?.next_check_id;
  const freshFinal = checkId === 'CHK-11' && !!priorControlSetup;
  const singleOption = (protocol?.options?.length ?? 0) === 1;
  useEffect(() => { setUnavailable(false); setChoice(singleOption ? 0 : null); setReason(''); setMeasurements({}); setProtocolFields({}); setManualRetest(false); setPresetId(null); keys.current.clear(); }, [caseId, epoch, stepId, singleOption]);

  const body = useMemo<SubmitObservation | null>(() => {
    if (unavailable) return reason.trim() ? { expected_revision: revision, graph_epoch: epoch, step_id: stepId, kind: 'unavailable', reason: reason.trim(), measurements: [] } : null;
    const kind = candidate.input.kind;
    if ((kind === 'choice' || kind === 'composite') && choice === null) return null;
    const protocolOption = choice === null ? undefined : protocol?.options?.[choice];
    const requiredProtocolFields = protocolOption?.fields ?? [];
    const automaticFields = new Set(['measurement_run_id','retest_run_id','final_retest_run_id','final_stage','source_observation_id']);
    if (requiredProtocolFields.some(field => field.required && !automaticFields.has(field.name) && !protocolFields[field.name]?.trim())) return null;
    if (Object.entries(protocolFields).some(([name, value]) => requiredProtocolFields.some(field => field.name === name && field.kind === 'decimal') && value !== '' && !validDecimal(value))) return null;
    if (checkId === 'CHK-07' && manualRetest && [1, 2, 3].some(index => !validDecimal(protocolFields[`target_${index}_hpa`] ?? '') || !validDecimal(protocolFields[`actual_${index}_hpa`] ?? ''))) return null;
    if (checkId === 'CHK-07' && !manualRetest && !presetId) return null;
    if (checkId === 'CHK-03' && !manualRetest && !presetId) return null;
    if (freshFinal && !manualRetest && !presetId) return null;
    const values = candidate.input.measurements ?? [];
    const measured = values.map(item => ({ spec_id: item.spec_id, value: measurements[item.spec_id]?.value.trim() ?? '', unit: measurements[item.spec_id]?.unit ?? item.unit, conditions: item.conditions }));
    if ((kind === 'measurement' || kind === 'composite') && measured.some(x => !validDecimal(x.value))) return null;
    return { expected_revision: revision, graph_epoch: epoch, step_id: stepId, kind,
      ...(protocolOption ? { option_id: protocolOption.option_id } : { choice_index: choice }), conditions: ((kind === 'choice' || kind === 'composite') && requiredConditions) ? requiredConditions : undefined,
      measurements: measured, protocol_fields: protocolFields };
  }, [unavailable, reason, revision, epoch, stepId, candidate, choice, requiredConditions, measurements, protocol, protocolFields, checkId, manualRetest, presetId, freshFinal]);
  const fingerprint = body ? JSON.stringify(body) : '';
  const submit = useMutation({
    mutationFn: async () => {
      if (!body) throw new Error('请完成当前检查所需输入。');
      let key = keys.current.get(fingerprint);
      if (!key) { key = idempotencyKey(`observation:${stepId}`); keys.current.set(fingerprint, key); }
      return apiClient.request<EnqueuedAction>(`/cases/${caseId}/observations`, { method: 'POST', body, idempotencyKey: key, timeoutMs: 20_000 });
    }, onSuccess: result => { keys.current.delete(fingerprint); onSubmitted(result); },
    onError: error => { if (error instanceof ApiError && error.status === 409) { keys.current.delete(fingerprint); void onConflict(); } },
  });
  const selectedFields = choice === null || checkId === 'CHK-03' ? [] : protocol?.options?.[choice]?.fields ?? [];
  const presets = protocol?.presentation?.demo_measurement_presets ?? [];
  const setProtocolField = (name: string, value: string) => setProtocolFields(old => ({ ...old, [name]: value }));
  const pressurePrefix = freshFinal ? 'final_' : '';
  const pressureRows = [1, 2, 3].map(index => {
    const target = protocolFields[`${pressurePrefix}target_${index}_hpa`] ?? '';
    const actual = protocolFields[`${pressurePrefix}actual_${index}_hpa`] ?? '';
    const valid = validDecimal(target) && validDecimal(actual);
    const delta = valid ? Number(target) - Number(actual) : null;
    return { index, target, actual, delta, judgment: delta === null ? '待填写' : Math.abs(delta) <= 150 ? '演示带内' : delta > 150 ? '实际压力低于目标' : '实际压力高于目标' };
  });
  return <form className="observation-form" onSubmit={event => { event.preventDefault(); submit.mutate(); }}>
    <h3>{checkId === 'CHK-03' ? '填写同次负荷三帧记录' : checkId === 'CHK-07' ? '填写处理后复检结果' : checkId === 'CHK-11' ? '完成最终演示确认' : '记录实际观察'}</h3>
    <label className="check-row"><input type="checkbox" checked={unavailable} onChange={e => setUnavailable(e.target.checked)} /> 当前无法测量或检查</label>
    {unavailable ? <label>无法完成原因<textarea value={reason} onChange={e => setReason(e.target.value)} maxLength={1000} /></label> : <>
      {!singleOption && (candidate.input.kind === 'choice' || candidate.input.kind === 'composite') && <fieldset><legend>选择实际结果</legend>{protocol ? <div className="outcome-buttons">{protocol.options.map((item, index) => <button type="button" key={item.option_id} aria-pressed={choice === index} className={choice === index ? 'selected' : 'secondary'} onClick={() => { setChoice(index); setProtocolFields({}); }}>{optionLabel(item.option_id, item.label)}</button>)}</div> : (candidate.input.choices ?? []).map((item, index) => <label className="choice-row" key={index}><input type="radio" name={`choice-${stepId}`} checked={choice === index} onChange={() => setChoice(index)} />{item.text}</label>)}</fieldset>}
      {singleOption && !['CHK-03','CHK-07','CHK-11'].includes(checkId ?? '') && <p className="section-note">本步骤只有一个记录动作，填写下方结果即可，无需再选择动作。</p>}
      {checkId === 'CHK-02' && <div className="preset-grid">{presets.map(preset => <button type="button" className={presetId === preset.id ? 'preset-card selected' : 'preset-card secondary'} aria-pressed={presetId === preset.id} key={preset.id} onClick={() => { const index = protocol?.options.findIndex(item => item.option_id === preset.option_id) ?? -1; if (index >= 0) setChoice(index); setPresetId(preset.id); setProtocolFields(preset.fields); }}><b>{preset.label}</b><small>{preset.explanation}</small></button>)}</div>}
      {['CHK-03','CHK-07'].includes(checkId ?? '') && <section className="retest-panel"><p className="section-note">记录由系统自动编号。请选择合成演示场景，或手工录入同次三帧数据；单位均为 hPa absolute。</p><div className="preset-grid">{presets.map(preset => <button type="button" className={presetId === preset.id ? 'preset-card selected' : 'preset-card secondary'} aria-pressed={presetId === preset.id} key={preset.id} onClick={() => { setChoice(0); setPresetId(preset.id); setManualRetest(false); setProtocolFields(preset.fields); }}><b>{preset.label}</b><small>{preset.explanation}</small></button>)}</div><button type="button" className="secondary" onClick={() => { setChoice(0); setPresetId(null); setManualRetest(true); setProtocolFields({}); }}>手工录入三帧数据</button>
        {(manualRetest || presetId) && <>{checkId === 'CHK-07' && <OutcomeButtons label="原位置局部泄漏复查" values={['not_found','localized','inconclusive']} value={protocolFields.leak_result} onChange={value => setProtocolField('leak_result', value)} />}<OutcomeButtons label="原症状" values={['absent','present']} value={protocolFields.symptom} onChange={value => setProtocolField('symptom', value)} /><div className="measurement-table" role="table" aria-label="同次三帧增压数据"><div className="measurement-head" role="row"><b>帧</b><b>目标绝对压力</b><b>实际绝对压力</b><b>系统计算差值</b><b>当前判断</b></div>{pressureRows.map(row => <div className="measurement-frame" role="row" key={row.index}><b>{row.index}</b><label>目标绝对压力<input aria-label={`第${row.index}帧目标绝对压力`} inputMode="decimal" readOnly={!manualRetest} value={row.target} onChange={event => setProtocolField(`target_${row.index}_hpa`, event.target.value)} /><small>hPa absolute</small></label><label>实际绝对压力<input aria-label={`第${row.index}帧实际绝对压力`} inputMode="decimal" readOnly={!manualRetest} value={row.actual} onChange={event => setProtocolField(`actual_${row.index}_hpa`, event.target.value)} /><small>hPa absolute</small></label><span>{row.delta === null ? '—' : `${row.delta} hPa`}</span><span>{row.judgment}</span></div>)}</div>{manualRetest && pressureRows.some(row => row.delta === null) && <p className="inline-error">请为三帧分别填写可解析、有限的目标值和实际值。</p>}<details><summary>技术判断范围</summary><p>服务端将按冻结协议校验全部字段和压力差；页面即时结果只帮助发现格式或明显缺项，不决定下一步。</p></details></>}
      </section>}
      {checkId === 'CHK-11' && <section className="final-confirm">{freshFinal ? <><div className="callout"><b>需要新的控制设置后复检记录</b><p>本次将保存为 after_control_setup，使用新的记录编号；此前 CHK-07 的残余增压不足历史保持不变。</p></div><div className="preset-grid">{presets.map(preset => <button type="button" className={presetId === preset.id ? 'preset-card selected' : 'preset-card secondary'} aria-pressed={presetId === preset.id} key={preset.id} onClick={() => { setChoice(0); setPresetId(preset.id); setManualRetest(false); setProtocolFields(preset.fields); }}><b>{preset.label}</b><small>{preset.explanation}</small></button>)}</div><button type="button" className="secondary" onClick={() => { setChoice(0); setPresetId(null); setManualRetest(true); setProtocolFields({}); }}>手工录入最终三帧数据</button>{(manualRetest || presetId) && <div className="measurement-table" role="table" aria-label="控制设置后最终三帧数据"><div className="measurement-head" role="row"><b>帧</b><b>目标绝对压力</b><b>实际绝对压力</b><b>系统计算差值</b><b>当前判断</b></div>{pressureRows.map(row => <div className="measurement-frame" role="row" key={row.index}><b>{row.index}</b><label>目标绝对压力<input inputMode="decimal" readOnly={!manualRetest} value={row.target} onChange={event => setProtocolField(`final_target_${row.index}_hpa`, event.target.value)} /></label><label>实际绝对压力<input inputMode="decimal" readOnly={!manualRetest} value={row.actual} onChange={event => setProtocolField(`final_actual_${row.index}_hpa`, event.target.value)} /></label><span>{row.delta === null ? '—' : `${row.delta} hPa`}</span><span>{row.judgment}</span></div>)}</div>}</> : <div className="callout"><b>已引用最近一次有效处理后复检</b><p>直接恢复路径沿用 after_air_repair 三帧数据，不需要重复填写。</p>{priorRetest ? <small>引用记录：{String(((priorRetest.payload as Record<string, unknown>).protocol_fields as Record<string, string>)?.retest_run_id || priorRetest.id)}</small> : <small>服务端将在提交时校验可引用记录。</small>}</div>}{selectedFields.filter(field => ['symptom','p0299','repairs_rechecked','conflict'].includes(field.name)).map(field => <OutcomeButtons key={field.name} label={field.label} values={field.options} value={protocolFields[field.name]} onChange={value => setProtocolField(field.name, value)} />)}</section>}
      {choice !== null && !['CHK-07','CHK-11'].includes(checkId ?? '') && selectedFields.length > 0 && <fieldset className="guided-fields"><legend>补充实际观察</legend>{selectedFields.map(field => <label key={field.name}>{field.label}{field.kind === 'select' ? <select value={protocolFields[field.name] ?? ''} onChange={event => setProtocolField(field.name, event.target.value)}><option value="">请选择</option>{field.options.map(option => <option key={option} value={option}>{fieldLabel(option)}</option>)}</select> : <input inputMode={field.kind === 'decimal' ? 'decimal' : undefined} value={protocolFields[field.name] ?? ''} onChange={event => setProtocolField(field.name, event.target.value)} maxLength={500} />}</label>)}</fieldset>}
      {(candidate.input.kind === 'measurement' || candidate.input.kind === 'composite') && <fieldset><legend>测量值</legend>{(candidate.input.measurements ?? []).map(item => <div className="measurement-row" key={item.spec_id}><label>{item.quantity ?? '测量'}<input inputMode="decimal" value={measurements[item.spec_id]?.value ?? ''} onChange={e => setMeasurements(old => ({ ...old, [item.spec_id]: { value: e.target.value, unit: old[item.spec_id]?.unit ?? item.unit } }))} /></label><label>单位<select value={measurements[item.spec_id]?.unit ?? item.unit} onChange={e => setMeasurements(old => ({ ...old, [item.spec_id]: { value: old[item.spec_id]?.value ?? '', unit: e.target.value as MeasurementDraft['unit'] } }))}>{['C','F','Pa','kPa','bar','V','mV','ohm','kohm'].map(unit => <option key={unit}>{unit}</option>)}</select></label><small>{Object.entries(item.conditions).map(([k,v]) => `${k}=${v}`).join(' · ')}</small></div>)}</fieldset>}
    </>}
    <button type="submit" disabled={!body || submit.isPending}>{submit.isPending ? '正在提交…' : protocol?.decision === 'need_input' ? '补充观察并继续' : protocol ? '保存观察并进入下一步' : '保存观察并启动下一轮'}</button>
    {submit.error && <ErrorState error={submit.error} />}
  </form>;
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

function evidenceIdsIn(value: unknown): string[] {
  const found = new Set<string>();
  const visit = (item: unknown) => {
    if (Array.isArray(item)) return item.forEach(visit);
    if (!item || typeof item !== 'object') return;
    const record = item as Record<string, unknown>;
    if (typeof record.evidence_id === 'string') found.add(record.evidence_id);
    if (Array.isArray(record.evidence_refs)) record.evidence_refs.forEach(id => { if (typeof id === 'string') found.add(id); });
    Object.values(record).forEach(visit);
  };
  visit(value);
  return [...found];
}

export function AreaConclusion({ area, observations = [], onEvidence }: { area?: DiagnosisArea; observations?: ObservationView[]; onEvidence?: (ids: string[]) => void }) {
  if (!area?.conclusion) return <EmptyState title="本区域尚无结论卡">待完成检查后由服务端保守收尾。</EmptyState>;
  const card = area.conclusion;
  const terminal = (card.content as { protocol_terminal?: { decision?: string; terminal_code?: string; reason?: string; protocol_version?: string } }).protocol_terminal;
  const effective = observations.filter(item => item.effective);
  const evidenceIds = evidenceIdsIn(card.content);
  const fullFlow = ['3.0.0', '3.1.0'].includes(terminal?.protocol_version ?? '');
  if (fullFlow && terminal?.terminal_code === 'AREA_SUMMARY_DEMO_PASS') return <article className="conclusion-card completion-summary"><div className="badge-row"><StatusBadge value="本次 DKVB/P0299 保守模式演示已完成" tone="good" /></div><h3>实际经过的路径</h3><ol>{effective.map(item => <li key={item.id}>{observationSummary(item)}</li>)}</ol><h3>最终复检数据来源</h3><p>{effective.some(item => ((item.payload as Record<string, unknown>).protocol_fields as Record<string, string> | undefined)?.final_stage === 'after_control_setup') ? '控制设置后新建记录（after_control_setup）；处理后残余增压不足记录仍保留。' : '直接沿用处理后复检记录（after_air_repair）。'}</p><h3>保守边界</h3><ul><li>仅证明本合成演示数据满足冻结协议条件。</li><li>不能证明真实车辆已经修复或排除其他故障。</li><li>不能替代实车测试，也不自动生成正式最终报告。</li></ul><div className="actions"><a className="button-link" href="/history">返回历史病例</a><a className="button-link" href="#saved-observations">查看观察记录</a>{evidenceIds.length > 0 && onEvidence && <button type="button" className="secondary" onClick={() => onEvidence(evidenceIds)}>查看资料出处</button>}<a className="button-link" href="/workbench?scenario=dkvb-p0299">创建新的支持场景病例</a></div><details><summary>技术详情</summary><code>{terminal.terminal_code}</code><pre>{JSON.stringify(card.content, null, 2)}</pre></details></article>;
  if (terminal?.terminal_code === 'AREA_SUMMARY_DEMO_PASS') return <article className="conclusion-card completion-summary"><div className="badge-row"><StatusBadge value="本次增压空气系统演示复检已完成" tone="good" /></div><h3>已观察到</h3><ul>{effective.map(item => <li key={item.id}>{observationSummary(item)}</li>)}</ul><h3>本片段支持的判断</h3><p>当前演示数据满足冻结协议中的局部泄漏处理后复检条件。</p><h3>本片段不能证明</h3><ul><li>不能证明真实车辆已经修复。</li><li>不能排除其他增压控制故障。</li><li>不能替代实车测试。</li><li>不能生成正式最终报告。</li></ul><div className="actions"><a className="button-link" href="/history">返回历史病例</a><a className="button-link" href="#saved-observations">查看观察记录</a>{evidenceIds.length > 0 && onEvidence && <button type="button" className="secondary" onClick={() => onEvidence(evidenceIds)}>查看资料出处</button>}<a className="button-link" href="/workbench?scenario=dkvb-p0299">创建新的支持场景病例</a></div><details><summary>技术详情</summary><code>{terminal.terminal_code}</code><pre>{JSON.stringify(card.content, null, 2)}</pre></details></article>;
  return <article className="conclusion-card"><div className="badge-row"><StatusBadge value={terminal?.decision === 'area_summary' ? '演示路径已完成' : terminal?.decision === 'handoff' ? '已暂停，等待补充条件' : statusText(card.assessment)} tone={terminal?.decision === 'area_summary' ? 'good' : 'warn'} />{card.needs_review && <StatusBadge value="需要复核" tone="bad" />}</div><p>{terminal?.reason ?? (card.assessment === 'unknown' ? '现有资料不足，无法继续判断。已检查事实仍会保留；这不是确诊、排除或最终报告就绪。' : '仅显示服务端保存的区域结论。')}</p><details><summary>技术详情：依据摘要</summary>{terminal?.terminal_code && <code>{terminal.terminal_code}</code>}<pre>{JSON.stringify(card.content, null, 2)}</pre></details></article>;
}

export function CorrectionForm({ caseId, revision, epoch, observation, onCorrected }: {
  caseId: string; revision: number; epoch: number; observation: ObservationView;
  onCorrected: () => void | Promise<void>;
}) {
  const payload = observation.payload as Record<string, unknown>;
  const input = (observation.input_schema ?? null) as StepCandidate['input'] | null;
  const [open, setOpen] = useState(false);
  const [correctionReason, setCorrectionReason] = useState('');
  const [choice, setChoice] = useState<number | null>(typeof payload.choice_index === 'number' ? payload.choice_index : null);
  const [unavailableReason, setUnavailableReason] = useState(typeof payload.reason === 'string' ? payload.reason : '');
  const protocol = (observation.protocol ?? null) as ProtocolDecision | null;
  const originalProtocolFields = (payload.protocol_fields && typeof payload.protocol_fields === 'object' ? payload.protocol_fields : {}) as Record<string,string>;
  const [protocolFields, setProtocolFields] = useState<Record<string,string>>(originalProtocolFields);
  const originalMeasurements = Array.isArray(payload.measurements) ? payload.measurements as Array<Record<string, unknown>> : [];
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(originalMeasurements.map(x => [String(x.spec_id), String(x.value ?? '')])));
  const measurementsValid = !['measurement', 'composite'].includes(observation.kind) || (input?.measurements ?? []).every(item => validDecimal(values[item.spec_id] ?? ''));
  const key = useRef<{ fingerprint: string; value: string } | null>(null);
  const mutation = useMutation({ mutationFn: async () => {
    if (!observation.step_id || !correctionReason.trim()) throw new Error('请填写更正原因。');
    if (!measurementsValid) throw new Error('测量值必须是有限且受支持精度的十进制数。');
    const kind = observation.kind as CorrectObservation['kind'];
    const body: CorrectObservation = { expected_revision: revision, graph_epoch: epoch,
      step_id: observation.step_id, kind, correction_reason: correctionReason.trim(), measurements: [] };
    if (kind === 'unavailable') body.reason = unavailableReason.trim();
    if (kind === 'choice' || kind === 'composite') { if (choice === null) throw new Error('请选择更正后的观察。'); if (protocol?.options?.[choice]) body.option_id = protocol.options[choice].option_id; else body.choice_index = choice; body.conditions = observation.required_conditions ?? undefined; body.protocol_fields = protocolFields; }
    if (kind === 'measurement' || kind === 'composite') body.measurements = (input?.measurements ?? []).map(item => ({ spec_id: item.spec_id, value: values[item.spec_id] ?? '', unit: item.unit, conditions: item.conditions }));
    const fingerprint = JSON.stringify({ route: `/cases/${caseId}/observations/${observation.id}/correct`, caseId, observationId: observation.id, stepId: observation.step_id, revision, epoch, body });
    if (!key.current || key.current.fingerprint !== fingerprint) key.current = { fingerprint, value: idempotencyKey(`correct:${observation.id}`) };
    return apiClient.request<EnqueuedAction>(`/cases/${caseId}/observations/${observation.id}/correct`, { method: 'POST', body, idempotencyKey: key.current.value });
  }, onSuccess: () => { key.current = null; setOpen(false); void onCorrected(); }, onError: error => { if (error instanceof ApiError && error.status === 409) { key.current = null; void onCorrected(); } } });
  if (!observation.effective) return null;
  return <div className="correction-form"><button type="button" className="secondary" onClick={() => setOpen(value => !value)}>{open ? '取消更正' : '更正此观察'}</button>{open && <form onSubmit={event => { event.preventDefault(); mutation.mutate(); }}>
    {observation.kind === 'unavailable' && <label>更正后的无法完成原因<textarea value={unavailableReason} onChange={e => setUnavailableReason(e.target.value)} /></label>}
    {(observation.kind === 'choice' || observation.kind === 'composite') && <fieldset><legend>更正后的选择</legend>{(input?.choices ?? []).map((item, index) => <label className="choice-row" key={index}><input type="radio" checked={choice === index} onChange={() => { setChoice(index); setProtocolFields({}); }} />{item.text}</label>)}</fieldset>}
    {choice !== null && (protocol?.options?.[choice]?.fields ?? []).length > 0 && <fieldset><legend>更正后的结构化观察</legend>{(protocol?.options?.[choice]?.fields ?? []).map(field => <label key={field.name}>{field.label}<input value={protocolFields[field.name] ?? ''} onChange={event => setProtocolFields(old => ({ ...old, [field.name]: event.target.value }))} /></label>)}</fieldset>}
    {(observation.kind === 'measurement' || observation.kind === 'composite') && (input?.measurements ?? []).map(item => <label key={item.spec_id}>{item.quantity ?? '测量值'}（{item.unit}）<input inputMode="decimal" value={values[item.spec_id] ?? ''} onChange={e => setValues(old => ({ ...old, [item.spec_id]: e.target.value }))} /></label>)}
    <label>更正原因 *<textarea value={correctionReason} onChange={e => setCorrectionReason(e.target.value)} maxLength={1000} /></label><button type="submit" disabled={mutation.isPending || !measurementsValid}>{mutation.isPending ? '正在更正…' : '保存更正并重新分析'}</button>{mutation.error && <ErrorState error={mutation.error} />}
  </form>}</div>;
}

export function RunStatus({ caseId, epoch, runId, hasSavedObservation, onChange }: { caseId: string; epoch: number; runId: string; hasSavedObservation: boolean; onChange: () => Promise<void> }) {
  const client = useQueryClient();
  const [lastEvent, setLastEvent] = useState('正在连接任务事件');
  const [recoveryError, setRecoveryError] = useState<unknown>(null);
  const cancelKeys = useRef(new Map<string, string>());
  const query = useQuery({ queryKey: ['run', runId], queryFn: ({ signal }) => apiClient.request<RunSnapshot>(`/runs/${runId}`, { signal }), refetchInterval: false });
  useEffect(() => { cancelKeys.current.clear(); setRecoveryError(null); }, [caseId, epoch, runId]);
  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    const invalidate = async () => { await Promise.all([
      client.invalidateQueries({ queryKey: ['case', caseId] }), client.invalidateQueries({ queryKey: ['diagnosis', caseId] }),
      client.invalidateQueries({ queryKey: ['areas', caseId] }), client.invalidateQueries({ queryKey: ['observations', caseId] }),
      client.invalidateQueries({ queryKey: ['reports', caseId] }), client.invalidateQueries({ queryKey: ['report-gate', caseId] }),
      client.invalidateQueries({ queryKey: ['run', runId] }),
    ]); };
    void consumeRunEvents({ runId, signal: controller.signal, contextValid: () => alive,
      onEvent: async event => { if (!alive) return; setLastEvent(event.type === 'reset_required' ? '事件游标已重置，已重新读取' : event.type); await invalidate(); },
      onDisconnect: async () => { const state = await apiClient.request<RunSnapshot>(`/runs/${runId}`); await onChange(); return { terminal: terminal.has(state.status) }; },
      onRecoveryError: error => { if (alive) setRecoveryError(error); },
    }).catch(error => { if (alive) setRecoveryError(error); });
    return () => { alive = false; controller.abort(); };
  }, [caseId, epoch, runId, client, onChange]);
  const cancel = useMutation({ mutationFn: () => { const fingerprint = JSON.stringify({ route: `/runs/${runId}/cancel`, runId, body: {} }); let key = cancelKeys.current.get(fingerprint); if (!key) { key = idempotencyKey(`cancel:${runId}`); cancelKeys.current.set(fingerprint, key); } return apiClient.request<EnqueuedAction>(`/runs/${runId}/cancel`, { method: 'POST', idempotencyKey: key }); }, onSuccess: () => { cancelKeys.current.clear(); return onChange(); }, onError: error => { if (error instanceof ApiError && error.status === 409) { cancelKeys.current.clear(); void onChange(); } } });
  const explanation = query.data ? runExplanation(query.data, hasSavedObservation) : null;
  return <div className="run-status"><div><StatusBadge value={explanation?.conservative ? '资料不足' : query.data ? statusText(query.data.status) : '正在连接'} tone={explanation?.conservative ? 'warn' : query.data?.status === 'failed' ? 'bad' : query.data && terminal.has(query.data.status) ? 'good' : 'warn'} /><span>{explanation?.conservative ? '当前流程已保守停止' : lastEvent.startsWith('run.') ? statusText(lastEvent.slice(4)) : lastEvent}</span></div>{explanation && <div className={explanation.conservative ? 'run-explanation needs-input' : 'run-explanation'}><b>{codeText(explanation.code)}</b><ul><li>{explanation.conservative ? '处理结果' : '失败步骤'}：{explanation.stage}</li><li>{explanation.saved}</li>{!explanation.conservative && <li>{explanation.usage}</li>}<li>下一步：{explanation.recovery}</li></ul><details><summary>技术详情</summary><code>{explanation.code || 'UNAVAILABLE'}</code></details></div>}{query.data && ['queued','running','cancel_requested'].includes(query.data.status) && <button type="button" className="secondary" disabled={cancel.isPending} onClick={() => cancel.mutate()}>取消任务</button>}{recoveryError !== null && <ErrorState error={recoveryError} />}{query.error && <ErrorState error={query.error} />}{cancel.error && <ErrorState error={cancel.error} />}</div>;
}

export function FinalAdvice({ caseId, revision, gate }: { caseId: string; revision: number; gate: FinalReportGate | null }) {
  const client = useQueryClient();
  const keys = useRef(new Map<string, string>());
  const [reportRunId, setReportRunId] = useState<string | null>(null);
  const list = useQuery({ queryKey: ['reports', caseId], queryFn: ({ signal }) => apiClient.request<ReportList>(`/cases/${caseId}/reports`, { signal }) });
  useEffect(() => { if (!reportRunId) setReportRunId(list.data?.items.find(item => item.status === 'draft')?.run_id ?? null); }, [list.data, reportRunId]);
  useEffect(() => { keys.current.clear(); setReportRunId(null); }, [caseId]);
  const refreshReports = useCallback(async () => { await Promise.all([client.invalidateQueries({ queryKey: ['reports', caseId] }), client.invalidateQueries({ queryKey: ['report-gate', caseId] }), client.invalidateQueries({ queryKey: ['case', caseId] })]); }, [caseId, client]);
  const request = useMutation({ mutationFn: (kind: 'progress' | 'final') => { const body = { kind, expected_revision: revision }; const fingerprint = JSON.stringify({ route: `/cases/${caseId}/reports`, caseId, revision, body }); let key = keys.current.get(fingerprint); if (!key) { key = idempotencyKey(`report:${caseId}:${kind}:${revision}`); keys.current.set(fingerprint, key); } return apiClient.request<EnqueuedAction>(`/cases/${caseId}/reports`, { method: 'POST', body, idempotencyKey: key }); }, onSuccess: (result, kind) => { keys.current.delete(JSON.stringify({ route: `/cases/${caseId}/reports`, caseId, revision, body: { kind, expected_revision: revision } })); setReportRunId(result.run_id); void refreshReports(); }, onError: (error, kind) => { if (error instanceof ApiError && error.status === 409) keys.current.delete(JSON.stringify({ route: `/cases/${caseId}/reports`, caseId, revision, body: { kind, expected_revision: revision } })); } });
  return <section className="report-panel"><div className="actions"><button type="button" disabled={request.isPending} onClick={() => request.mutate('progress')}>生成进度报告</button><button type="button" disabled={request.isPending || !gate?.allowed} onClick={() => request.mutate('final')}>生成最终报告</button></div>
    {!gate?.allowed && <div className="callout"><b>最终报告未就绪</b><ul>{(gate?.blocking_items ?? []).map((x, i) => <li key={i}>{codeText((x as Record<string, unknown>).code)}</li>)}</ul><details><summary>技术详情</summary><ul>{(gate?.blocking_items ?? []).map((x, i) => <li key={i}>{String((x as Record<string, unknown>).code ?? 'GATE_UNAVAILABLE')}</li>)}</ul></details></div>}
    {request.error && <ErrorState error={request.error} />}{list.error && <ErrorState error={list.error} />}
    {reportRunId && <RunStatus caseId={caseId} epoch={gate?.graph_epoch ?? 0} runId={reportRunId} hasSavedObservation={false} onChange={refreshReports} />}
    <div className="report-list">{list.data?.items.map(report => <article key={report.id}><div className="badge-row"><StatusBadge value={report.kind} /><StatusBadge value={report.status} tone={report.status === 'current' ? 'good' : report.status === 'stale' ? 'bad' : 'warn'} /></div>{report.status === 'stale' && <p>该报告属于历史快照，当前事实已变化。</p>}<details><summary>查看报告内容</summary><pre>{JSON.stringify(report.content, null, 2)}</pre></details></article>)}</div>
  </section>;
}

export function stepFrom(view: DiagnosisView | undefined) {
  return view?.current_step ? asStepCandidate(view.current_step.candidate as Record<string, unknown>) : null;
}
