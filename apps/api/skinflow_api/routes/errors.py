from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from skinflow_api.application.inventory.errors import (
    InventoryRateLimited,
    InventoryUnavailable,
    LoginUnavailable,
    SteamSessionExpired,
)


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    retry_after_seconds: int | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "retry_after_seconds": retry_after_seconds,
                "correlation_id": str(uuid4()),
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        return error_response(422, "INVALID_REQUEST", "request validation failed")

    @app.exception_handler(PermissionError)
    async def permission_error(_request: Request, _error: PermissionError) -> JSONResponse:
        return error_response(401, "SESSION_REQUIRED", "Steam 会话未连接或已过期")

    @app.exception_handler(ValueError)
    async def business_error(_request: Request, error: ValueError | LookupError) -> JSONResponse:
        return error_response(409, "CONFLICT", str(error))

    app.add_exception_handler(LookupError, business_error)

    @app.exception_handler(LoginUnavailable)
    async def login_unavailable(_request: Request, error: LoginUnavailable) -> JSONResponse:
        return error_response(409, "LOGIN_UNAVAILABLE", str(error))

    @app.exception_handler(InventoryRateLimited)
    async def inventory_rate_limited(
        _request: Request, error: InventoryRateLimited
    ) -> JSONResponse:
        return error_response(
            429,
            error.code,
            str(error),
            retryable=True,
            retry_after_seconds=error.retry_after_seconds,
        )

    @app.exception_handler(InventoryUnavailable)
    async def inventory_unavailable(_request: Request, error: InventoryUnavailable) -> JSONResponse:
        return error_response(503, error.code, str(error), retryable=True)

    @app.exception_handler(SteamSessionExpired)
    async def steam_session_expired(_request: Request, error: SteamSessionExpired) -> JSONResponse:
        return error_response(401, error.code, str(error))
