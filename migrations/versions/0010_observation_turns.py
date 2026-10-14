"""WP-12 observation correction and per-area conclusion state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0010_observation_turns"
down_revision = "0009_graph"
branch_labels = depends_on = None


def upgrade():
    op.add_column("observations", sa.Column("correction_reason", sa.Text(), nullable=True))
    op.add_column("diagnosis_areas", sa.Column("status", sa.String(20), nullable=False,
                                                server_default="pending"))
    op.add_column("diagnosis_areas", sa.Column("retired_reason", sa.Text(), nullable=True))
    op.create_check_constraint("ck_diagnosis_area_status", "diagnosis_areas",
                               "status IN ('pending','active','completed','stale','retired')")
    op.create_check_constraint("ck_diagnosis_area_retired_reason", "diagnosis_areas",
                               "status <> 'retired' OR length(trim(retired_reason)) > 0")
    op.create_table(
        "diagnosis_area_conclusions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", UUID(as_uuid=True), nullable=False),
        sa.Column("graph_epoch", sa.Integer(), nullable=False),
        sa.Column("created_revision", sa.BigInteger(), nullable=False),
        sa.Column("assessment", sa.String(30), nullable=False),
        sa.Column("content_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_reason", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["area_id"], ["diagnosis_areas.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("area_id", "created_revision", name="uq_area_conclusion_revision"),
        sa.CheckConstraint("assessment IN ('hypothesis','temporarily_excluded','unknown','conflicting','needs_input')",
                           name="ck_area_conclusion_assessment"),
    )
    op.execute("""
        CREATE FUNCTION wp12_observation_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'observations are append only';
        END $$
    """)
    op.execute("CREATE TRIGGER trg_wp12_observation_immutable BEFORE UPDATE OR DELETE ON observations FOR EACH ROW EXECUTE FUNCTION wp12_observation_immutable()")


def downgrade():
    op.execute("DROP TRIGGER trg_wp12_observation_immutable ON observations")
    op.execute("DROP FUNCTION wp12_observation_immutable()")
    op.drop_table("diagnosis_area_conclusions")
    op.drop_constraint("ck_diagnosis_area_retired_reason", "diagnosis_areas")
    op.drop_constraint("ck_diagnosis_area_status", "diagnosis_areas")
    op.drop_column("diagnosis_areas", "retired_reason")
    op.drop_column("diagnosis_areas", "status")
    op.drop_column("observations", "correction_reason")
