"""Add activity events and admin operations support.

Revision ID: 20260326_03
Revises: 20260326_02
Create Date: 2026-03-26 15:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_03"
down_revision = "20260326_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_username", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_events_action", "activity_events", ["action"], unique=False)
    op.create_index("ix_activity_events_actor_user_id", "activity_events", ["actor_user_id"], unique=False)
    op.create_index("ix_activity_events_created_at", "activity_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_activity_events_created_at", table_name="activity_events")
    op.drop_index("ix_activity_events_actor_user_id", table_name="activity_events")
    op.drop_index("ix_activity_events_action", table_name="activity_events")
    op.drop_table("activity_events")
