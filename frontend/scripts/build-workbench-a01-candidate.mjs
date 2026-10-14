// One-time Stage A materialization. The generated candidate JSON is the sole
// authority for later review; neither this script nor the V2 prototype is a
// runtime topic source. Never run export-workbench-v2-topic.mjs for this task.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const reference = 'E:/Work/v4-double/docs/参考/专题资料包/探岳维修资料1';
const baseline = JSON.parse(fs.readFileSync(path.join(root, 'backend/app/topics/dkvb_p0299_v2.json'), 'utf8'));
const output = path.join(root, 'backend/app/topics/candidates/tanyue-dkvb-p0299-a01-candidate.json');
if (fs.existsSync(output)) {
  const old = JSON.parse(fs.readFileSync(output, 'utf8'));
  if (old.schema_version !== 'workbench-topic-candidate/1' || old.version !== '2.1.0-a01-candidate')
    throw new Error(`Refusing to overwrite a different candidate: ${output}`);
}

const sourceIds = {
  M01: 'SRC-ID-DKVB', M02: 'SRC-CHARGE-AIR', M03: 'SRC-CHARGE-AIR', M04: 'SRC-CHARGE-AIR',
  M05: 'SRC-CHARGE-AIR', M06: 'SRC-CHARGE-AIR', M07: 'SRC-TURBO', M08: 'SRC-AIRFILTER',
  M09: 'SRC-FUEL', M10: 'SRC-IGNITION', M11: 'SRC-EXHAUST',
  E01: 'SRC-WIRING-DKVB-70', E02: 'SRC-WIRING-DKVB-70', E03: 'SRC-WIRING-DKVB-70',
  E04: 'SRC-WIRING-DKVB-70', E05: 'SRC-WIRING-DKVB-70',
  D01: 'EDITORIAL_DEMO', D02: 'EDITORIAL_DEMO', D03: 'EDITORIAL_DEMO',
};
const cardLong = {
  'intake-identity': [1], 'intake-dtcs': [1], 'intake-history': [1],
  'air-intake': [1], 'air-hose': [1], 'air-connector': [2], 'air-intercooler': [1], 'air-leak-test': [3],
  'pressure-static': [4, 5, 6], 'pressure-g31': [4], 'pressure-frame12': [6], 'pressure-frame3': [6], 'pressure-request': [6],
  'act-v465': [7], 'act-v465-response': [7], 'act-linkage': [7], 'act-n249': [8], 'act-setting': [7],
  'turbo-external': [9], 'turbo-fluids': [9], 'turbo-mechanical': [9], 'turbo-noise': [9], 'turbo-review': [9],
  'x-misfire': [10], 'x-ignition': [10], 'x-spark': [10], 'x-fuel-dtc': [11], 'x-fuel': [11], 'x-exhaust': [12], 'x-review': [10, 11, 12],
  'ret-repair': [13], 'ret-retest': [14], 'ret-symptom': [14], 'ret-outcome': [14],
};
const longText = fs.readFileSync(path.join(reference, '09-网页长内容卡-v2.md'), 'utf8');
const longCards = longText.split(/(?=^## 卡\d+ )/m).slice(1).map(section => {
  const [, number, title, markdown] = section.match(/^## 卡(\d+) ([^\r\n]+)\r?\n([\s\S]*)$/);
  const imageFiles = [...markdown.matchAll(/!\[[^\]]*\]\((assets\/[^)]+)\)/g)].map(m => m[1]);
  const imageAssetIds = imageFiles.map(file => baseline.assets.find(asset => asset.file.endsWith(file.slice('assets/'.length)))?.id);
  if (imageAssetIds.some(id => !id)) throw new Error(`Long card ${number} has unindexed image`);
  return { id: `LC-${number.padStart(2, '0')}`, title, markdown: markdown.trim(),
    image_asset_ids: imageAssetIds, source_document: '09-网页长内容卡-v2.md' };
});
if (longCards.length !== 14) throw new Error(`Expected 14 long cards, got ${longCards.length}`);

