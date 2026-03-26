from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _site_payload(name: str, region: str, wait_months: int, upgrade_cost: float) -> dict[str, object]:
    return {
        "name": name,
        "region": region,
        "state": "TX" if region == "ERCOT" else "IL",
        "technology": "solar_storage",
        "acreage": 550,
        "distance_to_substation_km": 3.0,
        "queue_wait_months": wait_months,
        "estimated_upgrade_cost_musd": upgrade_cost,
        "transmission_voltage_kv": 138,
        "environmental_sensitivity": 20,
        "community_support": 76,
        "permitting_complexity": "low" if region == "ERCOT" else "medium",
        "site_control": "secured",
        "land_use_conflict": "low",
    }


def test_compare_endpoint_ranks_sites_and_marks_top_pick() -> None:
    response = client.post(
        "/api/sites/compare",
        json={
            "portfolio_name": "Southwest Solar Pipeline",
            "sites": [
                _site_payload("Alpha Site", "ERCOT", 12, 7.0),
                _site_payload("Beta Site", "PJM", 48, 24.0),
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["top_pick"] == "Alpha Site"
    assert body["rankings"][0]["recommended_for_next_stage"] is True
    assert body["rankings"][1]["rank"] == 2


def test_memo_endpoint_returns_markdown_and_priorities() -> None:
    response = client.post(
        "/api/reports/interconnection-memo",
        json={
            "project_name": "High Plains Portfolio",
            "target_cod_year": 2029,
            "sites": [
                _site_payload("Delta Site", "ERCOT", 11, 6.5),
                _site_payload("Gamma Site", "MISO", 31, 17.5),
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_site"] == "Delta Site"
    assert "Interconnection Readiness Memo" in body["memo_markdown"]
    assert len(body["diligence_priorities"]) >= 1
