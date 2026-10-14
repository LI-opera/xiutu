"""Template case progress and user-controlled closure, separate from repair conclusions."""
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from app.infrastructure.orm import cases, observations, template_repair_rounds
from app.infrastructure.uow import UnitOfWork
from app.services.run_service import lock_case
from app.services.workbench_templates import is_template
from app.domain.policies import DomainError


def is_closed(case):
    return is_template(case) and bool((case.get('intake_snapshot') or {}).get('case_lifecycle', {}).get('closed'))


def require_open(case):
    if is_closed(case):
        raise DomainError('CASE_CLOSED', '此病例已结束，请先点击“继续此病例”再保存新记录。', 409)


def summarize(case, records, rounds):
    questions = [q for q in case['intake_snapshot']['template_content']['questions']
                 if q.get('area_id') and q['answer_kind'] != 'automatic_derived']
    superseded = {str(o['supersedes_id']) for o in records if o.get('supersedes_id')}
    effective = {o['payload'].get('question_id') for o in records if str(o['id']) not in superseded}
    recorded = sum(q['id'] in effective for q in questions)
    pending = sum(not item['retested_at'] for item in rounds)
    closed = is_closed(case)
    state = 'closed' if closed else 'retest_pending' if pending else 'retested' if rounds else 'checking' if recorded else 'not_started'
    labels = {'closed':'用户已结束', 'retest_pending':'待复检', 'retested':'已复检 · 待确认', 'checking':'检查中', 'not_started':'尚未检查'}
    latest = rounds[0] if rounds else None
    return {'state': state, 'label': labels[state], 'closed': closed, 'recorded': recorded, 'total':len(questions),
            'pending_retests':pending, 'repair_rounds':len(rounds),
            'latest_repair': latest['repair_action'] if latest else None,
            'latest_retest_outcome':latest['retest_outcome'] if latest else None}


def load_summary(conn, case):
    records = conn.execute(select(observations.c.id, observations.c.supersedes_id, observations.c.payload)
                           .where(observations.c.case_id == case['id'])).mappings().all()
    rounds = conn.execute(select(template_repair_rounds).where(template_repair_rounds.c.case_id == case['id'])
                          .order_by(template_repair_rounds.c.created_at.desc(), template_repair_rounds.c.id.desc())).mappings().all()
    return summarize(case, records, rounds)


def set_closed(engine, actor, case_id, revision, closed):
    with UnitOfWork(engine) as uow:
        case = lock_case(uow.connection, actor, case_id, revision)
        if not is_template(case):
            raise DomainError('TEMPLATE_REQUIRED', '此入口仅用于模板病例。', 422)
        if is_closed(case) != closed:
            snap = dict(case['intake_snapshot'])
            prior = snap.get('case_lifecycle', {})
            event = {'closed':closed, 'at':datetime.now(timezone.utc).isoformat(), 'actor_id':str(actor)}
            snap['case_lifecycle'] = {**event, 'events':[*prior.get('events', []), event]}
            uow.connection.execute(update(cases).where(cases.c.id == case_id).values(
                intake_snapshot=snap, revision=case['revision']+1, updated_at=func.now()))
    return {'closed':closed}
