from psycopg import Error
from psycopg_pool import ConnectionPool, PoolTimeout

from app.infrastructure.db_target import validate_target
from app.infrastructure.schema_version import EXPECTED_REVISION


class Database:
    def __init__(self, url: str | None, *, schema: str | None = None):
        target = validate_target(url, "migration") if url else None
        self.pool = (
            None
            if not url
            else ConnectionPool(
                "",
                min_size=0,
                max_size=2,
                timeout=2,
                open=False,
                kwargs=target.connect_kwargs(schema=schema),
            )
        )

    def open(self):
        if self.pool:
            self.pool.open(wait=False)

    def close(self):
        if self.pool:
            self.pool.close()

    def ready(self) -> bool:
        if self.pool is None:
            return False
        try:
            with self.pool.connection(timeout=2) as conn:
                conn.execute("SET LOCAL statement_timeout = '2000ms'")
                if conn.execute("SELECT 1").fetchone() != (1,):
                    return False
                vector = conn.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')"
                ).fetchone()[0]
                revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                return bool(vector and revision == (EXPECTED_REVISION,))
        except (Error, PoolTimeout):
            # Never serialize connection exceptions: they may carry connection credentials.
            return False
