"""WP05 immutable model-specific index generations; frozen schema."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0005_indexes"
down_revision = "0004_documents"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "document_versions",
        sa.Column("review_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.execute("""UPDATE document_versions v SET review_snapshot = r.review_json FROM
        (SELECT DISTINCT ON (document_version_id) document_version_id, review_json
         FROM document_reviews ORDER BY document_version_id, created_at DESC, id DESC) r
        WHERE v.id=r.document_version_id""")
    op.create_table(
        "index_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("profile", sa.String(16), nullable=False),
        sa.Column("dimension", sa.Integer, nullable=False),
        sa.Column("config_json", JSONB, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("error_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("status IN ('building','ready','failed')", name="ck_index_status"),
        sa.CheckConstraint("profile IN ('formal','synthetic')", name="ck_index_profile"),
        sa.CheckConstraint("dimension=384 AND chunk_count>0", name="ck_index_shape"),
        sa.UniqueConstraint("id", "document_version_id", name="uq_index_version_pair"),
    )
    op.create_index(
        "uq_index_building",
        "index_versions",
        ["document_version_id"],
        unique=True,
        postgresql_where=sa.text("status='building'"),
    )
    op.add_column("document_versions", sa.Column("active_index_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_active_index_version",
        "document_versions",
        "index_versions",
        ["active_index_id", "id"],
        ["id", "document_version_id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "chunk_embeddings",
        sa.Column(
            "index_id",
            UUID(as_uuid=True),
            sa.ForeignKey("index_versions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "chunk_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.CheckConstraint("vector_norm(embedding)>0", name="ck_embedding_nonzero"),
    )


def downgrade():
    op.drop_table("chunk_embeddings")
    op.drop_constraint("fk_active_index_version", "document_versions", type_="foreignkey")
    op.drop_column("document_versions", "active_index_id")
    op.drop_index("uq_index_building", table_name="index_versions")
    op.drop_table("index_versions")
    op.drop_column("document_versions", "review_snapshot")
