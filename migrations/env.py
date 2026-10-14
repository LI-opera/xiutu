from alembic import context
from app.config import Settings
from app.infrastructure.db_target import validate_target
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

settings = Settings()
if settings.database_url is None:
    raise RuntimeError("DATABASE_URL is required for migrations")
target = validate_target(settings.database_url.get_secret_value(), "migration")
engine = create_engine(
    target.sqlalchemy_url(), connect_args=target.connect_kwargs(), poolclass=NullPool
)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
