"""WP09 model-specific dimensions; retain existing generations and frozen indexes."""

import sqlalchemy as sa
from alembic import op

revision = "0008_model_indexes"
down_revision = "0007_tools"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint("ck_index_shape", "index_versions", type_="check")
    op.create_check_constraint(
        "ck_index_shape", "index_versions", "dimension IN (384,1024) AND chunk_count>0"
    )
    op.execute(
        "ALTER TABLE chunk_embeddings ALTER COLUMN embedding TYPE vector USING embedding::vector"
    )
    op.execute("""CREATE FUNCTION check_embedding_dimension() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF vector_dims(NEW.embedding) IS DISTINCT FROM (SELECT dimension FROM index_versions WHERE id=NEW.index_id) THEN
        RAISE EXCEPTION 'embedding dimension mismatch' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER embedding_dimension BEFORE INSERT OR UPDATE ON chunk_embeddings FOR EACH ROW EXECUTE FUNCTION check_embedding_dimension()"
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS(SELECT 1 FROM index_versions WHERE dimension<>384)"))
        .scalar()
    ):
        raise RuntimeError("Cannot downgrade while non-E5 indexes exist; no data removed")
    op.execute("DROP TRIGGER embedding_dimension ON chunk_embeddings")
    op.execute("DROP FUNCTION check_embedding_dimension()")
    op.execute(
        "ALTER TABLE chunk_embeddings ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384)"
    )
    op.drop_constraint("ck_index_shape", "index_versions", type_="check")
    op.create_check_constraint(
        "ck_index_shape", "index_versions", "dimension=384 AND chunk_count>0"
    )
