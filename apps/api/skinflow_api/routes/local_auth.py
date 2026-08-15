from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from skinflow_api.routes.errors import error_response
from skinflow_api.settings import Settings

COOKIE_PREFIX = "skinflow_session"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def session_cookie_name(settings: Settings) -> str:
    if not settings.startup_token:
        return COOKIE_PREFIX
    instance_id = hashlib.sha256(settings.startup_token.encode("utf-8")).hexdigest()[:16]
    return f"{COOKIE_PREFIX}_{instance_id}"


class SessionExchange(BaseModel):
    startup_token: str = Field(min_length=20, max_length=200)


class LocalSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._cookie_name = session_cookie_name(settings)

    async def dispatch(self, request: Request, call_next):
        token = self._settings.startup_token
        if not token:
            return await call_next(request)
        host = request.headers.get("host", "")
        if self._settings.allowed_host and host != self._settings.allowed_host:
            return error_response(403, "INVALID_HOST", "请求主机不受信任")
        if request.method in WRITE_METHODS and request.url.path != "/api/auth/session":
            origin = request.headers.get("origin", "")
            if not self._origin_allowed(origin):
                return error_response(403, "INVALID_ORIGIN", "请求来源不受信任")
            content_type = request.headers.get("content-type", "").split(";", 1)[0]
            if content_type != "application/json":
                return error_response(415, "JSON_REQUIRED", "写接口只接受 JSON")
            cookie = request.cookies.get(self._cookie_name, "")
            if not hmac.compare_digest(cookie, token):
                return error_response(401, "AUTH_REQUIRED", "本地启动会话无效")
        return await call_next(request)

    def _origin_allowed(self, origin: str) -> bool:
        if origin == self._settings.allowed_origin:
            return True
        # The Vite development shell is a fixed, loopback-only origin. It is
        # allowed only for development builds and still requires the HttpOnly
        # startup cookie above.
        return self._settings.environment == "development" and origin in {
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        }


def create_auth_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["local-auth"])

    @router.post("/session")
    def exchange(request: SessionExchange, response: Response) -> dict:
        expected = settings.startup_token
        if not expected or not hmac.compare_digest(request.startup_token, expected):
            return error_response(401, "INVALID_STARTUP_TOKEN", "启动令牌无效")
        response.set_cookie(
            session_cookie_name(settings),
            expected,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return {"authenticated": True}

    return router
