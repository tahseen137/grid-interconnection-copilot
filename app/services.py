from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models import AnalysisRun, AnalysisSiteResult, Project, Site
from app.reporting import compare_sites, generate_investment_memo
from app.schemas import (
    ComparisonRequest,
    ComparisonResponse,
    InvestmentMemoRequest,
    InvestmentMemoResponse,
    ProjectCreate,
    ProjectUpdate,
    SiteCreate,
    SiteInput,
    SiteUpdate,
)
from app.scoring import assess_site


def _projects_query() -> Select[tuple[Project]]:
    return (
        select(Project)
        .options(
            selectinload(Project.sites),
            selectinload(Project.analysis_runs).selectinload(AnalysisRun.results),
        )
        .order_by(Project.updated_at.desc())
    )


def list_projects(session: Session) -> list[Project]:
    return list(session.scalars(_projects_query()))


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project = Project(**payload.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def get_project(session: Session, project_id: str) -> Project | None:
    return session.scalars(_projects_query().where(Project.id == project_id)).first()


def update_project(session: Session, project: Project, payload: ProjectUpdate) -> Project:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project: Project) -> None:
    session.delete(project)
    session.commit()


def list_project_sites(project: Project) -> list[Site]:
    return sorted(project.sites, key=lambda site: site.created_at)


def _normalized_site_name(name: str) -> str:
    return name.strip().casefold()


def _ensure_unique_site_name(project: Project, name: str, exclude_site_id: str | None = None) -> None:
    candidate = _normalized_site_name(name)
    for existing_site in project.sites:
        if exclude_site_id and existing_site.id == exclude_site_id:
            continue
        if _normalized_site_name(existing_site.name) == candidate:
            raise ValueError("Site names must be unique within a project")


def add_site_to_project(session: Session, project: Project, payload: SiteCreate) -> Site:
    _ensure_unique_site_name(project, payload.name)
    site = Site(**payload.model_dump())
    project.sites.append(site)
    session.add(site)
    session.commit()
    session.refresh(site)
    return site


def add_sites_to_project(session: Session, project: Project, payloads: list[SiteCreate]) -> list[Site]:
    seen_names = {_normalized_site_name(site.name) for site in project.sites}
    for payload in payloads:
        normalized_name = _normalized_site_name(payload.name)
        if normalized_name in seen_names:
            raise ValueError("Site names must be unique within a project")
        seen_names.add(normalized_name)

    created_sites: list[Site] = []
    for payload in payloads:
        site = Site(**payload.model_dump())
        project.sites.append(site)
        session.add(site)
        created_sites.append(site)

    session.commit()
    for site in created_sites:
        session.refresh(site)
    return created_sites


def get_site(project: Project, site_id: str) -> Site | None:
    return next((site for site in project.sites if site.id == site_id), None)


def update_site(session: Session, site: Site, payload: SiteUpdate) -> Site:
    if payload.name is not None:
        _ensure_unique_site_name(site.project, payload.name, exclude_site_id=site.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, key, value)
    session.add(site)
    session.commit()
    session.refresh(site)
    return site


def delete_site(session: Session, site: Site) -> None:
    session.delete(site)
    session.commit()


def _site_to_input(site: Site) -> SiteInput:
    return SiteInput(
        name=site.name,
        region=site.region,  # type: ignore[arg-type]
        state=site.state,
        technology=site.technology,  # type: ignore[arg-type]
        acreage=site.acreage,
        distance_to_substation_km=site.distance_to_substation_km,
        queue_wait_months=site.queue_wait_months,
        estimated_upgrade_cost_musd=site.estimated_upgrade_cost_musd,
        transmission_voltage_kv=site.transmission_voltage_kv,
        environmental_sensitivity=site.environmental_sensitivity,
        community_support=site.community_support,
        permitting_complexity=site.permitting_complexity,  # type: ignore[arg-type]
        site_control=site.site_control,  # type: ignore[arg-type]
        land_use_conflict=site.land_use_conflict,  # type: ignore[arg-type]
    )


@dataclass
class AnalysisArtifacts:
    comparison: ComparisonResponse
    memo: InvestmentMemoResponse


def _build_analysis(project: Project) -> AnalysisArtifacts:
    inputs = [_site_to_input(site) for site in list_project_sites(project)]
    if not inputs:
        raise ValueError("At least one site is required before analysis can run.")

    memo = generate_investment_memo(
        InvestmentMemoRequest(
            project_name=project.name,
            target_cod_year=project.target_cod_year,
            sites=inputs,
        )
    )

    if len(inputs) == 1:
        assessment = assess_site(inputs[0])
        comparison = ComparisonResponse(
            portfolio_name=project.name,
            top_pick=assessment.site_name,
            rankings=[
                {
                    **assessment.model_dump(),
                    "rank": 1,
                    "recommended_for_next_stage": True,
                }
            ],
            gating_risks=assessment.risk_flags[:5],
            portfolio_recommendation="Advance the sole candidate into deeper diligence if the risk flags fit your target returns.",
        )
    else:
        comparison = compare_sites(
            ComparisonRequest(
                portfolio_name=project.name,
                sites=inputs,
            )
        )

    return AnalysisArtifacts(comparison=comparison, memo=memo)


def run_project_analysis(session: Session, project: Project) -> AnalysisRun:
    artifacts = _build_analysis(project)
    site_lookup = {site.name: site for site in project.sites}

    analysis_run = AnalysisRun(
        project_id=project.id,
        top_pick_site_id=site_lookup[artifacts.memo.recommended_site].id if artifacts.memo.recommended_site in site_lookup else None,
        top_pick_site_name=artifacts.memo.recommended_site,
        executive_summary=artifacts.memo.executive_summary,
        memo_markdown=artifacts.memo.memo_markdown,
        gating_risks=artifacts.comparison.gating_risks,
        portfolio_recommendation=artifacts.comparison.portfolio_recommendation,
    )
    session.add(analysis_run)
    session.flush()

    for ranking in artifacts.comparison.rankings:
        site = site_lookup[ranking.site_name]
        result = AnalysisSiteResult(
            analysis_run_id=analysis_run.id,
            site_id=site.id,
            site_name=ranking.site_name,
            overall_score=ranking.overall_score,
            readiness_tier=ranking.readiness_tier,
            rank=ranking.rank,
            recommended_for_next_stage=ranking.recommended_for_next_stage,
            interconnection_score=ranking.score_breakdown.interconnection,
            permitting_score=ranking.score_breakdown.permitting,
            development_score=ranking.score_breakdown.development,
            community_score=ranking.score_breakdown.community,
            risk_flags=ranking.risk_flags,
            strengths=ranking.strengths,
            next_actions=ranking.next_actions,
        )
        session.add(result)

    session.commit()
    session.refresh(analysis_run)
    return analysis_run


def latest_analysis(project: Project) -> AnalysisRun | None:
    return project.analysis_runs[0] if project.analysis_runs else None
