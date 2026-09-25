"""Consistent error envelope: {"error": {"code", "message"}}.

Every failure path — validation, HTTP, DB constraint, unknown — serializes
the same shape so clients (web now, mobile later) have one error contract.
"""

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import errors as pg_errors

log = structlog.get_logger()


def envelope(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exc(_req: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        code = (
            exc.headers.get("x-error-code") if exc.headers else None
        ) or f"HTTP_{exc.status_code}"
        return envelope(code, detail, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exc(_req: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        msg = f"{loc}: {first.get('msg', 'invalid')}" if loc else "invalid request"
        return envelope("VALIDATION", msg, 422)

    @app.exception_handler(pg_errors.UniqueViolation)
    async def unique_exc(_req: Request, exc: pg_errors.UniqueViolation) -> JSONResponse:
        return envelope("CONFLICT", "resource already exists", 409)

    @app.exception_handler(pg_errors.DataError)
    async def data_exc(_req: Request, exc: pg_errors.DataError) -> JSONResponse:
        return envelope("BAD_GEOMETRY", "geometry could not be parsed", 422)

    @app.exception_handler(Exception)
    async def unknown_exc(_req: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", error=str(exc))
        return envelope("INTERNAL", "internal error", 500)


def not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


def unauthorized(message: str = "authentication required") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"x-error-code": "UNAUTHENTICATED", "WWW-Authenticate": "Bearer"},
    )
