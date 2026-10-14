"""Store one semantic ordering attempt per template-bound case."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision = "0019_case_area_rankings"
down_revision = "0018_workbench_templates"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "case_area_rankings",
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("input_json", JSONB, nullable=False),
        sa.Column("result_json", JSONB),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('running','completed','failed')", name="ck_case_area_rankings_status"),
    )


def downgrade():
    op.drop_table("case_area_rankings")