const register = fs.readFileSync(path.join(reference, 'sources-register.md'), 'utf8');
const originalRoot = 'E:/BaiduNetdiskDownload/M164/06大众车系/大众车系/28探岳/2019一汽大众探岳（探岳GTE）';
const sources = [];
for (const line of register.split(/\r?\n/)) {
  if (!/^\| (SRC-|WEB-)/.test(line)) continue;
  const cells = line.split('|').slice(1, -1).map(x => x.trim());
  const id = cells[0];
  const originalFile = id.startsWith('SRC-') ? path.join(originalRoot, cells[1].replaceAll('`','')) : null;
  sources.push({ id, kind: originalFile ? 'local_manual' : 'generic_web_register_only',
    citation: cells[1], pages_or_use: cells[2], scope_or_limit: cells[3], original_file: originalFile,
    register_path: 'E:/Work/v4-double/docs/参考/专题资料包/探岳维修资料1/sources-register.md',
    verified_in_this_task: false });
}
sources.push({ id: 'EDITORIAL_DEMO', kind: 'editorial', citation: '专题包编辑性演示内容', pages_or_use: '07/08/09 与已确认网页',
  scope_or_limit: '不是厂家故障树、阈值或实车确诊', register_path: 'E:/Work/v4-double/docs/参考/专题资料包/探岳维修资料1/sources-register.md', verified_in_this_task: true });
sources.push({ id: 'SAFETY_BOUNDARY', kind: 'safety', citation: '专题包保守安全边界', pages_or_use: '00/09',
  scope_or_limit: '安全条件不足时停止或交接', register_path: 'E:/Work/v4-double/docs/参考/专题资料包/探岳维修资料1/00-专题知识包总规范-v2.md', verified_in_this_task: true });

