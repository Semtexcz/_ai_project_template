from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.system.application.status import GetHealthStatus, GetReadinessStatus
from app.shared.config.settings import Settings


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str


class SystemInfoResponse(BaseModel):
    name: str
    version: str
    environment: str
    next_step: str


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    health = GetHealthStatus().execute()
    return HealthResponse(status=health.status)


@router.get("/ready", response_model=ReadinessResponse, operation_id="getReadiness")
def get_readiness() -> ReadinessResponse:
    readiness = GetReadinessStatus().execute()
    return ReadinessResponse(status=readiness.status)


@router.get("/api/system/info", response_model=SystemInfoResponse, operation_id="getSystemInfo")
def get_system_info() -> SystemInfoResponse:
    settings = Settings()
    return SystemInfoResponse(
        name=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        next_step="Open project/brief.md",
    )
