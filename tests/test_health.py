from fastapi.testclient import TestClient
import app.main as main_module


def test_healthcheck(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_ready_when_database_is_available(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_returns_service_unavailable_when_database_is_down(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main_module, "database_is_ready", lambda database: False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
