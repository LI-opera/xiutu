"""Immutable source versions and review history; no indexes for retrieval."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004_documents"
down_revision = "0003_jobs"
branch_labels = depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("owner_id", UUID(as_uuid=True)))
    op.create_index(
        "ix_documents_owner_order",
        "documents",
        ["owner_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    for column in [
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("current_run_id", UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("chunker_version", sa.String(100)),
        sa.Column("tokenizer", sa.String(100)),
        sa.Column("page_count", sa.Integer),
        sa.Column("page_issues", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("parse_error", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    ]:
        op.add_column("document_versions", column)
    op.create_foreign_key(
        "fk_version_current_run",
        "document_versions",
        "runs",
        ["current_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_document_pages", "document_versions", "page_count IS NULL OR page_count>=1"
    )
    op.drop_constraint("ck_document_parse", "document_versions", type_="check")
    op.create_check_constraint(
        "ck_document_parse",
        "document_versions",
        "parse_status IN ('pending','parsing','review_pending','needs_ocr','failed','cancelled')",
    )
    op.add_column(
        "chunks",
        sa.Column("locator_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "chunks", sa.Column("token_count", sa.Integer, nullable=False, server_default="0")
    )
    op.create_check_constraint("ck_chunk_tokens", "chunks", "token_count>=0")
    op.create_table(
        "document_reviews",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "document_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("review_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved','rejected','revoked')", name="ck_review_decision"
        ),
    )


def downgrade():
    op.drop_table("document_reviews")
    op.drop_constraint("ck_chunk_tokens", "chunks", type_="check")
    op.drop_column("chunks", "token_count")
    op.drop_column("chunks", "locator_json")
    op.drop_constraint("ck_document_parse", "document_versions", type_="check")
    op.execute("UPDATE document_versions SET parse_status='failed' WHERE parse_status='cancelled'")
    op.create_check_constraint(
        "ck_document_parse",
        "document_versions",
        "parse_status IN ('pending','parsing','review_pending','needs_ocr','failed')",
    )
    op.drop_constraint("fk_version_current_run", "document_versions", type_="foreignkey")
    op.drop_constraint("ck_document_pages", "document_versions", type_="check")
    for name in [
        "metadata_json",
        "current_run_id",
        "created_at",
        "chunker_version",
        "tokenizer",
        "page_count",
        "page_issues",
        "parse_error",
    ]:
        op.drop_column("document_versions", name)
    op.drop_index("ix_documents_owner_order", "documents")
    op.drop_column("documents", "owner_id")
