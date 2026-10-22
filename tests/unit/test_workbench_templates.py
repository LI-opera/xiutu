from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

import pytest
from app.domain.policies import DomainError
from app.domain.schemas import CreateCase
from app.services.workbench_answer_validation import validate_answer
from app.services.workbench_observation_service import TopicAnswer
from app.services.workbench_templates import (
    FrozenTemplate,
    content_hash,
    frozen_snapshot,
    template_projection,
)

from scripts.seed_workbench_templates import build_templates


class Result:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def __iter__(self): return iter(self.rows)
    def one(self): return self.rows[0]


class Connection:
    def __init__(self, relation, topic): self.relation, self.topic = relation, topic
    def execute(self, statement):
        if 'FROM workbench_template_matches' in str(statement):
            return Result([self.relation])
        return Result([dict(template_id=self.relation['template_id'], version=self.relation['version'],
                            title=self.relation['title'], content_hash=content_hash(self.topic), content_json=self.topic)])


def body(code='P0299', engine='DKVB'):
    return CreateCase.model_validate(dict(workbench_flow='template-match-v1',
        vehicle=dict(brand='大众', model='探岳', year=2019, engine_code=engine),
        fault_description='测试输入，不代表实车观察', fault_codes=[code]))


@pytest.mark.parametrize('code,count', [('P0299', 5), ('P0236', 3)])
def test_complete_frozen_hierarchy_and_projection(code, count):
    relation, topic = next((r, t) for r, t in build_templates() if r['fault_code'] == code)
    snap = frozen_snapshot(Connection(relation, topic), body(code))
    case = {'intake_snapshot': snap}
    module = FrozenTemplate(case)
    loaded, digest = module.catalog()
    assert digest == snap['template_binding']['content_hash']
    assert len(loaded['areas']) == count
    questions = {q['id']: q for q in loaded['questions']}
    cards = {c['id']: c for c in loaded['cards']}
    for area in loaded['areas']:
        for card_id in area['componentIds']:
            assert cards[card_id]['areaId'] == area['id']
            for qid in cards[card_id]['questionIds']:
                assert questions[qid]['cardId'] == card_id
                assert questions[qid]['options']
    view = template_projection(case, [], loaded)
    assert len(view['areas']) == count
    assert set(view['question_states']) == set(questions)
    assert snap['topic_plan']['intake']['safety_gate'] == 'unprovided'
    assert not view['synthesis']['facts']
    if code == 'P0236':
        assert not any(q.startswith(('TUR-', 'X-')) for q in questions)
        with pytest.raises(DomainError):
            validate_answer(loaded, snap['topic_plan'], [], TopicAnswer(
                expected_revision=1, topic_version=loaded['version'], question_id='TUR-01',
                option_ids=['normal']), effective=lambda *args: None)
    original = deepcopy(snap)
    loaded['questions'][0]['title'] = 'changed'
    with pytest.raises(DomainError):
        FrozenTemplate(case)
    assert original['template_content']['questions'][0]['title'] != 'changed'


@pytest.mark.parametrize('engine', [None, '', '   '])
def test_missing_engine_matches_unique_template_without_inventing_vehicle(engine):
    relation, topic = next(build_templates())
    snap = frozen_snapshot(Connection(relation, topic), body(engine=engine))
    assert snap['vehicle']['engine_code'] is None
    assert snap['template_binding']['template_id'] == relation['template_id']


def test_explicit_unmatched_engine_is_not_ignored():
    relation, topic = next(build_templates())
    with pytest.raises(DomainError, match='此发动机尚无适用模板'):
        frozen_snapshot(Connection(relation, topic), body(engine='OTHER'))


def test_optional_engine_does_not_arbitrarily_choose_between_templates():
    relation, topic = next(build_templates())
    class Multiple(Connection):
        def execute(self, statement):
            if 'FROM workbench_template_matches' in str(statement):
                return Result([relation, {**relation, 'engine_code':'OTHER', 'template_id':'other-template'}])
            return super().execute(statement)
    with pytest.raises(DomainError, match='多个排查模板'):
        frozen_snapshot(Multiple(relation, topic), body(engine=None))
    snap = frozen_snapshot(Multiple(relation, topic), body())
    assert snap['vehicle']['engine_code'] == 'DKVB'


