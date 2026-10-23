"""Local database boundary. Never pass an unvalidated DSN to a driver."""

import os
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qsl, unquote, urlsplit

from sqlalchemy import URL


CONTAINER_HOST_ENV = "CONTAINER_DB_HOST"


@dataclass(frozen=True)
class DatabaseTarget:
    database: str
    user: str
    password: str = field(repr=False)
    connect_timeout: int = 2
    # Loopback by default; only the named Compose service when CONTAINER_DB_HOST allows it.
    host: str = "127.0.0.1"
    port: int = 5433

    def connect_kwargs(self, *, schema: str | None = None) -> dict:
        # Explicit address, credentials and passfile prevent ambient libpq fallback.
        kwargs = dict(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password,
            passfile=os.devnull,
            connect_timeout=self.connect_timeout,
        )
        if self.host == "127.0.0.1":
            kwargs["hostaddr"] = "127.0.0.1"
        if schema is not None:
            if not re.fullmatch(r"wp01_[a-z0-9_]{1,48}", schema):
                raise ValueError("Invalid isolated probe schema")
            kwargs["options"] = f"-c search_path={schema}"
        return kwargs

    def sqlalchemy_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )


def validate_target(
    url: str, scope: Literal["test", "development", "migration"] = "test"
) -> DatabaseTarget:
    # Fail closed instead of guessing which ambient libpq option overrides a URL.
    if any(k.upper().startswith("PG") and v for k, v in os.environ.items()):
        raise ValueError("PG* environment options are not allowed for isolated local connections")
    try:
        if not isinstance(url, str) or any(ord(c) < 32 for c in url):
            raise ValueError()
        parts = urlsplit(url)
        if parts.scheme not in {"postgresql", "postgres"} or parts.fragment:
            raise ValueError()
        host, port = "127.0.0.1", 5433
        if parts.hostname not in {"127.0.0.1", "localhost"} or parts.port != 5433:
            # Inside Docker Compose the database is the service named by CONTAINER_DB_HOST, on
            # PostgreSQL's own port. Without that variable only the loopback address above is allowed.
            container = os.environ.get(CONTAINER_HOST_ENV, "")
            if not (re.fullmatch(r"[a-z][a-z0-9-]{0,62}", container)
                    and parts.hostname == container and parts.port == 5432):
                raise ValueError()
            host, port = container, 5432
        user, password = unquote(parts.username or ""), unquote(parts.password or "")
        database = unquote(parts.path.removeprefix("/"))
        if not user or not re.fullmatch(r"[a-zA-Z0-9_]+", user):
            raise ValueError()
        is_test = bool(re.fullmatch(r"xiutu_test_[a-z0-9_]{1,40}", database))
        allowed = {
            "test": is_test,
            "development": database == "xiutu_dev",
            "migration": is_test or database == "xiutu_dev",
        }
        if not allowed.get(scope, False):
            raise ValueError()
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
        if len(query) > 1 or any(k != "connect_timeout" for k, v in query):
            raise ValueError()
        timeout = int(query[0][1]) if query else 2
        if not 1 <= timeout <= 5:
            raise ValueError()
        return DatabaseTarget(database, user, password, timeout, host, port)
    except (ValueError, TypeError):
        raise ValueError(
            "Require explicit local PostgreSQL :5433, allowed xiutu database and only connect_timeout query"
        ) from None
