from fastapi.testclient import TestClient


def test_index_serves_dashboard(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Grid Interconnection Copilot" in response.text
    assert "Generate memo" in response.text
