"""Explicit task ownership and queue/event lookup indexes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_jobs"
down_revision = "0002_core"
branch_labels = depends_on = None


def upgrade():
    op.add_column("runs", sa.Column("owner_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_jobs_due", "jobs", ["status", "available_at", "lease_until"])
    op.create_index("ix_run_events_order", "run_events", ["run_id", "id"])


def downgrade():
    op.drop_index("ix_run_events_order", table_name="run_events")
    op.drop_index("ix_jobs_due", table_name="jobs")
    op.drop_column("runs", "owner_id")
