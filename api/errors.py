"""Consistent error envelope for the whole API.

Every non-2xx JSON response — and the SSE `error` event — uses the single shape

    {"error": {"code": "...", "message": "...", "detail": ...}}

so the frontend's `ErrorState` renders all failures through one path
(see FRONTEND_V3_API.md §5). The service layer signals failure with plain
Python (`ValueError` for bad input, `None`/`False` for a missing row); this
module maps those to the envelope so routers stay thin.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from merlin.core.logging import logger


class APIError(Exception):
    """Raised by routers to produce a §5 error envelope with a chosen code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail


def error_body(code: str, message: str, detail: object | None = None) -> dict:
    """Build the bare `{"error": {...}}` envelope (also used by SSE streams)."""
    return {"error": {"code": code, "message": message, "detail": detail}}


def _json(status_code: int, code: str, message: str, detail: object | None = None):
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(error_body(code, message, detail)),
    )


# Map a bare HTTP status to a machine-readable code for HTTPExceptions raised
# outside our own APIError (e.g. FastAPI's 404 for an unknown route).
_STATUS_CODE = {
    400: "invalid_input",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    502: "upstream_error",
}


def not_found(message: str = "Not found.") -> APIError:
    return APIError(404, "not_found", message)


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers that turn exceptions into the §5 envelope."""

    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError):
        return _json(exc.status_code, exc.code, exc.message, exc.detail)

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError):
        # Services raise ValueError for bad input (bad URL, unsupported
        # language, malformed request) → 400 invalid_input with the real message.
        return _json(400, "invalid_input", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return _json(
            422,
            "validation_error",
            "Request validation failed.",
            detail=jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODE.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _json(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        logger.exception(f"Unhandled API error: {exc}")
        return _json(500, "internal_error", "An unexpected error occurred.")
