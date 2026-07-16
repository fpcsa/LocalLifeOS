from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.exceptions import DomainError
from app.schemas.errors import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", uuid4()))


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=_request_id(request),
            details=details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    detail = exc.detail
    message = detail if isinstance(detail, str) else "The request could not be completed."
    code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
    details = detail if not isinstance(detail, str) else None
    return _error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    details = [
        {
            "location": list(error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return _error_response(
        request,
        status_code=422,
        code="validation_error",
        message="The request contains invalid data.",
        details=details,
    )


async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    return _error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API error type=%s request_id=%s",
        type(exc).__name__,
        _request_id(request),
    )
    return _error_response(
        request,
        status_code=500,
        code="internal_error",
        message="The local service could not complete the request.",
    )
