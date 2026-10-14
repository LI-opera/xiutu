"""Frozen minimal observations, trusted tool budgets and call receipts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007_tools"
down_revision = "0006_evidence_specs"
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


def status_check(col, values, name):
    return sa.CheckConstraint(col + " IN (" + ",".join(repr(x) for x in values) + ")", name=name)


for name in ["cases", "runs"]:
    sa.Table(name, metadata, sa.Column("id", UUID, primary_key=True))
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
    uid("actor_id"),
    stamp("created_at"),
    sa.UniqueConstraint("supersedes_id", name="uq_observation_successor"),
    sa.CheckConstraint(
        "created_revision>=0 AND jsonb_typeof(payload)='object'", name="ck_observation_payload"
    ),
    status_check(
        "kind", ["choice", "measurement", "composite", "unavailable"], "ck_observation_kind"
    ),
)


def upgrade():
    for table in [tool_executions, tool_calls, observations]:
        table.create(op.get_bind())
    op.execute("""CREATE FUNCTION wp07_observation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE oldrow observations;
 BEGIN
 IF TG_OP != 'INSERT' THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Immutable observation'; END IF;
 IF NOT EXISTS(SELECT 1 FROM cases WHERE id=NEW.case_id AND owner_id=NEW.actor_id AND revision>=NEW.created_revision) THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Observation case revision invalid'; END IF;
 IF NEW.supersedes_id IS NOT NULL THEN
 SELECT * INTO oldrow FROM observations WHERE id=NEW.supersedes_id;
 IF oldrow.id IS NULL OR oldrow.case_id<>NEW.case_id OR oldrow.area_id IS DISTINCT FROM NEW.area_id OR oldrow.step_id IS DISTINCT FROM NEW.step_id OR oldrow.created_revision>=NEW.created_revision THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Observation lineage invalid'; END IF;
 END IF;
 RETURN NEW;
 END $$""")
    op.execute(
        "CREATE TRIGGER wp07_observation_guard BEFORE INSERT OR UPDATE OR DELETE ON observations FOR EACH ROW EXECUTE FUNCTION wp07_observation_guard()"
    )


def downgrade():
    for table in [observations, tool_calls, tool_executions]:
        table.drop(op.get_bind())
    op.execute("DROP FUNCTION wp07_observation_guard()")
