"""Versioned area references and independent area analysis attempts."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision = "0020_area_analysis"
down_revision = "0019_case_area_rankings"
branch_labels = depends_on = None


def upgrade():
    op.create_table("area_reference_documents",
        sa.Column("document_id", sa.String(100), primary_key=True),
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("provenance", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("area_reference_bindings",
        sa.Column("template_id", sa.String(100), primary_key=True),
        sa.Column("template_version", sa.String(32), primary_key=True),
        sa.Column("area_id", sa.String(80), primary_key=True),
        sa.Column("document_id", sa.String(100), primary_key=True),
        sa.Column("document_version", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["document_id", "document_version"],
            ["area_reference_documents.document_id", "area_reference_documents.version"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id", "template_version"],
            ["workbench_templates.template_id", "workbench_templates.version"], ondelete="RESTRICT"))
    op.create_table("area_analysis_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("area_id", sa.String(80), nullable=False),
        sa.Column("input_revision", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("input_json", JSONB, nullable=False),
        sa.Column("result_json", JSONB),
        sa.Column("diagnostic_json", JSONB),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("case_id", "area_id", "input_revision", name="uq_area_analysis_revision"),
        sa.CheckConstraint("status IN ('running','completed','failed')", name="ck_area_analysis_status"))


def downgrade():
    op.drop_table("area_analysis_attempts")
    op.drop_table("area_reference_bindings")
    op.drop_table("area_reference_documents")
