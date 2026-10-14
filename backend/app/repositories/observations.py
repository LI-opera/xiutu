from sqlalchemy import exists, select

from app.domain.policies import DomainError
from app.infrastructure.orm import observations


class ObservationRepository:
    def __init__(self, connection):
        self.connection = connection

    def read(self, case_id, area_id, revision, *, max_results=50):
        later = observations.alias("later")
        q = select(observations).where(
            observations.c.case_id == case_id,
            observations.c.created_revision <= revision,
            ~exists(
                select(later.c.id).where(
                    later.c.supersedes_id == observations.c.id, later.c.created_revision <= revision
                )
            ),
        )
        if area_id is not None:
            q = q.where(observations.c.area_id == area_id)
        ordered = q.order_by(observations.c.created_revision, observations.c.id)
        rows = self.connection.execute(
            ordered.limit(max_results + 1) if max_results is not None else ordered
        ).mappings().all()
        if max_results is not None and len(rows) > max_results:
            raise DomainError("RESULT_TOO_LARGE", "Observation result exceeds limit", 422)
        return rows
