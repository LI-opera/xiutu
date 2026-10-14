"""Atomic case intake snapshot and system intake fact for R1-FLOW-02."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_r1_flow_02_intake_snapshot"
down_revision = "0014_conservative_protocol_r1"
branch_labels = depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("intake_snapshot", JSONB(), nullable=False,
                                     server_default=sa.text("'{}'::jsonb")))
    op.drop_constraint("ck_cases_json", "cases", type_="check")
    op.create_check_constraint(
        "ck_cases_json", "cases",
        "jsonb_typeof(vehicle_json)='object' AND jsonb_typeof(fault_codes)='array' "
        "AND jsonb_typeof(corpus_manifest)='array' AND jsonb_typeof(intake_snapshot)='object'",
    )
    op.drop_constraint("ck_observation_kind", "observations", type_="check")
    op.create_check_constraint(
        "ck_observation_kind", "observations",
        "kind IN ('choice','measurement','composite','unavailable','intake_snapshot')",
    )


def downgrade():
    op.drop_constraint("ck_observation_kind", "observations", type_="check")
    op.create_check_constraint(
        "ck_observation_kind", "observations",
        "kind IN ('choice','measurement','composite','unavailable')",
    )
    op.drop_constraint("ck_cases_json", "cases", type_="check")
    op.create_check_constraint(
        "ck_cases_json", "cases",
        "jsonb_typeof(vehicle_json)='object' AND jsonb_typeof(fault_codes)='array' "
        "AND jsonb_typeof(corpus_manifest)='array'",
    )
    op.drop_column("cases", "intake_snapshot")
