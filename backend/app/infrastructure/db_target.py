"""WP-01 local database boundary. Never pass an unvalidated DSN to a driver."""

import os
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qsl, unquote, urlsplit

from sqlalchemy import URL


@dataclass(frozen=True)
class DatabaseTarget:
    database: str
    user: str
    password: str = field(repr=False)
    connect_timeout: int = 2

    def connect_kwargs(self, *, schema: str | None = None) -> dict:
        # Explicit numeric address, credentials and passfile prevent ambient libpq fallback.
        kwargs = dict(
            host="127.0.0.1",
            hostaddr="127.0.0.1",
            port=5433,
            dbname=self.database,
            user=self.user,
            password=self.password,
            passfile=os.devnull,
            connect_timeout=self.connect_timeout,
        )
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
            host="127.0.0.1",
            port=5433,
            database=self.database,
        )


def validate_target(
    url: str, scope: Literal["test", "development", "migration"] = "test"
) -> DatabaseTarget:
    # Fail closed instead of guessing which ambient libpq option overrides a URL.
    if any(k.upper().startswith("PG") and v for k, v in os.environ.items()):
        raise ValueError("PG* environment options are not allowed for isolated WP-01 connections")
    try:
        if not isinstance(url, str) or any(ord(c) < 32 for c in url):
            raise ValueError()
        parts = urlsplit(url)
        if parts.scheme not in {"postgresql", "postgres"} or parts.fragment:
            raise ValueError()
        if parts.hostname not in {"127.0.0.1", "localhost"} or parts.port != 5433:
            raise ValueError()
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
        return DatabaseTarget(database, user, password, timeout)
    except (ValueError, TypeError):
        raise ValueError(
            "Require explicit local PostgreSQL :5433, allowed xiutu database and only connect_timeout query"
        ) from None
