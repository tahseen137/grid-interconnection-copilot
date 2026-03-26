import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.user_service import create_user


def _login(client: TestClient, username: str = "admin", password: str = "pilot-password"):
    return client.post(
        "/api/session/login",
        json={"username": username, "password": password, "next_path": "/"},
    )


def test_auth_configuration_requires_session_secret_for_bootstrap_admin(tmp_path) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            database_url=f"sqlite:///{(tmp_path / 'missing-secret.db').resolve()}",
            bootstrap_admin_username="admin",
            bootstrap_admin_password="pilot-password",
        )


def test_workspace_and_api_require_login(auth_client: TestClient) -> None:
    home_response = auth_client.get("/", follow_redirects=False)
    assert home_response.status_code == 303
    assert home_response.headers["location"].startswith("/login")

    api_response = auth_client.get("/api/projects")
    assert api_response.status_code == 401
    assert api_response.json()["detail"] == "Authentication required"

    bad_login_response = _login(auth_client, password="wrong-password")
    assert bad_login_response.status_code == 401
    assert bad_login_response.json()["detail"] == "Invalid credentials"

    login_response = _login(auth_client)
    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["authenticated"] is True
    assert payload["auth_required"] is True
    assert payload["current_user"]["username"] == "admin"
    assert payload["permissions"]["can_write"] is True
    assert payload["csrf_token"]

    session_response = auth_client.get("/api/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True
    assert session_response.json()["current_user"]["role"] == "admin"

    authorized_response = auth_client.get("/api/projects")
    assert authorized_response.status_code == 200

    logout_response = auth_client.post("/api/session/logout", headers={"X-CSRF-Token": payload["csrf_token"]})
    assert logout_response.status_code == 200
    assert logout_response.json()["authenticated"] is False

    post_logout_response = auth_client.get("/api/projects")
    assert post_logout_response.status_code == 401


def test_login_page_and_security_headers(auth_client: TestClient) -> None:
    response = auth_client.get("/login")

    assert response.status_code == 200
    assert "Username" in response.text
    assert "Password" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "content-security-policy" in response.headers


def test_login_page_redirects_after_authentication(auth_client: TestClient) -> None:
    _login(auth_client)

    response = auth_client.get("/login?next=%2Fapi%2Fprojects", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/api/projects"


def test_login_behaviour_when_auth_is_disabled(client: TestClient) -> None:
    login_page_response = client.get("/login", follow_redirects=False)
    assert login_page_response.status_code == 303
    assert login_page_response.headers["location"] == "/"

    login_response = client.post(
        "/api/session/login",
        json={"username": "ignored", "password": "ignored", "next_path": "/"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["auth_required"] is False
    assert login_response.json()["authenticated"] is True


def test_csrf_token_required_for_mutating_requests(auth_client: TestClient) -> None:
    login_response = _login(auth_client)
    assert login_response.status_code == 200

    create_without_csrf = auth_client.post(
        "/api/projects",
        json={
            "name": "CSRF Coverage Project",
            "developer": "Grid Team",
            "status": "draft",
            "technology_focus": "solar",
            "target_cod_year": 2030,
            "notes": "",
        },
    )
    assert create_without_csrf.status_code == 403
    assert create_without_csrf.json()["detail"] == "CSRF token missing or invalid"


def test_viewer_cannot_write(auth_client: TestClient) -> None:
    with auth_client.app.state.database.session_factory() as session:
        create_user(
            session,
            username="viewer.user",
            password="viewer-password",
            role="viewer",
            full_name="Viewer User",
        )

    viewer_login = _login(auth_client, username="viewer.user", password="viewer-password")
    assert viewer_login.status_code == 200
    csrf_token = viewer_login.json()["csrf_token"]

    create_response = auth_client.post(
        "/api/projects",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "name": "Viewer Restricted Project",
            "developer": "Grid Team",
            "status": "draft",
            "technology_focus": "solar",
            "target_cod_year": 2030,
            "notes": "",
        },
    )
    assert create_response.status_code == 403
    assert create_response.json()["detail"] == "Write access requires analyst or admin role"


def test_login_lockout_after_repeated_failures(auth_client: TestClient) -> None:
    for _ in range(5):
        response = _login(auth_client, password="wrong-password")
        assert response.status_code == 401

    locked_response = _login(auth_client)
    assert locked_response.status_code == 401
    assert locked_response.json()["detail"] == "Account temporarily locked. Try again later."
