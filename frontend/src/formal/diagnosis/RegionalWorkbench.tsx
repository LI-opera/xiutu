import { Link } from 'react-router-dom';
import { StatusBadge } from '../components/States';
import type { FinalReportGate, WorkbenchArea, WorkbenchComponent, WorkbenchView } from './types';

const areaStatus: Record<WorkbenchArea['status'], string> = {
  locked: '未开放', available: '可以开始', current: '正在检查', waiting: '等待补充',
  abnormal: '存在异常', completed: '已完成', handed_off: '已交接',
};
const componentStatus: Record<WorkbenchComponent['status'], string> = {
  locked: '未开放', not_started: '未开始', current: '当前', completed: '已完成',
  needs_review: '需要重新确认', not_applicable: '不适用',
};

export function CaseHeader({ view }: { view: WorkbenchView }) {
  return <header className="regional-case-header"><div><p className="kicker">R1 · CONSERVATIVE WORKBENCH</p><h1>{view.case_summary.title}</h1><p className="regional-case-name">{view.case_summary.fault_description}</p><div className="badge-row"><StatusBadge value="保守模式" /><StatusBadge value="synthetic DEMO" tone="warn" /><StatusBadge value={view.case_summary.status_label} tone={view.synthesis.status === 'demo_complete' ? 'good' : 'warn'} /></div></div><div className="regional-header-actions"><Link className="button-link secondary" to="/history">返回病例列表</Link><details><summary>技术详情</summary><small>CASE {view.case_summary.id}</small><small>资料可正式使用：{view.case_summary.formal_usable ? '是' : '否'}</small></details></div></header>;
}

const shown = (value: unknown) => value === null || value === undefined || value === '' ? '未提供' : String(value);
export function VehicleFaultSummary({ view }: { view: WorkbenchView }) {
  const vehicle = view.case_summary.vehicle;
  const context = view.case_summary.symptom_context;
  return <section className="vehicle-fault-panel"><div className="section-heading"><div><p className="kicker">病例基础信息</p><h2>车辆与故障</h2></div><Link className="text-link" to="/workbench?scenario=dkvb-p0299">身份信息有误，重新建立病例</Link></div><dl className="vehicle-fault-grid"><div><dt>车型</dt><dd>{shown(vehicle.model)}</dd></div><div><dt>VIN</dt><dd>{shown(vehicle.vin)}</dd></div><div><dt>年款</dt><dd>{shown(vehicle.year)}</dd></div><div><dt>发动机</dt><dd>{shown(vehicle.engine_family)} / {shown(vehicle.engine_code)}</dd></div><div><dt>故障码</dt><dd>{view.case_summary.fault_codes.join('、') || '未提供'}</dd></div><div className="wide"><dt>故障描述</dt><dd>{shown(view.case_summary.fault_description)}</dd></div><div><dt>症状条件</dt><dd>{shown(context.symptom_conditions)}</dd></div><div><dt>近期维修</dt><dd>{shown(context.recent_pipe_work)}</dd></div><div><dt>其他故障码</dt><dd>{shown(context.other_codes)}</dd></div></dl><details><summary>查看 intake 来源</summary><pre>{JSON.stringify({ vehicle, fault_description: view.case_summary.fault_description, fault_codes: view.case_summary.fault_codes }, null, 2)}</pre></details></section>;
}

export function DiagnosticAreaGrid({ areas, selectedId, newlyCompleted, onSelect }: { areas: WorkbenchArea[]; selectedId: string; newlyCompleted: Set<string>; onSelect: (id: string) => void }) {
  return <section className="regional-area-section"><div className="section-heading"><div><p className="kicker">诊断问题区域</p><h2>按冻结协议建议顺序排查</h2></div><p>优先级来自故障码、有效观察、协议顺序与前置条件，不表示故障概率。</p></div><div className="diagnostic-area-grid">{areas.map(area => <button type="button" key={area.area_id} onClick={() => onSelect(area.area_id)} aria-pressed={selectedId === area.area_id} className={`diagnostic-area-card ${selectedId === area.area_id ? 'selected' : ''} status-${area.status} ${newlyCompleted.has(area.area_id) ? 'just-completed' : ''}`}><span className="area-priority">建议优先级 {area.priority}</span><span className="area-title">{area.status === 'completed' && <span className="completion-check" aria-label="已完成">✓</span>}{area.title}</span><span className="area-progress">已完成 {area.completed_checks} / {area.required_checks}</span><span className="area-state">{areaStatus[area.status]}{area.has_abnormality ? ' · 已记录异常' : ''}</span><small>{area.available ? area.priority_reason : area.locked_reason}</small></button>)}</div></section>;
}

