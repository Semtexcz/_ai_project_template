from __future__ import annotations

import asyncio
from typing import cast

import httpx
import pytest
from pydantic import ValidationError

from app.main import create_app
from app.shared.config.settings import Settings


async def request_json(path: str) -> tuple[int, dict[str, object]]:
    transport = httpx.ASGITransport(app=create_app(Settings(environment="test")))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path)

    return response.status_code, cast(dict[str, object], response.json())


def get_json(path: str) -> tuple[int, dict[str, object]]:
    return asyncio.run(request_json(path))


def response_schema(paths: dict[str, object], path: str) -> dict[str, object]:
    route = cast(dict[str, object], paths[path])
    operation = cast(dict[str, object], route["get"])
    responses = cast(dict[str, object], operation["responses"])
    ok_response = cast(dict[str, object], responses["200"])
    content = cast(dict[str, object], ok_response["content"])
    json_content = cast(dict[str, object], content["application/json"])
    return cast(dict[str, object], json_content["schema"])


def test_create_app() -> None:
    app = create_app(Settings(environment="test"))

    assert app.title == "Example Backend"
    assert app.version == "0.1.0"


def test_health_endpoint() -> None:
    status_code, payload = get_json("/health")

    assert status_code == 200
    assert payload == {"status": "ok"}


def test_readiness_endpoint() -> None:
    status_code, payload = get_json("/ready")

    assert status_code == 200
    assert payload == {"status": "ready"}


def test_openapi_contract() -> None:
    status_code, document = get_json("/openapi.json")

    assert status_code == 200
    assert document["info"] == {
        "title": "Example Backend",
        "description": "Stateless FastAPI backend service.",
        "version": "0.1.0",
    }

    paths = cast(dict[str, object], document["paths"])
    assert "/health" in paths
    assert "/ready" in paths

    assert response_schema(paths, "/health")["$ref"] == "#/components/schemas/HealthResponse"
    assert response_schema(paths, "/ready")["$ref"] == "#/components/schemas/ReadinessResponse"


def test_missing_endpoint_returns_404() -> None:
    status_code, payload = get_json("/missing")

    assert status_code == 404
    assert payload == {"detail": "Not Found"}


def test_invalid_log_level_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", "TRACE")

    with pytest.raises(ValidationError):
        Settings()
