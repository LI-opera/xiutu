import type { CaseSnapshot } from '../../types';
import './workbench-v2-prototype.css';
import './workbench-v2-content.css';
import './formal-workbench-v2.css';

export { MatchedVehicleIntake as FormalWorkbenchV2IntakePage } from './MatchedVehicleIntake';

export function SavedVehicleProfile({ item, caseId, topicVersion, symptomCondition, safetyGate }: {
  item: CaseSnapshot;
  caseId: string;
  topicVersion: string;
  symptomCondition: string | null;
  safetyGate: string | null;
}) {
  return <section className="prototype-vehicle-basics formal-v2-profile-saved">
    <div className="prototype-vehicle-basics-heading"><div><p className="prototype-eyebrow">VEHICLE & INTAKE PROFILE</p><h2>车辆基础信息与接诊事实</h2></div><span>历史接诊快照 · 只读</span></div>
    <fieldset disabled style={{ border: 0, padding: 0, margin: 0 }}><div className="formal-v2-reference-grid">
      <label className="formal-v2-ref-model">车型<input readOnly value={item.vehicle.model} /></label>
      <label className="formal-v2-ref-engine">发动机代码<input readOnly value={item.vehicle.engine_code ?? ''} /></label>
      <label className="formal-v2-ref-complaint">主诉摘要<input readOnly value={item.fault_description} /></label>
      <label className="formal-v2-ref-condition">症状发生工况<select value={symptomCondition ?? ''} disabled><option value="">未记录</option><option value="acceleration">加速时</option><option value="high_load">高负荷时</option><option value="intermittent">间歇出现</option><option value="unknown">未知</option></select></label>
      <label className="formal-v2-ref-codes">当前读取的故障码<input readOnly value={item.fault_codes.join('、')} /></label>
      <label className="formal-v2-ref-safety">安全风险<select value={safetyGate ?? ''} disabled><option value="">未记录</option><option value="none">未发现/无</option><option value="caution">需要谨慎</option><option value="stop_now">立即停止检查</option><option value="unavailable">无法判断</option></select></label>
    </div></fieldset>
    <p className="prototype-generated-status">历史接诊信息已归档，仅供查看。</p>
    <details className="formal-v2-profile-technical"><summary>技术详情</summary><small>case_id {caseId} · revision {item.revision} · 专题 {topicVersion} · 年款 {item.vehicle.year ?? '未记录'} · 发动机系列 {item.vehicle.engine_family ?? '未记录'}</small></details>
  </section>;
}
