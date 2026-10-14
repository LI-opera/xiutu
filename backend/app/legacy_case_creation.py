"""Explicit old-case construction for isolated replay and retired previews.

The formal application does not import this module. Historical reads continue
through CaseService; new product cases use its template-only create method.
"""
import hashlib
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.agents.trusted_protocol import DKVB_DEMO_PROTOCOL, required_demo_material_texts
from app.domain.policies import DomainError
from app.infrastructure.orm import (cases, chunks, diagnosis_areas,
    diagnosis_protocol_bindings, diagnosis_steps, graph_progress, idempotency_keys,
    jobs, observations, runs)
from app.infrastructure.uow import UnitOfWork
from app.repositories.cases import CaseRepository
from app.services.case_service import CaseService, SCOPE
from app.services.run_service import enqueue


class LegacyCaseService(CaseService):
    def create(self, actor, data, key):
        if not re.fullmatch(r"xiutu_test_[a-z0-9_]{1,40}", self.engine.url.database or ""):
            raise ValueError("Legacy case creation requires an isolated test database")
        if data.workbench_flow == "template-match-v1":
            return super().create(actor, data, key)
        if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
            raise DomainError("VALIDATION_ERROR", "Valid Idempotency-Key required", 422)
        digest = hashlib.sha256(
            json.dumps(
                data.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        match = (
            idempotency_keys.c.actor_id == actor,
            idempotency_keys.c.route_scope == SCOPE,
            idempotency_keys.c.key == key,
        )
        with UnitOfWork(self.engine) as uow:
            conn = uow.connection
            from app.services.evidence_scope import freeze_manifest, owner_lock

            owner_lock(conn, actor)
            acquired = conn.execute(
                insert(idempotency_keys)
                .values(
                    actor_id=actor,
                    route_scope=SCOPE,
                    key=key,
                    request_hash=digest,
                    response_status=201,
                    response_json={},
                )
                .on_conflict_do_nothing(index_elements=["actor_id", "route_scope", "key"])
                .returning(idempotency_keys.c.key)
            ).scalar_one_or_none()
            if acquired is None:
                saved = conn.execute(select(idempotency_keys).where(*match)).mappings().one()
                if saved["request_hash"] != digest:
                    raise DomainError(
                        "IDEMPOTENCY_CONFLICT", "Idempotency key belongs to a different request"
                    )
                return saved["response_status"], saved["response_json"]
            if data.topic_version is not None:
                from app.topics import dkvb_b01, dkvb_b02
                topic_module = {dkvb_b01.TOPIC_VERSION: dkvb_b01,
                                dkvb_b02.TOPIC_VERSION: dkvb_b02}.get(data.topic_version)
                actual = data.vehicle.model_dump(mode="json")
                if (topic_module is None or data.diagnosis_mode != "conservative"
                    or actual.get("model") != "虚拟探岳 DKVB 演示台架"
                    or actual.get("engine_code") != "DKVB-DEMO"
                    or actual.get("year") not in {2019, 2020} or "P0299" not in data.fault_codes):
                    raise DomainError("TOPIC_APPLICABILITY", "仅支持虚拟探岳 DKVB/P0299 合成专题", 422)
                intake = data.topic_intake or {}
                if intake.get("symptom_condition") not in {"mid_load", "high_load", "all_load", "intermittent"} or intake.get("safety_gate") not in {"none", "caution", "stop_now", "unavailable"}:
                    raise DomainError("TOPIC_INTAKE_REQUIRED", "请确认症状工况及安全风险", 422)
                snap = {"vehicle": actual, "fault_description": data.fault_description,
                        "fault_codes": data.fault_codes, "diagnosis_mode": data.diagnosis_mode,
                        "policy_version": data.policy_version, "synthetic": True,
                        "demo": True, "formal_usable": False, "topic_binding": topic_module.binding(),
                        "topic_plan": topic_module.plan(intake),
                        "source_scope": "B01 local cited topic only; no indexed retrieval assumed" if topic_module is dkvb_b01 else
                                        "DKVB B01 content/B02 execution overlay; local cited synthetic topic only; no indexed retrieval assumed"}
                row = CaseRepository(conn).create(actor, data, [], intake_override=snap)
                conn.execute(update(cases).where(cases.c.id == row["id"]).values(
                    revision=1, status="waiting_input", updated_at=text("clock_timestamp()")))
                row = conn.execute(select(cases).where(cases.c.id == row["id"])).mappings().one()
                body = self.with_active(conn, row)
                conn.execute(update(idempotency_keys).where(*match).values(response_json=body))
                return 201, body
            manifest = freeze_manifest(
                conn, actor, data.vehicle.model_dump(mode="json"), self.profile
            )
            if data.diagnosis_mode == "conservative":
                expected = DKVB_DEMO_PROTOCOL.applicable_vehicle_profile
                actual = data.vehicle.model_dump(mode="json")
                if any(actual.get(name) != value for name, value in expected.items()) or "P0299" not in data.fault_codes:
                    raise DomainError(
                        "CONSERVATIVE_SCENARIO_UNSUPPORTED",
                        "当前保守模式仅支持虚拟探岳 DKVB 演示台架（2020）/ P0299",
                        422,
                    )
                version_ids = [UUID(item["document_version_id"]) for item in manifest]
                material = "\n".join(
                    conn.execute(
                        select(chunks.c.text).where(chunks.c.document_version_id.in_(version_ids))
                    ).scalars()
                ) if version_ids else ""
                missing = [text for text in required_demo_material_texts() if text not in material]
                if missing:
                    raise DomainError(
                        "CONSERVATIVE_MATERIAL_MISSING",
                        "当前支持场景所需的受控资料尚未就绪，未创建病例",
                        422,
                        details={"missing_count": len(missing)},
                    )
            row = CaseRepository(conn).create(actor, data, manifest)
            if data.diagnosis_mode == "conservative":
                self._initialize_conservative(conn, actor, row)
                row = conn.execute(select(cases).where(cases.c.id == row["id"])).mappings().one()
            body = self.with_active(conn, row)
            conn.execute(update(idempotency_keys).where(*match).values(response_json=body))
            return 201, body

    def _initialize_conservative(self, conn, actor, case):
        """Create the frozen binding, system CHK-00 fact and CHK-01 task atomically."""
        from app.services.protocol_service import ProtocolService

        protocol_service = ProtocolService(self.engine, self.report_settings)
        protocol_service.bind_for_case(actor, case["id"], connection=conn)
        binding = conn.execute(select(diagnosis_protocol_bindings).where(
            diagnosis_protocol_bindings.c.case_id == case["id"],
            diagnosis_protocol_bindings.c.graph_epoch == case["graph_epoch"],
        )).mappings().one()
        frozen = binding["binding_json"]
        protocol = frozen["protocol"]
        if protocol["version"] != "3.1.0" or protocol["start_check_id"] != "CHK-01":
            raise DomainError("PROTOCOL_INTAKE_VERSION_INVALID",
                              "Current protocol cannot initialize from case intake")
        candidate = frozen["candidates"]["CHK-01"]
        check = next(item for item in protocol["checks"] if item["check_id"] == "CHK-01")
        evidence_refs = sorted({str(ref["evidence_id"])
            for claim in [candidate.get("purpose"), candidate.get("location"),
                          *candidate.get("prerequisites", []), *candidate.get("actions", []),
                          *candidate.get("input", {}).get("choices", [])]
            if isinstance(claim, dict) for ref in claim.get("references", [])})
        _, queued = enqueue(conn, actor, "diagnosis", {"case_id": str(case["id"]),
                            "source": "case_intake"}, case["id"], case["revision"])
        run_id = UUID(queued["run_id"])
        run = conn.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
        area_id, step_id = uuid4(), uuid4()
        conn.execute(diagnosis_areas.insert().values(
            id=area_id, case_id=case["id"], workflow_id=run["workflow_id"],
            graph_epoch=case["graph_epoch"], component_key="病例与测量确认",
            title="病例与测量确认", provenance_json={"source": "case_intake"},
            status="active",
        ))
        meta = {"decision": "next_check", "protocol_id": protocol["protocol_id"],
                "protocol_version": protocol["version"], "transition_id": "SYSTEM_INTAKE_TO_CHK01",
                "current_check_id": "CHK-00", "observation_id": None,
                "next_check_id": "CHK-01", "evidence_refs": evidence_refs,
                "reason_code": "CASE_INTAKE_COMPLETE", "handoff_reason": None,
                "options": check["input_schema"]["options"], "presentation": check["presentation"]}
        conn.execute(diagnosis_steps.insert().values(
            id=step_id, case_id=case["id"], area_id=area_id, run_id=run_id,
            turn_id=run["turn_id"], ordinal=1, candidate_json=candidate,
            validation_json={"issues": [], "provenance": [], "protocol": meta},
            status="waiting_input",
        ))
        intake = dict(case["intake_snapshot"])
        # The observation integrity trigger compares created_revision with the
        # case row at INSERT time; all of these writes remain in this one TX.
        conn.execute(update(cases).where(cases.c.id == case["id"]).values(
            revision=1, status="waiting_input", updated_at=text("clock_timestamp()")))
        conn.execute(observations.insert().values(
            id=uuid4(), case_id=case["id"], area_id=None, step_id=None,
            kind="intake_snapshot", created_revision=1, actor_id=actor,
            payload={"source": "case_intake", "actor": "system", "fact_kind": "intake_snapshot",
                     "check_id": "CHK-00", "option_id": "intake.confirmed",
                     "protocol_id": protocol["protocol_id"], "protocol_version": protocol["version"],
                     "protocol_content_hash": binding["content_hash"], "snapshot": intake,
                     "checked": True},
        ))
        conn.execute(graph_progress.insert().values(
            workflow_id=run["workflow_id"], turn_id=run["turn_id"], case_id=case["id"],
            run_id=run_id, graph_epoch=case["graph_epoch"], phase="waiting_input",
            step_id=step_id,
        ))
        conn.execute(update(runs).where(runs.c.id == run_id).values(
            status="waiting_input", output_revision=1, error_json={}))
        conn.execute(update(jobs).where(jobs.c.run_id == run_id).values(
            status="completed", lease_until=None))