export function ComponentNavigator({ area, selectedId, onSelect }: { area: WorkbenchArea; selectedId: string; onSelect: (id: string) => void }) {
  return <nav className="component-navigator" aria-label={`${area.title}部件与环节`}><p className="kicker">当前区域</p><h3>{area.title}</h3><p>{area.priority_reason}</p><div className="component-list">{area.components.map(component => <button type="button" key={component.component_id} aria-pressed={selectedId === component.component_id} onClick={() => onSelect(component.component_id)} className={selectedId === component.component_id ? 'selected' : ''}><span>{component.status === 'completed' ? '✓ ' : ''}{component.title}</span><small>{componentStatus[component.status]}</small></button>)}</div></nav>;
}

export function ComponentActionPreview({ component, isCurrent, onReturn }: { component: WorkbenchComponent; isCurrent: boolean; onReturn: () => void }) {
  return <section className="component-action-panel"><div className="section-heading"><div><p className="kicker">部件与逐项检查</p><h2>{component.title}</h2></div>{!isCurrent && <button type="button" className="secondary" onClick={onReturn}>查看归档时的任务</button>}</div><ol className="action-sequence">{component.actions.map(action => <li key={action.check_id} className={`action-${action.status}`}><span>{action.status === 'completed' ? '✓' : action.status === 'current' ? '→' : '·'}</span><div><b>{action.title}</b><small>{componentStatus[action.status]}</small></div></li>)}</ol>{!isCurrent && <p className="callout">这里是历史检查记录或预览，不能继续提交。</p>}</section>;
}

const List = ({ items, empty }: { items: string[]; empty: string }) => items.length ? <ul>{items.map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul> : <p className="muted">{empty}</p>;
export function CaseSynthesisPanel({ view, gate }: { view: WorkbenchView; gate: FinalReportGate | null }) {
  const complete = view.synthesis.can_generate_demo_summary;
  return <section className={`case-synthesis-panel ${complete ? 'complete' : ''}`}><div className="section-heading"><div><p className="kicker">综合分析与建议流程</p><h2>历史诊断总结</h2></div><StatusBadge value="历史病例 · 只读" tone="warn" /></div><div className="synthesis-grid"><article><h3>归档时已确认</h3><List items={view.synthesis.confirmed_facts} empty="尚无用户观察。" /></article><article><h3>已处理问题</h3><List items={view.synthesis.handled_issues} empty="尚无已完成处理。" /></article><article><h3>仍存在的异常</h3><List items={view.synthesis.remaining_abnormalities} empty="当前没有新增未解决异常。" /></article><article><h3>归档时待确认</h3><List items={view.synthesis.unchecked_items} empty="冻结协议范围内没有待检查项目。" /></article><article className="wide"><h3>归档时的下一步建议</h3><List items={view.synthesis.next_recommendations} empty="归档时没有下一步建议。" /></article></div>{complete && <article className="demo-process"><h3>演示维修与复检流程</h3><ol><li>复核已定位问题和保存位置。</li><li>按适用装配要求完成处理。</li><li>重新检查局部泄漏并取得新的负荷压力记录。</li><li>确认 P0299、原症状和未解决冲突。</li><li>若仍异常，转入调节方向或保守交接。</li></ol></article>}<div className="scope-warning"><b>范围限制</b><span>synthetic/DEMO；不代表实车维修验证，不构成正式换件建议。</span><span>正式最终报告：{gate?.allowed ? '门禁允许' : '仍不可生成'}</span></div></section>;
}
