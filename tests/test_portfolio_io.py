import pytest

from app.portfolio_io import analysis_results_csv, parse_sites_csv, site_template_csv
from app.schemas import ProjectCreate, SiteCreate
from app.services import add_site_to_project, create_project, get_project, run_project_analysis


def test_parse_sites_csv_parses_rows_and_skips_blank_lines() -> None:
    csv_content = """name,region,state,technology,acreage,distance_to_substation_km,queue_wait_months,estimated_upgrade_cost_musd,transmission_voltage_kv,environmental_sensitivity,community_support,permitting_complexity,site_control,land_use_conflict,notes
West Texas Pivot,ERCOT,tx,solar_storage,560,2.2,14,7.5,138,16,84,low,secured,low,Template row

Central Illinois Buildout,MISO,IL,solar,470,5.8,32,18,115,28,69,medium,optioned,medium,Second row
"""

    sites, errors, skipped_blank_rows = parse_sites_csv(csv_content)

    assert not errors
    assert skipped_blank_rows == 1
    assert len(sites) == 2
    assert sites[0].state == "TX"


def test_parse_sites_csv_reports_row_errors() -> None:
    csv_content = """name,region,state,technology,acreage,distance_to_substation_km,queue_wait_months,estimated_upgrade_cost_musd,transmission_voltage_kv,environmental_sensitivity,community_support,permitting_complexity,site_control,land_use_conflict,notes
Broken Site,ERCOT,TX,solar,-1,2.2,14,7.5,138,16,84,low,secured,low,Bad acreage
"""

    sites, errors, skipped_blank_rows = parse_sites_csv(csv_content)

    assert not sites
    assert skipped_blank_rows == 0
    assert len(errors) == 1
    assert "acreage" in errors[0]


def test_parse_sites_csv_requires_header_row() -> None:
    with pytest.raises(ValueError, match="header row"):
        parse_sites_csv("   ")


def test_parse_sites_csv_requires_expected_columns() -> None:
    with pytest.raises(ValueError, match="required columns"):
        parse_sites_csv("name,region\nWest Texas Pivot,ERCOT")


def test_site_template_and_analysis_export(session) -> None:
    project = create_project(
        session,
        ProjectCreate(
            name="Export Ready Portfolio",
            developer="GridWorks",
            status="screening",
            technology_focus="solar_storage",
            target_cod_year=2030,
            notes="",
        ),
    )
    loaded_project = get_project(session, project.id)
    assert loaded_project is not None

    add_site_to_project(
        session,
        loaded_project,
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
        loaded_project,
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

    refreshed_project = get_project(session, project.id)
    assert refreshed_project is not None
    analysis_run = run_project_analysis(session, refreshed_project)

    template = site_template_csv()
    csv_output = analysis_results_csv(analysis_run)

    assert "name,region,state,technology" in template
    assert "site_name,overall_score" in csv_output
    assert "Alpha Basin" in csv_output
