"""Exercise the real save service with an isolated in-memory transaction adapter."""
from copy import deepcopy
from uuid import uuid4

import pytest
from app.domain.policies import DomainError
from app.services import workbench_observation_service as service_module
from app.services.template_projection import build_plan, project_template
from app.services.workbench_observation_service import TopicAnswer, TopicService
from app.services.workbench_templates import content_hash
from sqlalchemy.sql.dml import Insert, Update


def topic():
    def question(id, stage, area, options, *, kind='single_choice', refs=None, conditions=None):
        return {'id': id, 'stage': stage, 'area_id': area, 'answer_kind': kind,
                'options': [{'id': name, 'outcome': outcome} for name, outcome in options],
                'fields': [], 'source_refs': [], 'prerequisites': {'refs': refs or []},
                'execution_conditions': conditions}
    return {'topic_id': 'separate-vehicle', 'version': 'independent-1',
            'areas': [{'id': 'cooling'}, {'id': 'electrical'}],
            'questions': [
                question('COOL-01', 'inspection', 'cooling', [('ok', 'normal'), ('fault', 'abnormal')]),
                question('ELEC-01', 'inspection', 'electrical', [('done', 'normal'), ('not_performed', 'unavailable')],
                         kind='conditional_operation', refs=['COOL-01'],
                         conditions={'bypass_options': ['not_performed'], 'requirements': [
                             {'ref': 'COOL-01', 'allowed': ['ok'], 'label': '先确认冷却状态'}]}),
                question('FIX-01', 'repair', None, [('replace', 'normal'), ('none', 'unavailable')]),
                question('VERIFY-01', 'repair', None, [('resolved', 'normal'), ('persists', 'abnormal')]),
            ],
            'observation_workflow': {'repair_question_id': 'FIX-01', 'retest_stage': 'repair',
                                     'no_action_options': ['none']}}


class Result:
    def __init__(self, value): self.value = value
    def mappings(self): return self
    def one(self): return self.value


class Connection:
    def __init__(self, case):
        self.case = case
        self.rows = []
    def execute(self, statement):
        if isinstance(statement, Update):
            values = {getattr(column, 'name', column): getattr(value, 'value', None) for column, value in statement._values.items()}
            self.case.update({key: value for key, value in values.items() if key in {'revision', 'intake_snapshot'}})
            return Result(None)
        if isinstance(statement, Insert):
            values = {getattr(column, 'name', column): getattr(value, 'value', None) for column, value in statement._values.items()}
            self.rows.append(values)
            return Result(None)
        return Result(self.case)


class Uow:
    def __init__(self, connection): self.connection = connection
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False


def fixture(monkeypatch):
    frozen = topic()
    claim = {'template_id': 'unrelated', 'version': '1', 'title': '独立专题', 'content_hash': content_hash(frozen)}
    case = {'id': uuid4(), 'owner_id': uuid4(), 'revision': 0,
            'intake_snapshot': {'workbench_flow': 'template-match-v1',
                                'template_binding': claim, 'template_content': frozen,
                                'topic_plan': build_plan(frozen, {'safety_gate': 'unprovided'})}}
    conn = Connection(case)
    monkeypatch.setattr(service_module, 'UnitOfWork', lambda engine: Uow(conn))
    monkeypatch.setattr(service_module, 'lock_case', lambda connection, actor, case_id: case)
    monkeypatch.setattr(service_module, 'idempotent', lambda connection, actor, scope, key, body, action: action())
    monkeypatch.setattr(TopicService, '_rows', staticmethod(lambda connection, case_id, version: list(conn.rows)))
    monkeypatch.setattr(TopicService, '_view', lambda self, connection, row:
                        {'view': project_template(row, conn.rows, row['intake_snapshot']['template_content'])})
    instance = TopicService(type('CaseService', (), {'engine': object()})())
    def save(qid, option, *, round_id=None, correction=None, fields=None):
        body = TopicAnswer(expected_revision=case['revision'], topic_version=frozen['version'],
                           question_id=qid, option_ids=[option], round_id=round_id, fields=fields or {})
        return instance.save(case['owner_id'], case['id'], body, str(uuid4()), correction)
    return case, conn, save


