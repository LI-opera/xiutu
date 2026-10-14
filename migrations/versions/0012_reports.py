"""WP-13 report requests and immutable report revisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0012_reports"
down_revision = "0011_area_closure"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint("ck_area_conclusion_assessment", "diagnosis_area_conclusions", type_="check")
    op.create_check_constraint("ck_area_conclusion_assessment", "diagnosis_area_conclusions",
        "assessment IN ('hypothesis','temporarily_excluded','unknown','conflicting','needs_input','supported','ruled_out')")
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("input_revision", sa.BigInteger(), nullable=False),
        sa.Column("graph_epoch", sa.Integer(), nullable=False),
        sa.Column("manifest_json", JSONB(), nullable=False),
        sa.Column("conclusion_ids", JSONB(), nullable=False),
        sa.Column("content_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("stale_reason", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", name="uq_report_run"),
        sa.CheckConstraint("kind IN ('progress','final')", name="ck_report_kind"),
        sa.CheckConstraint("status IN ('draft','current','stale','failed')", name="ck_report_status"),
        sa.CheckConstraint("input_revision>=0 AND graph_epoch>=0 AND jsonb_typeof(manifest_json)='array' AND jsonb_typeof(conclusion_ids)='array' AND jsonb_typeof(content_json)='object'", name="ck_report_shape"),
    )
    op.create_index("ix_reports_case_created", "reports", ["case_id", "created_at"])


def downgrade():
    op.drop_index("ix_reports_case_created", table_name="reports")
    op.drop_table("reports")
    op.drop_constraint("ck_area_conclusion_assessment", "diagnosis_area_conclusions", type_="check")
    op.create_check_constraint("ck_area_conclusion_assessment", "diagnosis_area_conclusions",
        "assessment IN ('hypothesis','temporarily_excluded','unknown','conflicting','needs_input')")
