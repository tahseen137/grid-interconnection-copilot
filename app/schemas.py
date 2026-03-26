from typing import Literal

from pydantic import BaseModel, Field


TechnologyType = Literal["solar", "storage", "solar_storage", "wind"]
PermittingComplexity = Literal["low", "medium", "high"]
SiteControlStatus = Literal["none", "optioned", "secured"]
LandUseConflict = Literal["low", "medium", "high"]
ReadinessTier = Literal["strong", "watchlist", "high_risk"]


class RegionReference(BaseModel):
    region: str
    typical_queue_months: int
    typical_upgrade_cost_musd: float
    permitting_friction: int = Field(..., ge=0, le=100)


class RegionReferenceResponse(BaseModel):
    regions: list[RegionReference]


class SiteInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    region: Literal["PJM", "MISO", "ERCOT", "CAISO", "SPP"]
    state: str = Field(..., min_length=2, max_length=2)
    technology: TechnologyType
    acreage: float = Field(..., gt=0)
    distance_to_substation_km: float = Field(..., ge=0)
    queue_wait_months: int = Field(..., ge=0)
    estimated_upgrade_cost_musd: float = Field(..., ge=0)
    transmission_voltage_kv: int = Field(..., ge=0)
    environmental_sensitivity: int = Field(..., ge=0, le=100)
    community_support: int = Field(..., ge=0, le=100)
    permitting_complexity: PermittingComplexity
    site_control: SiteControlStatus
    land_use_conflict: LandUseConflict


class ScoreBreakdown(BaseModel):
    interconnection: float
    permitting: float
    development: float
    community: float


class SiteAssessment(BaseModel):
    site_name: str
    overall_score: float
    readiness_tier: ReadinessTier
    score_breakdown: ScoreBreakdown
    risk_flags: list[str]
    strengths: list[str]
    next_actions: list[str]

