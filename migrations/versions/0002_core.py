"""WP-02 frozen eight-table schema; deliberately independent of live app metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002_core"
down_revision = "0001_environment"
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
        primary_key=(name == "id"),
        server_default=sa.text("gen_random_uuid()") if name == "id" else None,
    )


def stamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def obj(name, default="{}"):
    return sa.Column(
        name, JSONB, nullable=False, server_default=sa.text("'" + default + "'::jsonb")
    )


def status_check(column, values, name):
    return sa.CheckConstraint(column + " IN (" + ",".join(repr(v) for v in values) + ")", name=name)


cases = sa.Table(
    "cases",
    metadata,
    uid(),
    uid("owner_id"),
    obj("vehicle_json"),
    sa.Column("fault_description", sa.String(4000), nullable=False),
    obj("fault_codes", "[]"),
    obj("corpus_manifest", "[]"),
    sa.Column("revision", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("graph_epoch", sa.Integer, nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
    stamp("created_at"),
    stamp("updated_at"),
    sa.CheckConstraint("revision >= 0 AND graph_epoch >= 0", name="ck_cases_revision"),
    sa.CheckConstraint("length(trim(fault_description)) > 0", name="ck_cases_description"),
    sa.CheckConstraint(
        "jsonb_typeof(vehicle_json)='object' AND jsonb_typeof(fault_codes)='array' AND jsonb_typeof(corpus_manifest)='array'",
        name="ck_cases_json",
    ),
    status_check(
        "status",
        [
            "draft",
            "analyzing",
            "waiting_input",
            "ready_for_report",
            "reporting",
            "completed",
            "needs_review",
            "failed",
        ],
        "ck_cases_status",
    ),
)
sa.Index("ix_cases_owner_order", cases.c.owner_id, cases.c.created_at.desc(), cases.c.id.desc())
documents = sa.Table(
    "documents",
    metadata,
    uid(),
    sa.Column("title", sa.String(300), nullable=False),
    sa.Column("source_kind", sa.String(32), nullable=False),
    stamp("created_at"),
    sa.CheckConstraint(
        "length(trim(title))>0 AND length(trim(source_kind))>0", name="ck_documents_text"
    ),
)
document_versions = sa.Table(
    "document_versions",
    metadata,
    uid(),
    uid("document_id", "documents.id"),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("storage_key", sa.String(512), nullable=False),
    sa.Column("mime", sa.String(100), nullable=False),
    obj("scope_json"),
    sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
    sa.Column("parse_status", sa.String(32), nullable=False, server_default="pending"),
    sa.Column("parser_version", sa.String(100)),
    sa.UniqueConstraint("document_id", "sha256", name="uq_document_hash"),
    sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_document_hash"),
    status_check(
        "review_status", ["pending", "approved", "rejected", "revoked"], "ck_document_review"
    ),
    status_check(
        "parse_status",
        ["pending", "parsing", "review_pending", "needs_ocr", "failed"],
        "ck_document_parse",
    ),
)
chunks = sa.Table(
    "chunks",
    metadata,
    uid(),
    uid("document_version_id", "document_versions.id"),
    sa.Column("ordinal", sa.Integer, nullable=False),
    obj("heading_path", "[]"),
    sa.Column("page_start", sa.Integer),
    sa.Column("page_end", sa.Integer),
    sa.Column("char_start", sa.Integer),
    sa.Column("char_end", sa.Integer),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("text_hash", sa.String(64), nullable=False),
    sa.Column("kind", sa.String(32), nullable=False),
    uid("parent_id", "chunks.id", True),
    sa.UniqueConstraint("document_version_id", "ordinal", name="uq_chunk_ordinal"),
    sa.CheckConstraint(
        "ordinal>=0 AND (page_start IS NULL OR page_start>=1) AND (page_end IS NULL OR (page_start IS NOT NULL AND page_end>=page_start)) AND (char_start IS NULL OR char_start>=0) AND (char_end IS NULL OR (char_start IS NOT NULL AND char_end>=char_start))",
        name="ck_chunk_ranges",
    ),
    sa.CheckConstraint("text_hash ~ '^[0-9a-f]{64}$'", name="ck_chunk_hash"),
)
runs = sa.Table(
    "runs",
    metadata,
    uid(),
    uid("case_id", "cases.id", True),
    sa.Column("kind", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
    sa.Column("input_revision", sa.BigInteger),
    sa.Column("output_revision", sa.BigInteger),
    uid("workflow_id", nullable=True),
    uid("turn_id", nullable=True),
    obj("budget_json"),
    obj("usage_json"),
    obj("error_json"),
    obj("input_payload"),
    uid("parent_run_id", "runs.id", True),
    sa.CheckConstraint(
        "(input_revision IS NULL OR input_revision>=0) AND (output_revision IS NULL OR output_revision>=0)",
        name="ck_runs_revision",
    ),
    status_check(
        "status",
        [
            "queued",
            "running",
            "waiting_input",
            "succeeded",
            "failed",
            "cancel_requested",
            "cancelled",
            "superseded",
        ],
        "ck_runs_status",
    ),
)
sa.Index(
    "uq_runs_active_case",
    runs.c.case_id,
    unique=True,
    postgresql_where=sa.text(
        "case_id IS NOT NULL AND status IN ('queued','running','cancel_requested')"
    ),
)
jobs = sa.Table(
    "jobs",
    metadata,
    uid(),
    uid("run_id", "runs.id"),
    sa.Column("kind", sa.String(32), nullable=False),
    obj("payload"),
    sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
    sa.Column("attempt", sa.Integer, nullable=False, server_default="0"),
    sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
    sa.Column("lease_owner", sa.String(100)),
    sa.Column("lease_token", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("lease_until", sa.DateTime(timezone=True)),
    stamp("available_at"),
    sa.UniqueConstraint("run_id", name="uq_jobs_run"),
    sa.CheckConstraint(
        "attempt>=0 AND max_attempts>0 AND attempt<=max_attempts AND lease_token>=0",
        name="ck_jobs_ranges",
    ),
    status_check(
        "status", ["queued", "running", "completed", "failed", "cancelled"], "ck_jobs_status"
    ),
)
run_events = sa.Table(
    "run_events",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    uid("run_id", "runs.id"),
    uid("case_id", "cases.id", True),
    sa.Column("type", sa.String(100), nullable=False),
    obj("payload"),
    stamp("created_at"),
)
idempotency_keys = sa.Table(
    "idempotency_keys",
    metadata,
    sa.Column("actor_id", UUID(as_uuid=True), primary_key=True),
    sa.Column("route_scope", sa.String(100), primary_key=True),
    sa.Column("key", sa.String(128), primary_key=True),
    sa.Column("request_hash", sa.String(64), nullable=False),
    sa.Column("response_status", sa.Integer, nullable=False),
    obj("response_json"),
    stamp("created_at"),
    sa.CheckConstraint("response_status BETWEEN 100 AND 599", name="ck_idempotency_status"),
    sa.CheckConstraint(
        "request_hash ~ '^[0-9a-f]{64}$' AND length(key)>0 AND length(route_scope)>0",
        name="ck_idempotency_key",
    ),
)


def upgrade():
    metadata.create_all(op.get_bind(), checkfirst=False)


def downgrade():
    metadata.drop_all(op.get_bind(), checkfirst=False)
