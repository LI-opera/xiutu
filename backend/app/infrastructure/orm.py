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
    # Ingest state (0024): only "ready" versions are ever bound to an area.
    sa.Column("source_kind", sa.String(16), nullable=False, server_default="seed"),
    sa.Column("status", sa.String(16), nullable=False, server_default="ready"),
    sa.Column("error_code", sa.String(80)),
    sa.Column("chunker_version", sa.String(40)),
    sa.Column("chunk_count", sa.Integer),
    sa.Column("vector_fingerprint", sa.String(80)),
    sa.Column("always_include", JSONB, nullable=False, server_default="[]"),
    sa.Column("requested_areas", JSONB, nullable=False, server_default="[]"),
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
area_reference_bindings = sa.Table("area_reference_bindings", metadata,
    sa.Column("template_id", sa.String(100), primary_key=True),
    sa.Column("template_version", sa.String(32), primary_key=True),
    sa.Column("area_id", sa.String(80), primary_key=True),
    sa.Column("document_id", sa.String(100), primary_key=True),
    sa.Column("document_version", sa.String(32), nullable=False),
    sa.ForeignKeyConstraint(["document_id", "document_version"],
        ["area_reference_documents.document_id", "area_reference_documents.version"]),
    sa.ForeignKeyConstraint(["template_id", "template_version"],
        ["workbench_templates.template_id", "workbench_templates.version"]))
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
    obj("corpus_manifest", "[]"),
    sa.Column("diagnosis_mode", sa.String(20)),
    sa.Column("policy_version", sa.String(64)),
    obj("intake_snapshot"),
    sa.Column("revision", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("graph_epoch", sa.Integer, nullable=False, server_default="0"),
    sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
    stamp("created_at"),
    stamp("updated_at"),
    sa.CheckConstraint("revision >= 0 AND graph_epoch >= 0", name="ck_cases_revision"),
    sa.CheckConstraint("length(trim(fault_description)) > 0", name="ck_cases_description"),
    sa.CheckConstraint("diagnosis_mode IS NULL OR diagnosis_mode='conservative'",
                       name="ck_cases_diagnosis_mode"),
    sa.CheckConstraint(
        "jsonb_typeof(vehicle_json)='object' AND jsonb_typeof(fault_codes)='array' AND jsonb_typeof(corpus_manifest)='array' AND jsonb_typeof(intake_snapshot)='object'",
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
documents = sa.Table(
    "documents",
    metadata,
    uid(),
    uid("owner_id", nullable=True),
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
    obj("metadata_json"),
    obj("review_snapshot"),
    sa.Column("authorization_epoch", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("active_index_id", UUID(as_uuid=True)),
    sa.ForeignKeyConstraint(
        ["active_index_id", "id"],
        ["index_versions.id", "index_versions.document_version_id"],
        name="fk_active_index_version",
        ondelete="RESTRICT",
    ),
    uid("current_run_id", "runs.id", True),
    stamp("created_at"),
    sa.Column("chunker_version", sa.String(100)),
    sa.Column("tokenizer", sa.String(100)),
    sa.Column("page_count", sa.Integer),
    obj("page_issues", "[]"),
    obj("parse_error"),
    sa.CheckConstraint("page_count IS NULL OR page_count>=1", name="ck_document_pages"),
    sa.UniqueConstraint("document_id", "sha256", name="uq_document_hash"),
    sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_document_hash"),
    status_check(
        "review_status", ["pending", "approved", "rejected", "revoked"], "ck_document_review"
    ),
    status_check(
        "parse_status",
        ["pending", "parsing", "review_pending", "needs_ocr", "failed", "cancelled"],
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
    obj("locator_json"),
    sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
    sa.CheckConstraint("token_count>=0", name="ck_chunk_tokens"),
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

sa.Index(
    "ix_documents_owner_order",
    documents.c.owner_id,
    documents.c.created_at.desc(),
    documents.c.id.desc(),
)
document_reviews = sa.Table(
    "document_reviews",
    metadata,
    uid(),
    uid("document_version_id", "document_versions.id"),
    uid("actor_id"),
    stamp("created_at"),
    obj("review_json"),
    sa.Column("decision", sa.String(32), nullable=False),
    status_check("decision", ["approved", "rejected", "revoked"], "ck_review_decision"),
)

index_versions = sa.Table(
    "index_versions",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    uid("document_version_id", "document_versions.id"),
    uid("run_id", "runs.id"),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("profile", sa.String(16), nullable=False),
    sa.Column("dimension", sa.Integer, nullable=False),
    sa.Column("config_json", JSONB, nullable=False),
    sa.Column("chunk_count", sa.Integer, nullable=False),
    obj("error_json"),
    stamp("created_at"),
    status_check("status", ["building", "ready", "failed"], "ck_index_status"),
    status_check("profile", ["formal", "synthetic"], "ck_index_profile"),
    sa.CheckConstraint("dimension IN (384,1024) AND chunk_count>0", name="ck_index_shape"),
    sa.UniqueConstraint("run_id"),
    sa.UniqueConstraint("id", "document_version_id", name="uq_index_version_pair"),
)
sa.Index(
    "uq_index_building",
    index_versions.c.document_version_id,
    unique=True,
    postgresql_where=sa.text("status='building'"),
)
chunk_embeddings = sa.Table(
    "chunk_embeddings",
    metadata,
    sa.Column(
        "index_id",
        UUID(as_uuid=True),
        sa.ForeignKey("index_versions.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    sa.Column(
        "chunk_id",
        UUID(as_uuid=True),
        sa.ForeignKey("chunks.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    sa.Column("embedding", Vector(), nullable=False),
    sa.Column("text_hash", sa.String(64), nullable=False),
    sa.CheckConstraint("vector_norm(embedding)>0", name="ck_embedding_nonzero"),
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


tool_executions = sa.Table(
    "tool_executions",
    metadata,
    uid(),
    uid("actor_id"),
    uid("case_id", "cases.id"),
    uid("run_id", "runs.id", True),
    sa.Column("capability_hash", sa.String(64), nullable=False),
    sa.Column("revision", sa.BigInteger, nullable=False),
    obj("manifest", "[]"),
    obj("allowlist", "[]"),
    sa.Column("profile", sa.String(16), nullable=False),
    sa.Column("call_limit", sa.Integer, nullable=False),
    sa.Column("search_limit", sa.Integer, nullable=False),
    sa.Column("used", sa.Integer, nullable=False, server_default="0"),
    sa.Column("search_used", sa.Integer, nullable=False, server_default="0"),
    sa.Column("timeout_ms", sa.Integer, nullable=False),
    sa.Column("retry_limit", sa.Integer, nullable=False),
    stamp("created_at"),
    sa.CheckConstraint(
        "call_limit BETWEEN 1 AND 20 AND search_limit BETWEEN 0 AND 10 AND used BETWEEN 0 AND call_limit AND search_used BETWEEN 0 AND search_limit AND timeout_ms BETWEEN 50 AND 10000 AND retry_limit BETWEEN 0 AND 1",
        name="ck_tool_budget",
    ),
)
tool_calls = sa.Table(
    "tool_calls",
    metadata,
    uid(),
    uid("execution_id", "tool_executions.id"),
    sa.Column("call_key", sa.String(100), nullable=False),
    sa.Column("tool", sa.String(64), nullable=False),
    sa.Column("args_hash", sa.String(64), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("attempts", sa.Integer, nullable=False),
    sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
    sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
    obj("result_summary"),
    sa.Column("error_code", sa.String(64)),
    stamp("created_at"),
    sa.UniqueConstraint("execution_id", "call_key", name="uq_tool_logical_call"),
    status_check("status", ["running", "succeeded", "failed", "uncertain"], "ck_tool_status"),
    sa.CheckConstraint("attempts BETWEEN 1 AND 2 AND duration_ms>=0", name="ck_tool_attempts"),
)
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

# WP-11 business facts are separate from workflow checkpoints.  A checkpoint
# may point at these rows, but cannot replace them.
diagnosis_areas = sa.Table(
    "diagnosis_areas", metadata,
    uid(), uid("case_id", "cases.id"), uid("workflow_id"),
    sa.Column("graph_epoch", sa.Integer, nullable=False),
    sa.Column("component_key", sa.String(100), nullable=False),
    sa.Column("title", sa.String(200), nullable=False),
    obj("provenance_json"), stamp("created_at"),
    sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    sa.Column("retired_reason", sa.Text),
    status_check("status", ["pending", "active", "completed", "stale", "retired"], "ck_diagnosis_area_status"),
    sa.CheckConstraint("status <> 'retired' OR length(trim(retired_reason)) > 0",
                       name="ck_diagnosis_area_retired_reason"),
    sa.UniqueConstraint("case_id", "graph_epoch", "component_key", name="uq_diagnosis_area_key"),
)
diagnosis_steps = sa.Table(
    "diagnosis_steps", metadata,
    uid(), uid("case_id", "cases.id"), uid("area_id", "diagnosis_areas.id"),
    uid("run_id", "runs.id"), uid("turn_id"),
    sa.Column("ordinal", sa.Integer, nullable=False),
    obj("candidate_json"), obj("validation_json"),
    sa.Column("status", sa.String(20), nullable=False),
    stamp("created_at"),
    sa.UniqueConstraint("case_id", "turn_id", name="uq_diagnosis_step_turn"),
    sa.CheckConstraint("ordinal>=1", name="ck_diagnosis_step_ordinal"),
    status_check("status", ["waiting_input", "completed", "needs_review"], "ck_diagnosis_step_status"),
)
sa.Index("uq_diagnosis_current_step", diagnosis_steps.c.case_id, unique=True,
         postgresql_where=sa.text("status='waiting_input'"))
diagnosis_area_conclusions = sa.Table(
    "diagnosis_area_conclusions", metadata,
    uid(), uid("case_id", "cases.id"), uid("area_id", "diagnosis_areas.id"),
    sa.Column("graph_epoch", sa.Integer, nullable=False),
    sa.Column("created_revision", sa.BigInteger, nullable=False),
    sa.Column("assessment", sa.String(30), nullable=False),
    obj("content_json"),
    sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("review_reason", sa.String(100)), stamp("created_at"),
    sa.UniqueConstraint("area_id", "created_revision", name="uq_area_conclusion_revision"),
    status_check("assessment", ["hypothesis", "temporarily_excluded", "unknown",
                                "conflicting", "needs_input", "supported", "ruled_out"],
                 "ck_area_conclusion_assessment"),
)
diagnosis_publications = sa.Table(
    "diagnosis_publications", metadata,
    uid(), uid("workflow_id"), uid("turn_id"), uid("run_id", "runs.id"),
    uid("case_id", "cases.id"), uid("step_id", "diagnosis_steps.id", True),
    sa.Column("node", sa.String(40), nullable=False),
    sa.Column("payload_hash", sa.String(64), nullable=False),
    sa.Column("output_revision", sa.BigInteger, nullable=False),
    obj("response_json"), stamp("created_at"),
    sa.UniqueConstraint("workflow_id", "turn_id", "node", name="uq_diagnosis_publication_key"),
    sa.CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="ck_diagnosis_publication_hash"),
)
diagnosis_candidates = sa.Table(
    "diagnosis_candidates", metadata,
    uid(), uid("run_id", "runs.id"), uid("turn_id"),
    sa.Column("result_hash", sa.String(64), nullable=False),
    obj("result_json"), stamp("created_at"),
    sa.UniqueConstraint("run_id", name="uq_diagnosis_candidate_run"),
    sa.CheckConstraint("result_hash ~ '^[0-9a-f]{64}$'", name="ck_diagnosis_candidate_hash"),
)
graph_progress = sa.Table(
    "graph_progress", metadata,
    uid(), uid("workflow_id"), uid("case_id", "cases.id"),
    uid("turn_id"), uid("run_id", "runs.id"),
    sa.Column("graph_epoch", sa.Integer, nullable=False),
    sa.Column("phase", sa.String(32), nullable=False),
    uid("step_id", "diagnosis_steps.id", True),
    sa.Column("checkpoint_ref", sa.String(200)),
    stamp("created_at"),
    sa.UniqueConstraint("run_id", name="uq_graph_progress_run"),
    status_check("phase", ["queued", "evaluating", "waiting_input", "resuming", "needs_input", "failed", "completed"], "ck_graph_progress_phase"),
)

diagnosis_protocol_bindings = sa.Table(
    "diagnosis_protocol_bindings", metadata,
    uid(), uid("case_id", "cases.id"), uid("owner_id"),
    sa.Column("graph_epoch", sa.Integer, nullable=False),
    sa.Column("protocol_id", sa.String(100), nullable=False),
    sa.Column("protocol_version", sa.String(32), nullable=False),
    sa.Column("content_hash", sa.String(64)),
    sa.Column("requires_review", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("manifest_hash", sa.String(64), nullable=False),
    obj("vehicle_profile"), obj("binding_json"), stamp("created_at"),
    sa.UniqueConstraint("case_id", "graph_epoch", name="uq_protocol_binding_case_epoch"),
    sa.CheckConstraint("graph_epoch>=0 AND manifest_hash ~ '^[0-9a-f]{64}$'",
                       name="ck_protocol_binding_identity"),
)

reports = sa.Table(
    "reports", metadata,
    uid(), uid("case_id", "cases.id"), uid("owner_id"), uid("run_id", "runs.id"),
    sa.Column("kind", sa.String(16), nullable=False),
    sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
    sa.Column("input_revision", sa.BigInteger, nullable=False),
    sa.Column("graph_epoch", sa.Integer, nullable=False),
    obj("manifest_json", "[]"), obj("conclusion_ids", "[]"), obj("content_json"),
    sa.Column("stale_reason", sa.String(80)), stamp("created_at"),
    sa.UniqueConstraint("run_id", name="uq_report_run"),
    status_check("kind", ["progress", "final"], "ck_report_kind"),
    status_check("status", ["draft", "current", "stale", "failed"], "ck_report_status"),
    sa.CheckConstraint("input_revision>=0 AND graph_epoch>=0 AND jsonb_typeof(manifest_json)='array' AND jsonb_typeof(conclusion_ids)='array' AND jsonb_typeof(content_json)='object'", name="ck_report_shape"),
)
sa.Index("ix_reports_case_created", reports.c.case_id, reports.c.created_at)

case_analyses = sa.Table(
    "case_analyses", metadata,
    uid(), uid("case_id", "cases.id"), uid("owner_id"), uid("run_id", "runs.id"),
    sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
    sa.Column("input_revision", sa.BigInteger, nullable=False),
    sa.Column("topic_version", sa.String(32), nullable=False),
    sa.Column("topic_hash", sa.String(64), nullable=False),
    sa.Column("context_hash", sa.String(64), nullable=False),
    sa.Column("mode", sa.String(16), nullable=False),
    sa.Column("provider", sa.String(32), nullable=False),
    sa.Column("model", sa.String(80), nullable=False),
    sa.Column("prompt_version", sa.String(32), nullable=False),
    sa.Column("allowed_scope", sa.String(32), nullable=False),
    sa.Column("dispatch_state", sa.String(16), nullable=False, server_default="pending"),
    obj("snapshot_json"), obj("content_json"), obj("diagnostic_json"),
    sa.Column("error_code", sa.String(80)), stamp("created_at"),
    sa.UniqueConstraint("run_id", name="uq_case_analysis_run"),
    status_check("status", ["draft", "current", "failed"], "ck_case_analysis_status"),
    status_check("mode", ["stub", "real"], "ck_case_analysis_mode"),
    status_check("dispatch_state", ["pending", "reserved", "completed"], "ck_case_analysis_dispatch"),
    sa.CheckConstraint("input_revision>=0 AND topic_hash ~ '^[0-9a-f]{64}$' AND context_hash ~ '^[0-9a-f]{64}$' AND jsonb_typeof(snapshot_json)='object' AND jsonb_typeof(content_json)='object'", name="ck_case_analysis_shape"),
)
sa.Index("ix_case_analyses_case_created", case_analyses.c.case_id, case_analyses.c.created_at.desc(), case_analyses.c.id.desc())
