from .models import HealthStatus


class HealthService:
    def __init__(self, *, service: str, api_version: str, environment: str) -> None:
        self._service = service
        self._api_version = api_version
        self._environment = environment

    def get_status(self) -> HealthStatus:
        return HealthStatus(
            status="ok",
            service=self._service,
            api_version=self._api_version,
            environment=self._environment,
        )

