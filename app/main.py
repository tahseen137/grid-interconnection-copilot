from fastapi import FastAPI

from app.schemas import RegionReferenceResponse, SiteAssessment, SiteInput
from app.scoring import REFERENCE_PROFILES, assess_site


app = FastAPI(
    title="Grid Interconnection & Energy Siting Copilot",
    version="0.1.0",
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/reference/regions", response_model=RegionReferenceResponse)
def list_region_reference() -> RegionReferenceResponse:
    return RegionReferenceResponse(regions=REFERENCE_PROFILES)


@app.post("/api/sites/score", response_model=SiteAssessment)
def score_site(payload: SiteInput) -> SiteAssessment:
    return assess_site(payload)
