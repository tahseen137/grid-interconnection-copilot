from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TechnologyType = Literal["solar", "storage", "solar_storage", "wind"]
PermittingComplexity = Literal["low", "medium", "high"]
SiteControlStatus = Literal["none", "optioned", "secured"]
LandUseConflict = Literal["low", "medium", "high"]
ReadinessTier = Literal["strong", "watchlist", "high_risk"]
UserRole = Literal["admin", "analyst", "viewer"]


class RegionReference(BaseModel):
    region: str
    typical_queue_months: int
    typical_upgrade_cost_musd: float
    permitting_friction: int = Field(..., ge=0, le=100)


class RegionReferenceResponse(BaseModel):
    regions: list[RegionReference]


class SiteBase(BaseModel):
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
    notes: str = Field(default="", max_length=2000)


class SiteInput(SiteBase):
    notes: str = Field(default="", exclude=True)


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


class RankedAssessment(SiteAssessment):
    rank: int
    recommended_for_next_stage: bool


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    developer: str = Field(..., min_length=2, max_length=120)
    status: Literal["draft", "screening", "ready", "archived"] = "draft"
    technology_focus: TechnologyType = "solar_storage"
    target_cod_year: int = Field(..., ge=2026, le=2045)
    notes: str = Field(default="", max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    developer: str | None = Field(default=None, min_length=2, max_length=120)
    status: Literal["draft", "screening", "ready", "archived"] | None = None
    technology_focus: TechnologyType | None = None
    target_cod_year: int | None = Field(default=None, ge=2026, le=2045)
    notes: str | None = Field(default=None, max_length=4000)


class SiteCreate(SiteBase):
    pass


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    region: Literal["PJM", "MISO", "ERCOT", "CAISO", "SPP"] | None = None
    state: str | None = Field(default=None, min_length=2, max_length=2)
    technology: TechnologyType | None = None
    acreage: float | None = Field(default=None, gt=0)
    distance_to_substation_km: float | None = Field(default=None, ge=0)
    queue_wait_months: int | None = Field(default=None, ge=0)
    estimated_upgrade_cost_musd: float | None = Field(default=None, ge=0)
    transmission_voltage_kv: int | None = Field(default=None, ge=0)
    environmental_sensitivity: int | None = Field(default=None, ge=0, le=100)
    community_support: int | None = Field(default=None, ge=0, le=100)
    permitting_complexity: PermittingComplexity | None = None
    site_control: SiteControlStatus | None = None
    land_use_conflict: LandUseConflict | None = None
    notes: str | None = Field(default=None, max_length=2000)


class SiteRead(SiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime


class AnalysisSiteResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    site_name: str
    overall_score: float
    readiness_tier: str
    rank: int
    recommended_for_next_stage: bool
    interconnection_score: float
    permitting_score: float
    development_score: float
    community_score: float
    risk_flags: list[str]
    strengths: list[str]
    next_actions: list[str]


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    top_pick_site_id: str | None
    top_pick_site_name: str | None
    executive_summary: str
    memo_markdown: str
    gating_risks: list[str]
    portfolio_recommendation: str
    created_at: datetime
    results: list[AnalysisSiteResultRead]


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    developer: str
    status: str
    technology_focus: str
    target_cod_year: int
    created_at: datetime
    updated_at: datetime
    site_count: int
    latest_analysis_at: datetime | None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    developer: str
    status: str
    technology_focus: str
    target_cod_year: int
    notes: str
    created_at: datetime
    updated_at: datetime
    sites: list[SiteRead]
    analysis_runs: list[AnalysisRunRead]


class SessionLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(..., min_length=1, max_length=200)
    next_path: str = Field(default="/", max_length=500)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None


class UserRead(CurrentUserResponse):
    created_at: datetime
    updated_at: datetime
    failed_login_attempts: int
    locked_until: datetime | None


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str = Field(default="", max_length=120)
    role: UserRole = "analyst"
    password: str = Field(..., min_length=8, max_length=200)
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: UserRole | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)
    is_active: bool | None = None


class PermissionSummary(BaseModel):
    can_write: bool
    can_manage_users: bool


class SessionStatusResponse(BaseModel):
    auth_required: bool
    authenticated: bool
    next_path: str | None = None
    csrf_token: str | None = None
    current_user: CurrentUserResponse | None = None
    permissions: PermissionSummary = PermissionSummary(can_write=True, can_manage_users=False)


class SiteBulkImportRequest(BaseModel):
    csv_content: str = Field(..., min_length=1, max_length=500_000)


class SiteBulkImportResponse(BaseModel):
    created_count: int
    skipped_blank_rows: int
    error_count: int
    errors: list[str]
    sites: list[SiteRead]


class ActivityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str | None
    actor_username: str
    action: str
    entity_type: str
    entity_id: str | None
    project_id: str | None
    description: str
    details: dict[str, object]
    created_at: datetime


class ComparisonRequest(BaseModel):
    portfolio_name: str = Field(..., min_length=3, max_length=120)
    sites: list[SiteInput] = Field(..., min_length=1, max_length=10)


class ComparisonResponse(BaseModel):
    portfolio_name: str
    top_pick: str
    rankings: list[RankedAssessment]
    gating_risks: list[str]
    portfolio_recommendation: str


class InvestmentMemoRequest(BaseModel):
    project_name: str = Field(..., min_length=3, max_length=120)
    target_cod_year: int = Field(..., ge=2026, le=2040)
    sites: list[SiteInput] = Field(..., min_length=1, max_length=5)


class InvestmentMemoResponse(BaseModel):
    project_name: str
    recommended_site: str
    executive_summary: str
    diligence_priorities: list[str]
    memo_markdown: str

