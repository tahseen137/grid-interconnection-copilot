from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def _timestamp() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_timestamp)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_timestamp, onupdate=_timestamp)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_role", "role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="analyst", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    activity_events: Mapped[list["ActivityEvent"]] = relationship(back_populates="actor")


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        Index("ix_activity_events_created_at", "created_at"),
        Index("ix_activity_events_actor_user_id", "actor_user_id"),
        Index("ix_activity_events_action", "action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_username: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_timestamp)

    actor: Mapped[User | None] = relationship(back_populates="activity_events")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    developer: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    technology_focus: Mapped[str] = mapped_column(String(32), default="solar_storage", nullable=False)
    target_cod_year: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    sites: Mapped[list["Site"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Site.created_at",
    )
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(AnalysisRun.created_at)",
    )


class Site(TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_sites_project_name"),
        Index("ix_sites_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    technology: Mapped[str] = mapped_column(String(32), nullable=False)
    acreage: Mapped[float] = mapped_column(Float, nullable=False)
    distance_to_substation_km: Mapped[float] = mapped_column(Float, nullable=False)
    queue_wait_months: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_upgrade_cost_musd: Mapped[float] = mapped_column(Float, nullable=False)
    transmission_voltage_kv: Mapped[int] = mapped_column(Integer, nullable=False)
    environmental_sensitivity: Mapped[int] = mapped_column(Integer, nullable=False)
    community_support: Mapped[int] = mapped_column(Integer, nullable=False)
    permitting_complexity: Mapped[str] = mapped_column(String(16), nullable=False)
    site_control: Mapped[str] = mapped_column(String(16), nullable=False)
    land_use_conflict: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[Project] = relationship(back_populates="sites")
    analysis_results: Mapped[list["AnalysisSiteResult"]] = relationship(back_populates="site")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_project_id", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    top_pick_site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    top_pick_site_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    memo_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    gating_risks: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    portfolio_recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_timestamp)

    project: Mapped[Project] = relationship(back_populates="analysis_runs")
    results: Mapped[list["AnalysisSiteResult"]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        order_by="AnalysisSiteResult.rank",
    )


class AnalysisSiteResult(Base):
    __tablename__ = "analysis_site_results"
    __table_args__ = (
        Index("ix_analysis_site_results_analysis_run_id", "analysis_run_id"),
        Index("ix_analysis_site_results_site_id", "site_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    site_name: Mapped[str] = mapped_column(String(100), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    readiness_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_for_next_stage: Mapped[bool] = mapped_column(nullable=False)
    interconnection_score: Mapped[float] = mapped_column(Float, nullable=False)
    permitting_score: Mapped[float] = mapped_column(Float, nullable=False)
    development_score: Mapped[float] = mapped_column(Float, nullable=False)
    community_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    next_actions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="results")
    site: Mapped[Site] = relationship(back_populates="analysis_results")
