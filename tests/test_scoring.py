from app.schemas import SiteInput
from app.scoring import assess_site


def test_assess_site_scores_strong_site_higher_than_risky_site() -> None:
    strong_site = SiteInput(
        name="Prairie Solar One",
        region="ERCOT",
        state="TX",
        technology="solar_storage",
        acreage=560,
        distance_to_substation_km=2.4,
        queue_wait_months=12,
        estimated_upgrade_cost_musd=8.0,
        transmission_voltage_kv=138,
        environmental_sensitivity=18,
        community_support=78,
        permitting_complexity="low",
        site_control="secured",
        land_use_conflict="low",
    )
    risky_site = SiteInput(
        name="Wetland Ridge",
        region="PJM",
        state="PA",
        technology="solar",
        acreage=300,
        distance_to_substation_km=11.0,
        queue_wait_months=61,
        estimated_upgrade_cost_musd=38.0,
        transmission_voltage_kv=69,
        environmental_sensitivity=74,
        community_support=34,
        permitting_complexity="high",
        site_control="none",
        land_use_conflict="high",
    )

    strong_result = assess_site(strong_site)
    risky_result = assess_site(risky_site)

    assert strong_result.overall_score > risky_result.overall_score
    assert strong_result.readiness_tier == "strong"
    assert risky_result.readiness_tier == "high_risk"

