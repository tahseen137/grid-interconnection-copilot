from fastapi.testclient import TestClient

from app.user_service import create_user


def _login(client: TestClient, username: str = "admin", password: str = "pilot-password") -> str:
    response = client.post(
        "/api/session/login",
        json={"username": username, "password": password, "next_path": "/"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_admin_can_create_and_update_users(auth_client: TestClient) -> None:
    csrf_token = _login(auth_client)

    create_response = auth_client.post(
        "/api/admin/users",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "username": "analyst.one",
            "full_name": "Analyst One",
            "role": "analyst",
            "password": "analyst-password",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    list_response = auth_client.get("/api/admin/users")
    assert list_response.status_code == 200
    assert any(user["username"] == "analyst.one" for user in list_response.json())

    update_response = auth_client.patch(
        f"/api/admin/users/{user_id}",
        headers={"X-CSRF-Token": csrf_token},
        json={"role": "viewer", "is_active": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "viewer"
    assert update_response.json()["is_active"] is False


def test_last_admin_cannot_be_deactivated(auth_client: TestClient) -> None:
    csrf_token = _login(auth_client)

    response = auth_client.patch(
        "/api/admin/users/not-used",
        headers={"X-CSRF-Token": csrf_token},
        json={"is_active": False},
    )
    assert response.status_code == 404

    users_response = auth_client.get("/api/admin/users")
    admin_user_id = users_response.json()[0]["id"]

    deactivate_response = auth_client.patch(
        f"/api/admin/users/{admin_user_id}",
        headers={"X-CSRF-Token": csrf_token},
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 400
    assert deactivate_response.json()["detail"] == "Keep at least one active admin account in the workspace"


def test_non_admin_cannot_access_admin_api(auth_client: TestClient) -> None:
    with auth_client.app.state.database.session_factory() as session:
        create_user(
            session,
            username="viewer.user",
            password="viewer-password",
            role="viewer",
            full_name="Viewer User",
        )

    _login(auth_client, username="viewer.user", password="viewer-password")
    response = auth_client.get("/api/admin/users")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"
