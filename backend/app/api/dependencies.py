import hashlib
import hmac
import ipaddress
import secrets
import threading
import time
from dataclasses import dataclass
from uuid import UUID

from fastapi import Request

from app.domain.policies import DomainError

COOKIE = "xiutu_session"


@dataclass(frozen=True)
class Principal:
    actor_id: UUID
    csrf: str
    expires: float


class AuthStore:
    def __init__(self, settings):
        self.settings = settings
        self.sessions = {}
        self.lock = threading.Lock()

    def login(self, token, old_cookie=None):
        configured = self.settings.operator_token
        if configured is None:
            raise DomainError("AUTH_NOT_CONFIGURED", "Operator authentication not configured", 503)
        if not hmac.compare_digest(token.encode(), configured.get_secret_value().encode()):
            raise DomainError("UNAUTHORIZED", "Authentication required", 401)
        return self._issue(old_cookie)

    def local_session(self, old_cookie=None):
        if not self.settings.local_dev_auto_identity:
            raise DomainError("UNAUTHORIZED", "Authentication required", 401)
        return self._issue(old_cookie)

    def _issue(self, old_cookie=None):
        cookie = secrets.token_urlsafe(32)
        principal = Principal(
            self.settings.operator_id,
            secrets.token_urlsafe(32),
            time.monotonic() + self.settings.auth_session_seconds,
        )
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v.expires > time.monotonic()}
            if old_cookie:
                self.sessions.pop(hashlib.sha256(old_cookie.encode()).hexdigest(), None)
            if len(self.sessions) >= 1000:
                raise DomainError(
                    "AUTH_CAPACITY", "Authentication capacity reached", 503, retryable=True
                )
            self.sessions[hashlib.sha256(cookie.encode()).hexdigest()] = principal
        return cookie, principal

    def get(self, cookie):
        if not cookie or len(cookie) > 128:
            raise DomainError("UNAUTHORIZED", "Authentication required", 401)
        key = hashlib.sha256(cookie.encode()).hexdigest()
        with self.lock:
            principal = self.sessions.get(key)
            if principal is None or principal.expires <= time.monotonic():
                self.sessions.pop(key, None)
                raise DomainError("UNAUTHORIZED", "Authentication required", 401)
            return principal

    def revoke(self, cookie):
        with self.lock:
            self.sessions.pop(hashlib.sha256(cookie.encode()).hexdigest(), None)


def same_origin(request: Request):
    if request.headers.get("origin") != request.app.state.settings.app_origin:
        raise DomainError("ORIGIN_FORBIDDEN", "Same-origin request required", 403)


def local_loopback_request(request: Request) -> bool:
    """Use socket endpoints, never Host or forwarded headers, for local opt-in."""
    client = request.client
    server = request.scope.get("server")
    if client is None or not server:
        return False
    try:
        return ipaddress.ip_address(client.host).is_loopback and ipaddress.ip_address(server[0]).is_loopback
    except ValueError:
        return False


def authenticated(request: Request):
    return request.app.state.auth.get(request.cookies.get(COOKIE))


def writing(request: Request):
    principal = authenticated(request)
    same_origin(request)
    csrf = request.headers.get("x-csrf-token", "")
    if not hmac.compare_digest(csrf.encode(), principal.csrf.encode()):
        raise DomainError("CSRF_INVALID", "Valid CSRF token required", 403)
    return principal
