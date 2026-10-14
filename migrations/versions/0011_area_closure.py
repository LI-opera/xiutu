"""Allow a fenced graph turn to finish after a conservative area card."""

from alembic import op

revision = "0011_area_closure"
down_revision = "0010_observation_turns"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint("ck_graph_progress_phase", "graph_progress", type_="check")
    op.create_check_constraint("ck_graph_progress_phase", "graph_progress",
        "phase IN ('queued','evaluating','waiting_input','resuming','needs_input','failed','completed')")


def downgrade():
    op.execute("UPDATE graph_progress SET phase='needs_input' WHERE phase='completed'")
    op.drop_constraint("ck_graph_progress_phase", "graph_progress", type_="check")
    op.create_check_constraint("ck_graph_progress_phase", "graph_progress",
        "phase IN ('queued','evaluating','waiting_input','resuming','needs_input','failed')")
