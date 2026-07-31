from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.system.application.status import GetHealthStatus, GetReadinessStatus


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    health = GetHealthStatus().execute()
    return HealthResponse(status=health.status)


@router.get("/ready", response_model=ReadinessResponse)
def get_readiness() -> ReadinessResponse:
    readiness = GetReadinessStatus().execute()
    return ReadinessResponse(status=readiness.status)
