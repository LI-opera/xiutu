from sqlalchemy import select

from app.domain.policies import DomainError
from app.infrastructure.orm import run_events


def check_cursor(conn, run_id, raw):
    if raw is None:
        return 0
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 19:
        raise DomainError("INVALID_CURSOR", "Invalid event cursor", 400)
    value = int(raw)
    if value == 0:
        return 0
    if (
        value > 9223372036854775807
        or conn.execute(
            select(run_events.c.id).where(run_events.c.run_id == run_id, run_events.c.id == value)
        ).scalar_one_or_none()
        is None
    ):
        raise DomainError("INVALID_CURSOR", "Invalid event cursor", 400)
    return value


def read_events(conn, run_id, cursor, limit=100):
    return [
        dict(x)
        for x in conn.execute(
            select(run_events.c.id, run_events.c.type, run_events.c.payload)
            .where(run_events.c.run_id == run_id, run_events.c.id > cursor)
            .order_by(run_events.c.id)
            .limit(limit)
        ).mappings()
    ]
