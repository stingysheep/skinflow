from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from skinflow_api.application.health import HealthService


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    service: str
    api_version: str
    environment: str


def create_health_router(service: HealthService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["system"])

    @router.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        status = service.get_status()
        return HealthResponse(
            status=status.status,
            service=status.service,
            api_version=status.api_version,
            environment=status.environment,
        )

    return router

