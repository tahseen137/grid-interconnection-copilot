from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/session/login",
        json={"username": "admin", "password": "pilot-password", "next_path": "/"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_activity_feed_records_project_site_and_analysis_events(auth_client: TestClient) -> None:
    csrf_token = _login(auth_client)

    project_response = auth_client.post(
        "/api/projects",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "name": "Activity Coverage Project",
            "developer": "Grid Team",
            "status": "screening",
            "technology_focus": "solar_storage",
            "target_cod_year": 2029,
            "notes": "Used to verify activity logging.",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    site_response = auth_client.post(
        f"/api/projects/{project_id}/sites",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "name": "West Texas Pivot",
            "region": "ERCOT",
            "state": "TX",
            "technology": "solar_storage",
            "acreage": 550,
            "distance_to_substation_km": 2.5,
            "queue_wait_months": 12,
            "estimated_upgrade_cost_musd": 8.0,
            "transmission_voltage_kv": 138,
            "environmental_sensitivity": 18,
            "community_support": 80,
            "permitting_complexity": "low",
            "site_control": "secured",
            "land_use_conflict": "low",
            "notes": "High-level site screening notes",
        },
    )
    assert site_response.status_code == 201

    analysis_response = auth_client.post(
        f"/api/projects/{project_id}/analysis",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert analysis_response.status_code == 201

    activity_response = auth_client.get("/api/activity")
    assert activity_response.status_code == 200
    actions = [event["action"] for event in activity_response.json()]

    assert "auth.login" in actions
    assert "project.created" in actions
    assert "site.created" in actions
    assert "analysis.created" in actions
