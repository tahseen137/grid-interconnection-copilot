from app.schemas import ProjectCreate, SiteCreate
from app.services import create_project, get_project, run_project_analysis


def test_run_project_analysis_persists_ranked_results(session) -> None:
    project = create_project(
        session,
        ProjectCreate(
            name="Service Layer Portfolio",
            developer="GridWorks",
            status="screening",
            technology_focus="solar_storage",
            target_cod_year=2030,
            notes="",
        ),
    )
    session.refresh(project)
    project = get_project(session, project.id)
    assert project is not None

    from app.services import add_site_to_project

    add_site_to_project(
        session,
        project,
        SiteCreate(
            name="Alpha Basin",
            region="ERCOT",
            state="TX",
            technology="solar_storage",
            acreage=555,
            distance_to_substation_km=2.1,
            queue_wait_months=11,
            estimated_upgrade_cost_musd=7.2,
            transmission_voltage_kv=138,
            environmental_sensitivity=16,
            community_support=82,
            permitting_complexity="low",
            site_control="secured",
            land_use_conflict="low",
            notes="",
        ),
    )
    add_site_to_project(
        session,
        project,
        SiteCreate(
            name="Brush Country",
            region="PJM",
            state="PA",
            technology="solar",
            acreage=430,
            distance_to_substation_km=7.4,
            queue_wait_months=49,
            estimated_upgrade_cost_musd=27.0,
            transmission_voltage_kv=115,
            environmental_sensitivity=48,
            community_support=61,
            permitting_complexity="medium",
            site_control="optioned",
            land_use_conflict="medium",
            notes="",
        ),
    )

    refreshed = get_project(session, project.id)
    assert refreshed is not None
    analysis_run = run_project_analysis(session, refreshed)

    assert analysis_run.top_pick_site_name is not None
    assert len(analysis_run.results) == 2
    assert analysis_run.results[0].rank == 1
