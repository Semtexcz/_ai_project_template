from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ready_and_version() -> None:
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/version").json()["version"] == "0.1.0"


def test_example_route() -> None:
    client = TestClient(create_app())

    assert client.get("/example").json() == {"message": "ok"}
