"""WP-12 atomic observation admission; no model or tool calls in the transaction."""

import hashlib
import re
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import select, update

from app.domain.measurements import CompareInput, DecimalText
from app.domain.policies import DomainError, check_revision
from app.domain.schemas import InputModel, PersistedText
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import (
    case_evidence,
    cases,
    diagnosis_area_conclusions,
    diagnosis_steps,
    graph_progress,
    measurement_specs,
    observations,
    runs,
)
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import owner_lock
from app.services.evidence_service import EvidenceService, row_owned
from app.services.run_service import enqueue, idempotent, lock_case
from app.validators.support import operating_conditions


class MeasuredValue(InputModel):
    spec_id: UUID
    value: DecimalText
    unit: Literal["C", "F", "Pa", "kPa", "bar", "V", "mV", "ohm", "kohm"]
    conditions: dict[PersistedText, PersistedText] = Field(min_length=1, max_length=20)


class SubmitObservation(InputModel):
    expected_revision: int = Field(ge=0, strict=True)
    graph_epoch: int = Field(ge=0, strict=True)
    step_id: UUID
    kind: Literal["choice", "measurement", "composite", "unavailable"]
    choice_index: int | None = Field(default=None, ge=0, strict=True)
    option_id: PersistedText | None = Field(default=None, min_length=1, max_length=80)
    conditions: dict[PersistedText, PersistedText] | None = Field(default=None, max_length=20)
    measurements: list[MeasuredValue] = Field(default_factory=list, max_length=8)
    reason: PersistedText | None = Field(default=None, min_length=1, max_length=1000)
    protocol_fields: dict[PersistedText, PersistedText] = Field(default_factory=dict, max_length=16)
    topic_question_id: PersistedText | None = Field(default=None, min_length=1, max_length=80)
    topic_option_id: PersistedText | None = Field(default=None, min_length=1, max_length=80)
    topic_version: PersistedText | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def shape(self):
        if any(value is not None for value in (self.topic_question_id, self.topic_option_id, self.topic_version)) and not all(
            value is not None for value in (self.topic_question_id, self.topic_option_id, self.topic_version)
        ):
            raise ValueError("Topic question, option and version must be supplied together")
        if self.kind == "unavailable":
            if (not self.reason or self.choice_index is not None or self.option_id is not None or self.measurements
                    or self.conditions is not None or self.protocol_fields):
                raise ValueError("Unavailable requires only a reason")
        elif self.reason is not None:
            raise ValueError("Reason is reserved for unavailable")
        elif self.kind == "choice" and ((self.choice_index is None) == (self.option_id is None)
                                         or self.measurements):
            raise ValueError("Choice requires exactly one legacy index or stable option id")
        elif self.kind == "measurement" and (
                self.choice_index is not None or not self.measurements or self.conditions is not None):
            raise ValueError("Measurement requires measured values")
        elif self.kind == "composite" and (self.choice_index is None or not self.measurements):
            raise ValueError("Composite requires choice and measurements")
        return self


