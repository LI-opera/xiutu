"""Trusted synthetic diagnosis protocols bound to one case epoch."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0013_trusted_diagnosis_protocols"
down_revision = "0012_reports"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "diagnosis_protocol_bindings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("graph_epoch", sa.Integer(), nullable=False),
        sa.Column("protocol_id", sa.String(100), nullable=False),
        sa.Column("protocol_version", sa.String(32), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("vehicle_profile", JSONB(), nullable=False),
        sa.Column("binding_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("case_id", "graph_epoch", name="uq_protocol_binding_case_epoch"),
        sa.CheckConstraint("graph_epoch>=0 AND manifest_hash ~ '^[0-9a-f]{64}$'", name="ck_protocol_binding_identity"),
        sa.CheckConstraint("jsonb_typeof(vehicle_profile)='object' AND jsonb_typeof(binding_json)='object'", name="ck_protocol_binding_json"),
    )


def downgrade():
    op.drop_table("diagnosis_protocol_bindings")
