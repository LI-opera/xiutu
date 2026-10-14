from sqlalchemy import select

from app.infrastructure.orm import run_events, runs


def append_event(conn, run_id, kind, payload=None):
    # All writers serialize on this row BEFORE allocating the identity ID.
    row = conn.execute(select(runs).where(runs.c.id == run_id).with_for_update()).mappings().one()
    return conn.execute(
        run_events.insert()
        .values(run_id=run_id, case_id=row["case_id"], type=kind, payload=payload or {})
        .returning(run_events.c.id)
    ).scalar_one()