const derived = new Map([
  ['PRS-04', { rule_id: 'D-STATIC-CONSISTENCY', depends_on: ['PRS-01','PRS-02','PRS-03'],
    rationale: '仅同一熄火静态采集批次、hPa absolute、三项已保存且均为有效数值时计算 max-min；30 hPa 为演示带宽。否则输出 unavailable，不从草稿或默认值计算。',
    decision_table: [
      { output_option_id: 'unavailable', predicate_id: 'missing_or_invalid_saved_same_batch_absolute_hpa' },
      { output_option_id: 'consistent', predicate_id: 'all_three_max_minus_min_le_30' },
      { output_option_id: 'g31_outlier', predicate_id: 'abs_g31_minus_ambient_gt_30_and_abs_g71_minus_ambient_le_30' },
      { output_option_id: 'g71_outlier', predicate_id: 'abs_g71_minus_ambient_gt_30_and_abs_g31_minus_ambient_le_30' },
      { output_option_id: 'multiple_outliers', predicate_id: 'saved_valid_but_otherwise_not_consistent' },
    ],
    thresholds: [{ id: 'static_delta_max', value: 30, unit: 'hPa', source_id: 'EDITORIAL_DEMO' }] }],
  ['PRS-11', { rule_id: 'D-PRESSURE-TREND', depends_on: ['PRS-07','PRS-08','PRS-09','PRS-10'],
    rationale: '三帧同采集批次，目标和实际均为 hPa absolute；转速、负荷、挡位、驾驶请求和时间条件经实际记录确认可比后才分类。任何帧缺失/无法取得/不可比输出 unreliable；250/150 hPa 仅演示阈值。',
    decision_table: [
      { output_option_id: 'unreliable', predicate_id: 'missing_invalid_or_incomparable_saved_frames' },
      { output_option_id: 'tracks_target', predicate_id: 'three_abs_target_minus_actual_le_150' },
      { output_option_id: 'persistent_underboost', predicate_id: 'three_target_minus_actual_gt_250' },
      { output_option_id: 'intermittent_drop', predicate_id: 'at_least_one_gap_gt_250_and_one_abs_gap_le_150' },
      { output_option_id: null, predicate_id: 'otherwise_not_classified_needs_more_data', boundary: 'overshoot is listed in 07 but has no documented numeric criterion; do not invent one or auto-select it' },
    ],
    thresholds: [{ id: 'persistent_gap', value: 250, unit: 'hPa', source_id: 'EDITORIAL_DEMO' }, { id: 'follow_gap_max', value: 150, unit: 'hPa', source_id: 'EDITORIAL_DEMO' }] }],
  ['TUR-09', { rule_id: 'D-TURBO-INDEPENDENT-EVIDENCE', depends_on: ['TUR-01','TUR-02','TUR-03','TUR-04','TUR-05','TUR-06','TUR-07','TUR-08','PRS-11'],
    rationale: '按外部损伤/连接、油液、机械活动、负荷异响烟雾、可信持续低增压等独立证据类别去重；同一现象的两个异常选项只算一类。冲突或不足时不得输出本体损坏/换件结论。',
    evidence_classes: [
      { id: 'external_structure_connection', question_ids: ['TUR-01','TUR-02','TUR-05'] },
      { id: 'external_fluids', question_ids: ['TUR-03','TUR-04'] },
      { id: 'mechanical_movement', question_ids: ['TUR-06'] },
      { id: 'load_noise_smoke', question_ids: ['TUR-07','TUR-08'] },
      { id: 'credible_pressure_deficit', question_ids: ['PRS-11'] },
    ],
    decision_table: [
      { output_option_id: 'conflict', predicate_id: 'current_saved_evidence_contradictory' },
      { output_option_id: 'no_support', predicate_id: 'zero_qualified_independent_classes' },
      { output_option_id: 'weak_support', predicate_id: 'one_qualified_independent_class' },
      { output_option_id: 'multiple_supporting_facts', predicate_id: 'two_or_more_qualified_independent_classes', boundary: 'professional testing only; no turbo replacement verdict' },
    ] }],
  ['X-13', { rule_id: 'D-CROSS-SYSTEM-DIRECTION', depends_on: ['X-01','X-02','X-03','X-04','X-05','X-06','X-07','X-08','X-09','X-10','X-11','X-12'],
    rationale: '失火码与可控对调随件转移、燃油码与同工况负荷下持续落后等为支持链；单个代码/外观不形成换件判断，多方向同时成立输出 multiple。',
    decision_table: [
      { output_option_id: 'ignition', predicate_id: 'saved_misfire_id_and_controlled_swap_follows_part' },
      { output_option_id: 'fuel', predicate_id: 'saved_fuel_dtc_and_comparable_load_pressure_persistently_lags' },
      { output_option_id: 'exhaust', predicate_id: 'saved_exhaust_specific_clue', boundary: 'direction only, no backpressure threshold or blocked-catalyst verdict' },
      { output_option_id: 'intake_control', predicate_id: 'saved_X11_or_X12_control_specific_clue', boundary: 'direction only' },
      { output_option_id: 'multiple', predicate_id: 'two_or_more_supported_directions' },
      { output_option_id: 'none', predicate_id: 'no_supported_direction' },
    ] }],
  ['RET-07', { rule_id: 'D-RETEST-GAPS', depends_on: ['RET-01','RET-02','RET-03','RET-04','RET-05','RET-06'],
    rationale: '只评价已开启的处理后复检轮次的缺项；未知、未检查、无法取得不等于正常。',
    decision_table: [
      { output_option_id: null, predicate_id: 'no_post_repair_round_yet' },
      { output_option_id: 'critical', predicate_id: 'new_batch_or_comparability_or_safety_or_code_or_symptom_missing' },
      { output_option_id: 'minor', predicate_id: 'only_noncritical_applicable_detail_missing' },
      { output_option_id: 'none', predicate_id: 'all_applicable_retest_requirements_saved' },
    ] }],
  ['RET-08', { rule_id: 'D-RETEST-OUTCOME', depends_on: ['RET-01','RET-02','RET-03','RET-04','RET-05','RET-06','RET-07'],
    rationale: '必须比较新的复检批次与处理前事实；故障码复现、工况不可比或关键缺项时不得输出通过。最终正式报告仍由原报告门禁决定。',
    decision_table: [
      { output_option_id: null, predicate_id: 'no_actual_repair_and_new_retest_round' },
      { output_option_id: 'safety_stop', predicate_id: 'current_saved_safety_stop' },
      { output_option_id: 'handoff_unavailable', predicate_id: 'critical_gap_or_unavailable_or_not_comparable' },
      { output_option_id: 'demo_pass', predicate_id: 'new_comparable_batch_recovered_and_symptom_resolved_and_dtc_not_returned_and_no_critical_gap', boundary: 'synthetic demo only; formal report gate independent' },
      { output_option_id: 'partial_improvement', predicate_id: 'new_comparable_batch_improved_but_not_fully_resolved' },
      { output_option_id: 'continue_boost', predicate_id: 'new_comparable_batch_still_underboost' },
      { output_option_id: 'cross_system', predicate_id: 'boost_recovered_but_original_symptom_remains' },
    ] }],
]);
const multi = new Set(['IN-07','RET-01']);
const conditional = new Map([
  ['AIR-14', { refs: ['AIR-13'], when: 'AIR-13=available|alternative_safe_tool，设备受控且安全条件已确认；超过0.5 bar禁止提交完成。', kind: 'controlled_leak_test' }],
  ['AIR-15', { refs: ['AIR-13','AIR-14'], when: '已执行合规检漏，或记录其它可定位证据及方法；无法执行可记录 unavailable。', kind: 'leak_localization' }],
  ['AIR-16', { refs: ['AIR-15'], when: '已有定位观察；油雾/痕迹单独不能升级为已定位泄漏。', kind: 'evidence_grading' }],
  ['ACT-03', { refs: ['IN-08'], when: '无 stop_now，具备合适工具/操作者并确认输出测试安全条件；不具备时只记 test_rejected/unavailable。', kind: 'output_test' }],
  ['ACT-05', { refs: ['IN-08'], when: '仅安全可见活动，禁止拆解或强制动作；否则 not_testable。', kind: 'physical_test' }],
  ['ACT-09', { refs: ['ACT-08'], when: 'ACT-08=ready 且操作者确认适用工具/条件；本包只演示，不提供厂家基本设置编号。', kind: 'basic_setting' }],
  ['ACT-10', { refs: ['ACT-09'], when: 'ACT-09=completed 后的新采集批次，同工况比较；属于设置后诊断复核，不是首次检查必需项。', kind: 'after_setting_measurement' }],
  ['TUR-06', { refs: ['IN-08'], when: '仅外部安全可接近；不安全时 not_accessible。', kind: 'external_physical_test' }],
  ['X-05', { refs: ['X-01'], when: '有可追踪的失火对象、合适操作者和安全条件；否则 not_performed/unavailable。', kind: 'controlled_swap' }],
]);
const stages = {
  S0: 'intake', S1: 'diagnostic_observation', S2: 'diagnostic_observation',
  S3: 'diagnostic_observation', S4: 'diagnostic_observation', S5: 'diagnostic_observation',
  S6: 'post_repair_retest',
};
const issueUnknown = new Set(['unknown','unavailable','not_visible','not_performed','inconclusive','signal_missing','not_testable','not_accessible','not_available','data_missing','test_incomplete','not_comparable','unreliable','mark_unreadable']);
const optionLabelFixes = {
  'TUR-08/other': '其他烟雾或类型不明',
  'AIR-15/multiple': '多处泄漏响应',
  'X-06/multiple': '多类燃油相关故障码',
};
const questionById = new Map(baseline.questions.map(q => [q.id, q]));
const cards = baseline.cards.map(card => ({ ...card, long_card_ids: (cardLong[card.id] ?? []).map(n => `LC-${String(n).padStart(2, '0')}`) }));
const cardById = new Map(cards.map(c => [c.id, c]));
const questions = baseline.questions.map(q => {
  const card = cardById.get(q.cardId);
  const assets = [...new Set([...card.assetIds, ...q.assetIds])];
  const sourceRefs = [...new Set(['EDITORIAL_DEMO', ...assets.map(id => sourceIds[id]), ...(q.stage === 'S4' ? ['SAFETY_BOUNDARY'] : [])])];
  const decision = derived.get(q.id);
  const operation = conditional.get(q.id);
  const phase = q.id === 'RET-01' || q.id === 'RET-02' ? 'actual_repair' :
    q.id === 'ACT-10' ? 'after_setting_recheck' : stages[q.stage];
  const answerKind = decision ? 'automatic_derived' : operation ? 'conditional_operation' :
    multi.has(q.id) ? 'multi_choice' : q.fields.some(f => f.type === 'number') ? 'numeric_with_choice' : 'single_choice';
  const fields = q.fields.map(f => ({ ...f, demo_default_only: f.defaultValue !== '', required_when_recorded: f.type === 'number' && q.id !== 'AIR-14',
    validation: f.type === 'number' ? 'finite_positive; explicit unit; no default-as-fact' : 'trimmed text; no default-as-fact' }));
  if (q.id === 'PRS-08' || q.id === 'PRS-09' || q.id === 'PRS-10') {
    fields.push({ id: 'captured_at', label: '采集时间', type: 'text', defaultValue: '', demo_default_only: false, required_when_recorded: true, validation: 'ISO timestamp or documented relative time' });
    fields.push({ id: 'gear', label: '挡位/采集工况', type: 'text', defaultValue: '', demo_default_only: false, required_when_recorded: true, validation: 'nonempty' });
  }
  if (q.id === 'AIR-14') fields.push({ id: 'tool', label: '受控检漏工具', type: 'text', defaultValue: '', demo_default_only: false, required_when_recorded: true, validation: 'nonempty when within_limit' });
  if (q.id === 'RET-04') fields.push({ id: 'new_batch_id', label: '维修后新采集批次', type: 'text', defaultValue: '', demo_default_only: false, required_when_recorded: true, validation: 'different from before-repair batch' });
  return { ...q, fields,
    options: q.options.map(o => ({ ...o, label: optionLabelFixes[`${q.id}/${o.id}`] ?? o.label,
      legacy_outcome_display_only: true,
      status_semantics: issueUnknown.has(o.id) ? 'unknown_or_unavailable_not_normal' :
        phase === 'intake' ? (q.id === 'IN-08' && o.id === 'stop_now' ? 'safety_stop' : 'intake_context_not_component_judgment') :
        phase === 'actual_repair' ? 'actual_action_or_record_integrity_not_diagnostic_abnormality' :
        decision ? 'derived_state_not_user_submittable' :
        phase === 'post_repair_retest' || phase === 'after_setting_recheck' ? 'new_round_result_not_final_report' :
        o.outcome === 'normal' ? 'observed_no_issue_not_component_certified' : 'abnormal_clue_not_diagnosis' })),
    area_id: card.areaId ?? null, phase, answer_kind: answerKind,
    submission_semantics: decision ? 'server_derived_only' : 'server_persisted_observation',
    normal_observation_independent: !decision && !operation && q.stage !== 'S6',
    required_policy: q.stage === 'S6' ? 'only_when_repair_or_retest_round_started' : q.stage === 'S0' ? 'intake_plan' : 'only_if_in_case_plan_and_applicable',
    applicability: q.stage === 'S0' ? 'after_case_intake' : q.stage === 'S6' ? 'after_actual_repair_or_handoff_as_applicable' : 'DKVB/P0299 topic case; visible regardless of recommendation rank',
    prerequisites: decision ? { refs: decision.depends_on, when: 'all applicable saved inputs; otherwise insufficient' } : operation ? { refs: operation.refs, when: operation.when } : { refs: [], when: 'none for ordinary observation' },
    dependency_question_ids: decision?.depends_on ?? operation?.refs ?? [],
    unavailable_unknown_policy: 'distinct from not_checked; never infer normal or zero; keep reason and evidence',
    source_refs: sourceRefs, source_scope: 'Manual assets support location/assembly/safety only; wording, options and routing are editorial demo unless independently attributed.',
    long_card_ids: card.long_card_ids,
    capture: ['PRS-01','PRS-02','PRS-03'].includes(q.id) ? { batch_kind: 'engine_off_static', batch_id_required: true, unit: 'hPa absolute' } :
      ['PRS-08','PRS-09','PRS-10'].includes(q.id) ? { batch_kind: 'comparable_load_frames', batch_id_required: true, unit: 'hPa absolute' } :
      q.id === 'ACT-10' ? { batch_kind: 'after_setting_new_batch', batch_id_required: true } :
      q.id === 'RET-04' ? { batch_kind: 'post_repair_new_batch', batch_id_required: true,
        before_batch_id_required: true, required_frame_count_when_comparable: 3,
        frame_fields: [
          { id: 'captured_at', type: 'text', required: true }, { id: 'gear', type: 'text', required: true },
          { id: 'rpm', type: 'number', unit: 'rpm', required: true }, { id: 'load', type: 'number', unit: '%', required: true },
          { id: 'request', type: 'text', required: true },
          { id: 'target', type: 'number', unit: 'hPa absolute', required: true },
          { id: 'actual', type: 'number', unit: 'hPa absolute', required: true },
        ], legacy_frames_text_is_not_derived_input: true } : null,
    ...(decision ? { derived_rule_id: decision.rule_id } : {}),
    ...(operation ? { operation_kind: operation.kind } : {}),
  };
});
const resultDeps = [
  ['IN-01'], ['IN-08'], ['AIR-01','AIR-02'], ['AIR-03'], ['AIR-04'], ['AIR-07','AIR-08'], ['AIR-09','AIR-10'],
  ['AIR-11','AIR-12'], ['AIR-15','AIR-16'], ['AIR-01','AIR-02','AIR-03','AIR-04','AIR-07','AIR-08','AIR-09','AIR-10','AIR-11','AIR-12','AIR-15','AIR-16'],
  ['PRS-04','PRS-05','PRS-06'], ['PRS-04','PRS-03'], ['PRS-07','PRS-11'], ['PRS-11'], ['ACT-01','ACT-02'], ['ACT-03'],
  ['ACT-04','ACT-05'], ['ACT-06','ACT-07'], ['ACT-09','ACT-10'], ['ACT-09','ACT-10'], ['TUR-09'], ['TUR-09'],
  ['X-01','X-02','X-03','X-04','X-05'], ['X-06','X-07','X-08','X-09'], ['X-10','X-11','X-12'],
  ['RET-01','RET-02','RET-03','RET-04','RET-05','RET-06','RET-07','RET-08'],
];
// Small, named predicates avoid a general rule language. A Stage B evaluator
// must implement these keys against saved effective facts, never UI labels.
const resultCriteria = [
  'identity_unknown', 'safety_stop', 'intake_restriction', 'pre_turbo_duct_abnormal',
  'hose_external_abnormal', 'connector_seating_or_retention_abnormal', 'clamp_or_seal_abnormal',
  'intercooler_or_interface_suspect', 'localized_leak_with_strong_evidence',
  'main_air_checks_no_explanatory_abnormality', 'g31_static_outlier_with_corrob',
  'g71_static_outlier_needs_corrob', 'pressure_comparability_failed', 'saved_comparable_persistent_underboost',
  'v465_electrical_clue', 'v465_output_test_abnormal', 'linkage_external_clue', 'n249_clue',
  'after_setting_recovered_new_batch', 'after_setting_low_new_batch', 'turbo_independent_evidence_weak',
  'turbo_two_independent_classes', 'misfire_swap_support_chain', 'fuel_load_support_chain',
  'exhaust_or_intake_control_clue', 'post_repair_new_round_outcome',
];
const results = baseline.results.map((r, i) => ({ ...r, depends_on_question_ids: resultDeps[i],
  evaluation_key: resultCriteria[i],
  evaluation: 'server_only_current_effective_saved_facts; insufficient/conflict => pending_or_handoff',
  source_refs: ['EDITORIAL_DEMO'] }));
