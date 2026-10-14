import type { DiagnosisArea, DiagnosisView, ObservationView, RunSnapshot } from './types';

const CODE_TEXT: Record<string, string> = {
  CASE_NEEDS_REVIEW: '病例存在需要人工核对的内容',
  AREA_UNFINISHED: '尚有诊断区域未完成',
  CONCLUSION_MISSING: '尚未形成可支持的结论',
  MODEL_PRICE_UNVERIFIED: '体验服务加载的模型配置未通过已知模型检查',
  DIAGNOSIS_PROPOSAL_NEEDS_INPUT: '现有资料不足，无法继续形成有依据的检查',
  AREA_NEEDS_INPUT: '现有资料不足，无法生成下一项有依据的检查',
  MODEL_TURN_TIMEOUT: '本轮诊断已超过允许时间',
  TOOL_TURN_BUDGET_EXHAUSTED: '本轮只读资料工具次数已用完',
  MODEL_CALL_LIMIT_EXCEEDED: '本轮模型请求次数已用完',
  CHECKPOINT_QUARANTINED: '该病例需要管理员核对恢复状态',
  SOURCE_INVALID: '检查所引用的资料已失效或被撤销',
  SCOPE_NOT_MATCHED: '当前资料与病例适配信息不足',
};

export const codeText = (value: unknown) => {
  const code = typeof value === 'string' ? value : '';
  return CODE_TEXT[code] ?? '服务端门禁尚未满足';
};

export const statusText = (value: string) => ({
  draft: '尚未启动', queued: '等待处理', running: '正在处理',
  cancel_requested: '正在取消', cancelled: '已取消', failed: '运行失败',
  waiting_input: '等待填写观察', succeeded: '已完成', superseded: '已由新任务替代',
  needs_review: '需要人工核对', active: '当前区域',
  current: '当前区域', pending: '待生成', completed: '已完成', stale: '事实已变化',
  retired: '已合并', unknown: '资料不足', supported: '有依据支持', ruled_out: '有依据排除',
}[value] ?? value);

export type FlowPresentation = { title: string; description: string; action: string };

export const isConservativeStop = (code: unknown) => ['AREA_NEEDS_INPUT', 'DIAGNOSIS_PROPOSAL_NEEDS_INPUT'].includes(typeof code === 'string' ? code : '');

export function flowPresentation(input: {
  caseStatus: string;
  currentStep: boolean;
  canStart?: boolean;
  terminal?: { decision?: string; terminal_code?: string; reason?: string } | null;
  latestRun?: { status: string; error_code?: string | null; phase?: string } | null;
  areas: DiagnosisArea[];
}): FlowPresentation {
  const { caseStatus, currentStep, latestRun, areas, terminal } = input;
  if (terminal?.terminal_code === 'AREA_SUMMARY_DEMO_PASS') return { title: '本次增压空气系统演示复检已完成', description: '最终演示复检条件已满足；这是合成演示结果，不代表实车已经修复。', action: '查看已保存事实，或返回病例列表' };
  if (terminal?.decision === 'handoff') return { title: '病例已暂停，等待补充检查条件', description: terminal.reason ?? '当前检查无法继续，已保存的观察不会丢失。', action: '查看已保存观察，补充条件后重新开始' };
  if (currentStep) return { title: '等待填写观察', description: '阅读当前检查和依据，选择与你实际看到的情况一致的结果。', action: '前往“当前检查与观察”填写并保存' };
  if (latestRun && ['queued', 'running', 'cancel_requested'].includes(latestRun.status)) return { title: '正在生成下一步', description: '观察已经保存，服务端正在读取冻结资料并校验下一步。', action: '请保持页面打开；任务完成后会自动刷新' };
  if (latestRun?.status === 'failed' && isConservativeStop(latestRun.error_code)) return { title: '资料不足，暂时无法继续', description: '你的观察已保存。现有资料不足以支持下一项检查，系统没有编造检查或维修结论。', action: '可查看已保存观察和依据，或生成进度报告了解缺项' };
  if (latestRun?.status === 'failed') return { title: '本次运行无法继续', description: codeText(latestRun.error_code), action: '查看已保存事实，或从支持场景重新开始' };
  const unknown = areas.some(area => area.conclusion?.assessment === 'unknown');
  if (unknown || caseStatus === 'needs_review') return { title: '资料不足', description: '现有资料只能保守待补，不能据此确诊、排除或建议换件。', action: '查看区域卡中的缺项，或生成进度报告' };
  if (caseStatus === 'draft' && input.canStart) return { title: '等待检查', description: '病例已建立，尚未生成第一项检查。', action: '点击“开始诊断”' };
  if (caseStatus === 'draft') return { title: '当前缺少匹配资料，暂时不能继续', description: '这个历史病例没有可启动的受控资料，系统不会创建空任务。', action: '返回病例列表，或从支持场景重新开始' };
  if (caseStatus === 'completed') return { title: '已完成', description: '服务端已完成当前限定流程。', action: '查看区域结论与报告门禁' };
  return { title: '等待检查', description: '当前没有待填写的检查。', action: '查看区域状态和任务详情' };
}

