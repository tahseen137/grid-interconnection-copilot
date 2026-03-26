from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_region_reference_endpoint_returns_profiles() -> None:
    response = client.get("/api/reference/regions")

    assert response.status_code == 200
    body = response.json()
    assert len(body["regions"]) >= 5
    assert any(region["region"] == "ERCOT" for region in body["regions"])


def test_score_site_endpoint_returns_assessment() -> None:
    response = client.post(
        "/api/sites/score",
        json={
            "name": "South Plains Storage",
            "region": "ERCOT",
            "state": "TX",
            "technology": "storage",
            "acreage": 92,
            "distance_to_substation_km": 1.6,
            "queue_wait_months": 10,
            "estimated_upgrade_cost_musd": 6.2,
            "transmission_voltage_kv": 138,
            "environmental_sensitivity": 12,
            "community_support": 82,
            "permitting_complexity": "low",
            "site_control": "optioned",
            "land_use_conflict": "low",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["site_name"] == "South Plains Storage"
    assert body["overall_score"] >= 60
    assert "score_breakdown" in body
    assert isinstance(body["risk_flags"], list)
