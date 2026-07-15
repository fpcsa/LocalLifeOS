"""Add scheduling inputs and persisted preview snapshots.

Revision ID: 20260715_0007
Revises: 20260715_0006
Create Date: 2026-07-15 22:00:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0007"
down_revision: str | None = "20260715_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("earliest_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "preferred_time_of_day",
            sa.Enum(
                "ANY",
                "MORNING",
                "AFTERNOON",
                "EVENING",
                name="preferred_time_of_day",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
            server_default="ANY",
        ),
    )
    op.create_index(
        "ix_tasks_workspace_earliest_due",
        "tasks",
        ["workspace_id", "earliest_start_at", "due_at"],
    )

    op.create_table(
        "scheduling_previews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("commitment_id", sa.Uuid(), nullable=True),
        sa.Column("horizon_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("solver_status", sa.String(length=32), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(source_fingerprint) = 64",
            name="ck_scheduling_previews_fingerprint_length",
        ),
        sa.CheckConstraint(
            "horizon_end_at > horizon_start_at",
            name="ck_scheduling_previews_horizon",
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_scheduling_previews_revision_positive",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheduling_previews_workspace_id",
        "scheduling_previews",
        ["workspace_id"],
    )
    op.create_index(
        "ix_scheduling_previews_commitment_id",
        "scheduling_previews",
        ["commitment_id"],
    )
    op.create_index(
        "ix_scheduling_previews_workspace_created",
        "scheduling_previews",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduling_previews_workspace_created",
        table_name="scheduling_previews",
    )
    op.drop_index("ix_scheduling_previews_commitment_id", table_name="scheduling_previews")
    op.drop_index("ix_scheduling_previews_workspace_id", table_name="scheduling_previews")
    op.drop_table("scheduling_previews")
    op.drop_index("ix_tasks_workspace_earliest_due", table_name="tasks")
    op.drop_column("tasks", "preferred_time_of_day")
    op.drop_column("tasks", "earliest_start_at")
