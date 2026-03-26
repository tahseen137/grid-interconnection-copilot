from __future__ import annotations

from app.schemas import RegionReference, ScoreBreakdown, SiteAssessment, SiteInput


REFERENCE_PROFILES = [
    RegionReference(
        region="PJM",
        typical_queue_months=44,
        typical_upgrade_cost_musd=28.0,
        permitting_friction=62,
    ),
    RegionReference(
        region="MISO",
        typical_queue_months=38,
        typical_upgrade_cost_musd=22.0,
        permitting_friction=57,
    ),
    RegionReference(
        region="ERCOT",
        typical_queue_months=18,
        typical_upgrade_cost_musd=11.0,
        permitting_friction=42,
    ),
    RegionReference(
        region="CAISO",
        typical_queue_months=40,
        typical_upgrade_cost_musd=31.0,
        permitting_friction=71,
    ),
    RegionReference(
        region="SPP",
        typical_queue_months=28,
        typical_upgrade_cost_musd=15.0,
        permitting_friction=49,
    ),
]

PERMITTING_MULTIPLIER = {"low": 1.0, "medium": 0.82, "high": 0.62}
SITE_CONTROL_BONUS = {"none": 0.45, "optioned": 0.72, "secured": 1.0}
LAND_USE_MULTIPLIER = {"low": 1.0, "medium": 0.78, "high": 0.55}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _region_profile(region: str) -> RegionReference:
    return next(profile for profile in REFERENCE_PROFILES if profile.region == region)


def _size_fit(site: SiteInput) -> float:
    target_acreage = {
        "solar": 450.0,
        "storage": 80.0,
        "solar_storage": 550.0,
        "wind": 900.0,
    }[site.technology]
    variance = abs(site.acreage - target_acreage) / target_acreage
    return clamp(100 - variance * 80)


def assess_site(site: SiteInput) -> SiteAssessment:
    profile = _region_profile(site.region)

    queue_score = clamp(100 - ((site.queue_wait_months / profile.typical_queue_months) - 0.5) * 55)
    upgrade_score = clamp(100 - ((site.estimated_upgrade_cost_musd / profile.typical_upgrade_cost_musd) - 0.5) * 60)
    substation_score = clamp(100 - site.distance_to_substation_km * 7.5)
    voltage_score = clamp(site.transmission_voltage_kv / 3)
    interconnection_score = round((queue_score * 0.32) + (upgrade_score * 0.3) + (substation_score * 0.23) + (voltage_score * 0.15), 1)

    permitting_base = clamp(100 - profile.permitting_friction)
    environmental_score = clamp(100 - site.environmental_sensitivity)
    permitting_score = round(
        (
            (permitting_base * 0.35)
            + (environmental_score * 0.35)
            + (site.community_support * 0.3)
        )
        * PERMITTING_MULTIPLIER[site.permitting_complexity]
        * LAND_USE_MULTIPLIER[site.land_use_conflict],
        1,
    )

    development_score = round(
        (_size_fit(site) * 0.45)
        + (SITE_CONTROL_BONUS[site.site_control] * 35)
        + (clamp(100 - site.distance_to_substation_km * 4.0) * 0.2),
        1,
    )

    community_score = round(
        (site.community_support * 0.55)
        + (environmental_score * 0.2)
        + (clamp(100 - profile.permitting_friction) * 0.25),
        1,
    )

    overall = round(
        (interconnection_score * 0.38)
        + (permitting_score * 0.24)
        + (development_score * 0.22)
        + (community_score * 0.16),
        1,
    )

    if overall >= 72:
        tier = "strong"
    elif overall >= 55:
        tier = "watchlist"
    else:
        tier = "high_risk"

    risk_flags: list[str] = []
    strengths: list[str] = []
    next_actions: list[str] = []

    if site.queue_wait_months > profile.typical_queue_months:
        risk_flags.append("Queue duration is worse than the current regional baseline.")
        next_actions.append("Validate queue position and model commercial operation date slippage.")
    else:
        strengths.append("Queue timing is better than the regional baseline.")

    if site.estimated_upgrade_cost_musd > profile.typical_upgrade_cost_musd:
        risk_flags.append("Estimated network upgrade costs are elevated for this region.")
        next_actions.append("Stress test returns under higher interconnection capex assumptions.")
    else:
        strengths.append("Upgrade cost profile looks manageable against regional norms.")

    if site.environmental_sensitivity >= 65:
        risk_flags.append("Environmental sensitivity is high and may slow permitting.")
        next_actions.append("Commission an early fatal-flaw environmental review.")
    else:
        strengths.append("Environmental constraints appear moderate enough for early-stage screening.")

    if site.community_support <= 45:
        risk_flags.append("Community support is weak and social license risk is meaningful.")
        next_actions.append("Start local stakeholder outreach before locking development spend.")
    else:
        strengths.append("Community posture supports a more credible development path.")

    if site.site_control == "none":
        risk_flags.append("Site control is not yet secured.")
        next_actions.append("Prioritize exclusivity or option agreements with landowners.")
    elif site.site_control == "secured":
        strengths.append("Site control is already secured, which improves execution readiness.")

    if site.distance_to_substation_km > 8:
        risk_flags.append("Long substation distance could increase interconnection complexity.")
        next_actions.append("Refine interconnection design assumptions with a targeted power flow screen.")

    if not next_actions:
        next_actions.append("Advance to utility outreach and deeper engineering diligence.")

    return SiteAssessment(
        site_name=site.name,
        overall_score=overall,
        readiness_tier=tier,
        score_breakdown=ScoreBreakdown(
            interconnection=interconnection_score,
            permitting=permitting_score,
            development=development_score,
            community=community_score,
        ),
        risk_flags=risk_flags,
        strengths=strengths,
        next_actions=next_actions,
    )
