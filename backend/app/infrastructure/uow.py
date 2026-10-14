from sqlalchemy import create_engine

from app.domain.policies import DomainError
from app.infrastructure.db_target import validate_target


class UnitOfWork:
    def __init__(self, engine, *, connection=None):
        self.engine = engine
        self.external_connection = connection

    def __enter__(self):
        if self.external_connection is not None:
            self.connection = self.external_connection
            if not self.connection.in_transaction():
                raise RuntimeError("External UnitOfWork requires active transaction")
            return self
        if self.engine is None:
            raise DomainError("DATABASE_UNAVAILABLE", "Database unavailable", 503, retryable=True)
        self.connection = self.engine.connect()
        try:
            self.transaction = self.connection.begin()
            self.connection.exec_driver_sql("SET LOCAL statement_timeout = '10000ms'")
            return self
        except BaseException:
            self.connection.close()
            raise

    def __exit__(self, kind, value, traceback):
        if self.external_connection is not None:
            return False
        try:
            if kind is None:
                self.transaction.commit()
            else:
                self.transaction.rollback()
        finally:
            self.connection.close()


def make_engine(url):
    if not url:
        return None
    target = validate_target(url, "migration")
    return create_engine(
        target.sqlalchemy_url(),
        connect_args=target.connect_kwargs(),
        hide_parameters=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=3,
    )
