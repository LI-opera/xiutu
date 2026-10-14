"""Frozen WP06 evidence and reviewed measurement specifications."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_evidence_specs"
down_revision = "0005_indexes"
branch_labels = None
depends_on = None
metadata = sa.MetaData()


def uid(name="id", fk=None, nullable=False):
    args = [UUID(as_uuid=True)]
    if fk:
        args.append(sa.ForeignKey(fk, ondelete="RESTRICT"))
    return sa.Column(
        name,
        *args,
        nullable=nullable,
        primary_key=name == "id",
        server_default=sa.text("gen_random_uuid()") if name == "id" else None,
    )


def obj(name, default="{}"):
    return sa.Column(
        name, JSONB, nullable=False, server_default=sa.text("'" + default + "'::jsonb")
    )


def stamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def status_check(column, values, name):
    return sa.CheckConstraint(column + " IN (" + ",".join(repr(x) for x in values) + ")", name=name)


# Reference-only tables for FK DDL ordering; they are never created by this migration.
for name in ["cases", "document_versions", "chunks", "index_versions"]:
    sa.Table(
        name,
        metadata,
        sa.Column("id", UUID, primary_key=True),
        sa.Column("document_version_id", UUID),
    )

case_evidence = sa.Table(
    "case_evidence",
    metadata,
    uid(),
    uid("case_id", "cases.id"),
    uid("document_version_id", "document_versions.id"),
    uid("chunk_id", "chunks.id"),
    uid("index_id", "index_versions.id"),
    sa.Column("authorization_epoch", sa.BigInteger, nullable=False),
    sa.Column("start_offset", sa.Integer, nullable=False),
    sa.Column("end_offset", sa.Integer, nullable=False),
    sa.Column("quote", sa.Text, nullable=False),
    sa.Column("content_hash", sa.String(64), nullable=False),
    sa.Column("chunk_hash", sa.String(64), nullable=False),
    obj("locator"),
    obj("applicability"),
    obj("review_snapshot"),
    sa.Column("profile", sa.String(16), nullable=False),
    sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.false()),
    obj("review_reasons", "[]"),
    stamp("created_at"),
    sa.CheckConstraint(
        "start_offset >= 0 AND end_offset > start_offset AND char_length(quote)=end_offset-start_offset",
        name="ck_evidence_offsets",
    ),
    sa.ForeignKeyConstraint(
        ["index_id", "document_version_id"],
        ["index_versions.id", "index_versions.document_version_id"],
        ondelete="RESTRICT",
    ),
    sa.UniqueConstraint(
        "case_id",
        "chunk_id",
        "index_id",
        "start_offset",
        "end_offset",
        name="uq_case_quote_location",
    ),
)
measurement_specs = sa.Table(
    "measurement_specs",
    metadata,
    uid(),
    uid("evidence_id", "case_evidence.id"),
    uid("spec_root_id"),
    uid("supersedes_id", "measurement_specs.id", True),
    sa.Column("version", sa.Integer, nullable=False),
    obj("definition"),
    sa.Column("lower_value", sa.Numeric),
    sa.Column("upper_value", sa.Numeric),
    sa.Column("lower_inclusive", sa.Boolean, nullable=False),
    sa.Column("upper_inclusive", sa.Boolean, nullable=False),
    sa.Column("review_status", sa.String(16), nullable=False, server_default="pending"),
    sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.false()),
    obj("review_reasons", "[]"),
    stamp("created_at"),
    sa.UniqueConstraint("spec_root_id", "version", name="uq_spec_version"),
    sa.UniqueConstraint("supersedes_id", name="uq_spec_successor"),
    status_check("review_status", ["pending", "approved", "rejected", "revoked"], "ck_spec_status"),
    sa.CheckConstraint(
        "version>0 AND (lower_value IS NOT NULL OR upper_value IS NOT NULL)",
        name="ck_spec_bound_required",
    ),
    sa.CheckConstraint(
        "(lower_value IS NOT NULL OR NOT lower_inclusive) AND (upper_value IS NOT NULL OR NOT upper_inclusive)",
        name="ck_spec_unbounded",
    ),
    sa.CheckConstraint(
        "lower_value IS NULL OR upper_value IS NULL OR lower_value < upper_value OR (lower_value=upper_value AND lower_inclusive AND upper_inclusive)",
        name="ck_spec_order",
    ),
)
measurement_spec_reviews = sa.Table(
    "measurement_spec_reviews",
    metadata,
    uid(),
    uid("spec_id", "measurement_specs.id"),
    uid("actor_id"),
    sa.Column("decision", sa.String(16), nullable=False),
    sa.Column("note", sa.Text, nullable=False),
    stamp("created_at"),
    status_check("decision", ["approved", "rejected", "revoked"], "ck_spec_review_decision"),
)
measurement_comparisons = sa.Table(
    "measurement_comparisons",
    metadata,
    uid(),
    uid("spec_id", "measurement_specs.id"),
    uid("case_id", "cases.id"),
    obj("result"),
    sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.false()),
    obj("review_reasons", "[]"),
    stamp("created_at"),
)


def upgrade():
    op.add_column(
        "document_versions",
        sa.Column("authorization_epoch", sa.BigInteger, nullable=False, server_default="0"),
    )
    bind = op.get_bind()
    for table in [
        case_evidence,
        measurement_specs,
        measurement_spec_reviews,
        measurement_comparisons,
    ]:
        table.create(bind)
    op.execute("""CREATE FUNCTION wp06_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Immutable WP06 record'; END IF;
      IF (to_jsonb(NEW) - ARRAY['needs_review','review_reasons','review_status']) IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['needs_review','review_reasons','review_status']) THEN
         RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Immutable WP06 snapshot';
      END IF;
      IF to_jsonb(OLD)->>'needs_review'='true' AND to_jsonb(NEW)->>'needs_review'!='true' THEN
         RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Sticky review requirement';
      END IF;
      RETURN NEW;
    END $$""")
    for name in [
        "case_evidence",
        "measurement_specs",
        "measurement_spec_reviews",
        "measurement_comparisons",
    ]:
        op.execute(
            f"CREATE TRIGGER wp06_guard BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION wp06_immutable()"
        )


def downgrade():
    for table in [
        measurement_comparisons,
        measurement_spec_reviews,
        measurement_specs,
        case_evidence,
    ]:
        table.drop(op.get_bind())
    op.execute("DROP FUNCTION wp06_immutable()")
    op.drop_column("document_versions", "authorization_epoch")