const transitionDeps = [
  ['IN-01','IN-08'], ['AIR-15','AIR-16'], ['AIR-15','AIR-16','PRS-07','PRS-11'], ['PRS-04'],
  ['ACT-01','ACT-02','ACT-03','ACT-04','ACT-05','ACT-06','ACT-07'], ['ACT-10'],
  ['RET-03','RET-04','RET-05','RET-06'], ['RET-04','RET-05'], ['TUR-09','RET-05'],
  ['IN-05','IN-06','X-01','X-06'], ['IN-08','AIR-13','AIR-14'], [],
];
const transitions = baseline.transitions.map((t, i) => ({ ...t, depends_on_question_ids: transitionDeps[i],
  effect: 'recommendation_or_conditional_action_only; never clear unrelated saved observations', source_refs: ['EDITORIAL_DEMO'] }));

const candidate = {
  schema_version: 'workbench-topic-candidate/1', topic_id: baseline.topic_id, version: '2.1.0-a01-candidate',
  candidate_status: 'CANDIDATE_READY_NOT_ACCEPTED', publishable: false, runtime_enabled: false,
  synthetic: true, demo: true, formal_usable: false, base_topic_version: baseline.version,
  authority: 'This candidate JSON alone is the reviewed Stage A topic authority; generated from frozen V2 catalog and cited package, not loaded by running services.',
  provenance: { frozen_catalog: 'backend/app/topics/dkvb_p0299_v2.json', reviewed_web_content: 'frontend/src/formal/design/workbench-v2/prototypeKnowledge.ts',
    package_root: reference, documents: ['README.md','00-专题知识包总规范-v2.md','07-完整问题块与选项库-v2.md','08-结果组合与路由-v2.md','09-网页长内容卡-v2.md','04-器件图与电路图索引.md','sources-register.md'] },
  source_boundary: 'Only cited local topic assets and version-allowed sources may be used later; no old demo material is implicitly eligible. OEM PDF citations and generic web register entries were not reverified in this task.',
  stages: [{ id: 'S0', phase: 'intake' }, { id: 'S1', phase: 'diagnostic_observation' }, { id: 'S2', phase: 'diagnostic_observation' },
    { id: 'S3', phase: 'diagnostic_observation' }, { id: 'S4', phase: 'diagnostic_observation' }, { id: 'S5', phase: 'diagnostic_observation' },
    { id: 'S6', phase: 'actual_repair_and_post_repair_retest' }],
  areas: baseline.areas, cards, questions,
  assets: baseline.assets.map(a => ({ ...a, source_ref: sourceIds[a.id], package_file: `E:/Work/v4-double/docs/参考/专题资料包/探岳维修资料1/assets/${a.file.split('/workbench-v2-assets/')[1]}` })),
  sources, long_cards: longCards, results, transitions,
  derived_rules: [...derived.entries()].map(([question_id, rule]) => ({ question_id, ...rule, source_refs: ['EDITORIAL_DEMO'] })),
  issue_rules: [
    { id: 'C-AIR-07-08', refs: ['AIR-07','AIR-08'], condition: 'AIR-07=seated and AIR-08=pulls_out', output: 'conflict_needs_recheck', reason: '保持力事实与座合判断相冲突，不暗中择一。' },
    { id: 'C-PRS-07-11', refs: ['PRS-07','PRS-11'], condition: 'PRS-07!=comparable and PRS-11 in tracks_target|persistent_underboost|intermittent_drop|overshoot', output: 'trend_unreliable', reason: '工况不可比不得路由到涡轮。' },
    { id: 'C-RET-04-06', refs: ['RET-04','RET-06'], condition: 'RET-04=recovered and RET-06=returned', output: 'retest_conflict', reason: '复检增压恢复但故障码复现，不得通过。' },
  ],
  plan_policy: {
    case_binding: 'Bind exact topic_id, version and content hash at creation of a new case only; never silently rebind old cases.',
    initial_intake_required: ['IN-01','IN-02','IN-04','IN-08'],
    first_round_scope: { S1: ['AIR-01','AIR-02','AIR-03','AIR-04','AIR-05','AIR-06','AIR-07','AIR-08','AIR-09','AIR-10','AIR-11','AIR-12','AIR-13'],
      S2: ['PRS-01','PRS-02','PRS-03','PRS-04','PRS-07','PRS-08','PRS-09','PRS-10','PRS-11','PRS-12'] },
    conditional_expansion: [
      { id: 'P-LEAK', refs: ['AIR-13'], add: ['AIR-14','AIR-15','AIR-16'], when: 'safe controlled leak test available; otherwise record unavailable/handoff' },
      { id: 'P-SIGNAL', refs: ['PRS-04'], add: ['PRS-05','PRS-06'], when: 'static outlier or missing signal' },
      { id: 'P-ACT', refs: ['PRS-11','IN-05','ACT-01'], add: ['ACT-01','ACT-02','ACT-03','ACT-04','ACT-05','ACT-06','ACT-07','ACT-08','ACT-09','ACT-10'], when: 'credible low boost/actuator clue or operator expands; ACT-09/10 remain conditional and after-action' },
      { id: 'P-TUR', refs: ['PRS-11','TUR-01'], add: ['TUR-01','TUR-02','TUR-03','TUR-04','TUR-05','TUR-06','TUR-07','TUR-08','TUR-09','TUR-10'], when: 'external clue, unresolved credible low boost or operator expands' },
      { id: 'P-X', refs: ['IN-06','RET-05','X-01'], add: ['X-01','X-02','X-03','X-04','X-05','X-06','X-07','X-08','X-09','X-10','X-11','X-12','X-13','X-14'], when: 'cross-system clue, residual symptom or operator expands' },
    ],
    all_topic_questions_browsable: true, ordinary_observation_recordable_even_if_not_recommended: true,
    conditional_action_requires_its_own_prerequisites: true, area_card_order_frozen_for_case_plan: true,
    completion_denominator: 'Only applicable required instances in the versioned case plan; optional and S6 excluded from initial round. unavailable counts as addressed but unresolved, not normal.',
    ai_first_advice_ready: 'After initial and expanded applicable required instances are saved or explicitly unavailable with reason; unresolved critical gaps produce only supplementation/handoff advice. No RET question required.',
    final_report_ready: 'Use existing formal report gate; independent of first AI readiness and never relaxed by this candidate.',
  },
  correction_policy: 'Append revision, preserve old observation; recompute only rules whose dependency graph reaches the changed question. Region navigation/recommendation never mutates facts; new post-repair retest uses separate round/batch.',
  defaults_policy: 'All defaultValue entries are demonstration display hints only and MUST be blank in formal persisted input until explicitly entered and saved.',
};
for (const q of questions) if (!questionById.has(q.id)) throw new Error(`Unexpected question ${q.id}`);
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, JSON.stringify(candidate, null, 2) + '\n', 'utf8');
process.stdout.write(`Created isolated candidate: ${questions.length} questions, ${questions.reduce((n,q)=>n+q.options.length,0)} options, ${longCards.length} long cards, ${candidate.assets.length} assets\n`);
