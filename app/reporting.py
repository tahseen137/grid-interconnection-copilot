from __future__ import annotations

from app.schemas import (
    ComparisonRequest,
    ComparisonResponse,
    InvestmentMemoRequest,
    InvestmentMemoResponse,
    RankedAssessment,
)
from app.scoring import assess_site


def compare_sites(payload: ComparisonRequest) -> ComparisonResponse:
    assessments = [assess_site(site) for site in payload.sites]
    ordered = sorted(assessments, key=lambda item: item.overall_score, reverse=True)

    rankings = [
        RankedAssessment(
            **assessment.model_dump(),
            rank=index + 1,
            recommended_for_next_stage=index == 0,
        )
        for index, assessment in enumerate(ordered)
    ]

    gating_risks = []
    for assessment in ordered:
        gating_risks.extend(assessment.risk_flags[:2])

    top_pick = rankings[0].site_name
    recommendation = (
        f"Advance {top_pick} into deeper interconnection and permitting diligence first. "
        f"Hold the remaining {len(rankings) - 1} site(s) as backups until upgrade costs and schedule risk are refined."
    )

    return ComparisonResponse(
        portfolio_name=payload.portfolio_name,
        top_pick=top_pick,
        rankings=rankings,
        gating_risks=list(dict.fromkeys(gating_risks))[:5],
        portfolio_recommendation=recommendation,
    )


def generate_investment_memo(payload: InvestmentMemoRequest) -> InvestmentMemoResponse:
    comparison = compare_sites(
        ComparisonRequest(
            portfolio_name=payload.project_name,
            sites=payload.sites,
        )
    )
    winning_site = comparison.rankings[0]
    diligence_priorities = list(dict.fromkeys(winning_site.next_actions + comparison.gating_risks))[:6]
    risk_lines = [f"- {risk}" for risk in comparison.gating_risks]
    if not risk_lines:
        risk_lines = ["- No material gating risks were flagged in the first-pass screen."]

    memo_markdown = "\n".join(
        [
            f"# {payload.project_name} Interconnection Readiness Memo",
            "",
            f"## Recommended Site",
            f"- {winning_site.site_name}",
            f"- Score: {winning_site.overall_score}",
            f"- Tier: {winning_site.readiness_tier}",
            "",
            "## Why This Site Leads",
            *[f"- {strength}" for strength in winning_site.strengths[:4]],
            "",
            "## Key Risks To Resolve",
            *risk_lines,
            "",
            "## Diligence Priorities",
            *[f"- {item}" for item in diligence_priorities],
            "",
            f"## Target COD",
            f"- {payload.target_cod_year}",
        ]
    )

    summary = (
        f"{winning_site.site_name} is the strongest first-pass candidate for {payload.project_name} "
        f"because it offers the best combined interconnection, permitting, and development-readiness profile "
        f"for a {payload.target_cod_year} target COD."
    )

    return InvestmentMemoResponse(
        project_name=payload.project_name,
        recommended_site=winning_site.site_name,
        executive_summary=summary,
        diligence_priorities=diligence_priorities,
        memo_markdown=memo_markdown,
    )
