import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings


def test_auth_configuration_requires_session_secret(tmp_path) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            database_url=f"sqlite:///{(tmp_path / 'missing-secret.db').resolve()}",
            app_access_password="pilot-password",
        )


def test_workspace_and_api_require_login(auth_client: TestClient) -> None:
    home_response = auth_client.get("/", follow_redirects=False)
    assert home_response.status_code == 303
    assert home_response.headers["location"].startswith("/login")

    api_response = auth_client.get("/api/projects")
    assert api_response.status_code == 401
    assert api_response.json()["detail"] == "Authentication required"

    bad_login_response = auth_client.post(
        "/api/session/login",
        json={"password": "wrong-password", "next_path": "/"},
    )
    assert bad_login_response.status_code == 401
    assert bad_login_response.json()["detail"] == "Invalid password"

    login_response = auth_client.post(
        "/api/session/login",
        json={"password": "pilot-password", "next_path": "/"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["authenticated"] is True

    session_response = auth_client.get("/api/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True

    authorized_response = auth_client.get("/api/projects")
    assert authorized_response.status_code == 200

    logout_response = auth_client.post("/api/session/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["authenticated"] is False

    post_logout_response = auth_client.get("/api/projects")
    assert post_logout_response.status_code == 401


def test_login_page_and_security_headers(auth_client: TestClient) -> None:
    response = auth_client.get("/login")

    assert response.status_code == 200
    assert "Workspace password" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "content-security-policy" in response.headers


def test_login_page_redirects_after_authentication(auth_client: TestClient) -> None:
    auth_client.post("/api/session/login", json={"password": "pilot-password", "next_path": "/api/projects"})

    response = auth_client.get("/login?next=%2Fapi%2Fprojects", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/api/projects"


def test_login_behaviour_when_auth_is_disabled(client: TestClient) -> None:
    login_page_response = client.get("/login", follow_redirects=False)
    assert login_page_response.status_code == 303
    assert login_page_response.headers["location"] == "/"

    login_response = client.post(
        "/api/session/login",
        json={"password": "ignored", "next_path": "/"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["auth_enabled"] is False
    assert login_response.json()["authenticated"] is True
