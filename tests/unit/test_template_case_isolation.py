"""Template case reads must not depend on the old graph/report pipeline."""

from app.services import case_service, template_case_history


def test_template_snapshot_skips_legacy_graph_and_report_queries(monkeypatch):
    summary = {"recorded": 2, "total": 8, "repair_rounds": 1,
               "pending_retests": 1, "closed": False, "label": "待复检"}
    monkeypatch.setattr(case_service, "snapshot", lambda row: {"report_gate": {
        "available": False, "reason": "NOT_IMPLEMENTED", "blocking_items": []}})
    monkeypatch.setattr(template_case_history, "load_summary", lambda conn, row: summary)

    class NoLegacyQueries:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("template read entered legacy graph or report query")

    service = case_service.CaseService(None, b"test", report_settings=object())
    result = service.with_active(NoLegacyQueries(), {
        "intake_snapshot": {"workbench_flow": "template-match-v1"}})
    assert result["template_progress"] == summary
    assert result["experience"] == {
        "category": "waiting", "label": "待复检",
        "guidance": "检查 2/8 项 · 处理 1 轮 · 待复检 1 轮", "priority": 10}
    assert result["report_gate"]["reason"] == "NOT_IMPLEMENTED"
