"""Deduplicate and age advice by scoped inputs, not unrelated case edits."""
import hashlib
import json
import sqlalchemy as sa
from alembic import op

revision = "0021_area_input_identity"
down_revision = "0020_area_analysis"
branch_labels = depends_on = None


def upgrade():
    op.add_column("area_analysis_attempts", sa.Column("input_hash", sa.String(64)))
    conn = op.get_bind()
    for row in conn.execute(sa.text("select id, input_json from area_analysis_attempts")).mappings():
        payload = {k: v for k, v in row["input_json"].items() if k not in {"case_revision", "max_output_tokens"}}
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
        conn.execute(sa.text("update area_analysis_attempts set input_hash=:digest where id=:id"),
                     {"digest": digest, "id": row["id"]})
    op.alter_column("area_analysis_attempts", "input_hash", nullable=False)
    op.drop_constraint("uq_area_analysis_revision", "area_analysis_attempts", type_="unique")
    op.create_unique_constraint("uq_area_analysis_input", "area_analysis_attempts", ["case_id", "area_id", "input_hash"])


def downgrade():
    op.drop_constraint("uq_area_analysis_input", "area_analysis_attempts", type_="unique")
    op.create_unique_constraint("uq_area_analysis_revision", "area_analysis_attempts", ["case_id", "area_id", "input_revision"])
    op.drop_column("area_analysis_attempts", "input_hash")