class ObservationService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    @staticmethod
    def _reject_quarantined_parent(c, parent, current_epoch):
        progress = c.execute(select(graph_progress.c.phase, graph_progress.c.graph_epoch).where(
            graph_progress.c.run_id == parent["id"]).with_for_update()).one_or_none()
        if (progress is not None and progress.graph_epoch == current_epoch and
            (progress.phase == "failed" or
             (parent["error_json"] or {}).get("code") == "CHECKPOINT_INCONSISTENT")):
            raise DomainError("CHECKPOINT_QUARANTINED",
                              "Published check requires manual recovery", 409)

    def submit(self, actor: UUID, case_id: UUID, body: SubmitObservation, key: str):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            # Source revocation takes the same owner lock before any case row lock.
            owner_lock(c, actor)
            executed = False

            def action():
                nonlocal executed
                executed = True
                case = lock_case(c, actor, case_id)
                check_revision(case["revision"], body.expected_revision)
                if case["graph_epoch"] != body.graph_epoch:
                    raise DomainError("GRAPH_EPOCH_STALE", "Diagnosis graph changed")
                if case["status"] != "waiting_input":
                    raise DomainError("NOT_WAITING", "Case is not waiting for an observation")
                step = c.execute(select(diagnosis_steps).where(
                    diagnosis_steps.c.id == body.step_id,
                    diagnosis_steps.c.case_id == case_id,
                ).with_for_update()).mappings().one_or_none()
                if step is None or step["status"] != "waiting_input":
                    raise DomainError("STEP_NOT_CURRENT", "Current step changed")
                parent = c.execute(select(runs).where(runs.c.id == step["run_id"])
                                   .with_for_update()).mappings().one()
                self._reject_quarantined_parent(c, parent, case["graph_epoch"])
                if parent["status"] != "waiting_input" or parent["output_revision"] != case["revision"]:
                    raise DomainError("RUN_NOT_WAITING", "Published check changed")
                payload = self._payload(c, actor, case_id, case, step, body, key)
                next_revision = case["revision"] + 1
                # Existing observation integrity trigger checks against the
                # case revision at INSERT time; all writes still share one TX.
                c.execute(update(cases).where(cases.c.id == case_id).values(
                    revision=next_revision, status="analyzing"))
                obs_id = uuid4()
                c.execute(observations.insert().values(
                    id=obs_id, case_id=case_id, area_id=step["area_id"],
                    step_id=step["id"], kind=body.kind, payload=payload,
                    created_revision=next_revision, actor_id=actor,
                ))
                c.execute(update(diagnosis_steps).where(diagnosis_steps.c.id == step["id"])
                          .values(status="completed"))
                c.execute(update(diagnosis_area_conclusions).where(
                    diagnosis_area_conclusions.c.area_id == step["area_id"],
                    diagnosis_area_conclusions.c.graph_epoch == case["graph_epoch"])
                    .values(needs_review=True, review_reason="new_observation"))
                _, response = enqueue(c, actor, "diagnosis",
                    {"case_id": str(case_id), "observation_id": str(obs_id)},
                    case_id, next_revision, parent=parent, new_turn=True)
                run_id = UUID(response["run_id"])
                run = c.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
                c.execute(graph_progress.insert().values(
                    workflow_id=run["workflow_id"], turn_id=run["turn_id"],
                    case_id=case_id, run_id=run_id, graph_epoch=case["graph_epoch"],
                    phase="resuming", step_id=step["id"],
                ))
                append_event(c, run_id, "observation.saved",
                             {"observation_id": str(obs_id), "case_revision": next_revision})
                return 202, {**response, "observation_id": str(obs_id),
                             "case_revision": next_revision, "graph_epoch": case["graph_epoch"]}

            status, response = idempotent(c, actor,
                f"POST /api/v2/cases/{case_id}/observations", key,
                body.model_dump(mode="json"), action)
            if not executed:
                # A committed replay is historical, but cannot be presented as
                # currently usable after this parent is quarantined. Keep the
                # idempotency-row -> case -> step -> run -> progress lock order.
                case = lock_case(c, actor, case_id)
                step = c.execute(select(diagnosis_steps).where(
                    diagnosis_steps.c.id == body.step_id,
                    diagnosis_steps.c.case_id == case_id).with_for_update()
                ).mappings().one_or_none()
                if step is None:
                    raise DomainError("STEP_NOT_CURRENT", "Current step changed")
                parent = c.execute(select(runs).where(runs.c.id == step["run_id"])
                                   .with_for_update()).mappings().one()
                self._reject_quarantined_parent(c, parent, case["graph_epoch"])
            return status, response

    def list(self, actor: UUID, case_id: UUID):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            case = c.execute(select(cases).where(cases.c.id == case_id,
                cases.c.owner_id == actor)).mappings().one_or_none()
            if case is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            rows = c.execute(select(observations).where(observations.c.case_id == case_id)
                .order_by(observations.c.created_revision, observations.c.id)
                .limit(101)).mappings().all()
            if len(rows) > 100:
                raise DomainError("RESULT_TOO_LARGE", "Observation history exceeds page limit", 422)
            superseded = {x["supersedes_id"] for x in rows if x["supersedes_id"]}
            items = []
            for x in rows:
                step_data = c.execute(select(diagnosis_steps.c.candidate_json, diagnosis_steps.c.validation_json).where(
                    diagnosis_steps.c.id == x["step_id"],
                    diagnosis_steps.c.case_id == case_id)).mappings().one_or_none()
                candidate = step_data["candidate_json"] if step_data else None
                protocol = (step_data["validation_json"] or {}).get("protocol") if step_data else None
                required_conditions = None
                if candidate and candidate.get("type") == "propose_step":
                    from app.agents.state import ProposeStep
                    required_conditions = operating_conditions(
                        ProposeStep.model_validate(candidate).prerequisites)
                items.append({"id": str(x["id"]), "area_id": str(x["area_id"]) if x["area_id"] else None,
                           "step_id": str(x["step_id"]) if x["step_id"] else None,
                           "kind": x["kind"], "payload": x["payload"],
                           "input_schema": candidate.get("input") if candidate else None,
                           "protocol": protocol, "required_conditions": required_conditions,
                           "created_revision": x["created_revision"],
                           "supersedes_id": str(x["supersedes_id"]) if x["supersedes_id"] else None,
                           "correction_reason": x["correction_reason"],
                           "effective": x["id"] not in superseded})
            return {"case_id": str(case_id), "revision": case["revision"], "items": items}

    def _payload(self, c, actor, case_id, case, step, body, key):
        form = step["candidate_json"].get("input", {})
        if body.kind != "unavailable" and body.kind != form.get("kind"):
            raise DomainError("INPUT_KIND_MISMATCH", "Input type differs from current check", 422)
        if body.kind == "unavailable":
            from app.services.protocol_service import ProtocolService
            identity = ProtocolService(self.engine, self.settings).unavailable_identity(
                c, actor, case, step)
            return {"reason": body.reason, "component_key": step["candidate_json"]["component_key"],
                    "checked": False, **identity}
        component = step["candidate_json"]["component_key"]
        payload = {"component_key": component, "checked": False}
        from app.services.protocol_service import ProtocolService
        protocol_payload = ProtocolService(self.engine, self.settings).validate_observation_fields(
            c, actor, case, step, body)
        payload.update(protocol_payload)
        if body.topic_question_id is not None:
            from app.topics.dkvb_v2 import validate_annotation
            payload.update(validate_annotation(case, protocol_payload,
                body.topic_question_id, body.topic_option_id, body.topic_version))
        if protocol_payload:
            from app.agents.state import ProposeStep
            required = operating_conditions(ProposeStep.model_validate(
                step["candidate_json"]).prerequisites)
            if required is None or body.conditions != required:
                raise DomainError("CONDITIONS_MISMATCH",
                                  "Confirm the current check conditions", 422)
            payload.update(checked=True, conditions=required)
        if protocol_payload:
            protocol_options = ((step["validation_json"] or {}).get("protocol") or {}).get("options", [])
            published_index = next((index for index, item in enumerate(protocol_options)
                                    if item.get("option_id") == protocol_payload["option_id"]), -1)
            if published_index < 0 or published_index >= len(form.get("choices", [])):
                raise DomainError("PROTOCOL_OPTION_MISMATCH",
                                  "Published option id differs from frozen protocol", 409)
            payload.update(choice_index=published_index,
                           selected=protocol_payload["option_label"], checked=True)
        elif body.choice_index is not None:
            choices = form.get("choices", [])
            if body.choice_index >= len(choices):
                raise DomainError("CHOICE_INVALID", "Choice is not part of current check", 422)
            payload.update(choice_index=body.choice_index,
                           selected=choices[body.choice_index]["text"])
            # Only a bounded, source-backed observation choice may establish a
            # premise. A warning such as "not checked" is a saved answer, not
            # evidence that the component was inspected or found normal.
            selected = choices[body.choice_index]["text"].strip()
            states = (
                (rf"{re.escape(component)} 插头松动[。.]?", "connector_state", "loose"),
                (rf"{re.escape(component)} 插头牢固[。.]?", "connector_state", "secure"),
                (rf"{re.escape(component)} 外观完好[。.]?", "appearance_state", "intact"),
                (rf"{re.escape(component)} 外观损坏[。.]?", "appearance_state", "damaged"),
                (rf"{re.escape(component)} 外壳完整[。.]?", "housing_state", "intact"),
                (rf"{re.escape(component)} 外壳破损[。.]?", "housing_state", "damaged"),
            )
            for pattern, field, value in states:
                if re.fullmatch(pattern, selected):
                    payload.update(checked=True, **{field: value})
                    break
            if payload["checked"]:
                from app.agents.state import ProposeStep
                conditions = operating_conditions(ProposeStep.model_validate(
                    step["candidate_json"]).prerequisites)
                if conditions is not None and body.conditions == conditions:
                    payload["conditions"] = conditions
                else:
                    raise DomainError("CONDITIONS_MISMATCH",
                                      "Confirm the current check conditions", 422)
        expected = form.get("measurements", [])
        if len(body.measurements) != len(expected):
            raise DomainError("MEASUREMENT_INCOMPLETE", "All published measurements are required", 422)
        if len({x.spec_id for x in body.measurements}) != len(body.measurements):
            raise DomainError("MEASUREMENT_DUPLICATE", "Repeated specification", 422)
        measured = []
        evidence = EvidenceService(self.engine, self.settings)
        for item in body.measurements:
            claimed = next((x for x in expected if x.get("spec_id") == str(item.spec_id)), None)
            if claimed is None:
                raise DomainError("SPEC_NOT_IN_STEP", "Specification is not part of current check", 422)
            spec = row_owned(c, actor, measurement_specs, item.spec_id)
            linked = row_owned(c, actor, case_evidence, spec["evidence_id"])
            if (spec["review_status"] != "approved" or spec["needs_review"]
                    or linked["case_id"] != case_id
                    or spec["definition"] != {k: v for k, v in claimed.items() if k != "spec_id"}):
                raise DomainError("SPEC_INVALID", "Approved specification changed")
            if item.conditions != spec["definition"]["conditions"]:
                raise DomainError("CONDITIONS_MISMATCH", "Measurement conditions differ", 422)
            data = CompareInput(value=item.value, quantity=spec["definition"]["quantity"],
                                unit=item.unit, conditions=item.conditions)
            comparison_key = "obs-" + hashlib.sha256(
                f"{case_id}:{step['id']}:{key}:{item.spec_id}".encode()).hexdigest()
            _, result = evidence.compare(actor, item.spec_id, data,
                comparison_key, connection=c)
            if result["result"]["outcome"] == "unit_mismatch":
                raise DomainError("UNIT_MISMATCH", "Measurement unit does not match quantity", 422)
            if result["result"]["outcome"] not in {"within_range", "out_of_range"}:
                raise DomainError("SPEC_INVALID", "Specification is not currently usable")
            measured.append({"spec_id": str(item.spec_id), "comparison_id": result["id"],
                             "value": item.value, "unit": item.unit,
                             "conditions": item.conditions,
                             "outcome": result["result"]["outcome"]})
        if measured:
            payload["checked"] = True
            payload["measurements"] = measured
            if len(measured) == 1:
                payload["comparison_id"] = measured[0]["comparison_id"]
                payload["conditions"] = measured[0]["conditions"]
        return payload
