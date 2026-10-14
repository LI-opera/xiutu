"""Bounded, non-advice diagnostic record for rejected model responses."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017_case_analysis_diagnostics"
down_revision = "0016_case_analysis_advice"
branch_labels = depends_on = None


def upgrade():
    op.add_column("case_analyses", sa.Column(
        "diagnostic_json", JSONB(), nullable=False,
        server_default=sa.text("'{}'::jsonb")))
    op.create_check_constraint("ck_case_analysis_diagnostic_shape", "case_analyses",
                               "jsonb_typeof(diagnostic_json)='object'")


def downgrade():
    op.drop_constraint("ck_case_analysis_diagnostic_shape", "case_analyses", type_="check")
    op.drop_column("case_analyses", "diagnostic_json")