export function runExplanation(run: RunSnapshot, hasSavedObservation: boolean) {
  const code = typeof run.error?.code === 'string' ? run.error.code : '';
  if (run.status !== 'failed') return null;
  const conservative = isConservativeStop(code);
  return {
    conservative,
    stage: conservative ? '现有资料不足，未生成下一项检查' : '生成并校验下一步检查',
    saved: hasSavedObservation ? '用户填写的观察已经保存，不会因本次处理结果丢失。' : '本轮没有可确认的已保存观察。',
    usage: code === 'MODEL_PRICE_UNVERIFIED'
      ? '模型请求在发送前被拒绝，没有模型 usage。'
      : Object.keys(run.usage ?? {}).length ? '服务端记录了本轮用量；计量记录不是平台账单。' : '页面无法确认本轮费用状态，请管理员查看受限计量记录。',
    recovery: code === 'MODEL_PRICE_UNVERIFIED'
      ? '需要管理员修正已知模型配置；不要反复提交同一观察。'
      : conservative
        ? '无需重复提交同一观察。当前只能保守待补；可查看依据或生成进度报告。'
        : '请保留 trace 信息并联系管理员；现有事实仍可读取。',
    code,
  };
}
export function observationSummary(observation: ObservationView) {
  const payload = observation.payload as Record<string, unknown>;
  const fields = (payload.protocol_fields && typeof payload.protocol_fields === 'object' ? payload.protocol_fields : {}) as Record<string, string>;
  const human = (value: string | undefined) => ({ visual: '目视', touch: '触摸', leak_spray: '检漏喷剂', ultrasound: '超声设备', not_found: '未发现', localized: '已定位', inconclusive: '无法确定', absent: '未出现', present: '仍存在', completed: '已完成', incomplete: '未完成', none: '无' }[value ?? ''] ?? value ?? '未记录');
  const schema = observation.input_schema as { choices?: Array<{ text?: string }>; measurements?: Array<{ spec_id: string; quantity?: string; unit: string }> } | null;
  if (observation.kind === 'intake_snapshot') return '系统接诊事实：病例创建页已冻结车辆、故障描述、故障码、模式与 synthetic 边界';
  if (observation.kind === 'unavailable') return `无法完成：${String(payload.reason ?? '未填写原因')}`;
  if (payload.check_id === 'CHK-00') return '接车确认：已确认 synthetic 演示边界，不形成维修结论';
  if (payload.check_id === 'CHK-01') return `接车信息：P0299；近期管路作业${human(fields.recent_pipe_work)}${fields.other_codes ? `；其他故障码 ${fields.other_codes}` : ''}`;
  if (payload.check_id === 'CHK-02') return `静态可信度：${String(payload.option_label ?? '已记录')} ${fields.ambient_hpa ? `环境 ${fields.ambient_hpa} / G31 ${fields.g31_static_hpa} hPa absolute` : ''}`;
  if (payload.check_id === 'CHK-03') return `负荷记录：${fields.measurement_run_id ?? '同次记录'}；三帧 hPa absolute 已由冻结协议判断`;
  if (payload.check_id === 'CHK-04') return `空气路径外观：${String(payload.option_label ?? '已记录')}${fields.location ? `；位置 ${fields.location}` : ''}`;
  if (payload.check_id === 'CHK-05' || payload.check_id === 'CHK-05-SUPPLEMENT') return `${String(payload.option_label ?? '局部泄漏观察')} ${fields.leak_object_id ? `对象：${fields.leak_object_id}；` : ''}${fields.leak_location ? `位置：${fields.leak_location}；` : ''}${fields.evidence_kind ? `依据：${human(fields.evidence_kind)}` : ''}`.trim();
  if (payload.check_id === 'CHK-06') return `${String(payload.option_label ?? '模拟处理记录')} ${fields.repair_object ? `对象：${fields.repair_object}；` : ''}${fields.repair_action ? `动作：${fields.repair_action}` : fields.pending_reason ? `原因：${fields.pending_reason}` : ''}`.trim();
  if (payload.check_id === 'CHK-07') return `处理后复检：局部泄漏${human(fields.leak_result)}；原症状${human(fields.symptom)}；三帧数据已由冻结协议判断`;
  if (payload.check_id === 'CHK-08') return `调节机构观察：${String(payload.option_label ?? '已记录')}；插头${human(fields.connector_status)}；连接机构${human(fields.linkage_status)}`;
  if (payload.check_id === 'CHK-09') return `受控执行：${String(payload.option_label ?? '已记录')}`;
  if (payload.check_id === 'CHK-10') return '保守交接：已查看当前未解决问题与所需补充条件';
  if (payload.check_id === 'CHK-11') return `最终演示确认（${fields.final_stage ?? 'legacy'}）：原症状${human(fields.symptom)}；P0299 ${human(fields.p0299)}；处理复核${human(fields.repairs_rechecked)}；未解决冲突${human(fields.conflict)}`;
  const pieces: string[] = [];
  if (typeof payload.choice_index === 'number') pieces.push(schema?.choices?.[payload.choice_index]?.text ?? `选择 ${payload.choice_index + 1}`);
  if (Array.isArray(payload.measurements)) for (const raw of payload.measurements as Array<Record<string, unknown>>) {
    const item = schema?.measurements?.find(x => x.spec_id === raw.spec_id);
    pieces.push(`${item?.quantity ?? '测量值'}：${String(raw.value ?? '')} ${String(raw.unit ?? item?.unit ?? '')}`.trim());
  }
  return pieces.join('；') || '已保存观察';
}

export function latestRun(view: DiagnosisView) { return view.recent_runs?.[0] ?? null; }
