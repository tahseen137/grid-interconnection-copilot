from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Generator
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.auth import (
    auth_required,
    clear_session,
    csrf_token_matches,
    current_session_user_id,
    ensure_csrf_token,
    is_authenticated,
    login_redirect,
    refresh_session_from_user,
    sanitize_next_path,
    set_authenticated_user_session,
)
from app.activity_service import list_activity_events, record_activity
from app.config import Settings, get_settings
from app.db import DatabaseState, build_database_state, database_is_ready, init_database
from app.models import Project, Site, User
from app.portfolio_io import analysis_results_csv, build_project_export, parse_sites_csv, site_template_csv
from app.reporting import compare_sites, generate_investment_memo
from app.schemas import (
    AnalysisRunRead,
    ActivityEventRead,
    ComparisonRequest,
    ComparisonResponse,
    CurrentUserResponse,
    InvestmentMemoRequest,
    InvestmentMemoResponse,
    PermissionSummary,
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    RegionReferenceResponse,
    SessionLoginRequest,
    SessionStatusResponse,
    SiteAssessment,
    SiteBulkImportRequest,
    SiteBulkImportResponse,
    SiteCreate,
    SiteInput,
    SiteRead,
    SiteUpdate,
    UserCreateRequest,
    UserRead,
    UserUpdateRequest,
)
from app.scoring import REFERENCE_PROFILES, assess_site
from app.services import (
    add_site_to_project,
    add_sites_to_project,
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
from app.user_service import (
    authenticate_user,
    can_manage_users,
    can_write,
    create_user as create_workspace_user,
    ensure_bootstrap_admin,
    get_user_by_id,
    has_users,
    list_users as list_workspace_users,
    update_user as update_workspace_user,
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


def _current_user_response(user: User | None) -> CurrentUserResponse | None:
    if user is None:
        return None
    return CurrentUserResponse.model_validate(user)


def _permission_summary(request: Request, user: User | None) -> PermissionSummary:
    if not auth_required(request):
        return PermissionSummary(can_write=True, can_manage_users=True)
    return PermissionSummary(
        can_write=can_write(user),
        can_manage_users=can_manage_users(user),
    )


def _session_status(request: Request, user: User | None, next_path: str | None = "/") -> SessionStatusResponse:
    authenticated = is_authenticated(request, user)
    csrf_token = ensure_csrf_token(request) if auth_required(request) and authenticated else None
    return SessionStatusResponse(
        auth_required=auth_required(request),
        authenticated=authenticated,
        next_path=next_path,
        csrf_token=csrf_token,
        current_user=_current_user_response(user),
        permissions=_permission_summary(request, user),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    database_state = build_database_state(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_database(database_state, auto_create_schema=resolved_settings.auto_create_schema)
        app.state.settings = resolved_settings
        app.state.database = database_state

        with database_state.session_factory() as session:
            ensure_bootstrap_admin(session, resolved_settings)
            if has_users(session) and not resolved_settings.session_secret:
                raise RuntimeError("session_secret is required when database-backed users exist")
            app.state.auth_required = has_users(session)

        yield
        database_state.engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.3.0",
        lifespan=lifespan,
    )

    if resolved_settings.enable_gzip:
        app.add_middleware(GZipMiddleware, minimum_size=500)
    if resolved_settings.session_secret:
        app.add_middleware(
            SessionMiddleware,
            secret_key=resolved_settings.session_secret,
            session_cookie="gridcopilot_session",
            same_site="lax",
            https_only=resolved_settings.session_https_only,
            max_age=resolved_settings.session_max_age_seconds,
        )
    if resolved_settings.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=resolved_settings.allowed_hosts)
    if resolved_settings.enforce_https:
        app.add_middleware(HTTPSRedirectMiddleware)

    @app.middleware("http")
    async def add_response_headers(request: Request, call_next):
        request_id = uuid4().hex
        started_at = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - started_at) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
        if request.url.path in {"/", "/login"}:
            response.headers["Cache-Control"] = "no-store"

        return response

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    def get_database_state(request: Request) -> DatabaseState:
        return request.app.state.database  # type: ignore[return-value]

    def get_session(database: DatabaseState = Depends(get_database_state)) -> Generator[Session, None, None]:
        session = database.session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_current_user(
        request: Request,
        session: Session = Depends(get_session),
    ) -> User | None:
        if not auth_required(request):
            return None

        user_id = current_session_user_id(request)
        if not user_id:
            return None

        user = get_user_by_id(session, user_id)
        if user is None or not user.is_active:
            clear_session(request)
            return None

        refresh_session_from_user(request, user)
        return user

    def require_api_access(
        request: Request,
        current_user: User | None = Depends(get_current_user),
    ) -> User | None:
        if not auth_required(request):
            return None
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        return current_user

    def require_write_access(
        request: Request,
        current_user: User | None = Depends(get_current_user),
    ) -> User | None:
        user = require_api_access(request, current_user)
        if user is not None and not can_write(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write access requires analyst or admin role")
        return user

    def require_admin_access(
        request: Request,
        current_user: User | None = Depends(get_current_user),
    ) -> User | None:
        user = require_api_access(request, current_user)
        if user is not None and not can_manage_users(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
        return user

    def require_csrf_protection(
        request: Request,
        current_user: User | None = Depends(get_current_user),
    ) -> None:
        if not auth_required(request) or current_user is None:
            return
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token_matches(request, csrf_token):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")

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

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, current_user: User | None = Depends(get_current_user)) -> Response:
        if not auth_required(request):
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        if is_authenticated(request, current_user):
            next_path = sanitize_next_path(request.query_params.get("next"))
            return RedirectResponse(url=next_path, status_code=status.HTTP_303_SEE_OTHER)

        template = templates.get_template("login.html")
        return HTMLResponse(
            template.render(
                request=request,
                next_path=sanitize_next_path(request.query_params.get("next")),
            )
        )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, current_user: User | None = Depends(get_current_user)) -> Response:
        if auth_required(request) and not is_authenticated(request, current_user):
            return RedirectResponse(url=login_redirect("/"), status_code=status.HTTP_303_SEE_OTHER)
        template = templates.get_template("index.html")
        return HTMLResponse(
            template.render(
                request=request,
                auth_required=auth_required(request),
                current_user=_current_user_response(current_user),
                permissions=_permission_summary(request, current_user),
                csrf_token=ensure_csrf_token(request) if is_authenticated(request, current_user) else "",
            )
        )

    @app.get("/api/session", response_model=SessionStatusResponse)
    def session_status(request: Request, current_user: User | None = Depends(get_current_user)) -> SessionStatusResponse:
        return _session_status(request, current_user, "/")

    @app.post("/api/session/login", response_model=SessionStatusResponse)
    def login_session(
        payload: SessionLoginRequest,
        request: Request,
        session: Session = Depends(get_session),
    ) -> SessionStatusResponse:
        next_path = sanitize_next_path(payload.next_path)
        if not auth_required(request):
            return _session_status(request, None, next_path)

        result = authenticate_user(session, payload.username, payload.password, request.app.state.settings)
        if result.user is None:
            clear_session(request)
            record_activity(
                session,
                action="auth.login_failed",
                entity_type="session",
                entity_id=None,
                actor_username=payload.username,
                description=f"Failed login attempt for {payload.username}.",
                details={"username": payload.username},
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result.error or "Invalid credentials")

        set_authenticated_user_session(request, result.user)
        record_activity(
            session,
            action="auth.login",
            entity_type="session",
            entity_id=result.user.id,
            actor_user=result.user,
            description=f"{result.user.username} signed in.",
        )
        return _session_status(request, result.user, next_path)

    @app.post(
        "/api/session/logout",
        response_model=SessionStatusResponse,
        dependencies=[Depends(require_api_access), Depends(require_csrf_protection)],
    )
    def logout_session(
        request: Request,
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_api_access),
    ) -> SessionStatusResponse:
        if current_user is not None:
            record_activity(
                session,
                action="auth.logout",
                entity_type="session",
                entity_id=current_user.id,
                actor_user=current_user,
                description=f"{current_user.username} signed out.",
            )
        clear_session(request)
        return SessionStatusResponse(
            auth_required=auth_required(request),
            authenticated=False,
            next_path="/login",
            csrf_token=None,
            current_user=None,
            permissions=PermissionSummary(can_write=False, can_manage_users=False),
        )

    @app.get("/api/activity", response_model=list[ActivityEventRead], dependencies=[Depends(require_api_access)])
    def list_activity_endpoint(session: Session = Depends(get_session)) -> list[ActivityEventRead]:
        return [ActivityEventRead.model_validate(event) for event in list_activity_events(session)]

    @app.get("/api/admin/users", response_model=list[UserRead], dependencies=[Depends(require_admin_access)])
    def list_users_endpoint(session: Session = Depends(get_session)) -> list[UserRead]:
        return [UserRead.model_validate(user) for user in list_workspace_users(session)]

    @app.post(
        "/api/admin/users",
        response_model=UserRead,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_admin_access), Depends(require_csrf_protection)],
    )
    def create_user_endpoint(
        payload: UserCreateRequest,
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_admin_access),
    ) -> UserRead:
        try:
            user = create_workspace_user(
                session,
                username=payload.username,
                password=payload.password,
                role=payload.role,
                full_name=payload.full_name,
                is_active=payload.is_active,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        record_activity(
            session,
            action="user.created",
            entity_type="user",
            entity_id=user.id,
            actor_user=current_user,
            description=f"{current_user.username if current_user else 'admin'} created user {user.username}.",
            details={"role": user.role, "is_active": user.is_active},
        )
        return UserRead.model_validate(user)

    @app.patch(
        "/api/admin/users/{user_id}",
        response_model=UserRead,
        dependencies=[Depends(require_admin_access), Depends(require_csrf_protection)],
    )
    def update_user_endpoint(
        user_id: str,
        payload: UserUpdateRequest,
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_admin_access),
    ) -> UserRead:
        user = get_user_by_id(session, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        try:
            updated = update_workspace_user(
                session,
                user,
                full_name=payload.full_name,
                role=payload.role,
                is_active=payload.is_active,
                password=payload.password,
                acting_user=current_user,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        record_activity(
            session,
            action="user.updated",
            entity_type="user",
            entity_id=updated.id,
            actor_user=current_user,
            description=f"{current_user.username if current_user else 'admin'} updated user {updated.username}.",
            details={
                "role": updated.role,
                "is_active": updated.is_active,
                "password_reset": payload.password is not None,
            },
        )
        return UserRead.model_validate(updated)

    @app.get("/api/reference/regions", response_model=RegionReferenceResponse, dependencies=[Depends(require_api_access)])
    def list_region_reference() -> RegionReferenceResponse:
        return RegionReferenceResponse(regions=REFERENCE_PROFILES)

    @app.get("/api/reference/site-template.csv", dependencies=[Depends(require_api_access)])
    def download_site_template() -> PlainTextResponse:
        return PlainTextResponse(
            content=site_template_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="site-intake-template.csv"'},
        )

    @app.get("/api/projects", response_model=list[ProjectSummary], dependencies=[Depends(require_api_access)])
    def list_saved_projects(session: Session = Depends(get_session)) -> list[ProjectSummary]:
        return [_project_summary(project) for project in list_projects(session)]

    @app.post(
        "/api/projects",
        response_model=ProjectRead,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def create_project_endpoint(
        payload: ProjectCreate,
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> ProjectRead:
        project = create_project(session, payload)
        project = get_project(session, project.id) or project
        record_activity(
            session,
            action="project.created",
            entity_type="project",
            entity_id=project.id,
            actor_user=current_user,
            project_id=project.id,
            description=f"{current_user.username if current_user else 'system'} created project {project.name}.",
            details={"status": project.status, "technology_focus": project.technology_focus},
        )
        return _project_read(project)

    @app.get("/api/projects/{project_id}", response_model=ProjectRead, dependencies=[Depends(require_api_access)])
    def get_project_endpoint(project: Project = Depends(require_project)) -> ProjectRead:
        return _project_read(project)

    @app.patch(
        "/api/projects/{project_id}",
        response_model=ProjectRead,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def update_project_endpoint(
        payload: ProjectUpdate,
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> ProjectRead:
        updated = update_project(session, project, payload)
        refreshed = get_project(session, updated.id) or updated
        record_activity(
            session,
            action="project.updated",
            entity_type="project",
            entity_id=updated.id,
            actor_user=current_user,
            project_id=updated.id,
            description=f"{current_user.username if current_user else 'system'} updated project {updated.name}.",
            details=payload.model_dump(exclude_unset=True),
        )
        return _project_read(refreshed)

    @app.delete(
        "/api/projects/{project_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def delete_project_endpoint(
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> Response:
        project_snapshot = {"project_id": project.id, "project_name": project.name}
        delete_project(session, project)
        record_activity(
            session,
            action="project.deleted",
            entity_type="project",
            entity_id=project_snapshot["project_id"],
            actor_user=current_user,
            project_id=project_snapshot["project_id"],
            description=f"{current_user.username if current_user else 'system'} deleted project {project_snapshot['project_name']}.",
            details=project_snapshot,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/projects/{project_id}/sites", response_model=list[SiteRead], dependencies=[Depends(require_api_access)])
    def list_sites_endpoint(project: Project = Depends(require_project)) -> list[SiteRead]:
        return [SiteRead.model_validate(site) for site in list_project_sites(project)]

    @app.post(
        "/api/projects/{project_id}/sites",
        response_model=SiteRead,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def add_site_endpoint(
        payload: SiteCreate,
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> SiteRead:
        try:
            site = add_site_to_project(session, project, payload)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        record_activity(
            session,
            action="site.created",
            entity_type="site",
            entity_id=site.id,
            actor_user=current_user,
            project_id=project.id,
            description=f"{current_user.username if current_user else 'system'} added site {site.name} to {project.name}.",
            details={"region": site.region, "state": site.state, "technology": site.technology},
        )
        return SiteRead.model_validate(site)

    @app.post(
        "/api/projects/{project_id}/sites/import-csv",
        response_model=SiteBulkImportResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def import_sites_endpoint(
        payload: SiteBulkImportRequest,
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> SiteBulkImportResponse:
        try:
            parsed_sites, errors, skipped_blank_rows = parse_sites_csv(payload.csv_content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": errors, "skipped_blank_rows": skipped_blank_rows},
            )
        if not parsed_sites:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid site rows were found in the CSV upload")

        try:
            created_sites = add_sites_to_project(session, project, parsed_sites)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        record_activity(
            session,
            action="site.bulk_imported",
            entity_type="project",
            entity_id=project.id,
            actor_user=current_user,
            project_id=project.id,
            description=f"{current_user.username if current_user else 'system'} imported {len(created_sites)} sites into {project.name}.",
            details={"created_count": len(created_sites), "skipped_blank_rows": skipped_blank_rows},
        )

        return SiteBulkImportResponse(
            created_count=len(created_sites),
            skipped_blank_rows=skipped_blank_rows,
            error_count=0,
            errors=[],
            sites=[SiteRead.model_validate(site) for site in created_sites],
        )

    @app.patch(
        "/api/projects/{project_id}/sites/{site_id}",
        response_model=SiteRead,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def update_site_endpoint(
        payload: SiteUpdate,
        site: Site = Depends(require_site),
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> SiteRead:
        try:
            updated = update_site(session, site, payload)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        record_activity(
            session,
            action="site.updated",
            entity_type="site",
            entity_id=updated.id,
            actor_user=current_user,
            project_id=updated.project_id,
            description=f"{current_user.username if current_user else 'system'} updated site {updated.name}.",
            details=payload.model_dump(exclude_unset=True),
        )
        return SiteRead.model_validate(updated)

    @app.delete(
        "/api/projects/{project_id}/sites/{site_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def delete_site_endpoint(
        site: Site = Depends(require_site),
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> Response:
        site_snapshot = {"site_id": site.id, "site_name": site.name, "project_id": site.project_id}
        delete_site(session, site)
        record_activity(
            session,
            action="site.deleted",
            entity_type="site",
            entity_id=site_snapshot["site_id"],
            actor_user=current_user,
            project_id=site_snapshot["project_id"],
            description=f"{current_user.username if current_user else 'system'} deleted site {site_snapshot['site_name']}.",
            details=site_snapshot,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/projects/{project_id}/analysis",
        response_model=AnalysisRunRead,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_write_access), Depends(require_csrf_protection)],
    )
    def run_analysis_endpoint(
        project: Project = Depends(require_project),
        session: Session = Depends(get_session),
        current_user: User | None = Depends(require_write_access),
    ) -> AnalysisRunRead:
        if not project.sites:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add at least one site before running analysis")
        analysis_run = run_project_analysis(session, project)
        refreshed = get_project(session, project.id)
        latest = latest_analysis(refreshed or project)
        recorded_run = latest or analysis_run
        if recorded_run is not None:
            record_activity(
                session,
                action="analysis.created",
                entity_type="analysis_run",
                entity_id=recorded_run.id,
                actor_user=current_user,
                project_id=project.id,
                description=f"{current_user.username if current_user else 'system'} ran analysis for {project.name}.",
                details={"top_pick_site_name": recorded_run.top_pick_site_name},
            )
        return AnalysisRunRead.model_validate(recorded_run)

    @app.get(
        "/api/projects/{project_id}/analysis/latest",
        response_model=AnalysisRunRead,
        dependencies=[Depends(require_api_access)],
    )
    def latest_analysis_endpoint(project: Project = Depends(require_project)) -> AnalysisRunRead:
        analysis_run = latest_analysis(project)
        if analysis_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis has been run yet")
        return AnalysisRunRead.model_validate(analysis_run)

    @app.get("/api/projects/{project_id}/export", dependencies=[Depends(require_api_access)])
    def export_project_endpoint(project: Project = Depends(require_project)) -> dict[str, object]:
        return build_project_export(project, _project_read(project))

    @app.get("/api/projects/{project_id}/analysis/latest.csv", dependencies=[Depends(require_api_access)])
    def export_latest_analysis_csv(project: Project = Depends(require_project)) -> PlainTextResponse:
        analysis_run = latest_analysis(project)
        if analysis_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis has been run yet")

        safe_slug = project.name.lower().replace(" ", "-")
        return PlainTextResponse(
            content=analysis_results_csv(analysis_run),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_slug}-rankings.csv"'},
        )

    @app.get("/api/projects/{project_id}/analysis/latest.md", dependencies=[Depends(require_api_access)])
    def export_latest_analysis_memo(project: Project = Depends(require_project)) -> PlainTextResponse:
        analysis_run = latest_analysis(project)
        if analysis_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis has been run yet")

        safe_slug = project.name.lower().replace(" ", "-")
        return PlainTextResponse(
            content=analysis_run.memo_markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_slug}-memo.md"'},
        )

    @app.post("/api/sites/score", response_model=SiteAssessment, dependencies=[Depends(require_api_access), Depends(require_csrf_protection)])
    def score_site(payload: SiteInput) -> SiteAssessment:
        return assess_site(payload)

    @app.post("/api/sites/compare", response_model=ComparisonResponse, dependencies=[Depends(require_api_access), Depends(require_csrf_protection)])
    def compare_site_options(payload: ComparisonRequest) -> ComparisonResponse:
        return compare_sites(payload)

    @app.post(
        "/api/reports/interconnection-memo",
        response_model=InvestmentMemoResponse,
        dependencies=[Depends(require_api_access), Depends(require_csrf_protection)],
    )
    def create_investment_memo(payload: InvestmentMemoRequest) -> InvestmentMemoResponse:
        return generate_investment_memo(payload)

    return app


app = create_app()
