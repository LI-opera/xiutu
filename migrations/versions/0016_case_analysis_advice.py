"""Persist frozen, source-bounded case advice separately from final reports."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0016_case_analysis_advice"
down_revision = "0015_r1_flow_02_intake_snapshot"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "case_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("input_revision", sa.BigInteger(), nullable=False),
        sa.Column("topic_version", sa.String(32), nullable=False),
        sa.Column("topic_hash", sa.String(64), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("allowed_scope", sa.String(32), nullable=False),
        sa.Column("dispatch_state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("snapshot_json", JSONB(), nullable=False),
        sa.Column("content_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", name="uq_case_analysis_run"),
        sa.CheckConstraint("status IN ('draft','current','failed')", name="ck_case_analysis_status"),
        sa.CheckConstraint("mode IN ('stub','real')", name="ck_case_analysis_mode"),
        sa.CheckConstraint("dispatch_state IN ('pending','reserved','completed')", name="ck_case_analysis_dispatch"),
        sa.CheckConstraint("input_revision>=0 AND topic_hash ~ '^[0-9a-f]{64}$' AND context_hash ~ '^[0-9a-f]{64}$' AND jsonb_typeof(snapshot_json)='object' AND jsonb_typeof(content_json)='object'", name="ck_case_analysis_shape"),
    )
    op.create_index("ix_case_analyses_case_created", "case_analyses", ["case_id", "created_at", "id"])


def downgrade():
    op.drop_index("ix_case_analyses_case_created", table_name="case_analyses")
    op.drop_table("case_analyses")
