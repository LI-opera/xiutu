"""WP-11 diagnosis facts and publication/recovery journal.

Frozen migration: does not import application metadata.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009_graph"
down_revision = "0008_model_indexes"
branch_labels = depends_on = None


def _id(name="id", *, pk=False, fk=None, nullable=False):
    args = [sa.Column(name, UUID(as_uuid=True), primary_key=pk, nullable=nullable,
                      server_default=sa.text("gen_random_uuid()") if pk else None)]
    return args[0]


def _stamp():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.text("now()"))


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS wp01_wp11")
    op.create_table(
        "diagnosis_areas",
        _id(pk=True), _id("case_id"), _id("workflow_id"),
        sa.Column("graph_epoch", sa.Integer(), nullable=False),
        sa.Column("component_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("provenance_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _stamp(),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("case_id", "graph_epoch", "component_key", name="uq_diagnosis_area_key"),
    )
    op.create_table(
        "diagnosis_steps",
        _id(pk=True), _id("case_id"), _id("area_id"), _id("run_id"), _id("turn_id"),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("candidate_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("validation_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False), _stamp(),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["area_id"], ["diagnosis_areas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("case_id", "turn_id", name="uq_diagnosis_step_turn"),
        sa.CheckConstraint("ordinal>=1", name="ck_diagnosis_step_ordinal"),
        sa.CheckConstraint("status IN ('waiting_input','completed','needs_review')", name="ck_diagnosis_step_status"),
    )
    op.create_index("uq_diagnosis_current_step", "diagnosis_steps", ["case_id"], unique=True,
                    postgresql_where=sa.text("status='waiting_input'"))
    op.create_table(
        "diagnosis_publications",
        _id(pk=True), _id("workflow_id"), _id("turn_id"), _id("run_id"),
        _id("case_id"), _id("step_id", nullable=True),
        sa.Column("node", sa.String(40), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("output_revision", sa.BigInteger(), nullable=False),
        sa.Column("response_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _stamp(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["step_id"], ["diagnosis_steps.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("workflow_id", "turn_id", "node", name="uq_diagnosis_publication_key"),
        sa.CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="ck_diagnosis_publication_hash"),
    )
    op.create_table(
        "diagnosis_candidates", _id(pk=True), _id("run_id"), _id("turn_id"),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("result_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _stamp(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("run_id", name="uq_diagnosis_candidate_run"),
        sa.CheckConstraint("result_hash ~ '^[0-9a-f]{64}$'", name="ck_diagnosis_candidate_hash"),
    )
    op.create_table(
        "graph_progress", _id(pk=True), _id("workflow_id"), _id("case_id"),
        _id("turn_id"), _id("run_id"),
        sa.Column("graph_epoch", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        _id("step_id", nullable=True),
        sa.Column("checkpoint_ref", sa.String(200)), _stamp(),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["step_id"], ["diagnosis_steps.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("run_id", name="uq_graph_progress_run"),
        sa.CheckConstraint("phase IN ('queued','evaluating','waiting_input','resuming','needs_input','failed')", name="ck_graph_progress_phase"),
    )


def downgrade():
    op.drop_table("graph_progress")
    op.drop_table("diagnosis_candidates")
    op.drop_table("diagnosis_publications")
    op.drop_index("uq_diagnosis_current_step", table_name="diagnosis_steps")
    op.drop_table("diagnosis_steps")
    op.drop_table("diagnosis_areas")
    # Refuse a destructive downgrade while external saver checkpoints exist.
    op.execute("DROP SCHEMA wp01_wp11")
