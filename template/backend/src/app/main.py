from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.modules.example.api.routes import router as example_router
from app.modules.system.api.routes import router as system_router
from app.shared.config.settings import Settings
from app.shared.observability.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger(__name__)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        logger.info("application_startup", app=settings.app_name, environment=settings.environment)
        yield
        logger.info("application_shutdown", app=settings.app_name, environment=settings.environment)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Stateless FastAPI backend service.",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "system", "description": "Process health and readiness endpoints."},
            {"name": "example", "description": "Example feature endpoint."},
        ],
    )

    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            exception_type=type(exc).__name__,
            method=request.method,
            path=request.url.path,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(system_router)
    app.include_router(example_router)
    return app


app = create_app()
