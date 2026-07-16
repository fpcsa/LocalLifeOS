from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import (
    domain_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import DomainError
from app.core.logging import configure_safe_logging
from app.core.middleware import (
    LocalOriginMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.network import configure_outbound_network_guard
from app.db.session import initialize_database
from app.services.automation_scheduler import (
    start_automation_scheduler,
    stop_automation_scheduler,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    start_automation_scheduler()
    try:
        yield
    finally:
        stop_automation_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_safe_logging()
    configure_outbound_network_guard(external_requests_enabled=settings.external_requests_enabled)
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Loopback-only API for the LocalLife OS local workspace.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(
        LocalOriginMiddleware,
        allowed_origins=settings.cors_origins,
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
        www_redirect=False,
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(DomainError, domain_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
