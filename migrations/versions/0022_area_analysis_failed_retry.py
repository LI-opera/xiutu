"""Allow a new manual attempt after a terminal failure without losing history."""
import sqlalchemy as sa
from alembic import op

revision = "0022_area_analysis_failed_retry"
down_revision = "0021_area_input_identity"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint("uq_area_analysis_input", "area_analysis_attempts", type_="unique")
    op.create_index("uq_area_analysis_active_input", "area_analysis_attempts",
        ["case_id", "area_id", "input_hash"], unique=True,
        postgresql_where=sa.text("status IN ('running', 'completed')"))


def downgrade():
    conn = op.get_bind()
    duplicates = conn.execute(sa.text("""
        SELECT 1 FROM area_analysis_attempts
        GROUP BY case_id, area_id, input_hash HAVING COUNT(*) > 1 LIMIT 1
    """)).first()
    if duplicates:
        raise RuntimeError("Cannot restore the old unique constraint while retry history exists")
    op.drop_index("uq_area_analysis_active_input", table_name="area_analysis_attempts")
    op.create_unique_constraint("uq_area_analysis_input", "area_analysis_attempts",
        ["case_id", "area_id", "input_hash"])
