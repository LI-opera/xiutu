"""Store actual template-case treatment separately from independent retest."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0023_template_repair_retest"
down_revision = "0022_area_analysis_failed_retry"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "template_repair_rounds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("area_id", sa.String(80), nullable=False),
        sa.Column("repair_action", sa.Text, nullable=False),
        sa.Column("repair_note", sa.Text, nullable=False, server_default=""),
        sa.Column("pre_repair_revision", sa.BigInteger, nullable=False),
        sa.Column("retest_condition", sa.String(24)),
        sa.Column("retest_outcome", sa.String(24)),
        sa.Column("retest_evidence", sa.Text),
        sa.Column("next_area_id", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("retested_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("length(trim(repair_action)) > 0", name="ck_template_repair_action"),
        sa.CheckConstraint("retest_condition IN ('same','different','unavailable')", name="ck_template_retest_condition"),
        sa.CheckConstraint("retest_outcome IN ('resolved','persists','uncertain')", name="ck_template_retest_outcome"),
    )
    op.create_index("ix_template_repair_case_order", "template_repair_rounds", ["case_id", "created_at"])


def downgrade():
    op.drop_index("ix_template_repair_case_order", table_name="template_repair_rounds")
    op.drop_table("template_repair_rounds")