def test_distinct_template_save_correction_conditions_repair_and_independent_retest(monkeypatch):
    case, conn, save = fixture(monkeypatch)
    initial = project_template(case, [], topic())
    assert initial['question_states']['ELEC-01']['condition_blockers'][0]['ref'] == 'COOL-01'
    with pytest.raises(DomainError, match='前置条件'):
        save('ELEC-01', 'done')
    assert case['revision'] == 0 and not conn.rows
    _, first = save('COOL-01', 'ok')
    assert case['revision'] == 1
    old_id = conn.rows[-1]['id']
    _, corrected = save('COOL-01', 'fault', correction=old_id)
    assert corrected['view']['view']['synthesis']['issues'][0]['question_id'] == 'COOL-01'
    assert len(conn.rows) == 2 and conn.rows[-1]['supersedes_id'] == old_id
    with pytest.raises(DomainError, match='前置条件'):
        save('ELEC-01', 'done')
    save('COOL-01', 'ok', correction=conn.rows[-1]['id'])
    assert project_template(case, conn.rows, topic())['question_states']['ELEC-01']['condition_blockers'] == []
    save('ELEC-01', 'done')
    with pytest.raises(DomainError, match='复检轮次'):
        save('VERIFY-01', 'resolved')
    _, repair = save('FIX-01', 'replace')
    round_id = repair['view']['view']['active_round_id']
    assert round_id and len(case['intake_snapshot']['topic_plan']['rounds']) == 1
    _, retest = save('VERIFY-01', 'resolved', round_id=round_id)
    assert retest['view']['view']['question_states']['VERIFY-01']['option_ids'] == ['resolved']
    _, corrected_repair = save('FIX-01', 'none', correction=conn.rows[-2]['id'])
    assert corrected_repair['view']['view']['active_round_id'] is None
    assert corrected_repair['view']['view']['question_states']['VERIFY-01']['option_ids'] == []
    assert len(conn.rows) == 7  # original and corrected observations remain in history


def test_generic_conditions_do_not_reinterpret_legacy_safety_id(monkeypatch):
    case, conn, save = fixture(monkeypatch)
    save('COOL-01', 'ok')
    _, result = save('ELEC-01', 'done')
    assert result['view']['view']['question_states']['ELEC-01']['option_ids'] == ['done']
    assert case['intake_snapshot']['topic_plan']['intake']['safety_gate'] == 'unprovided'


def test_new_topic_reuses_a_legacy_question_id_without_legacy_round_semantics(monkeypatch):
    case, conn, save = fixture(monkeypatch)
    frozen = deepcopy(case['intake_snapshot']['template_content'])
    frozen['questions'][0]['id'] = 'RET-01'
    frozen['questions'][1]['prerequisites']['refs'] = ['RET-01']
    frozen['questions'][1]['execution_conditions']['requirements'][0]['ref'] = 'RET-01'
    case['intake_snapshot']['template_content'] = frozen
    case['intake_snapshot']['template_binding']['content_hash'] = content_hash(frozen)
    case['intake_snapshot']['topic_plan'] = build_plan(frozen, {'safety_gate': 'unprovided'})
    _, saved = save('RET-01', 'ok')
    assert saved['view']['view']['question_states']['RET-01']['option_ids'] == ['ok']
    assert case['intake_snapshot']['topic_plan']['rounds'] == []
    assert conn.rows[-1]['payload']['round_id'] is None


def test_configured_safety_and_new_capture_batch_are_not_legacy_ids(monkeypatch):
    case, conn, save = fixture(monkeypatch)
    frozen = deepcopy(case['intake_snapshot']['template_content'])
    frozen['questions'].extend([
        {'id': 'SAFE-01', 'stage': 'inspection', 'area_id': 'cooling',
         'answer_kind': 'single_choice',
         'options': [{'id': 'caution', 'outcome': 'unavailable'},
                     {'id': 'none', 'outcome': 'normal'}],
         'fields': [], 'source_refs': [], 'prerequisites': {'refs': []},
         'execution_conditions': None},
        {'id': 'SET-01', 'stage': 'inspection', 'area_id': 'electrical',
         'answer_kind': 'single_choice',
         'options': [{'id': 'completed', 'outcome': 'normal'},
                     {'id': 'failed', 'outcome': 'abnormal'}],
         'fields': [], 'source_refs': [], 'prerequisites': {'refs': []},
         'execution_conditions': None},
    ])
    frozen['observation_workflow'].update({
        'safety_question_id': 'SAFE-01',
        'new_batch_on_answer': {'question_id': 'SET-01', 'option_id': 'completed',
                                'batch_kind': 'post_setting'},
    })
    case['intake_snapshot']['template_content'] = frozen
    case['intake_snapshot']['template_binding']['content_hash'] = content_hash(frozen)
    case['intake_snapshot']['topic_plan'] = build_plan(frozen, {'safety_gate': 'unprovided'})
    original_batches = deepcopy(case['intake_snapshot']['topic_plan']['capture_batches'])
    save('SAFE-01', 'caution')
    assert case['intake_snapshot']['topic_plan']['intake']['safety_gate'] == 'caution'
    save('SET-01', 'failed')
    assert case['intake_snapshot']['topic_plan']['capture_batches'] == original_batches
    _, result = save('SET-01', 'completed', correction=conn.rows[-1]['id'])
    assert result['view']['view']['question_states']['SET-01']['option_ids'] == ['completed']
    assert case['intake_snapshot']['topic_plan']['capture_batches']['post_setting']


