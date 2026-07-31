from app.modules.system.domain.status import HealthStatus, ReadinessStatus


class GetHealthStatus:
    def execute(self) -> HealthStatus:
        return HealthStatus()


class GetReadinessStatus:
    def execute(self) -> ReadinessStatus:
        return ReadinessStatus()
