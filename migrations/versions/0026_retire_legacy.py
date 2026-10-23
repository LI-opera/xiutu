"""Retire everything the template workbench does not use; keep only template v2 cases.

Removes, for good:
  - the old document center (documents, versions, chunks, reviews, index generations, embeddings);
  - the earlier diagnosis flow (diagnosis areas/steps/conclusions, evidence, measurement specs,
    tool calls, reports, case analyses) and the LangGraph checkpoint schema;
  - the area-to-manual binding table (analyses choose manuals by vehicle and content since 0025);
  - every case that is not a template case on a current (non-v1) template, with its records,
    rankings, analyses, repair rounds and runs; then the v1 templates themselves;
  - background runs of retired kinds, and four case columns only the old flow used.

Data loss is the point, so the upgrade refuses to delete existing cases unless
XIUTU_ALLOW_LEGACY_DELETE=1 is set (back up the database first). An empty database needs nothing.
There is no downgrade: restore the backup instead.
"""
import os

from alembic import op

revision = "0026_retire_legacy"
down_revision = "0025_reference_vehicle"
branch_labels = depends_on = None

OLD_TABLES = [
    "tool_calls", "tool_executions",
    "measurement_comparisons", "measurement_spec_reviews", "measurement_specs", "case_evidence",
    "chunk_embeddings", "document_reviews", "chunks", "index_versions", "document_versions", "documents",
    "diagnosis_publications", "graph_progress", "diagnosis_steps", "diagnosis_area_conclusions",
    "diagnosis_areas", "diagnosis_candidates", "diagnosis_protocol_bindings",
    "reports", "case_analyses", "area_reference_bindings",
]
# A case the template workbench keeps: created by template matching, on a template other than v1.
# COALESCE matters: older cases have no workbench_flow at all, and NOT (NULL AND ...) is NULL,
# which a WHERE clause treats as "do not select" -- such cases would silently survive.
KEEP_CASE = ("coalesce(intake_snapshot->>'workbench_flow', '') = 'template-match-v1' "
             "AND coalesce(intake_snapshot->'template_binding'->>'version', '') <> '1'")
RUNTIME_JOB_KINDS = "('reference_ingest', 'no_op')"


def upgrade():
    conn = op.get_bind()
    retired = conn.exec_driver_sql(f"SELECT count(*) FROM cases WHERE NOT ({KEEP_CASE})").scalar_one()
    if retired and os.environ.get("XIUTU_ALLOW_LEGACY_DELETE") != "1":
        raise RuntimeError(
            f"0026 would delete {retired} old cases and their data. Back up the database, "
            "then run again with XIUTU_ALLOW_LEGACY_DELETE=1.")

    op.execute("DROP SCHEMA IF EXISTS wp01_wp11 CASCADE")
    op.execute("DROP TABLE IF EXISTS " + ", ".join(OLD_TABLES))
    op.execute("DROP FUNCTION IF EXISTS wp06_immutable()")
    op.execute("DROP FUNCTION IF EXISTS check_embedding_dimension()")

    # Runs: every run of a retired kind or of a retired case goes, with its job and events.
    op.execute(f"""
        CREATE TEMP TABLE retired_runs ON COMMIT DROP AS
        SELECT id FROM runs
        WHERE kind NOT IN {RUNTIME_JOB_KINDS}
           OR case_id IN (SELECT id FROM cases WHERE NOT ({KEEP_CASE}))
    """)
    op.execute("UPDATE runs SET parent_run_id = NULL WHERE parent_run_id IN (SELECT id FROM retired_runs)")
    op.execute("DELETE FROM run_events WHERE run_id IN (SELECT id FROM retired_runs)")
    op.execute("DELETE FROM jobs WHERE run_id IN (SELECT id FROM retired_runs)")
    op.execute("DELETE FROM runs WHERE id IN (SELECT id FROM retired_runs)")

    # Retired cases. Observations are append-only (triggers); lift that only for this delete.
    op.execute(f"CREATE TEMP TABLE retired_cases ON COMMIT DROP AS SELECT id FROM cases WHERE NOT ({KEEP_CASE})")
    op.execute("ALTER TABLE observations DISABLE TRIGGER USER")
    op.execute("UPDATE observations SET supersedes_id = NULL WHERE case_id IN (SELECT id FROM retired_cases)")
    op.execute("DELETE FROM observations WHERE case_id IN (SELECT id FROM retired_cases)")
    op.execute("ALTER TABLE observations ENABLE TRIGGER USER")
    for table in ("area_analysis_attempts", "case_area_rankings", "template_repair_rounds", "run_events"):
        op.execute(f"DELETE FROM {table} WHERE case_id IN (SELECT id FROM retired_cases)")
    op.execute("DELETE FROM cases WHERE id IN (SELECT id FROM retired_cases)")

    # v1 templates kept their rules in code that no longer exists.
    op.execute("DELETE FROM workbench_template_matches WHERE version = '1'")
    op.execute("DELETE FROM workbench_templates WHERE version = '1'")

    # Case columns only the earlier diagnosis flow wrote.
    for name in ("ck_cases_revision", "ck_cases_json", "ck_cases_diagnosis_mode"):
        op.execute(f"ALTER TABLE cases DROP CONSTRAINT IF EXISTS {name}")
    for column in ("corpus_manifest", "diagnosis_mode", "policy_version", "graph_epoch"):
        op.execute(f"ALTER TABLE cases DROP COLUMN IF EXISTS {column}")
    op.create_check_constraint("ck_cases_revision", "cases", "revision >= 0")
    op.create_check_constraint(
        "ck_cases_json", "cases",
        "jsonb_typeof(vehicle_json)='object' AND jsonb_typeof(fault_codes)='array' "
        "AND jsonb_typeof(intake_snapshot)='object'")


def downgrade():
    raise RuntimeError("0026 deleted retired data; restore the database backup instead of downgrading.")
