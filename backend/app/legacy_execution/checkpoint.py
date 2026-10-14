"""LangGraph saver writes on the SAME physically locked worker connection.

The saver tables are isolated in wp01_wp11. Every read/write is bracketed by
the original PID/token/deadline fence, including after a terminal publication.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import select, text

from app.infrastructure.job_store import LeaseLost
from app.infrastructure.orm import cases, diagnosis_publications, graph_progress, runs


class FencedPostgresSaver(PostgresSaver):
    def __init__(self, store, lease):
        self.store, self.lease = store, lease
        raw = lease.connection.connection.driver_connection
        super().__init__(raw)

    def _guarded(self, config, action):
        if config["configurable"].get("thread_id") != self.workflow_id:
            raise LeaseLost()
        with self.lease.mutex:
            c = self.lease.connection
            with c.begin():
                deadline = self.lease.final_deadline
                if deadline is None:
                    deadline = c.execute(select(self.store_job_lease()).where(
                        self.store_job_id() == self.lease.job["id"])).scalar_one()
                if deadline is None:
                    raise LeaseLost()
                self.store._finish_valid(self.lease, deadline)
                run = c.execute(select(runs.c.status).where(
                    runs.c.id == self.lease.job["run_id"])).scalar_one()
                if run not in {"running", "waiting_input"}:
                    if run != "succeeded" or c.execute(select(diagnosis_publications.c.id).where(
                        diagnosis_publications.c.run_id == self.lease.job["run_id"],
                        diagnosis_publications.c.node == "area_close")).first() is None:
                        raise LeaseLost()
                    # A successful area end may be followed immediately by a
                    # fact correction. Hold the case row through checkpoint
                    # commit so an old epoch cannot write after that correction.
                    expected = c.execute(select(graph_progress.c.graph_epoch).where(
                        graph_progress.c.run_id == self.lease.job["run_id"])).scalar_one()
                    actual = c.execute(select(cases.c.graph_epoch).join(
                        runs, runs.c.case_id == cases.c.id).where(
                        runs.c.id == self.lease.job["run_id"]).with_for_update()).scalar_one()
                    if actual != expected:
                        raise LeaseLost()
                c.execute(text("SET LOCAL search_path TO wp01_wp11, public"))
                answer = action()
                self.store._finish_valid(self.lease, deadline)
                return answer

    @staticmethod
    def store_job_lease():
        from app.infrastructure.orm import jobs

        return jobs.c.lease_until

    @staticmethod
    def store_job_id():
        from app.infrastructure.orm import jobs

        return jobs.c.id

    @property
    def workflow_id(self):
        with self.store.engine.connect() as c:
            value = c.execute(select(runs.c.workflow_id, runs.c.turn_id).where(
                runs.c.id == self.lease.job["run_id"])).one()
        return str(value[0]) + ":" + str(value[1])

    def get_tuple(self, config):
        return self._guarded(config, lambda: super(FencedPostgresSaver, self).get_tuple(config))

    def put(self, config, checkpoint, metadata, new_versions):
        return self._guarded(config, lambda: super(FencedPostgresSaver, self).put(
            config, checkpoint, metadata, new_versions))

    def put_writes(self, config, writes, task_id, task_path=""):
        return self._guarded(config, lambda: super(FencedPostgresSaver, self).put_writes(
            config, writes, task_id, task_path))
