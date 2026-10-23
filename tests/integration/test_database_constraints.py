import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from app.domain.enums import CaseStatus
from app.infrastructure.orm import cases, jobs, runs
from app.infrastructure.uow import make_engine
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.database


@pytest.fixture
def engine(database_url):
    e = make_engine(database_url)
    try:
        yield e
    finally:
        e.dispose()


def case_id(engine):
    with engine.begin() as c:
        return c.execute(insert(cases).values(
            owner_id=uuid4(), vehicle_json={"model": "synthetic"}, fault_description="constraint",
        ).returning(cases.c.id)).scalar_one()


def test_active_run_true_concurrency(engine):
    case = case_id(engine)
    barrier = threading.Barrier(2)

    def attempt(_):
        try:
            with engine.begin() as c:
                barrier.wait(timeout=10)
                value = c.execute(
                    insert(runs)
                    .values(case_id=case, kind="synthetic", status="queued")
                    .returning(runs.c.id)
                ).scalar_one()
            return "ok", value
        except IntegrityError:
            return "conflict", None

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(attempt, range(2)))
    assert sorted(x[0] for x in result) == ["conflict", "ok"]
    with engine.begin() as c:
        assert c.scalar(select(func.count()).select_from(runs).where(runs.c.case_id == case)) == 1
        c.execute(runs.update().where(runs.c.case_id == case).values(status="waiting_input"))
        new = c.execute(
            insert(runs)
            .values(case_id=case, kind="synthetic", status="running")
            .returning(runs.c.id)
        ).scalar_one()
        c.execute(insert(jobs).values(run_id=new, kind="synthetic"))
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(insert(jobs).values(run_id=new, kind="synthetic"))
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(insert(runs).values(case_id=case, kind="synthetic", status="cancel_requested"))
    with engine.begin() as c:
        c.execute(insert(runs).values(case_id=None, kind="synthetic", status="queued"))
        c.execute(insert(runs).values(case_id=None, kind="synthetic", status="queued"))
    print(
        "active-run concurrency: one committed, one unique conflict; waiting_input releases slot; jobs.run_id unique"
    )


def test_enum_checks_and_ranges(engine):
    for table, column, enum in [
        (cases, "status", CaseStatus),
    ]:
        expression = " ".join(str(x.sqltext) for x in table.constraints if hasattr(x, "sqltext"))
        for value in enum:
            assert repr(value.value) in expression
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(
            insert(cases).values(
                owner_id=uuid4(), vehicle_json={}, fault_description="x", status="invalid"
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(
            insert(cases).values(
                owner_id=uuid4(), vehicle_json={}, fault_description="x", revision=-1
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(insert(runs).values(case_id=uuid4(), kind="synthetic"))


def test_actual_database_checks_match_enums(engine):
    from sqlalchemy import inspect

    inspector = inspect(engine)
    for table, enum, name in [
        ("cases", CaseStatus, "ck_cases_status"),
    ]:
        constraints = {x["name"]: x["sqltext"] for x in inspector.get_check_constraints(table)}
        for value in enum:
            assert "'" + value.value + "'" in constraints[name]


def test_database_error_rolls_back_uow(engine):
    from app.infrastructure.uow import UnitOfWork

    actor = uuid4()
    with pytest.raises(IntegrityError):
        with UnitOfWork(engine) as uow:
            uow.connection.execute(
                insert(cases).values(owner_id=actor, vehicle_json={}, fault_description="rollback")
            )
            uow.connection.execute(insert(runs).values(kind="synthetic", status="invalid"))
    with engine.connect() as c:
        assert (
            c.scalar(select(func.count()).select_from(cases).where(cases.c.owner_id == actor)) == 0
        )
