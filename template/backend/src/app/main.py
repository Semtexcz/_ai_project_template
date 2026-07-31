from fastapi import FastAPI

from app.modules.example.api.routes import router as example_router
from app.shared.config.settings import Settings
from app.shared.observability.logging import configure_logging


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version=settings.version)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["system"])
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/version", tags=["system"])
    def version() -> dict[str, str]:
        return {"version": settings.version}

    app.include_router(example_router)
    return app


app = create_app()
