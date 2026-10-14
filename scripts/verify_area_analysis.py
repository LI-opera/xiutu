"""Rollback-only persistence probe. No model/network provider call or permanent test advice."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import create_engine, select
from app.domain.case_analysis import CaseAdviceOpenV2
from app.domain.policies import DomainError
from app.infrastructure.db_target import validate_target
from app.infrastructure.orm import cases, area_analysis_attempts
from app.services.case_service import CaseService
from app.services.area_analysis_service import AreaAnalysisService, MATCHED_SCOPE_ID
from scripts.wp15_workbench import STATE, environment
from scripts.seed_area_references import seed


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    env = environment(state)
    target = validate_target(env["DATABASE_URL"], "test")
    engine = create_engine(target.sqlalchemy_url(), connect_args=target.connect_kwargs())
    actor = UUID(state["actor"])
    settings = SimpleNamespace(deepseek_api_key=True, deepseek_model="offline-test",
        area_analysis_max_output_tokens=8192, area_analysis_max_input_chars=1)
    calls = []

    class FakeGateway:
        def __init__(self, *args, **kwargs):
            assert kwargs["max_model_calls"] == 1
            assert kwargs["input_profile"] == "matched_areas"
        def close(self):
            pass
        def generate_structured_once(self, schema, messages, on_response):
            payload = json.loads(messages[1].content)
            calls.append(payload)
            on_response('{"summary":"离线接线测试"}', {"usage": {"input_tokens": 0, "output_tokens": 0}})
            return CaseAdviceOpenV2(summary="离线接线测试；本事务将回滚。")

    service = AreaAnalysisService(CaseService(engine, b"test", "synthetic", settings), settings, FakeGateway)
    with engine.connect() as conn:
        transaction = conn.begin()
        class ProbeUow:
            def __init__(self, *_):
                self.connection = conn
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass
        try:
            relations = seed(conn)
            # Use the saved user case with a terminal failure; the newest case may have no observations.
            row = conn.execute(select(cases).where(cases.c.owner_id == actor,
                cases.c.id == UUID("18a144fe-dfa2-4d44-8824-11388d26fa9a"))).mappings().first()
            assert row is not None
            cid, revision = row["id"], row["revision"]
            with patch("app.services.area_analysis_service.UnitOfWork", ProbeUow):
                before = service.get(actor, cid, "pressure")
                assert before["documents"][0]["id"] == "tayron-dkvb-pressure"
                combined = service.get(actor, cid, MATCHED_SCOPE_ID)
                assert len(combined["areas"]) >= 2
                assert len(combined["documents"]) == len(combined["areas"])
                assert all(area["observation_ids"] for area in combined["areas"])
                assert combined["history"] and combined["history"][0]["status"] == "failed"
                service.start(actor, cid, MATCHED_SCOPE_ID, revision)
                service.start(actor, cid, MATCHED_SCOPE_ID, revision)
                assert len(calls) == 1
                retried = service.get(actor, cid, MATCHED_SCOPE_ID)
                assert retried["history"][0]["status"] == "completed"
                assert retried["history"][1]["status"] == "failed"
                assert [area["id"] for area in calls[0]["areas"]] == [area["id"] for area in combined["areas"]]
                assert [doc["id"] for doc in calls[0]["documents"]] == [doc["id"] for doc in combined["documents"]]
                try:
                    service.get(UUID(int=0), cid, "pressure")
                    raise AssertionError("Ownership bypass")
                except DomainError as exc:
                    assert exc.code == "NOT_FOUND"
                assert conn.execute(select(cases.c.revision).where(cases.c.id == cid)).scalar_one() == revision
                print(json.dumps({"bindings": len(relations), "offline_generations": len(calls),
                    "deduplicated": True, "area_isolation": True,
                    "combined_one_call_for_recorded_areas": [area["id"] for area in combined["areas"]],
                    "owner_isolation": True,
                    "case_unchanged": True, "real_model_calls": 0, "rollback": True}))
        finally:
            transaction.rollback()
    engine.dispose()


if __name__ == "__main__":
    main()
