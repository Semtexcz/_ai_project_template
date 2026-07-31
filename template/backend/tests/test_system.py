# pyright: reportUnknownMemberType=false
from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.modules.system.api.routes import SystemInfoResponse
from app.shared.config.settings import Settings


def get_json(path: str) -> tuple[int, dict[str, object]]:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = cast(httpx.Response, client.get(path))
    return response.status_code, cast(dict[str, object], response.json())


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

    assert app.title == Settings().app_name
    assert app.version == "0.1.0"


def test_health_endpoint() -> None:
    status_code, payload = get_json("/health")

    assert status_code == 200
    assert payload == {"status": "ok"}


def test_readiness_endpoint() -> None:
    status_code, payload = get_json("/ready")

    assert status_code == 200
    assert payload == {"status": "ready"}


def test_system_info_endpoint() -> None:
    status_code, payload = get_json("/api/system/info")

    assert status_code == 200
    response = SystemInfoResponse.model_validate(payload)
    assert response == SystemInfoResponse(
        name=Settings().app_name,
        version="0.1.0",
        environment="local",
        next_step="Open project/index.md",
    )


def test_openapi_contract() -> None:
    status_code, document = get_json("/openapi.json")

    assert status_code == 200
    assert document["info"] == {
        "title": Settings().app_name,
        "description": "Stateless FastAPI backend service.",
        "version": "0.1.0",
    }

    paths = cast(dict[str, object], document["paths"])
    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/system/info" in paths

    system_info_route = cast(dict[str, object], paths["/api/system/info"])
    system_info_operation = cast(dict[str, object], system_info_route["get"])
    assert system_info_operation["operationId"] == "getSystemInfo"
    system_info_responses = cast(dict[str, object], system_info_operation["responses"])
    assert "200" in system_info_responses

    assert response_schema(paths, "/health")["$ref"] == "#/components/schemas/HealthResponse"
    assert response_schema(paths, "/ready")["$ref"] == "#/components/schemas/ReadinessResponse"
    assert (
        response_schema(paths, "/api/system/info")["$ref"]
        == "#/components/schemas/SystemInfoResponse"
    )


def test_cors_allows_documented_local_frontend_origin() -> None:
    app = create_app(
        Settings(
            environment="test",
            cors_allowed_origins=["http://127.0.0.1:3000"],
        )
    )
    with TestClient(app) as client:
        response = cast(
            httpx.Response,
            client.options(
                "/api/system/info",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "Access-Control-Request-Method": "GET",
                },
            ),
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_missing_endpoint_returns_404() -> None:
    status_code, payload = get_json("/missing")

    assert status_code == 404
    assert payload == {"detail": "Not Found"}


def test_invalid_log_level_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", "TRACE")

    with pytest.raises(ValidationError):
        Settings()
