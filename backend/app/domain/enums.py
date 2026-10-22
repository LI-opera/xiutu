from enum import StrEnum


class CaseStatus(StrEnum):
    draft = "draft"
    analyzing = "analyzing"
    waiting_input = "waiting_input"
    ready_for_report = "ready_for_report"
    reporting = "reporting"
    completed = "completed"
    needs_review = "needs_review"
    failed = "failed"
