from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={
            "name": "Bulk Intake Portfolio",
            "developer": "Prairie Grid Partners",
            "status": "screening",
            "technology_focus": "solar_storage",
            "target_cod_year": 2029,
            "notes": "Bulk import workflow validation.",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_bulk_csv_import_and_exports(client: TestClient) -> None:
    project_id = _create_project(client)

    template_response = client.get("/api/reference/site-template.csv")
    assert template_response.status_code == 200
    assert "name,region,state,technology" in template_response.text

    import_response = client.post(
        f"/api/projects/{project_id}/sites/import-csv",
        json={
            "csv_content": """name,region,state,technology,acreage,distance_to_substation_km,queue_wait_months,estimated_upgrade_cost_musd,transmission_voltage_kv,environmental_sensitivity,community_support,permitting_complexity,site_control,land_use_conflict,notes
West Texas Pivot,ERCOT,TX,solar_storage,560,2.2,14,7.5,138,16,84,low,secured,low,Fast first-pass screen
Central Illinois Buildout,MISO,IL,solar,470,5.8,32,18,115,28,69,medium,optioned,medium,Useful backup site
"""
        },
    )
    assert import_response.status_code == 201
    assert import_response.json()["created_count"] == 2

    duplicate_import_response = client.post(
        f"/api/projects/{project_id}/sites/import-csv",
        json={
            "csv_content": """name,region,state,technology,acreage,distance_to_substation_km,queue_wait_months,estimated_upgrade_cost_musd,transmission_voltage_kv,environmental_sensitivity,community_support,permitting_complexity,site_control,land_use_conflict,notes
West Texas Pivot,ERCOT,TX,solar_storage,560,2.2,14,7.5,138,16,84,low,secured,low,Duplicate row
"""
        },
    )
    assert duplicate_import_response.status_code == 400
    assert duplicate_import_response.json()["detail"] == "Site names must be unique within a project"

    analysis_response = client.post(f"/api/projects/{project_id}/analysis")
    assert analysis_response.status_code == 201

    export_response = client.get(f"/api/projects/{project_id}/export")
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["site_count"] == 2
    assert export_payload["project"]["name"] == "Bulk Intake Portfolio"

    rankings_response = client.get(f"/api/projects/{project_id}/analysis/latest.csv")
    assert rankings_response.status_code == 200
    assert "site_name,overall_score" in rankings_response.text

    memo_response = client.get(f"/api/projects/{project_id}/analysis/latest.md")
    assert memo_response.status_code == 200
    assert "Bulk Intake Portfolio" in memo_response.text


def test_bulk_import_reports_invalid_rows(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/sites/import-csv",
        json={
            "csv_content": """name,region,state,technology,acreage,distance_to_substation_km,queue_wait_months,estimated_upgrade_cost_musd,transmission_voltage_kv,environmental_sensitivity,community_support,permitting_complexity,site_control,land_use_conflict,notes
Broken Site,ERCOT,TX,solar,-1,2.2,14,7.5,138,16,84,low,secured,low,Bad acreage
"""
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["skipped_blank_rows"] == 0
    assert "acreage" in detail["errors"][0]
