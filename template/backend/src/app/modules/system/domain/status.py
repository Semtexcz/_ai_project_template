from dataclasses import dataclass


@dataclass(frozen=True)
class HealthStatus:
    status: str = "ok"


@dataclass(frozen=True)
class ReadinessStatus:
    status: str = "ready"
