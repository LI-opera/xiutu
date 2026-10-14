"""Read-only candidate validation; never publishes a step, run or report."""

from pydantic import ValidationError

from app.agents.state import ConcludeArea, NeedInput, ProposalEnvelope, ProposeStep, RequestTools
from app.domain.policies import DomainError
from app.infrastructure.uow import UnitOfWork
from app.services.evidence_scope import owner_lock
from app.validators.proposal import HardGate, claims, issue
from app.validators.repetition import fingerprint
from app.validators.support import ExtractiveSupport, SupportAnswer


class ProposalService:
    def __init__(self, engine, settings, support=None, *, conclusion_rules=()):
        self.engine = engine
        self.settings = settings
        self.gate = HardGate(engine, settings, conclusion_rules)
        self.support = support or ExtractiveSupport()

    def _load(self, context, proposal, connection=None):
        with UnitOfWork(self.engine, connection=connection) as u:
            owner_lock(u.connection, context.actor)
            return self.gate.load(u.connection, context, proposal)

    def validate(self, context, raw, *, connection=None):
        try:
            proposal = ProposalEnvelope.model_validate(raw).root
        except ValidationError:
            return dict(
                accepted=False,
                disposition="needs_input",
                issues=[
                    issue(
                        "PROPOSAL_SCHEMA_INVALID",
                        "proposal",
                        "Invalid or extra fields; no input echoed",
                    )
                ],
                support=[],
                provenance=[],
                published=False,
            )
        try:
            loaded = self._load(context, proposal, connection)
            errors = list(loaded["issues"])
            assessments = []
            if not errors:
                for path, claim, _ in claims(proposal):
                    quotes = [loaded["quotes"][str(ref.evidence_id)] for ref in claim.references]
                    try:
                        answer = SupportAnswer.model_validate(
                            self.support.assess(claim.text, quotes)
                        ).model_dump()
                    except (ValidationError, ValueError):
                        answer = dict(
                            verdict="uncertain", quote="", reason="Support response invalid"
                        )
                    if answer["verdict"] == "supported" and answer["quote"] not in [
                        q.strip() for q in quotes
                    ]:
                        answer = dict(
                            verdict="uncertain", quote="", reason="Unverified supporting excerpt"
                        )
                    assessments.append(dict(path=path, **answer))
                    if answer["verdict"] != "supported":
                        errors.append(
                            issue("CLAIM_" + answer["verdict"].upper(), path, answer["reason"])
                        )
            fp = None
            if isinstance(proposal, ProposeStep):
                fp = fingerprint(proposal)
                if any(not x.fingerprint.startswith("v2:") for x in context.history):
                    errors.append(
                        issue(
                            "HISTORY_UNSUPPORTED",
                            "history",
                            "Legacy action keys omit the check object; trusted history must be reconstructed from source checks, never treated as unchecked",
                        )
                    )
                duplicates = [x for x in context.history if x.fingerprint == fp]
                if duplicates:
                    retest = proposal.retest
                    if retest is None:
                        errors.append(
                            issue(
                                "DUPLICATE_CHECK",
                                "actions",
                                "Same component, action, measurement and conditions despite title",
                            )
                        )
                    elif any(x.retest_count >= 1 for x in duplicates):
                        errors.append(
                            issue(
                                "RETEST_LIMIT", "retest", "At most one automatic retest suggestion"
                            )
                        )
                elif proposal.retest:
                    errors.append(
                        issue("RETEST_WITHOUT_PRIOR", "retest", "No corresponding prior check")
                    )
            # A semantic check may be slow or invoke a gateway: recheck source/revision afterwards.
            final = self._load(context, proposal, connection)
            errors.extend(x for x in final["issues"] if x not in errors)
            disposition = (
                "needs_input"
                if errors or isinstance(proposal, NeedInput)
                else ("request_tools" if isinstance(proposal, RequestTools) else "candidate")
            )
            if isinstance(proposal, ConcludeArea) and proposal.assessment in (
                "unknown",
                "not_checked",
                "insufficient_data",
            ):
                disposition = "needs_input"
            return dict(
                accepted=not errors,
                disposition=disposition,
                issues=errors,
                support=assessments,
                provenance=final["provenance"],
                fingerprint=fp,
                candidate=proposal.model_dump(mode="json"),
                conclusion_support=final["conclusion_support"] if not errors else None,
                synthetic=self.settings.retrieval_profile == "synthetic",
                published=False,
                validated_revision=context.revision,
                diagnosis=False,
            )
        except DomainError as exc:
            return dict(
                accepted=False,
                disposition="needs_input",
                issues=[
                    issue(exc.code, "references", "Current case/source authorization rejected")
                ],
                support=[],
                provenance=[],
                published=False,
            )
