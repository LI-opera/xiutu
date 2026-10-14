class DomainError(Exception):
    def __init__(self, code, message, status=409, *, retryable=False, details=None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.retryable, self.details = retryable, details


def check_revision(current: int, expected: int):
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise DomainError("VALIDATION_ERROR", "Invalid expected revision", 422)
    if current != expected:
        raise DomainError(
            "REVISION_CONFLICT", "Case revision has changed", details={"current_revision": current}
        )
