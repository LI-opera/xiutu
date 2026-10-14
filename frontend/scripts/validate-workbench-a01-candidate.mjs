// Read-only, focused Stage A contract checks. No database or service access.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const candidatePath = path.join(root, 'backend/app/topics/candidates/tanyue-dkvb-p0299-a01-candidate.json');
const topic = JSON.parse(fs.readFileSync(candidatePath, 'utf8'));
const unique = (items, label) => assert.equal(new Set(items).size, items.length, `duplicate ${label}`);
unique(topic.questions.map(q => q.id), 'question ID');
unique(topic.cards.map(c => c.id), 'card ID');
unique(topic.areas.map(a => a.id), 'area ID');
unique(topic.assets.map(a => a.id), 'asset ID');
unique(topic.sources.map(s => s.id), 'source ID');
unique(topic.results.map(r => r.id), 'result ID');
unique(topic.transitions.map(t => t.id), 'transition ID');
unique(topic.derived_rules.map(r => r.rule_id), 'derived rule ID');
assert.equal(topic.questions.length, 78);
assert.equal(topic.questions.reduce((n,q) => n + q.options.length, 0), 359);
assert.equal(topic.areas.length, 5);
assert.equal(topic.cards.length, 34);
assert.equal(topic.assets.length, 19);
assert.equal(topic.long_cards.length, 14);
assert.equal(topic.results.length, 26);
assert.equal(topic.transitions.length, 12);
assert.equal(topic.synthetic, true);
assert.equal(topic.demo, true);
assert.equal(topic.formal_usable, false);
assert.equal(topic.runtime_enabled, false);

const questions = new Map(topic.questions.map(q => [q.id,q]));
const cards = new Map(topic.cards.map(c => [c.id,c]));
const areas = new Map(topic.areas.map(a => [a.id,a]));
const assets = new Map(topic.assets.map(a => [a.id,a]));
const sources = new Map(topic.sources.map(s => [s.id,s]));
const longs = new Map(topic.long_cards.map(c => [c.id,c]));
const rules = new Map(topic.derived_rules.map(r => [r.rule_id,r]));
const allowedPhases = new Set(['intake','diagnostic_observation','after_setting_recheck','actual_repair','post_repair_retest']);
const allowedKinds = new Set(['single_choice','multi_choice','numeric_with_choice','automatic_derived','conditional_operation']);
const knownStages = new Set(topic.stages.map(s => s.id));
const questionCountByStage = new Map();
for (const q of topic.questions) {
  assert(knownStages.has(q.stage), `${q.id}: invalid stage`);
  questionCountByStage.set(q.stage, (questionCountByStage.get(q.stage) ?? 0) + 1);
  assert(allowedPhases.has(q.phase), `${q.id}: unclassified phase`);
  assert(allowedKinds.has(q.answer_kind), `${q.id}: unclassified answer kind`);
  assert(q.prompt && q.purpose && q.instructions && q.factKey, `${q.id}: missing content`);
  assert(cards.has(q.cardId), `${q.id}: invalid card`);
  assert(cards.get(q.cardId).questionIds.includes(q.id), `${q.id}: not mapped back from card`);
  assert(q.area_id === null || areas.has(q.area_id), `${q.id}: invalid area`);
  assert(q.options.length > 0, `${q.id}: no options`);
  unique(q.options.map(o => o.id), `${q.id} option`);
  unique(q.fields.map(f => f.id), `${q.id} field`);
  for (const o of q.options) assert(o.label && o.status_semantics, `${q.id}/${o.id}: incomplete option`);
  for (const f of q.fields) assert(f.label && f.type && f.validation && (f.type !== 'number' || f.unit), `${q.id}/${f.id}: incomplete field or unit`);
  for (const id of q.dependency_question_ids) assert(questions.has(id), `${q.id}: invalid dependency ${id}`);
  for (const id of q.source_refs) assert(sources.has(id), `${q.id}: invalid source ${id}`);
  for (const id of q.assetIds) assert(assets.has(id), `${q.id}: invalid image ${id}`);
  for (const id of q.long_card_ids) assert(longs.has(id), `${q.id}: invalid long card ${id}`);
  assert(q.long_card_ids.length > 0 && q.source_refs.length > 0, `${q.id}: missing long content/source`);
  if (q.answer_kind === 'automatic_derived') assert(rules.has(q.derived_rule_id), `${q.id}: missing derived rule`);
  if (q.answer_kind !== 'automatic_derived') assert.equal(q.submission_semantics, 'server_persisted_observation');
}
assert.deepEqual([...questionCountByStage.values()], [8,16,12,10,10,14,8]);
for (const card of topic.cards) {
  for (const id of card.questionIds) assert(questions.has(id), `${card.id}: invalid question`);
  for (const id of card.assetIds) assert(assets.has(id), `${card.id}: invalid asset`);
  for (const id of card.long_card_ids) assert(longs.has(id), `${card.id}: invalid long card`);
}
for (const area of topic.areas) for (const id of area.componentIds) assert(cards.has(id), `${area.id}: invalid card`);
for (const asset of topic.assets) {
  assert(sources.has(asset.source_ref), `${asset.id}: invalid source`);
  assert(fs.existsSync(path.join(root, 'frontend/public', asset.file.slice(1))), `${asset.id}: missing public image`);
  assert(fs.existsSync(asset.package_file), `${asset.id}: missing package image`);
}
for (const source of topic.sources) {
  assert(fs.existsSync(source.register_path), `${source.id}: missing register`);
  if (source.kind === 'local_manual') assert(source.original_file && fs.existsSync(source.original_file), `${source.id}: missing local original`);
}
for (const card of topic.long_cards) {
  assert(card.markdown.length > 60, `${card.id}: empty/truncated long card`);
  for (const id of card.image_asset_ids) assert(assets.has(id), `${card.id}: invalid image ${id}`);
  for (const [, relative] of card.markdown.matchAll(/!\[[^\]]*\]\((assets\/[^)]+)\)/g))
    assert(fs.existsSync(path.join('E:/Work/v4-double/docs/参考/专题资料包/探岳维修资料1', relative)), `${card.id}: broken markdown image ${relative}`);
}
for (const row of [...topic.results,...topic.transitions,...topic.issue_rules]) {
  for (const id of row.depends_on_question_ids ?? row.refs ?? []) assert(questions.has(id), `${row.id}: invalid question reference ${id}`);
}
for (const rule of topic.derived_rules) {
  assert(questions.has(rule.question_id), `${rule.rule_id}: invalid output`);
  for (const id of rule.depends_on) assert(questions.has(id), `${rule.rule_id}: invalid dependency ${id}`);
  assert(rule.decision_table?.length > 0, `${rule.rule_id}: missing decision table`);
  const outputOptions = new Set(questions.get(rule.question_id).options.map(o => o.id));
  for (const row of rule.decision_table) {
    assert(row.predicate_id, `${rule.rule_id}: unnamed predicate`);
    assert(row.output_option_id === null || outputOptions.has(row.output_option_id), `${rule.rule_id}: invalid output option`);
  }
  for (const group of rule.evidence_classes ?? []) for (const id of group.question_ids) assert(questions.has(id), `${rule.rule_id}: invalid evidence class question`);
}
const visiting = new Set(), visited = new Set();
function visit(id) {
  if (visited.has(id)) return;
  assert(!visiting.has(id), `derived cycle at ${id}`);
  visiting.add(id);
  for (const dep of questions.get(id).dependency_question_ids) if (questions.get(dep).answer_kind === 'automatic_derived') visit(dep);
  visiting.delete(id); visited.add(id);
}
for (const q of topic.questions.filter(q => q.answer_kind === 'automatic_derived')) visit(q.id);
const plan = topic.plan_policy;
for (const id of [...plan.initial_intake_required,...Object.values(plan.first_round_scope).flat()]) assert(questions.has(id), `plan missing ${id}`);
for (const expansion of plan.conditional_expansion) {
  for (const id of [...expansion.refs,...expansion.add]) assert(questions.has(id), `${expansion.id}: invalid question`);
}
assert(![...plan.initial_intake_required,...Object.values(plan.first_round_scope).flat()].some(id => id.startsWith('RET-')));
assert(!topic.derived_rules.some(r => !r.question_id.startsWith('RET-') && r.depends_on.some(id => id.startsWith('RET-'))), 'first advice depends on S6');

