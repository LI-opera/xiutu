"""Server-owned protocol binding and deterministic routing for the DKVB demo."""

import hashlib
import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from sqlalchemy import select

from app.agents.state import ProposalContext
from app.agents.trusted_protocol import (
    APPROVED_PROTOCOLS, DKVB_DEMO_PROTOCOL, TrustedProtocol, build_demo_candidates,
)
from app.domain.measurements import BindEvidence
from app.domain.policies import DomainError
from app.infrastructure.orm import (
    cases,
    chunks,
    diagnosis_protocol_bindings,
    diagnosis_steps,
)
from app.infrastructure.uow import UnitOfWork
from app.repositories.observations import ObservationRepository
from app.services.evidence_scope import owner_lock
from app.services.evidence_service import EvidenceService
from app.services.proposal_service import ProposalService


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def manifest_hash(manifest):
    return hashlib.sha256(_canonical(manifest).encode()).hexdigest()


def protocol_hash(protocol):
    payload = protocol.model_dump(mode="json") if hasattr(protocol, "model_dump") else protocol
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _profile_matches(actual, expected):
    return all(actual.get(key) == value for key, value in expected.items())


class ProtocolService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    def register(self, actor: UUID, case_id: UUID, candidates: dict[str, dict], *, connection=None):
        """Trusted application assembly only; intentionally not exposed as HTTP."""
        protocol = DKVB_DEMO_PROTOCOL
        expected = {x.check_id for x in protocol.checks}
        if set(candidates) != expected:
            raise DomainError("PROTOCOL_CANDIDATES_INVALID", "All registered checks are required")
        with UnitOfWork(self.engine, connection=connection) as lookup:
            c = lookup.connection
            case = c.execute(select(cases).where(cases.c.id == case_id,
                cases.c.owner_id == actor)).mappings().one_or_none()
        if case is None:
            raise DomainError("NOT_FOUND", "Case not found", 404)
        if not _profile_matches(case["vehicle_json"], protocol.applicable_vehicle_profile):
            raise DomainError("PROTOCOL_PROFILE_MISMATCH", "Synthetic vehicle profile differs")
        checked = {}
        validator = ProposalService(self.engine, self.settings)
        for check_id, candidate in candidates.items():
            result = validator.validate(ProposalContext(actor, case_id, case["revision"]), candidate,
                                        connection=connection)
            if not result["accepted"]:
                raise DomainError("PROTOCOL_CANDIDATE_REJECTED", check_id + " failed hard gates",
                                  details={"check_id": check_id,
                                           "issues": [{"code": x["code"], "path": x["path"]}
                                                      for x in result["issues"]]})
            checked[check_id] = result["candidate"]
        binding = {"protocol": protocol.model_dump(mode="json"), "candidates": checked}
        with UnitOfWork(self.engine, connection=connection) as u:
            c = u.connection
            owner_lock(c, actor)
            locked = c.execute(select(cases).where(cases.c.id == case_id,
                cases.c.owner_id == actor).with_for_update()).mappings().one()
            if locked["revision"] != case["revision"]:
                raise DomainError("REVISION_CONFLICT", "Case changed during protocol registration")
            if c.execute(select(diagnosis_protocol_bindings.c.id).where(
                    diagnosis_protocol_bindings.c.case_id == case_id,
                    diagnosis_protocol_bindings.c.graph_epoch == case["graph_epoch"])).first():
                raise DomainError("PROTOCOL_ALREADY_BOUND", "Protocol already bound", 409)
            c.execute(diagnosis_protocol_bindings.insert().values(
                id=uuid4(), case_id=case_id, owner_id=actor,
                graph_epoch=case["graph_epoch"], protocol_id=protocol.protocol_id,
                protocol_version=protocol.version, manifest_hash=manifest_hash(case["corpus_manifest"]),
                content_hash=protocol_hash(protocol), requires_review=False,
                vehicle_profile=protocol.applicable_vehicle_profile, binding_json=binding))
        return {"protocol_id": protocol.protocol_id, "protocol_version": protocol.version,
                "graph_epoch": case["graph_epoch"]}

    @staticmethod
    def clone_epoch(c, case_id: UUID, owner: UUID, old_epoch: int, new_epoch: int):
        old = c.execute(select(diagnosis_protocol_bindings).where(
            diagnosis_protocol_bindings.c.case_id == case_id,
            diagnosis_protocol_bindings.c.owner_id == owner,
            diagnosis_protocol_bindings.c.graph_epoch == old_epoch)).mappings().one_or_none()
        if old is None:
            return
        c.execute(diagnosis_protocol_bindings.insert().values(
            id=uuid4(), case_id=case_id, owner_id=owner, graph_epoch=new_epoch,
            protocol_id=old["protocol_id"], protocol_version=old["protocol_version"],
            manifest_hash=old["manifest_hash"], content_hash=old.get("content_hash"),
            requires_review=old.get("requires_review", True), vehicle_profile=old["vehicle_profile"],
            binding_json=old["binding_json"]))

    def bind_for_case(self, actor: UUID, case_id: UUID, *, connection=None):
        """Bind the approved conservative package without a private seed script."""
        with UnitOfWork(self.engine, connection=connection) as lookup:
            c = lookup.connection
            case = c.execute(select(cases).where(
                cases.c.id == case_id, cases.c.owner_id == actor)).mappings().one_or_none()
            if case is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            existing = c.execute(select(diagnosis_protocol_bindings.c.id).where(
                diagnosis_protocol_bindings.c.case_id == case_id,
                diagnosis_protocol_bindings.c.graph_epoch == case["graph_epoch"])).first()
            if existing:
                return
            if case.get("diagnosis_mode") != "conservative":
                return
            if not _profile_matches(case["vehicle_json"], DKVB_DEMO_PROTOCOL.applicable_vehicle_profile):
                raise DomainError("CONSERVATIVE_PROTOCOL_NOT_APPLICABLE",
                                  "No conservative protocol matches this vehicle", 422)
            manifest = list(case["corpus_manifest"])
            version_ids = [UUID(item["document_version_id"]) for item in manifest]
            rows = c.execute(select(chunks).where(
                chunks.c.document_version_id.in_(version_ids))).mappings().all()
        if not rows:
            raise DomainError("CONSERVATIVE_PROTOCOL_MATERIAL_MISSING",
                              "Conservative protocol material is not indexed", 422)

        bound = {}
        evidence = EvidenceService(self.engine, self.settings)

        def cite(text):
            row = next((item for item in rows if text in item["text"]), None)
            if row is None:
                raise DomainError("CONSERVATIVE_PROTOCOL_MATERIAL_MISSING",
                                  "Required conservative protocol text is unavailable", 422,
                                  details={"text": text[:80]})
            start = row["text"].index(text)
            index_id = next(UUID(item["index_id"]) for item in manifest
                if item["document_version_id"] == str(row["document_version_id"]))
            body = BindEvidence(chunk_id=row["id"], document_version_id=row["document_version_id"],
                                index_id=index_id, start=start, end=start + len(text), quote=text)
            key = "protocol-r1-" + hashlib.sha256(
                f"{case_id}:{row['id']}:{start}:{text}".encode()).hexdigest()
            _, item = evidence.bind(actor, case_id, body, key, connection=connection)
            return {"text": text, "references": [{"evidence_id": item["evidence_id"],
                "document_version_id": str(row["document_version_id"])}]}

        bound.update(build_demo_candidates(cite))
        self.register(actor, case_id, bound, connection=connection)

    def _binding(self, c, case, actor):
        row = c.execute(select(diagnosis_protocol_bindings).where(
            diagnosis_protocol_bindings.c.case_id == case["id"],
            diagnosis_protocol_bindings.c.owner_id == actor,
            diagnosis_protocol_bindings.c.graph_epoch == case["graph_epoch"])).mappings().one_or_none()
        if row is None:
            return None
        if row["manifest_hash"] != manifest_hash(case["corpus_manifest"]):
            raise DomainError("PROTOCOL_MANIFEST_CHANGED", "Frozen material range changed")
        if not _profile_matches(case["vehicle_json"], row["vehicle_profile"]):
            raise DomainError("PROTOCOL_PROFILE_MISMATCH", "Vehicle profile changed")
        if row.get("requires_review") or not row.get("content_hash"):
            raise DomainError("PROTOCOL_HISTORY_REVIEW_REQUIRED",
                              "Historical protocol observations require explicit review", 409)
        if (row["protocol_id"], row["protocol_version"]) not in APPROVED_PROTOCOLS:
            raise DomainError("PROTOCOL_NOT_TRUSTED", "Protocol version is not registered")
        try:
            protocol = TrustedProtocol.model_validate(row["binding_json"]["protocol"])
        except Exception as exc:
            raise DomainError("PROTOCOL_SNAPSHOT_INVALID", "Frozen protocol is invalid") from exc
        if (protocol.protocol_id != row["protocol_id"] or protocol.version != row["protocol_version"]
                or protocol_hash(protocol) != row["content_hash"]):
            raise DomainError("PROTOCOL_SNAPSHOT_CHANGED", "Frozen protocol hash differs")
        return row, protocol

    def validate_observation_fields(self, c, actor, case, step, body):
        loaded = self._binding(c, case, actor)
        fields = dict(body.protocol_fields or {})
        meta = (step["validation_json"] or {}).get("protocol") or {}
        if loaded is None or not meta:
            if fields:
                raise DomainError("PROTOCOL_FIELDS_FORBIDDEN", "Current check has no guided fields", 422)
            return {}
        _, protocol = loaded
        check = next((x for x in protocol.checks if x.check_id == meta.get("next_check_id")), None)
        option = next((x for x in check.input_schema.options if x.option_id == body.option_id), None) if check else None
        if check is None or option is None:
            raise DomainError("PROTOCOL_INPUT_INVALID", "Guided input does not match current check", 422)
        if check.check_id == "CHK-03" and not fields.get("measurement_run_id"):
            fields["measurement_run_id"] = f"LOAD-{str(case['id'])[:8]}-{case['revision'] + 1:04d}"
        if check.check_id == "CHK-07" and not fields.get("retest_run_id"):
            fields["retest_run_id"] = f"R1-{str(case['id'])[:8]}-{case['revision'] + 1:04d}"
        if check.check_id == "CHK-11":
            history = list(ObservationRepository(c).read(case["id"], None, case["revision"]))
            prior_control = next((item for item in reversed(history)
                if item["payload"].get("check_id") == "CHK-09"
                and item["payload"].get("option_id") == "setup.completed"), None)
            prior_retest = next((item for item in reversed(history)
                if item["payload"].get("check_id") == "CHK-07"), None)
            if prior_control:
                fields["final_stage"] = "after_control_setup"
                fields["source_observation_id"] = str(prior_control["id"])
                fields.setdefault("final_retest_run_id", f"CTRL-{str(case['id'])[:8]}-{case['revision'] + 1:04d}")
                missing_final = [f"final_{side}_{index}_hpa" for index in range(1, 4)
                                 for side in ("target", "actual")
                                 if not str(fields.get(f"final_{side}_{index}_hpa", "")).strip()]
                if missing_final:
                    raise DomainError("PROTOCOL_FIELDS_MISSING", "Control setup requires a new final three-frame record", 422,
                                      details={"missing_fields": missing_final})
            else:
                prior_fields = (prior_retest or {}).get("payload", {}).get("protocol_fields", {})
                fields["final_stage"] = "after_air_repair"
                fields["source_observation_id"] = str(prior_retest["id"]) if prior_retest else ""
                fields.setdefault("final_retest_run_id", prior_fields.get("retest_run_id", ""))
                for index in range(1, 4):
                    for side in ("target", "actual"):
                        source = f"{side}_{index}_hpa"
                        fields.setdefault(f"final_{source}", prior_fields.get(source, ""))
        definitions = option.fields
        allowed = {x.name: x for x in definitions}
        if set(fields) - set(allowed):
            raise DomainError("PROTOCOL_FIELD_UNKNOWN", "Unknown guided observation field", 422)
        normalized = {}
        missing = []
        for name, definition in allowed.items():
            raw = fields.get(name)
            if definition.required and (not isinstance(raw, str) or not raw.strip()):
                missing.append(name)
                continue
            if raw is None:
                continue
            value_text = raw.strip()
            if definition.kind == "select" and value_text not in definition.options:
                raise DomainError("PROTOCOL_FIELD_INVALID", "Guided field option is invalid", 422)
            if definition.kind == "decimal":
                try:
                    number = Decimal(value_text)
                except InvalidOperation:
                    raise DomainError("PROTOCOL_FIELD_INVALID", "Guided decimal is invalid", 422) from None
                if not number.is_finite() or abs(number) > Decimal("1e30"):
                    raise DomainError("PROTOCOL_FIELD_INVALID", "Guided decimal is out of range", 422)
            if len(value_text) > 500:
                raise DomainError("PROTOCOL_FIELD_INVALID", "Guided field is too long", 422)
            normalized[name] = value_text
        if missing:
            raise DomainError("PROTOCOL_FIELDS_MISSING", "Required guided fields are missing", 422,
                              details={"missing_fields": missing})
        return {"option_id": option.option_id, "option_label": option.label,
                "protocol_fields": normalized,
                "protocol_id": protocol.protocol_id, "protocol_version": protocol.version,
                "protocol_content_hash": row["content_hash"] if (row := loaded[0]) else None,
                "check_id": check.check_id}

    def unavailable_identity(self, c, actor, case, step):
        loaded = self._binding(c, case, actor)
        meta = (step["validation_json"] or {}).get("protocol") or {}
        if loaded is None or not meta:
            return {}
        row, protocol = loaded
        check_id = meta.get("next_check_id")
        if not any(item.check_id == check_id for item in protocol.checks):
            raise DomainError("PROTOCOL_INPUT_INVALID", "Guided input does not match current check", 422)
        return {"option_id": "unavailable", "option_label": "当前无法测量或检查",
                "protocol_fields": {}, "protocol_id": protocol.protocol_id,
                "protocol_version": protocol.version,
                "protocol_content_hash": row["content_hash"], "check_id": check_id}

    def route(self, run, case, progress):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            loaded = self._binding(c, case, case["owner_id"])
            if loaded is None:
                return None
            row, protocol = loaded
            binding = row["binding_json"]
            observation_id = run["input_payload"].get("observation_id")
            if observation_id is None and not run["input_payload"].get("context_revised"):
                return self._decision(case, protocol, binding, f"PROTOCOL_START_{protocol.start_check_id}", None,
                                      protocol.start_check_id, "next_check", None, None)
            effective = {x["id"]: x for x in ObservationRepository(c).read(
                case["id"], None, case["revision"])}
            if run["input_payload"].get("context_revised"):
                replacement = UUID(run["input_payload"]["context_revised"])
                obs = effective.get(replacement)
                if obs is None:
                    raise DomainError("OBSERVATION_INVALID", "Corrected observation is not current")
                step = c.execute(select(diagnosis_steps).where(
                    diagnosis_steps.c.id == obs["step_id"], diagnosis_steps.c.case_id == case["id"])
                    ).mappings().one()
            else:
                obs = effective.get(UUID(observation_id))
                step = c.execute(select(diagnosis_steps).where(
                    diagnosis_steps.c.id == progress["step_id"], diagnosis_steps.c.case_id == case["id"])
                    ).mappings().one_or_none()
            if obs is None or step is None or obs["step_id"] != step["id"]:
                raise DomainError("OBSERVATION_INVALID", "Protocol observation is not current")
            protocol_meta = (step["validation_json"] or {}).get("protocol") or {}
            current_check = protocol_meta.get("next_check_id")
            payload = obs["payload"]
            if (payload.get("protocol_id") != protocol.protocol_id or
                    payload.get("protocol_version") != protocol.version or
                    payload.get("protocol_content_hash") != row["content_hash"] or
                    payload.get("check_id") != current_check):
                raise DomainError("PROTOCOL_OBSERVATION_INVALID", "Observation lacks trusted protocol identity")
            result_value = self._result_value(current_check, payload)
            matches = [x for x in protocol.transitions if x.current_check_id == current_check
                       and x.result_value == result_value]
            if len(matches) != 1:
                raise DomainError("PROTOCOL_TRANSITION_AMBIGUOUS", "Exactly one transition is required")
            transition = matches[0]
            return self._decision(case, protocol, binding, transition.transition_id,
                                  str(obs["id"]), transition.next_check_id,
                                  transition.decision, transition.terminal_code,
                                  transition.reason, current_check=current_check,
                                  observation_ids=[str(obs["id"])])

    @staticmethod
    def _result_value(check_id, payload):
        if payload.get("option_id") == "unavailable":
            return "unavailable"
        option_id, fields = payload.get("option_id"), payload.get("protocol_fields", {})
        if check_id == "CHK-05-SUPPLEMENT":
            if payload.get("protocol_version") == "3.0.0":
                return option_id
            return {"supplement.localized": "leak.localized",
                    "supplement.inconclusive": "leak.inconclusive"}.get(option_id, option_id)
        if check_id == "CHK-03":
            try:
                deficits = [Decimal(fields[f"target_{i}_hpa"]) - Decimal(fields[f"actual_{i}_hpa"])
                            for i in range(1, 4)]
            except (KeyError, InvalidOperation):
                return "load.insufficient"
            in_band = all(Decimal("-150") <= value <= Decimal("150") for value in deficits)
            under = all(value > Decimal("150") for value in deficits)
            over = all(value < Decimal("-150") for value in deficits)
            if under:
                return "load.underboost"
            if in_band and fields.get("symptom") == "present":
                return "load.symptom_elsewhere"
            if over:
                return "load.overboost"
            return "load.insufficient"
        if check_id == "CHK-07":
            if fields.get("leak_result") == "localized":
                return "retest.same_leak"
            try:
                deficits = [Decimal(fields[f"target_{i}_hpa"]) - Decimal(fields[f"actual_{i}_hpa"])
                            for i in range(1, 4)]
            except (KeyError, InvalidOperation):
                return "retest.insufficient"
            if fields.get("leak_result") != "not_found":
                return "retest.insufficient"
            in_band = all(Decimal("-150") <= value <= Decimal("150") for value in deficits)
            under = all(value > Decimal("150") for value in deficits)
            if in_band and fields.get("symptom") == "absent":
                return "retest.recovered"
            if under:
                return "retest.residual_underboost"
            if in_band and fields.get("symptom") == "present":
                return "retest.symptom_elsewhere"
            return "retest.insufficient"
        if check_id == "CHK-11":
            try:
                deficits = [Decimal(fields[f"final_target_{i}_hpa"]) - Decimal(fields[f"final_actual_{i}_hpa"])
                            for i in range(1, 4)]
            except (KeyError, InvalidOperation):
                return "final.incomplete"
            passed = (all(Decimal("-150") <= value <= Decimal("150") for value in deficits)
                      and fields.get("symptom") == "absent" and fields.get("p0299") == "absent"
                      and fields.get("repairs_rechecked") == "completed"
                      and fields.get("conflict") == "none")
            return "final.passed" if passed else "final.incomplete"
        return option_id

    def _decision(self, case, protocol, binding, transition_id, observation_id,
                  next_check_id, decision, terminal_code, reason, current_check=None,
                  observation_ids=None):
        if decision in {"handoff", "area_summary"}:
            prior = binding["candidates"][current_check]
            checked = ProposalService(self.engine, self.settings).validate(
                ProposalContext(case["owner_id"], case["id"], case["revision"]), prior)
            if not checked["accepted"]:
                raise DomainError("PROTOCOL_CANDIDATE_REJECTED",
                                  "Terminal check source no longer validates",
                                  details={"issues": [{"code": x["code"], "path": x["path"]}
                                                       for x in checked["issues"]]})
            candidate = {"type": "conclude_area", "component_key": prior["component_key"],
                         "finding": prior["purpose"], "support_rule_id": None,
                         "conclusion_scope": None, "assessment": "unknown",
                         "observation_ids": observation_ids or []}
            evidence_refs = sorted({str(ref["evidence_id"])
                for path in [prior.get("purpose"), prior.get("location"),
                             *prior.get("prerequisites", []), *prior.get("actions", []),
                             *prior.get("input", {}).get("choices", [])]
                if isinstance(path, dict) for ref in path.get("references", [])})
            return {"accepted": True, "candidate": candidate, "disposition": "needs_input",
                    "issues": [], "provenance": [], "proposal_repair_used": False,
                    "tool_call_count": 0, "protocol_terminal": {
                        "decision": decision, "terminal_code": terminal_code,
                        "transition_id": transition_id, "reason": reason,
                        "protocol_id": protocol.protocol_id, "protocol_version": protocol.version,
                        "evidence_refs": evidence_refs}}
        if next_check_id is None or next_check_id not in binding["candidates"]:
            raise DomainError("PROTOCOL_CANDIDATE_MISSING", "Registered next check is unavailable")
        candidate = deepcopy(binding["candidates"][next_check_id])
        checked = ProposalService(self.engine, self.settings).validate(
            ProposalContext(case["owner_id"], case["id"], case["revision"]), candidate)
        if not checked["accepted"]:
            raise DomainError("PROTOCOL_CANDIDATE_REJECTED", "Registered check no longer validates",
                              details={"issues": [{"code": x["code"], "path": x["path"]}
                                                   for x in checked["issues"]]})
        evidence_refs = sorted({str(ref["evidence_id"])
            for path in [candidate.get("purpose"), candidate.get("location"),
                         *candidate.get("prerequisites", []), *candidate.get("actions", []),
                         *candidate.get("input", {}).get("choices", [])]
            if isinstance(path, dict) for ref in path.get("references", [])})
        target = next(c for c in protocol.checks if c.check_id == next_check_id)
        meta = {"decision": decision, "protocol_id": protocol.protocol_id,
                "protocol_version": protocol.version, "transition_id": transition_id,
                "current_check_id": current_check, "observation_id": observation_id,
                "next_check_id": next_check_id, "evidence_refs": evidence_refs,
                "reason_code": "GUIDED_INPUT_REQUIRED" if decision == "need_input" else "TRUSTED_TRANSITION",
                "handoff_reason": reason,
                "options": [item.model_dump(mode="json") for item in target.input_schema.options],
                "presentation": target.presentation.model_dump(mode="json")}
        checked["protocol_decision"] = meta
        checked["proposal_repair_used"] = False
        checked["tool_call_count"] = 0
        return checked
