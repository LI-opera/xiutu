import asyncio
import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import COOKIE, authenticated, writing
from app.domain.policies import DomainError
from app.domain.tasks import RetryInput, RunAction, RunSnapshot
from app.api.legacy_case_policy import require_template_case

router = APIRouter(prefix="/api/v2/runs", tags=["runs"])


@router.get("/{run_id}", response_model=RunSnapshot)
def get_run(run_id: UUID, request: Request, principal=Depends(authenticated)):
    return request.app.state.run_service.get(principal.actor_id, run_id)


@router.post(
    "/{run_id}/cancel",
    response_model=RunAction,
    status_code=202,
    responses={200: {"model": RunAction}},
)
def cancel(
    run_id: UUID,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
):
    run = request.app.state.run_service.get(principal.actor_id, run_id)
    if run["case_id"] is not None:
        require_template_case(request, principal.actor_id, UUID(run["case_id"]))
    status, body = request.app.state.run_service.cancel(principal.actor_id, run_id, idempotency_key)
    return JSONResponse(body, status_code=status)


@router.post("/{run_id}/retry", response_model=RunAction, status_code=202)
def retry(
    run_id: UUID,
    body: RetryInput,
    request: Request,
    principal=Depends(writing),
    idempotency_key: str = Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
):
    run = request.app.state.run_service.get(principal.actor_id, run_id)
    if run["case_id"] is not None:
        require_template_case(request, principal.actor_id, UUID(run["case_id"]))
    status, result = request.app.state.run_service.retry(
        principal.actor_id, run_id, body, idempotency_key
    )
    return JSONResponse(result, status_code=status)


@router.get(
    "/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
async def events(
    run_id: UUID,
    request: Request,
    principal=Depends(authenticated),
    last_event_id: str | None = Header(default=None),
):
    origin = request.headers.get("origin")
    if (
        origin is not None and origin != request.app.state.settings.app_origin
    ) or request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
        raise DomainError("ORIGIN_FORBIDDEN", "Same-origin request required", 403)
    service = request.app.state.run_service
    cursor = await run_in_threadpool(service.cursor, principal.actor_id, run_id, last_event_id)

    async def stream():
        nonlocal cursor
        beat = time.monotonic()
        while not await request.is_disconnected():
            try:
                request.app.state.auth.get(request.cookies.get(COOKIE))
            except DomainError:
                return
            rows, terminal = await run_in_threadpool(
                service.events, principal.actor_id, run_id, cursor
            )
            for row in rows:
                cursor = row["id"]
                yield f"id: {cursor}\nevent: {row['type']}\ndata: {json.dumps(row['payload'], separators=(',', ':'))}\n\n"
            if terminal and len(rows) < 100:
                return
            if time.monotonic() - beat >= 15:
                yield ": heartbeat\n\n"
                beat = time.monotonic()
            await asyncio.sleep(0.25)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
