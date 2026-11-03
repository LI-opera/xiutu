"""Manuals may come from a reviewed guide package (POST /api/v2/area-references/packages).

Only widens the allowed source kinds: seed, upload, and now package.
"""
from alembic import op

revision = "0027_reference_package_source"
down_revision = "0026_retire_legacy"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint("ck_reference_source_kind", "area_reference_documents", type_="check")
    op.create_check_constraint("ck_reference_source_kind", "area_reference_documents",
                               "source_kind IN ('seed','upload','package')")


def downgrade():
    # Imported packages become plain uploads; their review stays in provenance.package.
    op.execute("UPDATE area_reference_documents SET source_kind = 'upload' WHERE source_kind = 'package'")
    op.drop_constraint("ck_reference_source_kind", "area_reference_documents", type_="check")
    op.create_check_constraint("ck_reference_source_kind", "area_reference_documents",
                               "source_kind IN ('seed','upload')")
