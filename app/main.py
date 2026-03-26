from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.reporting import compare_sites, generate_investment_memo
from app.schemas import (
    ComparisonRequest,
    ComparisonResponse,
    InvestmentMemoRequest,
    InvestmentMemoResponse,
    RegionReferenceResponse,
    SiteAssessment,
    SiteInput,
)
from app.scoring import REFERENCE_PROFILES, assess_site


app = FastAPI(
    title="Grid Interconnection & Energy Siting Copilot",
    version="0.1.0",
)
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    template = templates.get_template("index.html")
    return HTMLResponse(template.render(request=request))


@app.get("/api/reference/regions", response_model=RegionReferenceResponse)
def list_region_reference() -> RegionReferenceResponse:
    return RegionReferenceResponse(regions=REFERENCE_PROFILES)


@app.post("/api/sites/score", response_model=SiteAssessment)
def score_site(payload: SiteInput) -> SiteAssessment:
    return assess_site(payload)


@app.post("/api/sites/compare", response_model=ComparisonResponse)
def compare_site_options(payload: ComparisonRequest) -> ComparisonResponse:
    return compare_sites(payload)


@app.post("/api/reports/interconnection-memo", response_model=InvestmentMemoResponse)
def create_investment_memo(payload: InvestmentMemoRequest) -> InvestmentMemoResponse:
    return generate_investment_memo(payload)
