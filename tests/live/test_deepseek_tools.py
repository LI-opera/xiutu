# ruff: noqa: E402
# Test-only sys.path setup precedes imported integration fixtures.
"""Explicit WP09-only paid probe. Never collected by the standard/offline entrypoints."""

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/integration"))
from app.config import Settings
from app.infrastructure.model_budget import LIVE_LEDGER, BudgetLedger
from app.infrastructure.model_factory import llm_factory
from app.skills.registry import SkillRegistry


class SyntheticResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    synthetic: bool
    summary: str
    chunk_ids: list[str]
    spec_ids: list[str]


@pytest.fixture(autouse=True)
def explicit_gate(monkeypatch):
    if os.environ.get("XIUTU_WP09_LIVE") != "1":
        pytest.skip("Explicit paid WP09 probe authorization required")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local_bge_m3")
    monkeypatch.setenv(
        "EMBEDDING_MODEL_PATH",
        "E:/AI_Cache/huggingface/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181",
    )


@pytest.mark.live
@pytest.mark.database
def test_real_deepseek_business_tools(mcp_rig):
    from dotenv import dotenv_values

    # Read only selected LLM fields in memory; no dotenv copy, no DB configuration import.
    private = dotenv_values(ROOT / ".env")
    settings = Settings(
        deepseek_api_key=private.get("DEEPSEEK_API_KEY"),
        deepseek_base_url=private.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model="deepseek-flash",
    )
    del private
    m = mcp_rig
    registry = SkillRegistry()
    skill = registry.load_body("cooling-system-diagnosis", "1.0.0")
    refs = registry.load_references("cooling-system-diagnosis", ["method.md"])
    gateway = llm_factory(settings, paid=True, turn_id="wp09-e10-" + uuid4().hex)
    try:
        result, records = gateway.run_tools(
            [
                SystemMessage(
                    content="Synthetic technical contract test only; never real repair advice. "
                    + skill["body"]
                ),
                HumanMessage(
                    content='In the first response call BOTH search_manuals(query="voltage",vehicle_scope={},top_k=2) and get_measurement_spec(component_key="SYNTHETIC-COMPONENT",quantity="voltage",vehicle_scope={}). Use native tool calls, not descriptions. After their responses, do not call more tools. Summarize the synthetic evidence and preserve returned chunk/spec IDs in the final JSON. Mark synthetic=true.'
                ),
            ],
            SyntheticResult,
            m["ex"],
            m["ctx"],
            allowed_tools=["search_manuals", "get_measurement_spec"],
            skill=skill["metadata"],
            tool_round_limit=1,
        )
        assert (
            result.synthetic
            and {x["name"] for x in records} == {"search_manuals", "get_measurement_spec"}
            and all(x["ok"] for x in records)
        )
        chunks = {p["chunk_id"] for x in records for p in x["provenance"] if "chunk_id" in p}
        specs = {p["spec_id"] for x in records for p in x["provenance"] if "spec_id" in p}
        assert result.chunk_ids and set(result.chunk_ids) <= chunks
        assert result.spec_ids and set(result.spec_ids) <= specs
        output = dict(
            result=result.model_dump(),
            records=records,
            trace=gateway.trace,
            model=gateway.health_config(),
            skill=skill["metadata"],
            references=list(refs),
            ledger=BudgetLedger(LIVE_LEDGER).read(),
            synthetic=True,
        )
        (
            Path(os.environ["WP09_EVIDENCE"]) / ("deepseek-live-" + gateway.turn + ".json")
        ).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf8")
    finally:
        gateway.close()
        (Path(os.environ["WP09_EVIDENCE"]) / ("live-trace-" + gateway.turn + ".json")).write_text(
            json.dumps(
                dict(trace=gateway.trace, records=getattr(gateway, "tool_records", [])), indent=2
            ),
            encoding="utf8",
        )
        (Path(os.environ["WP09_EVIDENCE"]) / ("paid-ledger-" + gateway.turn + ".json")).write_text(
            json.dumps(BudgetLedger(LIVE_LEDGER).read(), indent=2), encoding="utf8"
        )
