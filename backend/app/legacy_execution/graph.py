"""One-step LangGraph with fenced PostgreSQL checkpoints and DB facts.

Graph state contains IDs and progress only. The business step and publication
are read from authoritative tables after every process boundary.
"""

import hashlib
from typing import TypedDict
from uuid import UUID

from langgraph.graph import START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select

from app.legacy_execution.checkpoint import FencedPostgresSaver
from app.legacy_execution.runner import load_snapshot, run_diagnosis
from app.domain.policies import DomainError
from app.infrastructure.orm import diagnosis_publications, graph_progress, runs
from app.skills.registry import SkillRegistry


class GraphState(TypedDict, total=False):
    run_id: str
    candidate_ref: str
    step_id: str
    observation_id: str
    skill_ref: str
    question_hash: str


class DiagnosisGraph:
    def __init__(self, store, lease, stopped, on_published=lambda: None,
                 diagnostic_sink=None):
        self.store, self.lease = store, lease
        self.stopped, self.on_published = stopped, on_published
        self.diagnostic_sink = diagnostic_sink
        self.saver = FencedPostgresSaver(store, lease)
        builder = StateGraph(GraphState)
        for name in (
            "load_snapshot", "validate_context", "load_skill", "plan_questions",
            "agent_decide", "assess_evidence", "propose", "validate",
            "publish", "wait", "load_saved_observation", "update_hypotheses",
        ):
            builder.add_node(name, getattr(self, name))
        order = (
            "load_snapshot", "validate_context", "load_skill",
            "load_saved_observation", "update_hypotheses", "plan_questions",
            "agent_decide", "assess_evidence", "propose", "validate", "publish",
            "wait",
        )
        builder.add_edge(START, order[0])
        for left, right in zip(order, order[1:]):
            builder.add_edge(left, right)
        self.graph = builder.compile(checkpointer=self.saver)

    def _snapshot(self, state):
        return load_snapshot(self.store.engine, UUID(state["run_id"]))

    def load_snapshot(self, state):
        self._snapshot(state)
        return {"run_id": state["run_id"]}

    def validate_context(self, state):
        snap = self._snapshot(state)
        if not snap["case"]["corpus_manifest"]:
            raise DomainError("CORPUS_EMPTY", "No frozen eligible material")
        return {}

    def load_skill(self, state):
        snap = self._snapshot(state)
        system = snap["case"]["vehicle_json"].get("system", "")
        choices = SkillRegistry().select(system, {"vehicle": snap["case"]["vehicle_json"]})
        if len(choices) > 1:
            raise DomainError("SKILL_AMBIGUOUS", "Multiple skills match")
        if not choices:
            return {"skill_ref": ""}
        skill = SkillRegistry().load_body(choices[0]["name"], choices[0]["version"])
        return {"skill_ref": skill["metadata"]["name"] + ":" + skill["metadata"]["version"]}

    def plan_questions(self, state):
        snap = self._snapshot(state)
        query = snap["case"]["fault_description"]
        return {"question_hash": hashlib.sha256(query.encode()).hexdigest()}

    def agent_decide(self, state):
        snap = self._snapshot(state)
        if self.stopped.is_set():
            raise DomainError("DIAGNOSIS_INTERRUPTED", "Worker lost authorization")
        result = run_diagnosis(self.store, self.lease, self.stopped,
                               skill_ref=state.get("skill_ref") or None,
                               diagnostic_sink=self.diagnostic_sink)
        if not result.get("accepted"):
            raise DomainError("PROPOSAL_NOT_ACCEPTED", "Candidate was not accepted")
        with self.store.engine.connect() as c:
            reference = c.execute(select(graph_progress.c.checkpoint_ref).where(
                graph_progress.c.run_id == snap["run"]["id"])).scalar_one()
        if not reference:
            raise DomainError("CANDIDATE_NOT_STAGED", "Candidate checkpoint is unavailable")
        return {"candidate_ref": reference}

    def assess_evidence(self, state):
        draft = self.store.staged_diagnosis(self.lease)
        if draft is None or not draft.get("accepted"):
            raise DomainError("PROPOSAL_NOT_ACCEPTED", "Candidate evidence is unavailable")
        return {}

    def propose(self, state):
        draft = self.store.staged_diagnosis(self.lease)
        if draft["candidate"]["type"] not in {"propose_step", "conclude_area"}:
            raise DomainError("STEP_REQUIRED", "Current turn has no validated step or area end")
        return {}

    def validate(self, state):
        self._snapshot(state)
        if self.stopped.is_set():
            raise DomainError("DIAGNOSIS_INTERRUPTED", "Worker lost authorization")
        return {}

    def publish(self, state):
        run_id = UUID(state["run_id"])
        # Replaying a committed node after a checkpoint crash reads the original
        # publication; it never invokes the model or inserts another step.
        if run_id != self.lease.job["run_id"]:
            with self.store.engine.connect() as c:
                prior = c.execute(select(diagnosis_publications).where(
                    diagnosis_publications.c.run_id == run_id,
                    diagnosis_publications.c.node.in_(["publish", "area_close"]))).mappings().one_or_none()
            if prior is None:
                raise DomainError("RECOVERY_REQUIRED", "Prior publication is unavailable")
            return {"step_id": str(prior["step_id"]) if prior["step_id"] else ""}
        draft = self.store.staged_diagnosis(self.lease)
        if draft is None:
            raise DomainError("CANDIDATE_NOT_STAGED", "Candidate is unavailable")
        self.store.finish(self.lease, result=draft)
        with self.store.engine.connect() as c:
            published = c.execute(select(diagnosis_publications).where(
                diagnosis_publications.c.run_id == run_id,
                diagnosis_publications.c.node.in_(["publish", "area_close"]))).mappings().one_or_none()
        if published is None:
            raise DomainError("PUBLICATION_REJECTED", "Candidate publication failed")
        self.on_published()
        return {"step_id": str(published["step_id"]) if published["step_id"] else ""}

    def wait(self, state):
        if not state.get("step_id"):
            # A fenced area end has no invented question or observation.
            return {}
        token = interrupt({"case_id": self._snapshot_case_id(state),
                           "step_id": state["step_id"]})
        if not isinstance(token, dict) or set(token) != {"run_id", "observation_id"}:
            raise DomainError("RESUME_INVALID", "Saved observation reference required")
        if UUID(token["run_id"]) != self.lease.job["run_id"]:
            raise DomainError("RESUME_INVALID", "Run does not match the leased turn")
        return {"run_id": token["run_id"], "observation_id": token["observation_id"]}

    def _snapshot_case_id(self, state):
        with self.store.engine.connect() as c:
            return str(c.execute(select(runs.c.case_id).where(
                runs.c.id == UUID(state["run_id"]))).scalar_one())

    def load_saved_observation(self, state):
        snap = self._snapshot(state)
        observation_id = snap["run"]["input_payload"].get("observation_id")
        if observation_id is None:
            return {}
        if UUID(observation_id) not in {x["id"] for x in snap["observations"]}:
            raise DomainError("OBSERVATION_INVALID", "Saved observation is no longer effective")
        if snap["progress"]["step_id"] is None or not any(
            x["id"] == UUID(observation_id) and
            x["step_id"] == snap["progress"]["step_id"] for x in snap["observations"]
        ):
            raise DomainError("OBSERVATION_INVALID", "Saved observation is unrelated to current check")
        return {"observation_id": observation_id}

    def update_hypotheses(self, state):
        # No diagnostic conclusion is inferred here. The next candidate sees
        # current saved observations through load_snapshot/ProposalService.
        self._snapshot(state)
        return {}

    def execute(self):
        with self.store.engine.connect() as c:
            run = c.execute(select(runs).where(
                runs.c.id == self.lease.job["run_id"])).mappings().one()
        # One checkpoint thread per workflow turn. A committed publication is
        # authoritative even when its final checkpoint was interrupted; the
        # next turn starts from the saved observation and DB publication, not
        # from replaying the old run against an advanced case revision.
        config = {"configurable": {"thread_id": self.saver.workflow_id}}
        snapshot = self.graph.get_state(config)
        if snapshot.next:
            self.graph.invoke(None, config)
        else:
            self.graph.invoke({"run_id": str(run["id"])}, config)
