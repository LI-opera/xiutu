"""Retired generation handlers retained for explicit isolated legacy tests."""


LEGACY_JOB_KINDS = frozenset({"diagnosis", "report", "case_analysis"})


def transient_model_failure(code):
    # Only structured transport/rate-limit failures are safe to re-attempt.
    # Each attempt remains in the same run/turn and consumes its existing budgets.
    return code in {
        "TOOL_TRANSIENT", "DATABASE_BUSY", "PROVIDER_TIMEOUT_OR_CONNECTION",
        "PROVIDER_HTTP_429", "PROVIDER_HTTP_500", "PROVIDER_HTTP_502",
        "PROVIDER_HTTP_503", "PROVIDER_HTTP_504",
    }


class LegacyDispatcher:
    def __init__(self, diagnostic_sink=None):
        self.diagnostic_sink = diagnostic_sink

    @staticmethod
    def prepare(store):
        store.reconcile_pending()

    def execute(self, store, lease, stopped, finished):
        kind = lease.job["kind"]
        if kind == "diagnosis":
            from app.legacy_execution.graph import DiagnosisGraph

            DiagnosisGraph(
                store, lease, stopped, on_published=finished.set,
                diagnostic_sink=self.diagnostic_sink,
            ).execute()
            return None, True, lease.job["run_id"]
        if kind == "report":
            from app.legacy_execution.report_graph import run_report

            return run_report(store, lease, stopped), False, None
        if kind == "case_analysis":
            from app.legacy_execution.case_analysis import run_case_analysis

            return run_case_analysis(store, lease, stopped), False, None
        raise ValueError("Unsupported legacy job kind")

    @staticmethod
    def model_failure_is_transient(kind, code):
        return kind == "diagnosis" and transient_model_failure(code)

    @staticmethod
    def recover_published(store, lease, finished, diagnosis_executed, published_run):
        if lease.job["kind"] == "diagnosis" and not diagnosis_executed:
            # A checkpoint failure after COMMIT cannot turn a published step
            # into a failed run or invoke the model again.
            if store.published(lease.job["run_id"]):
                finished.set()
                return True, lease.job["run_id"]
        return diagnosis_executed, published_run

    @staticmethod
    def reconcile_published(store, published_run):
        store.reconcile_wait(published_run)
