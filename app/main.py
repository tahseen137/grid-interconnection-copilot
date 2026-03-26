from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import DatabaseState, build_database_state, database_is_ready, init_database
from app.models import Project, Site
from app.reporting import compare_sites, generate_investment_memo
from app.schemas import (
    AnalysisRunRead,
    ComparisonRequest,
    ComparisonResponse,
    InvestmentMemoRequest,
    InvestmentMemoResponse,
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    RegionReferenceResponse,
    SiteAssessment,
    SiteCreate,
    SiteInput,
    SiteRead,
    SiteUpdate,
)
from app.scoring import REFERENCE_PROFILES, assess_site
from app.services import (
    add_site_to_project,
    create_project,
    delete_project,
    delete_site,
    get_project,
    get_site,
    latest_analysis,
    list_project_sites,
    list_projects,
    run_project_analysis,
    update_project,
    update_site,
)


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _project_summary(project: Project) -> ProjectSummary:
    return ProjectSummary(
        id=project.id,
        name=project.name,
        developer=project.developer,
        status=project.status,
        technology_focus=project.technology_focus,
        target_cod_year=project.target_cod_year,
        created_at=project.created_at,
        updated_at=project.updated_at,
        site_count=len(project.sites),
        latest_analysis_at=latest_analysis(project).created_at if latest_analysis(project) else None,
    )


def _project_read(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        developer=project.developer,
        status=project.status,
        technology_focus=project.technology_focus,
        target_cod_year=project.target_cod_year,
        notes=project.notes,
        created_at=project.created_at,
        updated_at=project.updated_at,
        sites=[SiteRead.model_validate(site) for site in list_project_sites(project)],
        analysis_runs=[AnalysisRunRead.model_validate(run) for run in project.analysis_runs],
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    database_state = build_database_state(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_database(database_state)
        app.state.settings = resolved_settings
        app.state.database = database_state
        yield
        database_state.engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    def get_database_state(request: Request) -> DatabaseState:
        return request.app.state.database  # type: ignore[return-value]

    def get_session(database: DatabaseState = Depends(get_database_state)) -> Generator[Session, None, None]:
        session = database.session_factory()
        try:
            yield session
        finally:
            session.close()

    def require_project(project_id: str, session: Session = Depends(get_session)) -> Project:
        project = get_project(session, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def require_site(site_id: str, project: Project = Depends(require_project)) -> Site:
        site = get_site(project, site_id)
        if site is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        return site

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def readiness(database: DatabaseState = Depends(get_database_state)) -> dict[str, str]:
        if not database_is_ready(database):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
        return {"status": "ready"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        template = templates.get_template("index.html")
        return HTMLResponse(template.render(request=request))

    @app.get("/api/reference/regions", response_model=RegionReferenceResponse)
    def list_region_reference() -> RegionReferenceResponse:
        return RegionReferenceResponse(regions=REFERENCE_PROFILES)

    @app.get("/api/projects", response_model=list[ProjectSummary])
    def list_saved_projects(session: Session = Depends(get_session)) -> list[ProjectSummary]:
        return [_project_summary(project) for project in list_projects(session)]

    @app.post("/api/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
    def create_project_endpoint(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectRead:
        project = create_project(session, payload)
        project = get_project(session, project.id) or project
        return _project_read(project)

    @app.get("/api/projects/{project_id}", response_model=ProjectRead)
    def get_project_endpoint(project: Project = Depends(require_project)) -> ProjectRead:
        return _project_read(project)

    @app.patch("/api/projects/{project_id}", response_model=ProjectRead)
    def update_project_endpoint(
        payload: ProjectUpdate,
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
    ) -> ProjectRead:
        updated = update_project(session, project, payload)
        refreshed = get_project(session, updated.id) or updated
        return _project_read(refreshed)

    @app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_project_endpoint(
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
    ) -> Response:
        delete_project(session, project)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/projects/{project_id}/sites", response_model=list[SiteRead])
    def list_sites_endpoint(project: Project = Depends(require_project)) -> list[SiteRead]:
        return [SiteRead.model_validate(site) for site in list_project_sites(project)]

    @app.post("/api/projects/{project_id}/sites", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
    def add_site_endpoint(
        payload: SiteCreate,
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
    ) -> SiteRead:
        site = add_site_to_project(session, project, payload)
        return SiteRead.model_validate(site)

    @app.patch("/api/projects/{project_id}/sites/{site_id}", response_model=SiteRead)
    def update_site_endpoint(
        payload: SiteUpdate,
        site: Site = Depends(require_site),
        session: Session = Depends(get_session),
    ) -> SiteRead:
        updated = update_site(session, site, payload)
        return SiteRead.model_validate(updated)

    @app.delete("/api/projects/{project_id}/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_site_endpoint(
        site: Site = Depends(require_site),
        session: Session = Depends(get_session),
    ) -> Response:
        delete_site(session, site)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/projects/{project_id}/analysis", response_model=AnalysisRunRead, status_code=status.HTTP_201_CREATED)
    def run_analysis_endpoint(
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
    ) -> AnalysisRunRead:
        if not project.sites:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add at least one site before running analysis")
        analysis_run = run_project_analysis(session, project)
        refreshed = get_project(session, project.id)
        latest = latest_analysis(refreshed or project)
        return AnalysisRunRead.model_validate(latest or analysis_run)

    @app.get("/api/projects/{project_id}/analysis/latest", response_model=AnalysisRunRead)
    def latest_analysis_endpoint(project: Project = Depends(require_project)) -> AnalysisRunRead:
        analysis_run = latest_analysis(project)
        if analysis_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis has been run yet")
        return AnalysisRunRead.model_validate(analysis_run)

    @app.post("/api/sites/score", response_model=SiteAssessment)
    def score_site(payload: SiteInput) -> SiteAssessment:
        return assess_site(payload)

    @app.post("/api/sites/compare", response_model=ComparisonResponse)
    def compare_site_options(payload: ComparisonRequest) -> ComparisonResponse:
        return compare_sites(payload)

    @app.post("/api/reports/interconnection-memo", response_model=InvestmentMemoResponse)
    def create_investment_memo(payload: InvestmentMemoRequest) -> InvestmentMemoResponse:
        return generate_investment_memo(payload)

    return app


app = create_app()
