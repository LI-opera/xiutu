"""Environment only. WP-02 must create a new revision, not replace this one."""

from alembic import op

revision = "0001_environment"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade():
    # Do not remove a shared extension and potentially destroy dependent objects.
    pass
