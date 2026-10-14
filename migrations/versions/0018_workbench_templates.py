"""Versioned complete inspection templates and explicit vehicle/DTC relations."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0018_workbench_templates"
down_revision = "0017_case_analysis_diagnostics"
branch_labels = depends_on = None


def upgrade():
    op.create_table("workbench_templates",
        sa.Column("template_id", sa.String(80), primary_key=True),
        sa.Column("version", sa.String(40), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_json", JSONB, nullable=False))
    op.create_table("workbench_template_matches",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year_from", sa.Integer, nullable=False),
        sa.Column("year_to", sa.Integer, nullable=False),
        sa.Column("engine_code", sa.String(64), nullable=False),
        sa.Column("fault_code", sa.String(32), nullable=False),
        sa.Column("template_id", sa.String(80), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["template_id", "version"],
                                ["workbench_templates.template_id", "workbench_templates.version"]),
        sa.CheckConstraint("year_from <= year_to"))
    op.create_index("ix_workbench_match_vehicle_code", "workbench_template_matches",
                    ["brand", "model", "fault_code"])


def downgrade():
    op.drop_table("workbench_template_matches")
    op.drop_table("workbench_templates")
