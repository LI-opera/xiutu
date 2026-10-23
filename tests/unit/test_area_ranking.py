import pytest
from types import SimpleNamespace

from app.domain.policies import DomainError
from app.services.area_ranking_service import AreaRankingService, RankedArea, RankingProposal, ranking_input, validate_ranking


def _case():
    return {
        "fault_description": "换过中冷器后加速有嘶嘶声",
        "fault_codes": ["P0299"],
        "intake_snapshot": {
            "topic_plan": {"intake": {"symptom_condition": "mid_load"}},
            "template_content": {"areas": [
                {"id": "boost-air", "title": "增压空气通路", "description": "检查管路座合与漏气"},
                {"id": "pressure", "title": "增压压力测量", "description": "核对压力信号"},
            ]},
        },
    }


def test_input_contains_only_intake_and_matched_area_summaries():
    payload = ranking_input(_case())
    assert payload["complaint"] == "换过中冷器后加速有嘶嘶声"
    assert payload["symptom_condition"] == "mid_load"
    assert [entry["area_id"] for entry in payload["candidates"]] == ["boost-air", "pressure"]
    assert "observations" not in payload


@pytest.mark.parametrize("ids", [
    ["boost-air"], ["boost-air", "boost-air"], ["boost-air", "turbo"],
])
def test_model_cannot_add_drop_or_duplicate_matched_areas(ids):
    proposal = RankingProposal(areas=[RankedArea(area_id=id, reason="与当前主诉相关") for id in ids])
    with pytest.raises(DomainError, match="完整保留"):
        validate_ranking(proposal, ranking_input(_case())["candidates"])


def test_model_can_reorder_exact_candidate_subset():
    proposal = RankingProposal(areas=[
        RankedArea(area_id="pressure", reason="压力信号需先核对"),
        RankedArea(area_id="boost-air", reason="再检查管路座合"),
    ])
    assert [item["area_id"] for item in validate_ranking(proposal, ranking_input(_case())["candidates"])["areas"]] == ["pressure", "boost-air"]


def test_standing_ranking_grant_is_local_test_only(monkeypatch):
    monkeypatch.setenv("XIUTU_AREA_RANKING_PAID_AUTHORIZED", "1")
    monkeypatch.setenv("XIUTU_AREA_RANKING_LOCAL_TESTING", "1")
    monkeypatch.delenv("XIUTU_AREA_RANKING_ALLOWED_CASE_ID", raising=False)
    from pydantic import SecretStr
    test_db = SecretStr("postgresql://xiutu:pw@127.0.0.1:5433/xiutu_test_workbench")
    settings = SimpleNamespace(deepseek_api_key=object(), app_mode="test", database_url=test_db,
                               local_dev_auto_identity=True, app_origin="http://localhost:5215")
    service = AreaRankingService(None, settings)
    assert service._authorized("case-a")
    settings.database_url = SecretStr("postgresql://xiutu:pw@127.0.0.1:5433/xiutu_dev")
    assert not service._authorized("case-a")
    settings.database_url = test_db
    settings.app_mode = "production"
    assert not service._authorized("case-a")
    settings.app_mode = "test"
    settings.app_origin = "https://example.com"
    assert not service._authorized("case-a")
    settings.app_origin = "http://localhost:5215"
    monkeypatch.delenv("XIUTU_AREA_RANKING_PAID_AUTHORIZED")
    assert not service._authorized("case-a")
