"""WP10 bounded proposal/repair adapter. No persistent graph or automatic paid call."""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.agents.state import ProposalEnvelope, ProposalTurn
from app.infrastructure.model_gateway import ModelError


class ProposalRunner:
    def __init__(self, gateway, service):
        self.gateway, self.service = gateway, service

    def run(self, context, messages, turn: ProposalTurn):
        prompt = (Path(__file__).parent / "prompts/initial.md").read_text(encoding="utf-8")
        if getattr(context, "history", ()):
            prompt += "\n" + (Path(__file__).parent / "prompts/next_step.md").read_text(
                encoding="utf-8"
            )
        history = [
            SystemMessage(
                content=prompt
                + "\nJSON schema: "
                + json.dumps(ProposalEnvelope.model_json_schema())
            )
        ] + list(messages)
        while True:
            if turn.attempts >= 2:
                return dict(
                    accepted=False,
                    disposition="needs_input",
                    issues=[
                        dict(
                            code="REPAIR_EXHAUSTED",
                            path="proposal",
                            detail="This proposal turn is exhausted",
                        )
                    ],
                    published=False,
                )
            try:
                turn.attempts += 1
                # Direct request avoids a hidden JSON repair in addition to proposal repair.
                answer = self.gateway.request(history, response_format={"type": "json_object"})
                raw = ProposalEnvelope.model_validate_json(answer.content).model_dump(mode="json")
                result = self.service.validate(context, raw)
            except (ValidationError, ValueError):
                result = dict(
                    accepted=False,
                    disposition="needs_input",
                    issues=[
                        dict(
                            code="PROPOSAL_SCHEMA_INVALID",
                            path="proposal",
                            detail="Malformed proposal",
                        )
                    ],
                    published=False,
                )
            except ModelError as exc:
                return dict(
                    accepted=False,
                    disposition="needs_input",
                    issues=[
                        dict(code=exc.code, path="budget", detail="Model/support call stopped")
                    ],
                    published=False,
                )
            if result["accepted"] or turn.repair_used:
                return dict(result, repair_used=turn.repair_used, attempts=turn.attempts)
            turn.repair_used = True
            history.append(
                HumanMessage(
                    content="Repair once using these validation failures. If sources are missing return need_input, never invent: "
                    + json.dumps(result["issues"], ensure_ascii=False)
                )
            )
