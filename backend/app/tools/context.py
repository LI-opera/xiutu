import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select

from app.domain.policies import DomainError, check_revision
from app.infrastructure.orm import runs, tool_executions
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import owned_case, owner_lock, source
from app.tools.schemas import INPUTS


@dataclass(frozen=True)
class ToolContext:
    execution_id: UUID
    capability: str = field(repr=False)
    auth: object = field(repr=False, compare=False)
    cookie: str = field(repr=False)


class ContextFactory:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    def open(
        self,
        auth,
        cookie,
        case_id,
        *,
        run_id=None,
        allowlist=None,
        call_limit=8,
        search_limit=3,
        timeout_ms=10000,
        retry_limit=1,
    ):
        principal = auth.get(cookie)
        allowlist = list(INPUTS) if allowlist is None else list(allowlist)
        if not set(allowlist) <= set(INPUTS) or len(allowlist) != len(set(allowlist)):
            raise ValueError("Invalid server allowlist")
        for v, low, high in [
            (call_limit, 1, 20),
            (search_limit, 0, 10),
            (timeout_ms, 50, 10000),
            (retry_limit, 0, 1),
        ]:
            if type(v) is not int or not low <= v <= high:
                raise ValueError("Invalid server budget")
        cap = secrets.token_urlsafe(32)
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, principal.actor_id)
            case = owned_case(c, principal.actor_id, case_id)
            if run_id is not None:
                run = (
                    c.execute(select(runs).where(runs.c.id == run_id, runs.c.case_id == case_id))
                    .mappings()
                    .one_or_none()
                )
                if run is None:
                    raise DomainError("NOT_FOUND", "Run not owned", 404)
            eid = c.execute(
                tool_executions.insert()
                .values(
                    actor_id=principal.actor_id,
                    case_id=case_id,
                    run_id=run_id,
                    capability_hash=hashlib.sha256(cap.encode()).hexdigest(),
                    revision=case["revision"],
                    manifest=case["corpus_manifest"],
                    profile=self.settings.retrieval_profile,
                    allowlist=allowlist,
                    call_limit=call_limit,
                    search_limit=search_limit,
                    timeout_ms=timeout_ms,
                    retry_limit=retry_limit,
                )
                .returning(tool_executions.c.id)
            ).scalar_one()
        return ToolContext(eid, cap, auth, cookie)

    def load(self, c, context, *, lock=False, current=True):
        if not isinstance(context, ToolContext):
            raise DomainError("CONTEXT_INVALID", "Trusted context required", 403)
        principal = context.auth.get(context.cookie)
        q = select(tool_executions).where(tool_executions.c.id == context.execution_id)
        if lock:
            q = q.with_for_update()
        row = c.execute(q).mappings().one_or_none()
        if (
            row is None
            or row["actor_id"] != principal.actor_id
            or not hmac.compare_digest(
                row["capability_hash"], hashlib.sha256(context.capability.encode()).hexdigest()
            )
        ):
            raise DomainError("CONTEXT_INVALID", "Context not authorized", 403)
        case = owned_case(c, principal.actor_id, row["case_id"])
        if current:
            validate_scope(c, row, case, self.settings.retrieval_profile)
        return row, case


def validate_scope(c, row, case, profile):
    check_revision(case["revision"], row["revision"])
    if row["manifest"] != case["corpus_manifest"] or row["profile"] != profile:
        raise DomainError("CONTEXT_STALE", "Context scope changed")
    for x in row["manifest"]:
        source(
            c,
            row["actor_id"],
            case,
            UUID(x["document_version_id"]),
            UUID(x["index_id"]),
            row["profile"],
        )
