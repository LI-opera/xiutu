import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

metadata = sa.MetaData()

area_reference_documents = sa.Table("area_reference_documents", metadata,
    sa.Column("document_id", sa.String(100), primary_key=True),
    sa.Column("version", sa.String(32), primary_key=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("body", sa.Text, nullable=False),
    sa.Column("content_hash", sa.String(64), nullable=False),
    sa.Column("provenance", JSONB, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    # Ingest state (0024): analyses read only "ready" versions.
    sa.Column("source_kind", sa.String(16), nullable=False, server_default="seed"),
    sa.Column("status", sa.String(16), nullable=False, server_default="ready"),
    sa.Column("error_code", sa.String(80)),
    sa.Column("chunker_version", sa.String(40)),
    sa.Column("chunk_count", sa.Integer),
    sa.Column("vector_fingerprint", sa.String(80)),
    sa.Column("always_include", JSONB, nullable=False, server_default="[]"),
    # 0025: the vehicle a manual applies to; analyses find manuals by it.
    sa.Column("vehicle_brand", sa.String(100)),
    sa.Column("vehicle_model", sa.String(100)),
    sa.Column("vehicle_year", sa.Integer),
    sa.Column("vehicle_engine_code", sa.String(64)),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
area_reference_chunks = sa.Table("area_reference_chunks", metadata,
    sa.Column("document_id", sa.String(100), primary_key=True),
    sa.Column("version", sa.String(32), primary_key=True),
    sa.Column("ordinal", sa.Integer, primary_key=True),
    sa.Column("section", sa.Text, nullable=False),
    sa.Column("subsection", sa.Text),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("char_start", sa.Integer, nullable=False),
    sa.Column("char_end", sa.Integer, nullable=False),
    sa.Column("identifiers", ARRAY(sa.Text), nullable=False, server_default="{}"),
    sa.Column("searchable", sa.Boolean, nullable=False),
    sa.Column("search_hash", sa.String(64), nullable=False),
    sa.ForeignKeyConstraint(["document_id", "version"],
        ["area_reference_documents.document_id", "area_reference_documents.version"]))
area_reference_chunk_vectors = sa.Table("area_reference_chunk_vectors", metadata,
    sa.Column("document_id", sa.String(100), primary_key=True),
    sa.Column("version", sa.String(32), primary_key=True),
    sa.Column("ordinal", sa.Integer, primary_key=True),
    sa.Column("fingerprint", sa.String(80), primary_key=True),
    sa.Column("search_hash", sa.String(64), nullable=False),
    sa.Column("embedding", Vector(), nullable=False),
    sa.ForeignKeyConstraint(["document_id", "version", "ordinal"],
        ["area_reference_chunks.document_id", "area_reference_chunks.version",
         "area_reference_chunks.ordinal"], ondelete="CASCADE"))
area_analysis_attempts = sa.Table("area_analysis_attempts", metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("area_id", sa.String(80), nullable=False),
    sa.Column("input_revision", sa.BigInteger, nullable=False),
    sa.Column("input_hash", sa.String(64), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("model", sa.String(80), nullable=False),
    sa.Column("prompt_version", sa.String(40), nullable=False),
    sa.Column("input_json", JSONB, nullable=False),
    sa.Column("result_json", JSONB),
    sa.Column("diagnostic_json", JSONB),
    sa.Column("error_code", sa.String(80)),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
sa.Index("uq_area_analysis_active_input", area_analysis_attempts.c.case_id,
    area_analysis_attempts.c.area_id, area_analysis_attempts.c.input_hash,
    unique=True, postgresql_where=area_analysis_attempts.c.status.in_(["running", "completed"]))

workbench_templates = sa.Table("workbench_templates", metadata,
    sa.Column("template_id", sa.String(80), primary_key=True),
    sa.Column("version", sa.String(40), primary_key=True),
    sa.Column("title", sa.String(200), nullable=False),
    sa.Column("content_hash", sa.String(64), nullable=False),
    sa.Column("content_json", JSONB, nullable=False))
workbench_template_matches = sa.Table("workbench_template_matches", metadata,
    sa.Column("id", sa.String(100), primary_key=True),
    sa.Column("brand", sa.String(100), nullable=False),
    sa.Column("model", sa.String(100), nullable=False),
    sa.Column("year_from", sa.Integer, nullable=False),
    sa.Column("year_to", sa.Integer, nullable=False),
    sa.Column("engine_code", sa.String(64), nullable=False),
    sa.Column("fault_code", sa.String(32), nullable=False),
    sa.Column("template_id", sa.String(80), nullable=False),
    sa.Column("version", sa.String(40), nullable=False),
    sa.ForeignKeyConstraint(["template_id", "version"],
                            ["workbench_templates.template_id", "workbench_templates.version"]))


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
    obj("intake_snapshot"),
    sa.Column("revision", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
    stamp("created_at"),
    stamp("updated_at"),
    sa.CheckConstraint("revision >= 0", name="ck_cases_revision"),
    sa.CheckConstraint("length(trim(fault_description)) > 0", name="ck_cases_description"),
    sa.CheckConstraint(
        "jsonb_typeof(vehicle_json)='object' AND jsonb_typeof(fault_codes)='array' AND jsonb_typeof(intake_snapshot)='object'",
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
case_area_rankings = sa.Table(
    "case_area_rankings", metadata,
    sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), primary_key=True),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("model", sa.String(80), nullable=False),
    sa.Column("prompt_version", sa.String(40), nullable=False),
    sa.Column("input_json", JSONB, nullable=False),
    sa.Column("result_json", JSONB),
    sa.Column("error_code", sa.String(80)),
    stamp("created_at"),
    stamp("updated_at"),
    status_check("status", ["running", "completed", "failed"], "ck_case_area_rankings_status"),
)
template_repair_rounds = sa.Table(
    "template_repair_rounds", metadata,
    uid(),
    uid("case_id", "cases.id"),
    sa.Column("area_id", sa.String(80), nullable=False),
    sa.Column("repair_action", sa.Text, nullable=False),
    sa.Column("repair_note", sa.Text, nullable=False, server_default=""),
    sa.Column("pre_repair_revision", sa.BigInteger, nullable=False),
    sa.Column("retest_condition", sa.String(24)),
    sa.Column("retest_outcome", sa.String(24)),
    sa.Column("retest_evidence", sa.Text),
    sa.Column("next_area_id", sa.String(80)),
    stamp("created_at"),
    sa.Column("retested_at", sa.DateTime(timezone=True)),
    sa.CheckConstraint("length(trim(repair_action)) > 0", name="ck_template_repair_action"),
    status_check("retest_condition", ["same", "different", "unavailable"], "ck_template_retest_condition"),
    status_check("retest_outcome", ["resolved", "persists", "uncertain"], "ck_template_retest_outcome"),
)
sa.Index("ix_template_repair_case_order", template_repair_rounds.c.case_id,
         template_repair_rounds.c.created_at.desc())
runs = sa.Table(
    "runs",
    metadata,
    uid(),
    uid("owner_id", nullable=True),
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

sa.Index("ix_jobs_due", jobs.c.status, jobs.c.available_at, jobs.c.lease_until)
sa.Index("ix_run_events_order", run_events.c.run_id, run_events.c.id)
observations = sa.Table(
    "observations",
    metadata,
    uid(),
    uid("case_id", "cases.id"),
    uid("area_id", nullable=True),
    uid("step_id", nullable=True),
    sa.Column("kind", sa.String(20), nullable=False),
    obj("payload"),
    sa.Column("created_revision", sa.BigInteger, nullable=False),
    uid("supersedes_id", "observations.id", True),
    sa.Column("correction_reason", sa.Text),
    uid("actor_id"),
    stamp("created_at"),
    sa.UniqueConstraint("supersedes_id", name="uq_observation_successor"),
    sa.CheckConstraint(
        "created_revision>=0 AND jsonb_typeof(payload)='object'", name="ck_observation_payload"
    ),
    status_check(
        "kind", ["choice", "measurement", "composite", "unavailable", "intake_snapshot"], "ck_observation_kind"
    ),
)
