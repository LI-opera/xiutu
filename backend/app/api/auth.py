import time

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import COOKIE, authenticated, local_loopback_request, same_origin, writing
from app.domain.policies import DomainError
from app.domain.schemas import AuthSession, LoginInput, LogoutResponse

router = APIRouter(prefix="/api/v2/auth", tags=["authentication"])


def session_body(principal):
    return dict(
        actor_id=principal.actor_id,
        csrf_token=principal.csrf,
        expires_in=max(0, int(principal.expires - time.monotonic())),
    )


def set_session_cookie(request: Request, response: Response, cookie: str):
    response.set_cookie(
        COOKIE,
        cookie,
        max_age=request.app.state.settings.auth_session_seconds,
        httponly=True,
        samesite="strict",
        secure=request.app.state.settings.app_origin.startswith("https:"),
        path="/",
    )


@router.post("/login", response_model=AuthSession, dependencies=[Depends(same_origin)])
def login(body: LoginInput, request: Request, response: Response):
    cookie, principal = request.app.state.auth.login(body.token, request.cookies.get(COOKIE))
    set_session_cookie(request, response, cookie)
    response.headers["Cache-Control"] = "no-store"
    return session_body(principal)


@router.get("/session", response_model=AuthSession)
def session(request: Request, response: Response):
    if request.app.state.settings.local_dev_auto_identity and local_loopback_request(request):
        try:
            principal = authenticated(request)
        except DomainError as error:
            if error.status != 401:
                raise
            cookie, principal = request.app.state.auth.local_session(request.cookies.get(COOKIE))
            set_session_cookie(request, response, cookie)
    else:
        principal = authenticated(request)
    response.headers["Cache-Control"] = "no-store"
    return session_body(principal)


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, principal=Depends(writing)):
    request.app.state.auth.revoke(request.cookies[COOKIE])
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=request.app.state.settings.app_origin.startswith("https:"),
    )
    response.headers["Cache-Control"] = "no-store"
    return {"logged_out": True}