def test_independent_focus_conflict_and_operation_gate_follow_effective_corrections(monkeypatch):
    case, conn, save = fixture(monkeypatch)
    frozen = deepcopy(case['intake_snapshot']['template_content'])
    frozen['questions'].append({
        'id': 'ELEC-02', 'stage': 'inspection', 'area_id': 'electrical',
        'answer_kind': 'single_choice',
        'options': [{'id': 'fault', 'outcome': 'abnormal'}, {'id': 'ok', 'outcome': 'normal'}],
        'fields': [], 'source_refs': [], 'prerequisites': {'refs': []},
        'execution_conditions': None})
    frozen['observation_rules'] = {'version': 'observation-v1',
        'focus_rules': [{'id': 'inspect-electrical',
                         'all': [{'question_id': 'COOL-01', 'option_ids': ['fault']}],
                         'question_ids': ['ELEC-01', 'ELEC-02']}],
        'conflict_rules': [{'id': 'conflicting-claims',
                            'all': [{'question_id': 'COOL-01', 'option_ids': ['fault']},
                                    {'question_id': 'ELEC-02', 'option_ids': ['fault']}],
                            'reason': '两处记录同时异常，需核对是否共享条件。'}]}
    case['intake_snapshot']['template_content'] = frozen
    case['intake_snapshot']['template_binding']['content_hash'] = content_hash(frozen)
    case['intake_snapshot']['topic_plan'] = build_plan(frozen, {'safety_gate': 'unprovided'})
    save('COOL-01', 'fault')
    projection = project_template(case, conn.rows, frozen)
    assert projection['question_states']['ELEC-01']['focused']
    assert projection['plan_evaluation']['focus_question_ids'] == ['ELEC-01', 'ELEC-02']
    with pytest.raises(DomainError, match='前置条件'):
        save('ELEC-01', 'done')
    assert len(conn.rows) == 1
    save('ELEC-01', 'not_performed')
    save('ELEC-02', 'fault')
    projection = project_template(case, conn.rows, frozen)
    assert projection['synthesis']['conflicts'][0]['id'] == 'conflicting-claims'
    assert len(projection['synthesis']['conflicts'][0]['basis_observation_ids']) == 2
    original = conn.rows[0]['id']
    save('COOL-01', 'ok', correction=original)
    projection = project_template(case, conn.rows, frozen)
    assert projection['plan_evaluation']['focus_question_ids'] == []
    assert projection['synthesis']['conflicts'] == []
    assert projection['question_states']['ELEC-01']['condition_blockers'] == []
    assert len(conn.rows) == 4


def test_independent_rule_validation_rejects_false_completion_and_bad_refs():
    frozen = topic()
    frozen['questions'][1]['execution_conditions']['bypass_options'] = ['done']
    with pytest.raises(DomainError, match='观察规则配置无效'):
        build_plan(frozen, {})
    frozen = topic()
    frozen['questions'][1]['execution_conditions']['requirements'][0]['allowed'] = ['missing']
    with pytest.raises(DomainError, match='观察规则配置无效'):
        build_plan(frozen, {})
    frozen = topic()
    frozen['observation_rules'] = {'version': 'observation-v1', 'focus_rules': [
        {'id': 'wrong', 'all': [{'question_id': 'MISSING', 'option_ids': ['ok']}],
         'question_ids': ['ELEC-01']}], 'conflict_rules': []}
    with pytest.raises(DomainError, match='观察规则配置无效'):
        build_plan(frozen, {})


def test_independent_field_applicability_is_checked_on_save(monkeypatch):
    case, conn, save = fixture(monkeypatch)
    frozen = deepcopy(case['intake_snapshot']['template_content'])
    frozen['questions'][0]['fields'] = [{
        'id': 'reading', 'label': '实测读数', 'type': 'number', 'unit': 'kPa',
        'allowed_when_options': ['fault'], 'required_when_options': ['fault']}]
    case['intake_snapshot']['template_content'] = frozen
    case['intake_snapshot']['template_binding']['content_hash'] = content_hash(frozen)
    case['intake_snapshot']['topic_plan'] = build_plan(frozen, {})
    with pytest.raises(DomainError, match='不适用于当前选项'):
        save('COOL-01', 'ok', fields={'reading': {'value': 15, 'unit': 'kPa'}})
    with pytest.raises(DomainError, match='请填写'):
        save('COOL-01', 'fault')
    save('COOL-01', 'fault', fields={'reading': {'value': 15, 'unit': 'kPa'}})
    assert len(conn.rows) == 1