// Representative evaluations are intentionally read-only contract checks, not a new runtime engine.
const staticClass = rows => {
  const ids = ['PRS-01','PRS-02','PRS-03'];
  const saved = ids.map(id => rows[id]);
  if (saved.some(x => !x?.saved || x.unit !== 'hPa absolute' || x.batch_id !== saved[0].batch_id || !Number.isFinite(x.value))) return 'unavailable';
  const [ambient,g31,g71] = saved.map(x => x.value);
  if (Math.max(ambient,g31,g71) - Math.min(ambient,g31,g71) <= 30) return 'consistent';
  if (Math.abs(g31-ambient)>30 && Math.abs(g71-ambient)<=30) return 'g31_outlier';
  if (Math.abs(g71-ambient)>30 && Math.abs(g31-ambient)<=30) return 'g71_outlier';
  return 'multiple_outliers';
};
assert.equal(staticClass({ 'PRS-01': { saved:true, batch_id:'a',unit:'hPa absolute',value:1005 }, 'PRS-02': { saved:true,batch_id:'a',unit:'hPa absolute',value:1450 }, 'PRS-03': { saved:true,batch_id:'a',unit:'hPa absolute',value:1010 } }), 'g31_outlier');
assert.equal(staticClass({ 'PRS-01': { saved:true, batch_id:'a',unit:'hPa absolute',value:1005 }, 'PRS-02': { saved:false,batch_id:'a',unit:'hPa absolute',value:1450 }, 'PRS-03': { saved:true,batch_id:'a',unit:'hPa absolute',value:1010 } }), 'unavailable');
assert.equal(questions.get('AIR-07').normal_observation_independent, true);
assert.equal(questions.get('AIR-07').options.find(o => o.id === 'unavailable').status_semantics, 'unknown_or_unavailable_not_normal');
const affected = new Set(['PRS-02']);
for (let changed=true; changed;) {
  changed=false;
  for (const rule of topic.derived_rules) if (rule.depends_on.some(id => affected.has(id)) && !affected.has(rule.question_id)) { affected.add(rule.question_id); changed=true; }
}
assert(affected.has('PRS-04') && !affected.has('TUR-09') && !affected.has('AIR-07'), 'correction dependency propagation');
process.stdout.write(`A01 candidate valid: 78 questions / 359 options / 14 long cards / 19 assets / 26 results / 12 routes; representative saved, unavailable, correction checks passed\n`);
