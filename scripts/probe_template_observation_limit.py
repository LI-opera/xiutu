"""Rollback-only check of template answers crossing the legacy 50-row boundary."""
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4
from sqlalchemy import create_engine, select, func
from scripts.wp15_workbench import STATE, environment
from app.infrastructure.db_target import validate_target
from app.infrastructure.orm import cases, observations
from app.services.case_service import CaseService
from app.services.workbench_b01_service import TopicService, TopicAnswer

state = json.loads(STATE.read_text(encoding='utf-8'))
env = environment(state, ranking_local_testing=False)
target = validate_target(env['DATABASE_URL'], 'test')
engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
cid = UUID('18a144fe-dfa2-4d44-8824-11388d26fa9a')
actor = UUID(state['actor'])
service = TopicService(CaseService(engine, b'probe', 'synthetic', SimpleNamespace(retrieval_profile='synthetic')))
with engine.connect() as conn:
    transaction = conn.begin()
    class ProbeUow:
        def __init__(self, *_): self.connection = conn
        def __enter__(self): return self
        def __exit__(self, *_): pass
    try:
        before_revision = conn.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one()
        before_count = conn.execute(select(func.count()).select_from(observations).where(observations.c.case_id == cid)).scalar_one()
        with patch('app.services.workbench_b01_service.UnitOfWork', ProbeUow):
            view = service.get(actor, cid)
            before_gate = view['case']['report_gate']
            counts = []
            for qid in ['X-11', 'X-12', 'X-14']:
                q = next(q for q in view['topic']['questions'] if q['id'] == qid)
                old = next((r for r in view['observations'] if r['effective'] and r['question_id'] == qid), None)
                body = TopicAnswer(expected_revision=view['case']['revision'], topic_version=view['topic']['version'], question_id=qid,
                    option_ids=[q['options'][0]['id']], note='事务内回归测试，非实测；全部回滚')
                status, result = service.save(actor, cid, body, 'limit-probe-' + uuid4().hex,
                    original_id=UUID(old['id']) if old else None)
                assert status == 200
                view = result['view']
                counts.append(sum(r['effective'] for r in view['observations']))
            assert counts[-1] > 50
            assert service.get(actor, cid)['case']['revision'] == view['case']['revision']
            assert view['case']['report_gate'] == before_gate
            print(json.dumps({'effective_counts': counts, 'save_and_readback': True, 'report_gate_unchanged': True}))
    finally:
        transaction.rollback()
    assert conn.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == before_revision
    assert conn.execute(select(func.count()).select_from(observations).where(observations.c.case_id == cid)).scalar_one() == before_count
    print(json.dumps({'rollback_verified': True, 'persisted_revision': before_revision, 'model_calls': 0}))
engine.dispose()
