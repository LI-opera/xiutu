from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.domain.policies import DomainError
from app.infrastructure.model_factory import selected_config
from app.infrastructure.orm import chunks
from app.infrastructure.orm import index_versions as indexes
from app.infrastructure.uow import UnitOfWork
from app.retrieval.eligibility import exclusion
from app.services.run_service import enqueue, idempotent


def schedule(c, actor, version, profile, settings=None):
    from app.config import Settings

    config = selected_config(settings or Settings())
    reason = exclusion(version, profile)
    if reason:
        raise DomainError(
            "INDEX_NOT_ELIGIBLE",
            "Version is not eligible for this server profile",
            details={"reason": reason},
        )
    if c.execute(
        select(indexes.c.id).where(
            indexes.c.document_version_id == version["id"], indexes.c.status == "building"
        )
    ).first():
        raise DomainError("INDEX_BUILDING", "A build is already in progress")
    count = c.execute(
        select(func.count())
        .select_from(chunks)
        .where(chunks.c.document_version_id == version["id"])
    ).scalar_one()
    if not count:
        raise DomainError("INDEX_EMPTY", "No parsed chunks")
    iid = uuid4()
    _, run = enqueue(c, actor, "index", dict(index_id=str(iid), version_id=str(version["id"])))
    c.execute(
        indexes.insert().values(
            id=iid,
            document_version_id=version["id"],
            run_id=UUID(run["run_id"]),
            status="building",
            profile=profile,
            dimension=config["dimension"],
            config_json=config,
            chunk_count=count,
        )
    )
    return dict(index_id=str(iid), run_id=run["run_id"], status="building")


class IndexService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    def reindex(self, actor, document_id, version_id, body, key):
        from app.services.document_service import owned

        with UnitOfWork(self.engine) as u:
            c = u.connection
            owned(c, actor, document_id, version_id)

            def action():
                version = owned(c, actor, document_id, version_id, lock=True)
                if (
                    body.config_version is not None
                    and body.config_version != selected_config(self.settings)["config_version"]
                ):
                    raise DomainError(
                        "INDEX_CONFIG_UNSUPPORTED", "Unsupported index configuration", 422
                    )
                return 202, schedule(
                    c, actor, version, self.settings.retrieval_profile, self.settings
                )

            return idempotent(
                c, actor, "reindex:" + str(version_id), key, body.model_dump(mode="json"), action
            )
