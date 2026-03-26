from __future__ import annotations

import csv
from datetime import UTC, datetime
from io import StringIO

from pydantic import ValidationError

from app.models import AnalysisRun, Project
from app.schemas import ProjectRead, SiteCreate
from app.services import list_project_sites


SITE_IMPORT_COLUMNS = [
    "name",
    "region",
    "state",
    "technology",
    "acreage",
    "distance_to_substation_km",
    "queue_wait_months",
    "estimated_upgrade_cost_musd",
    "transmission_voltage_kv",
    "environmental_sensitivity",
    "community_support",
    "permitting_complexity",
    "site_control",
    "land_use_conflict",
    "notes",
]


def site_template_csv() -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=SITE_IMPORT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(
        {
            "name": "West Texas Pivot",
            "region": "ERCOT",
            "state": "TX",
            "technology": "solar_storage",
            "acreage": 560,
            "distance_to_substation_km": 2.2,
            "queue_wait_months": 14,
            "estimated_upgrade_cost_musd": 7.5,
            "transmission_voltage_kv": 138,
            "environmental_sensitivity": 16,
            "community_support": 84,
            "permitting_complexity": "low",
            "site_control": "secured",
            "land_use_conflict": "low",
            "notes": "Template example row",
        }
    )
    return buffer.getvalue()


def parse_sites_csv(csv_content: str) -> tuple[list[SiteCreate], list[str], int]:
    raw_lines = csv_content.strip().splitlines()
    if not raw_lines:
        raise ValueError("CSV file is missing a header row.")

    non_blank_lines = [raw_lines[0]]
    skipped_blank_rows = 0
    for line in raw_lines[1:]:
        if line.strip():
            non_blank_lines.append(line)
        else:
            skipped_blank_rows += 1

    buffer = StringIO("\n".join(non_blank_lines))
    reader = csv.DictReader(buffer)
    if reader.fieldnames is None:
        raise ValueError("CSV file is missing a header row.")

    missing_columns = [column for column in SITE_IMPORT_COLUMNS if column not in reader.fieldnames]
    if missing_columns:
        raise ValueError(f"CSV file is missing required columns: {', '.join(missing_columns)}")

    parsed_sites: list[SiteCreate] = []
    errors: list[str] = []

    for row_number, row in enumerate(reader, start=2):
        normalized = {
            key: (value.strip() if isinstance(value, str) else value)
            for key, value in row.items()
            if key is not None
        }

        if normalized.get("state"):
            normalized["state"] = normalized["state"].upper()

        try:
            parsed_sites.append(SiteCreate.model_validate(normalized))
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            errors.append(f"Row {row_number}: {details}")

    return parsed_sites, errors, skipped_blank_rows


def analysis_results_csv(analysis_run: AnalysisRun) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "rank",
            "site_name",
            "overall_score",
            "readiness_tier",
            "recommended_for_next_stage",
            "interconnection_score",
            "permitting_score",
            "development_score",
            "community_score",
            "top_risk_flag",
            "top_next_action",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for result in analysis_run.results:
        writer.writerow(
            {
                "rank": result.rank,
                "site_name": result.site_name,
                "overall_score": result.overall_score,
                "readiness_tier": result.readiness_tier,
                "recommended_for_next_stage": result.recommended_for_next_stage,
                "interconnection_score": result.interconnection_score,
                "permitting_score": result.permitting_score,
                "development_score": result.development_score,
                "community_score": result.community_score,
                "top_risk_flag": result.risk_flags[0] if result.risk_flags else "",
                "top_next_action": result.next_actions[0] if result.next_actions else "",
            }
        )
    return buffer.getvalue()


def build_project_export(project: Project, project_read: ProjectRead) -> dict[str, object]:
    latest_run = project.analysis_runs[0] if project.analysis_runs else None
    return {
        "export_version": "2026-03-26",
        "exported_at": datetime.now(UTC).isoformat(),
        "project": project_read.model_dump(mode="json"),
        "site_count": len(list_project_sites(project)),
        "analysis_run_count": len(project.analysis_runs),
        "latest_analysis_id": latest_run.id if latest_run else None,
    }
