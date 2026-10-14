"""Conservative diagnosis mode and immutable protocol bindings for R1."""

import sqlalchemy as sa
from alembic import op

revision = "0014_conservative_protocol_r1"
down_revision = "0013_trusted_diagnosis_protocols"
branch_labels = depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("diagnosis_mode", sa.String(20)))
    op.add_column("cases", sa.Column("policy_version", sa.String(64)))
    op.create_check_constraint(
        "ck_cases_diagnosis_mode", "cases",
        "diagnosis_mode IS NULL OR diagnosis_mode='conservative'",
    )
    op.add_column("diagnosis_protocol_bindings", sa.Column("content_hash", sa.String(64)))
    op.add_column(
        "diagnosis_protocol_bindings",
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_check_constraint(
        "ck_protocol_binding_content_hash", "diagnosis_protocol_bindings",
        "content_hash IS NULL OR content_hash ~ '^[0-9a-f]{64}$'",
    )


def downgrade():
    op.drop_constraint("ck_protocol_binding_content_hash", "diagnosis_protocol_bindings")
    op.drop_column("diagnosis_protocol_bindings", "requires_review")
    op.drop_column("diagnosis_protocol_bindings", "content_hash")
    op.drop_constraint("ck_cases_diagnosis_mode", "cases")
    op.drop_column("cases", "policy_version")
    op.drop_column("cases", "diagnosis_mode")
