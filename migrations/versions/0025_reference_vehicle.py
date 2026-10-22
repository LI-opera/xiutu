"""Manuals carry the vehicle they apply to; analyses find them by vehicle, not by an area table.

Existing rows get the vehicle of the templates their document was bound to. The area-binding
table stays (old data) but analyses no longer read it; requested_areas is dropped.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0025_reference_vehicle"
down_revision = "0024_reference_ingest"
branch_labels = depends_on = None


def upgrade():
    op.add_column("area_reference_documents", sa.Column("vehicle_brand", sa.String(100)))
    op.add_column("area_reference_documents", sa.Column("vehicle_model", sa.String(100)))
    op.add_column("area_reference_documents", sa.Column("vehicle_year", sa.Integer))
    op.add_column("area_reference_documents", sa.Column("vehicle_engine_code", sa.String(64)))
    # Every version of a document gets the vehicle of any template one of its versions was bound to.
    op.execute("""
        UPDATE area_reference_documents d
        SET vehicle_brand = v.brand, vehicle_model = v.model,
            vehicle_year = v.year_from, vehicle_engine_code = v.engine_code
        FROM (
            SELECT DISTINCT ON (b.document_id) b.document_id, m.brand, m.model, m.year_from, m.engine_code
            FROM area_reference_bindings b
            JOIN workbench_template_matches m
              ON m.template_id = b.template_id AND m.version = b.template_version
            ORDER BY b.document_id, m.template_id, m.version
        ) v
        WHERE d.document_id = v.document_id
    """)
    op.create_check_constraint(
        "ck_reference_vehicle_year", "area_reference_documents",
        "vehicle_year IS NULL OR vehicle_year BETWEEN 1950 AND 2100")
    op.create_index("ix_reference_vehicle", "area_reference_documents",
                    ["vehicle_brand", "vehicle_model", "vehicle_year", "vehicle_engine_code"])
    op.drop_column("area_reference_documents", "requested_areas")


def downgrade():
    op.add_column("area_reference_documents",
                  sa.Column("requested_areas", JSONB, nullable=False, server_default="[]"))
    op.drop_index("ix_reference_vehicle", table_name="area_reference_documents")
    op.drop_constraint("ck_reference_vehicle_year", "area_reference_documents", type_="check")
    for column in ("vehicle_engine_code", "vehicle_year", "vehicle_model", "vehicle_brand"):
        op.drop_column("area_reference_documents", column)
