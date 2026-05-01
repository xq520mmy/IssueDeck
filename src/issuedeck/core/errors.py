"""Business exception hierarchy.

Service layer raises only IssueDeckError subclasses — never ValueError / RuntimeError.
Each subclass has a unique `code` (machine-readable) and a `http_status` class var
read by the FastAPI exception handler installed in `app.py`.
"""

from __future__ import annotations

from typing import Any, ClassVar


class IssueDeckError(Exception):
    code: ClassVar[str] = "issuedeck_error"
    http_status: ClassVar[int] = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ConfigError(IssueDeckError):
    code = "config_error"
    http_status = 500


class ProjectNotFound(IssueDeckError):
    code = "project_not_found"
    http_status = 404


class ItemNotFound(IssueDeckError):
    code = "item_not_found"
    http_status = 404


class WorkSessionNotFound(IssueDeckError):
    code = "work_session_not_found"
    http_status = 404


class InvalidKind(IssueDeckError):
    code = "invalid_kind"
    http_status = 422


class InvalidStatus(IssueDeckError):
    code = "invalid_status"
    http_status = 422


class InvalidBranch(IssueDeckError):
    code = "invalid_branch"
    http_status = 422


class InvalidTransition(IssueDeckError):
    code = "invalid_transition"
    http_status = 422


class ShipRequiresBranchConfig(IssueDeckError):
    code = "ship_requires_branch_config"
    http_status = 422


class RelationshipSelfLoop(IssueDeckError):
    code = "relationship_self_loop"
    http_status = 409


class RelationshipDuplicate(IssueDeckError):
    code = "relationship_duplicate"
    http_status = 409


class Unauthorized(IssueDeckError):
    code = "unauthorized"
    http_status = 401


def install_error_handlers(app) -> None:
    """Install FastAPI exception handlers. Called from create_app."""
    import logging

    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    log = logging.getLogger("issuedeck.errors")

    @app.exception_handler(IssueDeckError)
    async def _issuedeck(request: Request, exc: IssueDeckError):
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {
                "code": exc.code, "message": exc.message, "details": exc.details,
            }},
        )

    @app.exception_handler(RequestValidationError)
    async def _pydantic(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {
                "code": "validation_error",
                "message": "Request payload validation failed",
                "details": {"errors": exc.errors()},
            }},
        )

    @app.exception_handler(Exception)
    async def _catchall(request: Request, exc: Exception):
        log.exception("unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": {
                "code": "internal_error",
                "message": "An internal error occurred. Check server logs.",
                "details": {},
            }},
        )
