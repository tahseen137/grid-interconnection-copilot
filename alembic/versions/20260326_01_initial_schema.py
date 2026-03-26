"""Initial schema.

Revision ID: 20260326_01
Revises:
Create Date: 2026-03-26 09:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("developer", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("technology_focus", sa.String(length=32), nullable=False),
        sa.Column("target_cod_year", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("technology", sa.String(length=32), nullable=False),
        sa.Column("acreage", sa.Float(), nullable=False),
        sa.Column("distance_to_substation_km", sa.Float(), nullable=False),
        sa.Column("queue_wait_months", sa.Integer(), nullable=False),
        sa.Column("estimated_upgrade_cost_musd", sa.Float(), nullable=False),
        sa.Column("transmission_voltage_kv", sa.Integer(), nullable=False),
        sa.Column("environmental_sensitivity", sa.Integer(), nullable=False),
        sa.Column("community_support", sa.Integer(), nullable=False),
        sa.Column("permitting_complexity", sa.String(length=16), nullable=False),
        sa.Column("site_control", sa.String(length=16), nullable=False),
        sa.Column("land_use_conflict", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sites_project_id", "sites", ["project_id"], unique=False)
    op.create_index("uq_sites_project_name", "sites", ["project_id", "name"], unique=True)

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("top_pick_site_id", sa.String(length=36), nullable=True),
        sa.Column("top_pick_site_name", sa.String(length=100), nullable=True),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("memo_markdown", sa.Text(), nullable=False),
        sa.Column("gating_risks", sa.JSON(), nullable=False),
        sa.Column("portfolio_recommendation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["top_pick_site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"], unique=False)

    op.create_table(
        "analysis_site_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("site_name", sa.String(length=100), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("readiness_tier", sa.String(length=16), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("recommended_for_next_stage", sa.Boolean(), nullable=False),
        sa.Column("interconnection_score", sa.Float(), nullable=False),
        sa.Column("permitting_score", sa.Float(), nullable=False),
        sa.Column("development_score", sa.Float(), nullable=False),
        sa.Column("community_score", sa.Float(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("next_actions", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_site_results_analysis_run_id", "analysis_site_results", ["analysis_run_id"], unique=False)
    op.create_index("ix_analysis_site_results_site_id", "analysis_site_results", ["site_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analysis_site_results_site_id", table_name="analysis_site_results")
    op.drop_index("ix_analysis_site_results_analysis_run_id", table_name="analysis_site_results")
    op.drop_table("analysis_site_results")

    op.drop_index("ix_analysis_runs_project_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")

    op.drop_index("uq_sites_project_name", table_name="sites")
    op.drop_index("ix_sites_project_id", table_name="sites")
    op.drop_table("sites")

    op.drop_table("projects")
