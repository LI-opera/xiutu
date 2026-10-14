"""Read/activate bounded diagnosis areas and persist conservative cards."""

from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import select, update

from app.domain.policies import DomainError, check_revision
from app.domain.schemas import InputModel
from app.infrastructure.event_store import append_event
from app.infrastructure.orm import (
    case_evidence, cases, diagnosis_area_conclusions, diagnosis_areas, diagnosis_steps,
    diagnosis_publications, graph_progress, measurement_comparisons, runs,
)
from app.infrastructure.uow import UnitOfWork
from app.repositories.observations import ObservationRepository
from app.services.evidence_scope import owner_lock
from app.services.evidence_service import EvidenceService, row_owned
from app.services.area_lifecycle import completion_basis
from app.services.evidence_scope import source
from app.services.run_service import enqueue, idempotent, idle_case, lock_case


class AreaAction(InputModel):
    expected_revision: int = Field(ge=0, strict=True)
    graph_epoch: int = Field(ge=0, strict=True)


class AreaService:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings

    @staticmethod
    def _area(c, case, area_id):
        area = c.execute(select(diagnosis_areas).where(
            diagnosis_areas.c.id == area_id,
            diagnosis_areas.c.case_id == case["id"],
            diagnosis_areas.c.graph_epoch == case["graph_epoch"])
            .with_for_update()).mappings().one_or_none()
        if area is None:
            raise DomainError("NOT_FOUND", "Area not found", 404)
        return area

    def list(self, actor, case_id):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            case = c.execute(select(cases).where(cases.c.id == case_id,
                          cases.c.owner_id == actor)).mappings().one_or_none()
            if case is None:
                raise DomainError("NOT_FOUND", "Case not found", 404)
            areas = c.execute(select(diagnosis_areas).where(
                diagnosis_areas.c.case_id == case_id,
                diagnosis_areas.c.graph_epoch == case["graph_epoch"])
                .order_by(diagnosis_areas.c.created_at, diagnosis_areas.c.id)
            ).mappings().all()
            output = []
            for area in areas:
                step = c.execute(select(diagnosis_steps.c.id).where(
                    diagnosis_steps.c.area_id == area["id"],
                    diagnosis_steps.c.status == "waiting_input")).scalar_one_or_none()
                card = c.execute(select(diagnosis_area_conclusions).where(
                    diagnosis_area_conclusions.c.area_id == area["id"],
                    diagnosis_area_conclusions.c.graph_epoch == case["graph_epoch"])
                    .order_by(diagnosis_area_conclusions.c.created_revision.desc())
                ).mappings().first()
                output.append({"id": str(area["id"]), "component_key": area["component_key"],
                    "title": area["title"], "status": area["status"],
                    "current_step_id": str(step) if step else None,
                    "conclusion": None if card is None else {
                        "id": str(card["id"]), "assessment": card["assessment"],
                        "content": card["content_json"],
                        "created_revision": card["created_revision"],
                        "needs_review": card["needs_review"]}})
            return {"case_id": str(case_id), "revision": case["revision"],
                    "graph_epoch": case["graph_epoch"], "areas": output}

    def activate(self, actor, case_id, area_id, body: AreaAction, key):
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)

            def action():
                case = lock_case(c, actor, case_id)
                check_revision(case["revision"], body.expected_revision)
                if case["graph_epoch"] != body.graph_epoch:
                    raise DomainError("GRAPH_EPOCH_STALE", "Diagnosis graph changed")
                areas = c.execute(select(diagnosis_areas).where(
                    diagnosis_areas.c.case_id == case_id,
                    diagnosis_areas.c.graph_epoch == case["graph_epoch"])
                    .order_by(diagnosis_areas.c.created_at, diagnosis_areas.c.id)
                    .with_for_update()).mappings().all()
                area = next((item for item in areas if item["id"] == area_id), None)
                if area is None:
                    raise DomainError("NOT_FOUND", "Area not found", 404)
                if area["status"] in {"retired", "stale", "completed"}:
                    raise DomainError("AREA_NOT_ACTIVE", "Area is read-only")
                own_step = c.execute(select(diagnosis_steps.c.id).where(
                    diagnosis_steps.c.area_id == area_id,
                    diagnosis_steps.c.status == "waiting_input")).scalar_one_or_none()
                if own_step:
                    return 200, {"area_id": str(area_id), "current_step_id": str(own_step),
                                 "revision": case["revision"], "mode": "read_only"}
                other = c.execute(select(diagnosis_steps.c.id).where(
                    diagnosis_steps.c.case_id == case_id,
                    diagnosis_steps.c.status == "waiting_input")).first()
                if other:
                    raise DomainError("ACTIVE_STEP", "Another check is waiting; browse it without activation")
                if case["status"] != "needs_review":
                    raise DomainError("AREA_NOT_READY", "Case is not waiting for area activation")
                idle_case(c, case_id)
                if area["status"] != "pending" or any(
                    item["status"] == "retired" for item in areas
                ):
                    raise DomainError("AREA_NOT_READY", "Target area is not eligible")
                pending = [item for item in areas if item["status"] == "pending"]
                if pending[0]["id"] != area_id or any(
                    item["status"] == "active" for item in areas
                ):
                    raise DomainError("AREA_NOT_READY", "Previous area is unfinished")
                # A continuation is identified by its committed publication,
                # not by UUID order or a process-local notion of recency.
                publications = c.execute(select(diagnosis_publications).where(
                    diagnosis_publications.c.case_id == case_id,
                    diagnosis_publications.c.node == "area_close",
                    diagnosis_publications.c.output_revision == case["revision"])
                    .with_for_update()).mappings().all()
                if len(publications) != 1:
                    raise DomainError("WORKFLOW_MISSING", "Unique completed area turn required")
                published = publications[0]
                response = published["response_json"]
                if not isinstance(response, dict):
                    raise DomainError("WORKFLOW_INCONSISTENT", "Area publication is inconsistent")
                parent = c.execute(select(runs).where(
                    runs.c.id == published["run_id"],
                    runs.c.case_id == case_id,
                    runs.c.kind == "diagnosis").with_for_update()).mappings().one_or_none()
                progress = c.execute(select(graph_progress).where(
                    graph_progress.c.run_id == published["run_id"])
                    .with_for_update()).mappings().one_or_none()
                closed = next((item for item in areas if str(item["id"]) ==
                               response.get("area_id")), None)
                if (parent is None or progress is None or closed is None or
                    closed["workflow_id"] != area["workflow_id"] or
                    parent["status"] != "succeeded" or parent["workflow_id"] != area["workflow_id"] or
                    response.get("run_id") != str(parent["id"]) or
                    response.get("output_revision") != case["revision"] or
                    published["workflow_id"] != parent["workflow_id"] or
                    published["turn_id"] != parent["turn_id"] or
                    parent["output_revision"] != case["revision"] or
                    progress["workflow_id"] != parent["workflow_id"] or
                    progress["turn_id"] != parent["turn_id"] or
                    progress["graph_epoch"] != case["graph_epoch"] or
                    progress["phase"] != "completed" or
                    response.get("next_run_id") is not None):
                    raise DomainError("WORKFLOW_INCONSISTENT", "Area continuation is inconsistent")
                observations, source_ids = completion_basis(
                    c, case=case, actor=actor, area_id=closed["id"], run_id=None,
                    settings=self.settings, expected_status="completed")
                try:
                    card_id = UUID(response["card_id"])
                except (KeyError, ValueError, TypeError):
                    raise DomainError("WORKFLOW_INCONSISTENT", "Area publication has no valid card") from None
                card = c.execute(select(diagnosis_area_conclusions).where(
                    diagnosis_area_conclusions.c.id == card_id,
                    diagnosis_area_conclusions.c.case_id == case_id,
                    diagnosis_area_conclusions.c.area_id == closed["id"],
                    diagnosis_area_conclusions.c.graph_epoch == case["graph_epoch"],
                    diagnosis_area_conclusions.c.created_revision == case["revision"] - 1)
                    .with_for_update()).mappings().one_or_none()
                if (card is None or card["needs_review"] or card["assessment"] != "unknown" or
                    card["content_json"].get("observation_ids") !=
                        [str(obs["id"]) for obs in observations] or
                    card["content_json"].get("source_evidence_ids") != sorted(source_ids)):
                    raise DomainError("AREA_NOT_READY", "Previous area card is not current")
                for entry in case["corpus_manifest"]:
                    source(c, actor, case, UUID(entry["document_version_id"]),
                           UUID(entry["index_id"]), self.settings.retrieval_profile)
                # Even a terminal automatically queued activation cannot be
                # recreated through this public endpoint.
                prior = c.execute(select(runs.c.id).join(
                    graph_progress, graph_progress.c.run_id == runs.c.id).where(
                    runs.c.case_id == case_id,
                    runs.c.kind == "diagnosis",
                    runs.c.workflow_id == parent["workflow_id"],
                    graph_progress.c.graph_epoch == case["graph_epoch"],
                    runs.c.input_payload["area_activation"].as_string() == str(area_id))
                ).first()
                if prior:
                    raise DomainError("AREA_ALREADY_ACTIVATED", "Area activation already exists")
                _, queued = enqueue(c, actor, "diagnosis",
                    {"case_id": str(case_id), "area_activation": str(area_id)},
                    case_id, case["revision"], parent=parent, new_turn=True)
                new_run = c.execute(select(runs).where(
                    runs.c.id == UUID(queued["run_id"]))).mappings().one()
                c.execute(graph_progress.insert().values(
                    workflow_id=new_run["workflow_id"], turn_id=new_run["turn_id"],
                    case_id=case_id, run_id=new_run["id"], graph_epoch=case["graph_epoch"],
                    phase="queued"))
                c.execute(update(cases).where(cases.c.id == case_id).values(status="analyzing"))
                append_event(c, new_run["id"], "area.activated", {"area_id": str(area_id)})
                return 202, {**queued, "area_id": str(area_id), "mode": "generating"}

            return idempotent(c, actor,
                f"area_activate:{area_id}",
                key, {"case_id": str(case_id), **body.model_dump(mode="json")}, action)

    def conclude(self, actor, case_id, area_id, body: AreaAction, key):
        """A card reports observed evidence status, never a diagnosis conclusion."""
        with UnitOfWork(self.engine) as u:
            c = u.connection
            owner_lock(c, actor)

            def action():
                case = lock_case(c, actor, case_id)
                check_revision(case["revision"], body.expected_revision)
                if case["graph_epoch"] != body.graph_epoch:
                    raise DomainError("GRAPH_EPOCH_STALE", "Diagnosis graph changed")
                area = self._area(c, case, area_id)
                if area["status"] in {"retired", "stale"}:
                    raise DomainError("AREA_NOT_ACTIVE", "Area is unavailable")
                if c.execute(select(diagnosis_steps.c.id).where(
                    diagnosis_steps.c.area_id == area_id,
                    diagnosis_steps.c.status == "waiting_input")).first():
                    raise DomainError("ACTIVE_STEP", "Answer the current check first")
                if case["status"] == "analyzing":
                    raise DomainError("ACTIVE_RUN", "Analysis is still running")
                if c.execute(select(diagnosis_area_conclusions.c.id).where(
                    diagnosis_area_conclusions.c.area_id == area_id,
                    diagnosis_area_conclusions.c.created_revision == case["revision"])).first():
                    raise DomainError("AREA_ALREADY_CONCLUDED", "Area card already exists for this revision")
                saved = ObservationRepository(c).read(case_id, area_id, case["revision"])
                evidence = EvidenceService(self.engine, self.settings)
                groups = {}
                incomplete = not saved
                invalid_sources = []
                source_ids = set()
                for obs in saved:
                    incomplete |= (obs["kind"] == "unavailable"
                                   or obs["payload"].get("checked") is not True)
                    step = c.execute(select(diagnosis_steps.c.candidate_json).where(
                        diagnosis_steps.c.id == obs["step_id"],
                        diagnosis_steps.c.case_id == case_id,
                        diagnosis_steps.c.area_id == area_id)).scalar_one_or_none()
                    if step is None:
                        invalid_sources.append("step_missing")
                        continue
                    claims = [step["purpose"], step.get("location"),
                              *step.get("prerequisites", []), *step.get("actions", []),
                              *step.get("input", {}).get("choices", [])]
                    for claim in claims:
                        if not claim:
                            continue
                        for ref in claim.get("references", []):
                            try:
                                ev = row_owned(c, actor, case_evidence, UUID(ref["evidence_id"]))
                                source_ids.add(str(ev["id"]))
                                if (ev["case_id"] != case_id or
                                    str(ev["document_version_id"]) != ref["document_version_id"] or
                                    not evidence.validity(c, actor, ev)["valid"]):
                                    invalid_sources.append("source_invalid")
                            except (DomainError, ValueError, KeyError):
                                invalid_sources.append("source_invalid")
                    for item in obs["payload"].get("measurements", []):
                        group = (item["spec_id"], tuple(sorted(item["conditions"].items())))
                        groups.setdefault(group, {}).setdefault(item["outcome"], set()).add(
                            str(obs["id"]))
                        try:
                            comp = row_owned(c, actor, measurement_comparisons,
                                             UUID(item["comparison_id"]))
                            if (comp["case_id"] != case_id or
                                str(comp["spec_id"]) != item["spec_id"] or
                                not evidence.get_comparison(actor, comp["id"],
                                                            connection=c)["current_validity"]["valid"]):
                                invalid_sources.append("comparison_invalid")
                        except (DomainError, ValueError, KeyError):
                            invalid_sources.append("comparison_invalid")
                conflict = any({"within_range", "out_of_range"} <= set(values)
                               for values in groups.values())
                assessment = "needs_input" if invalid_sources else (
                    "conflicting" if conflict else "needs_input" if incomplete else "unknown")
                content = {"observation_ids": [str(x["id"]) for x in saved],
                    "source_evidence_ids": sorted(source_ids),
                    "within_range_observation_ids": sorted({oid for values in groups.values()
                        for oid in values.get("within_range", set())}),
                    "out_of_range_observation_ids": sorted({oid for values in groups.values()
                        for oid in values.get("out_of_range", set())}),
                    "basis": "source_invalid" if invalid_sources else
                             "same_spec_conflict" if conflict else
                             "missing_or_unavailable" if incomplete else "observations_without_trusted_conclusion",
                    "diagnosis": False}
                identifier = uuid4()
                c.execute(diagnosis_area_conclusions.insert().values(
                    id=identifier, case_id=case_id, area_id=area_id,
                    graph_epoch=case["graph_epoch"], created_revision=case["revision"],
                    assessment=assessment, content_json=content))
                # A conservative card does not mark a diagnosis finished.
                return 201, {"id": str(identifier), "area_id": str(area_id),
                             "assessment": assessment, "content": content,
                             "created_revision": case["revision"]}

            return idempotent(c, actor,
                f"area_conclude:{area_id}",
                key, {"case_id": str(case_id), **body.model_dump(mode="json")}, action)
