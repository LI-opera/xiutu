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


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    waiting_input = "waiting_input"
    succeeded = "succeeded"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    superseded = "superseded"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ReviewStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    revoked = "revoked"


class ParseStatus(StrEnum):
    cancelled = "cancelled"
    pending = "pending"
    parsing = "parsing"
    review_pending = "review_pending"
    needs_ocr = "needs_ocr"
    failed = "failed"
