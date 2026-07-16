"""Add production productivity and calendar fields, links, and note search.

Revision ID: 20260715_0003
Revises: 20260715_0002
Create Date: 2026-07-15 16:00:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0003"
down_revision: str | None = "20260715_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DOMAIN_ENTITY_VALUES = (
    "WORKSPACE",
    "USER_PREFERENCES",
    "TAG",
    "ATTACHMENT",
    "PROJECT",
    "TASK",
    "NOTE",
    "CALENDAR_EVENT",
    "FINANCIAL_ACCOUNT",
    "TRANSACTION",
    "BUDGET",
    "SAVINGS_GOAL",
    "COMMITMENT",
    "GOAL",
    "AUTOMATION_RULE",
    "SCENARIO",
)


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def link_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("projects", sa.Column("target_start_date", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("target_end_date", sa.Date(), nullable=True))

    op.add_column("tasks", sa.Column("actual_duration_minutes", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("recurrence_rrule", sa.String(length=1000), nullable=True))

    op.add_column("notes", sa.Column("daily_note_date", sa.Date(), nullable=True))
    op.create_index(
        "ux_notes_workspace_daily_date_active",
        "notes",
        ["workspace_id", "daily_note_date"],
        unique=True,
        sqlite_where=sa.text("daily_note_date IS NOT NULL AND deleted_at IS NULL"),
    )

    op.add_column(
        "calendar_events",
        sa.Column("recurrence_rrule", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "calendar_events",
        sa.Column("category", sa.String(length=120), nullable=True),
    )
    for column_name in (
        "preparation_buffer_minutes",
        "travel_buffer_minutes",
        "recovery_buffer_minutes",
    ):
        op.add_column(
            "calendar_events",
            sa.Column(column_name, sa.Integer(), nullable=False, server_default="0"),
        )

    op.create_table(
        "note_entity_links",
        *link_columns(),
        sa.Column(
            "note_id",
            sa.Uuid(),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            enum_type("note_entity_type", *_DOMAIN_ENTITY_VALUES),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "note_id",
            "entity_type",
            "entity_id",
            name="uq_note_entity_link",
        ),
    )
    op.create_index("ix_note_entity_links_workspace_id", "note_entity_links", ["workspace_id"])
    op.create_index("ix_note_entity_links_note_id", "note_entity_links", ["note_id"])
    op.create_index("ix_note_entity_links_entity_id", "note_entity_links", ["entity_id"])

    op.create_table(
        "calendar_event_entity_links",
        *link_columns(),
        sa.Column(
            "calendar_event_id",
            sa.Uuid(),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            enum_type("calendar_link_entity_type", *_DOMAIN_ENTITY_VALUES),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "calendar_event_id",
            "entity_type",
            "entity_id",
            name="uq_calendar_event_entity_link",
        ),
    )
    op.create_index(
        "ix_calendar_event_entity_links_workspace_id",
        "calendar_event_entity_links",
        ["workspace_id"],
    )
    op.create_index(
        "ix_calendar_event_entity_links_calendar_event_id",
        "calendar_event_entity_links",
        ["calendar_event_id"],
    )
    op.create_index(
        "ix_calendar_event_entity_links_entity_id",
        "calendar_event_entity_links",
        ["entity_id"],
    )

    op.execute(
        "CREATE VIRTUAL TABLE notes_fts USING fts5("
        "note_id UNINDEXED, workspace_id UNINDEXED, title, markdown, "
        "tokenize='unicode61 remove_diacritics 2')"
    )
    op.execute(
        "INSERT INTO notes_fts(note_id, workspace_id, title, markdown) "
        "SELECT id, workspace_id, title, markdown FROM notes WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE TRIGGER notes_fts_after_insert AFTER INSERT ON notes "
        "WHEN new.deleted_at IS NULL BEGIN "
        "INSERT INTO notes_fts(note_id, workspace_id, title, markdown) "
        "VALUES (new.id, new.workspace_id, new.title, new.markdown); END"
    )
    op.execute(
        "CREATE TRIGGER notes_fts_after_update AFTER UPDATE ON notes BEGIN "
        "DELETE FROM notes_fts WHERE note_id = old.id; "
        "INSERT INTO notes_fts(note_id, workspace_id, title, markdown) "
        "SELECT new.id, new.workspace_id, new.title, new.markdown "
        "WHERE new.deleted_at IS NULL; END"
    )
    op.execute(
        "CREATE TRIGGER notes_fts_after_delete AFTER DELETE ON notes BEGIN "
        "DELETE FROM notes_fts WHERE note_id = old.id; END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS notes_fts_after_delete")
    op.execute("DROP TRIGGER IF EXISTS notes_fts_after_update")
    op.execute("DROP TRIGGER IF EXISTS notes_fts_after_insert")
    op.execute("DROP TABLE IF EXISTS notes_fts")

    op.drop_table("calendar_event_entity_links")
    op.drop_table("note_entity_links")

    for column_name in (
        "recovery_buffer_minutes",
        "travel_buffer_minutes",
        "preparation_buffer_minutes",
        "category",
        "recurrence_rrule",
    ):
        op.drop_column("calendar_events", column_name)

    op.drop_index("ux_notes_workspace_daily_date_active", table_name="notes")
    op.drop_column("notes", "daily_note_date")

    op.drop_column("tasks", "recurrence_rrule")
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "actual_duration_minutes")

    op.drop_column("projects", "target_end_date")
    op.drop_column("projects", "target_start_date")
