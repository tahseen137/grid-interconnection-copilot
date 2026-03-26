from fastapi.testclient import TestClient

from app.main import app


def test_index_serves_dashboard() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Grid Interconnection Copilot" in response.text
    assert "Generate memo" in response.text
