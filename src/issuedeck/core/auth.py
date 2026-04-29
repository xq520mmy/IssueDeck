"""Bearer token and dashboard session middleware."""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Iterable
from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

DASHBOARD_SESSION_COOKIE = "issuedeck_dashboard_session"
DASHBOARD_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7


def make_dashboard_session_cookie(token: str, *, issued_at: int | None = None) -> str:
    timestamp = issued_at or int(time.time())
    signature = _dashboard_session_signature(token, timestamp)
    return f"v1.{timestamp}.{signature}"


def is_valid_dashboard_session_cookie(
    value: str | None,
    token: str,
    *,
    now: int | None = None,
    max_age_seconds: int = DASHBOARD_SESSION_MAX_AGE_SECONDS,
) -> bool:
    if not value:
        return False

    try:
        version, raw_timestamp, presented_signature = value.split(".", 2)
        timestamp = int(raw_timestamp)
    except (TypeError, ValueError):
        return False

    current_time = now or int(time.time())
    if version != "v1":
        return False
    if timestamp > current_time + 60:
        return False
    if current_time - timestamp > max_age_seconds:
        return False

    expected_signature = _dashboard_session_signature(token, timestamp)
    return hmac.compare_digest(presented_signature, expected_signature)


def _dashboard_session_signature(token: str, timestamp: int) -> str:
    payload = f"issuedeck.dashboard.v1.{timestamp}".encode()
    return hmac.new(token.encode(), payload, hashlib.sha256).hexdigest()


class BearerTokenMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        token: str,
        exempt_paths: Iterable[str] = (),
        dashboard_paths: Iterable[str] = (),
        dashboard_login_path: str = "/dashboard/login",
        dashboard_cookie_name: str = DASHBOARD_SESSION_COOKIE,
        dashboard_session_max_age_seconds: int = DASHBOARD_SESSION_MAX_AGE_SECONDS,
    ):
        super().__init__(app)
        self._token = token
        self._exempt = tuple(exempt_paths)
        self._dashboard_paths = tuple(dashboard_paths)
        self._dashboard_login_path = dashboard_login_path
        self._dashboard_cookie_name = dashboard_cookie_name
        self._dashboard_session_max_age_seconds = dashboard_session_max_age_seconds

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in self._exempt):
            return await call_next(request)

        bearer_error = self._bearer_token_error(request)
        if bearer_error is None:
            return await call_next(request)

        if self._is_dashboard_path(path):
            cookie_value = request.cookies.get(self._dashboard_cookie_name)
            if is_valid_dashboard_session_cookie(
                cookie_value,
                self._token,
                max_age_seconds=self._dashboard_session_max_age_seconds,
            ):
                return await call_next(request)

            if request.method in {"GET", "HEAD"}:
                return RedirectResponse(
                    url=self._dashboard_login_url(request),
                    status_code=303,
                )
            return self._unauth("missing dashboard session")

        return self._unauth(bearer_error)

    def _bearer_token_error(self, request: Request) -> str | None:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return "missing bearer token"
        presented = header.split(" ", 1)[1]
        if not hmac.compare_digest(presented, self._token):
            return "invalid bearer token"
        return None

    def _is_dashboard_path(self, path: str) -> bool:
        return any(path == p or path.startswith(p + "/") for p in self._dashboard_paths)

    def _dashboard_login_url(self, request: Request) -> str:
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        return f"{self._dashboard_login_path}?next={quote(next_url, safe='')}"

    @staticmethod
    def _unauth(msg: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthorized", "message": msg, "details": {}}},
        )
