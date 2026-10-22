"""Area reference documents become an ingest pipeline: processing state, stored chunks, vectors."""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "0024_reference_ingest"
down_revision = "0023_template_repair_retest"
branch_labels = depends_on = None

DOC_KEY = ["document_id", "version"]
DOC_REF = ["area_reference_documents.document_id", "area_reference_documents.version"]


def upgrade():
    # Existing rows were imported by script and are already in use: they stay "ready".
    op.add_column("area_reference_documents",
                  sa.Column("source_kind", sa.String(16), nullable=False, server_default="seed"))
    op.add_column("area_reference_documents",
                  sa.Column("status", sa.String(16), nullable=False, server_default="ready"))
    op.add_column("area_reference_documents", sa.Column("error_code", sa.String(80)))
    op.add_column("area_reference_documents", sa.Column("chunker_version", sa.String(40)))
    op.add_column("area_reference_documents", sa.Column("chunk_count", sa.Integer))
    op.add_column("area_reference_documents", sa.Column("vector_fingerprint", sa.String(80)))
    op.add_column("area_reference_documents",
                  sa.Column("always_include", JSONB, nullable=False, server_default="[]"))
    op.add_column("area_reference_documents",
                  sa.Column("requested_areas", JSONB, nullable=False, server_default="[]"))
    op.add_column("area_reference_documents",
                  sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                            server_default=sa.func.now()))
    op.create_check_constraint("ck_reference_source_kind", "area_reference_documents",
                               "source_kind IN ('seed','upload')")
    op.create_check_constraint("ck_reference_status", "area_reference_documents",
                               "status IN ('queued','processing','ready','failed')")
    op.create_check_constraint("ck_reference_chunk_count", "area_reference_documents",
                               "chunk_count IS NULL OR chunk_count >= 0")

    op.create_table(
        "area_reference_chunks",
        sa.Column("document_id", sa.String(100), primary_key=True),
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        sa.Column("section", sa.Text, nullable=False),
        sa.Column("subsection", sa.Text),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_start", sa.Integer, nullable=False),
        sa.Column("char_end", sa.Integer, nullable=False),
        sa.Column("identifiers", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("searchable", sa.Boolean, nullable=False),
        sa.Column("search_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(DOC_KEY, DOC_REF, ondelete="RESTRICT"),
        sa.CheckConstraint("ordinal >= 0 AND char_start >= 0 AND char_end > char_start",
                           name="ck_reference_chunk_range"),
        sa.CheckConstraint("search_hash ~ '^[0-9a-f]{64}$'", name="ck_reference_chunk_hash"),
    )
    op.create_index("ix_reference_chunk_identifiers", "area_reference_chunks", ["identifiers"],
                    postgresql_using="gin")

    op.create_table(
        "area_reference_chunk_vectors",
        sa.Column("document_id", sa.String(100), primary_key=True),
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        sa.Column("fingerprint", sa.String(80), primary_key=True),
        sa.Column("search_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.ForeignKeyConstraint(DOC_KEY + ["ordinal"],
                                ["area_reference_chunks.document_id",
                                 "area_reference_chunks.version", "area_reference_chunks.ordinal"],
                                ondelete="CASCADE"),
        sa.CheckConstraint("vector_norm(embedding) > 0", name="ck_reference_vector_nonzero"),
    )


def downgrade():
    op.drop_table("area_reference_chunk_vectors")
    op.drop_index("ix_reference_chunk_identifiers", table_name="area_reference_chunks")
    op.drop_table("area_reference_chunks")
    for name in ("ck_reference_chunk_count", "ck_reference_status", "ck_reference_source_kind"):
        op.drop_constraint(name, "area_reference_documents", type_="check")
    for column in ("updated_at", "requested_areas", "always_include", "vector_fingerprint",
                   "chunk_count", "chunker_version", "error_code", "status", "source_kind"):
        op.drop_column("area_reference_documents", column)
