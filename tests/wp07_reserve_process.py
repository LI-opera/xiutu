"""Isolated process reserves one call then exits; no tool is executed."""

import hashlib
import json
import os
from uuid import UUID

from app.api.dependencies import AuthStore
from app.config import Settings
from app.infrastructure.uow import make_engine
from app.tools.context import ToolContext
from app.tools.executor import ToolExecutor
from app.tools.schemas import ObservationInput

settings = Settings(
    database_url=os.environ["TEST_DATABASE_URL"],
    app_mode="test",
    retrieval_profile="synthetic",
    operator_id=UUID(os.environ["WP07_ACTOR"]),
    operator_token="synthetic-wp07-process-token-only-00",
)
auth = AuthStore(settings)
cookie, _ = auth.login("synthetic-wp07-process-token-only-00")
context = ToolContext(
    UUID(os.environ["WP07_EXECUTION"]), os.environ["WP07_CAPABILITY"], auth, cookie
)
engine = make_engine(os.environ["TEST_DATABASE_URL"])
ex = ToolExecutor(engine, settings)
body = ObservationInput(at_revision=0)
digest = hashlib.sha256(
    json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
call, _, _ = ex.reserve(context, "get_case_observations", body, "crashed", digest)
assert call["attempts"] == 1
engine.dispose()
print(os.getpid())
