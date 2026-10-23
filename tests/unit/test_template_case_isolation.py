"""A case read is the snapshot plus its progress summary; nothing else is queried."""

from app.services import case_service


def test_case_read_adds_progress_and_experience(monkeypatch):
    summary = {"recorded": 2, "total": 8, "repair_rounds": 1,
               "pending_retests": 1, "closed": False, "label": "待复检"}
    monkeypatch.setattr(case_service, "snapshot", lambda row: {"id": "case"})
    monkeypatch.setattr(case_service, "load_summary", lambda conn, row: summary)

    class NoQueries:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("case read queried the database beyond the progress summary")

    service = case_service.CaseService(None, b"test")
    result = service.with_progress(NoQueries(), {
        "intake_snapshot": {"workbench_flow": "template-match-v1"}})
    assert result["template_progress"] == summary
    assert result["experience"] == {
        "category": "waiting", "label": "待复检",
        "guidance": "检查 2/8 项 · 处理 1 轮 · 待复检 1 轮", "priority": 10}
