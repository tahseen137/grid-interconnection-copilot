from fastapi.testclient import TestClient


def _site_payload(name: str) -> dict[str, object]:
    return {
        "name": name,
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
    }


def test_project_crud_and_analysis_workflow(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "High Plains Solar Portfolio",
            "developer": "Prairie Grid Partners",
            "status": "screening",
            "technology_focus": "solar_storage",
            "target_cod_year": 2029,
            "notes": "Focus on fast interconnection paths in ERCOT.",
        },
    )

    assert create_response.status_code == 201
    project = create_response.json()
    project_id = project["id"]
    assert project["developer"] == "Prairie Grid Partners"

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    assert list_response.json()[0]["site_count"] == 0

    first_site_response = client.post(f"/api/projects/{project_id}/sites", json=_site_payload("West Texas Pivot"))
    second_site_response = client.post(f"/api/projects/{project_id}/sites", json=_site_payload("Permian Ridge"))
    assert first_site_response.status_code == 201
    assert second_site_response.status_code == 201

    update_response = client.patch(
        f"/api/projects/{project_id}",
        json={
            "status": "ready",
            "notes": "Updated after internal IC review.",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "ready"

    analysis_response = client.post(f"/api/projects/{project_id}/analysis")
    assert analysis_response.status_code == 201
    analysis = analysis_response.json()
    assert analysis["top_pick_site_name"] in {"West Texas Pivot", "Permian Ridge"}
    assert len(analysis["results"]) == 2

    latest_analysis_response = client.get(f"/api/projects/{project_id}/analysis/latest")
    assert latest_analysis_response.status_code == 200
    assert latest_analysis_response.json()["id"] == analysis["id"]

    project_detail_response = client.get(f"/api/projects/{project_id}")
    assert project_detail_response.status_code == 200
    detail = project_detail_response.json()
    assert len(detail["sites"]) == 2
    assert len(detail["analysis_runs"]) == 1


def test_analysis_requires_at_least_one_site(client: TestClient) -> None:
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Queue Triage Project",
            "developer": "North Fork Development",
            "status": "draft",
            "technology_focus": "solar",
            "target_cod_year": 2030,
            "notes": "",
        },
    )
    project_id = project_response.json()["id"]

    analysis_response = client.post(f"/api/projects/{project_id}/analysis")
    assert analysis_response.status_code == 400
    assert analysis_response.json()["detail"] == "Add at least one site before running analysis"


def test_project_and_site_not_found_paths(client: TestClient) -> None:
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Path Coverage Project",
            "developer": "North Fork Development",
            "status": "draft",
            "technology_focus": "solar",
            "target_cod_year": 2030,
            "notes": "",
        },
    )
    project_id = project_response.json()["id"]

    missing_project_response = client.get("/api/projects/missing-project")
    assert missing_project_response.status_code == 404
    assert missing_project_response.json()["detail"] == "Project not found"

    list_sites_response = client.get(f"/api/projects/{project_id}/sites")
    assert list_sites_response.status_code == 200
    assert list_sites_response.json() == []

    missing_site_response = client.patch(
        f"/api/projects/{project_id}/sites/missing-site",
        json={"name": "Updated"},
    )
    assert missing_site_response.status_code == 404
    assert missing_site_response.json()["detail"] == "Site not found"


def test_site_update_duplicate_validation_and_delete_project(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Delete Coverage Project",
            "developer": "Prairie Grid Partners",
            "status": "screening",
            "technology_focus": "solar_storage",
            "target_cod_year": 2029,
            "notes": "",
        },
    )
    project_id = create_response.json()["id"]

    first_site = client.post(
        f"/api/projects/{project_id}/sites",
        json=_site_payload("West Texas Pivot"),
    ).json()
    second_site = client.post(
        f"/api/projects/{project_id}/sites",
        json=_site_payload("Permian Ridge"),
    ).json()

    duplicate_add_response = client.post(
        f"/api/projects/{project_id}/sites",
        json=_site_payload("West Texas Pivot"),
    )
    assert duplicate_add_response.status_code == 400
    assert duplicate_add_response.json()["detail"] == "Site names must be unique within a project"

    update_site_response = client.patch(
        f"/api/projects/{project_id}/sites/{second_site['id']}",
        json={"name": "South Plains Storage"},
    )
    assert update_site_response.status_code == 200
    assert update_site_response.json()["name"] == "South Plains Storage"

    duplicate_update_response = client.patch(
        f"/api/projects/{project_id}/sites/{second_site['id']}",
        json={"name": first_site["name"]},
    )
    assert duplicate_update_response.status_code == 400
    assert duplicate_update_response.json()["detail"] == "Site names must be unique within a project"

    delete_site_response = client.delete(f"/api/projects/{project_id}/sites/{first_site['id']}")
    assert delete_site_response.status_code == 204

    delete_project_response = client.delete(f"/api/projects/{project_id}")
    assert delete_project_response.status_code == 204
