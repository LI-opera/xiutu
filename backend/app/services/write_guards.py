"""Guards every write to a case goes through: row lock + revision check, and idempotency keys."""
import hashlib
import json
import re

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.domain.policies import DomainError, check_revision
from app.infrastructure.orm import cases, idempotency_keys


def lock_case(conn, actor, identifier, revision=None):
    row = (
        conn.execute(
            select(cases)
            .where(cases.c.id == identifier, cases.c.owner_id == actor)
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DomainError("NOT_FOUND", "Case not found", 404)
    if revision is not None:
        check_revision(row["revision"], revision)
    return row


def idempotent(conn, actor, scope, key, body, action):
    if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
        raise DomainError("VALIDATION_ERROR", "Valid Idempotency-Key required", 422)
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    match = (
        idempotency_keys.c.actor_id == actor,
        idempotency_keys.c.route_scope == scope,
        idempotency_keys.c.key == key,
    )
    won = conn.execute(
        insert(idempotency_keys)
        .values(
            actor_id=actor,
            route_scope=scope,
            key=key,
            request_hash=digest,
            response_status=202,
            response_json={},
        )
        .on_conflict_do_nothing(index_elements=["actor_id", "route_scope", "key"])
        .returning(idempotency_keys.c.key)
    ).scalar_one_or_none()
    if won is None:
        saved = conn.execute(select(idempotency_keys).where(*match)).mappings().one()
        if saved["request_hash"] != digest:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT", "Idempotency key belongs to a different request"
            )
        return saved["response_status"], saved["response_json"]
    status, response = action()
    conn.execute(
        update(idempotency_keys)
        .where(*match)
        .values(response_status=status, response_json=response)
    )
    return status, response