def test_multiple_engine_relations_to_same_template_remain_unambiguous():
    relation, topic = next(build_templates())
    class Shared(Connection):
        def execute(self, statement):
            if 'FROM workbench_template_matches' in str(statement):
                return Result([relation, {**relation, 'engine_code':'OTHER'}])
            return super().execute(statement)
    assert frozen_snapshot(Shared(relation, topic), body(engine=None))['vehicle']['engine_code'] is None


def test_new_case_chooses_newest_version_of_same_applicability_and_preserves_old_snapshot():
    relation, old_topic = next(build_templates())
    newer = {**relation, 'id': relation['id'].replace('-v2', '-v3'), 'version': '3'}
    new_topic = deepcopy(old_topic)
    new_topic['version'] = relation['template_id'] + '-v3'

    class Versioned(Connection):
        def execute(self, statement):
            if 'FROM workbench_template_matches' in str(statement):
                return Result([relation, newer])
            return Result([dict(template_id=relation['template_id'], version='3',
                                title=newer['title'], content_hash=content_hash(new_topic),
                                content_json=new_topic)])

    for engine in ('DKVB', None):
        with patch('app.services.workbench_templates.build_plan', return_value={'version': 1}):
            snap = frozen_snapshot(Versioned(relation, old_topic), body(engine=engine))
        assert snap['template_binding']['version'] == '3'
        assert snap['vehicle']['engine_code'] == engine
    old_snap = frozen_snapshot(Connection(relation, old_topic), body())
    assert FrozenTemplate({'intake_snapshot': old_snap}).catalog()[0]['version'].endswith('-v2')


def test_ordinary_answer_and_correction_projection():
    relation, topic = next(build_templates())
    snap = frozen_snapshot(Connection(relation, topic), body())
    q = next(q for q in topic['questions'] if q['id'] == 'AIR-01')
    payload = dict(question_id=q['id'], option_ids=[q['options'][0]['id']], fields={}, round_id=None)
    rows = [dict(id=uuid4(), payload=payload, supersedes_id=None, created_revision=2)]
    view = template_projection({'intake_snapshot': snap}, rows, topic)
    assert view['question_states']['AIR-01']['status'] == 'saved'
    assert view['areas'][0]['recorded'] == 1
    rows.append(dict(id=uuid4(), payload={**payload, 'option_ids': [q['options'][1]['id']]},
                     supersedes_id=rows[0]['id'], created_revision=3))
    changed = template_projection({'intake_snapshot': snap}, rows, topic)
    assert changed['question_states']['AIR-01']['option_ids'] == [q['options'][1]['id']]
    assert changed['areas'][0]['recorded'] == 1


def test_template_synthesis_keeps_current_facts_issues_and_in_scope_conflicts():
    relation, topic = next((r, t) for r, t in build_templates() if r['fault_code'] == 'P0236')
    snap = frozen_snapshot(Connection(relation, topic), body('P0236'))
    rows = [
        dict(id=uuid4(), payload=dict(question_id='AIR-07', option_ids=['seated'], fields={}, round_id=None),
             supersedes_id=None, created_revision=2),
        dict(id=uuid4(), payload=dict(question_id='AIR-08', option_ids=['pulls_out'], fields={}, round_id=None),
             supersedes_id=None, created_revision=3),
    ]
    synthesis = template_projection({'intake_snapshot': snap}, rows, topic)['synthesis']
    assert any(item['question_id'] == 'AIR-07' for item in synthesis['facts'])
    assert any(item['question_id'] == 'AIR-08' for item in synthesis['issues'])
    assert [item['id'] for item in synthesis['conflicts']] == ['joint-seating-tension']
    assert all(item['question_id'] in {q['id'] for q in topic['questions']}
               for name in ('facts', 'issues', 'unavailable') for item in synthesis[name])
