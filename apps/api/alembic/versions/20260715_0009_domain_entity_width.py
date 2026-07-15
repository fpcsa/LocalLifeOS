"""Align shared domain entity columns with planned transactions.

Revision ID: 20260715_0009
Revises: 20260715_0008
Create Date: 2026-07-15 23:45:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0009"
down_revision: str | None = "20260715_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASE_VALUES = (
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

PLANNING_VALUES = (*BASE_VALUES[:10], "PLANNED_TRANSACTION", *BASE_VALUES[10:])

ENTITY_TYPE_CONSTRAINTS = {
    "attachment_entity_links": "attachment_entity_type",
    "calendar_event_entity_links": "calendar_link_entity_type",
    "note_entity_links": "note_entity_type",
    "scenario_changes": "scenario_entity_type",
    "tag_entity_links": "tag_entity_type",
    "timeline_events": "timeline_entity_type",
}


def _expression(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"entity_type IN ({quoted})"


def upgrade() -> None:
    for table_name, constraint_name in ENTITY_TYPE_CONSTRAINTS.items():
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="check")
            batch_op.alter_column(
                "entity_type",
                existing_type=sa.String(length=17),
                type_=sa.String(length=19),
                existing_nullable=False,
            )
            batch_op.create_check_constraint(
                constraint_name,
                _expression(PLANNING_VALUES),
            )


def downgrade() -> None:
    for table_name, constraint_name in reversed(ENTITY_TYPE_CONSTRAINTS.items()):
        allowed_values = PLANNING_VALUES if table_name == "scenario_changes" else BASE_VALUES
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="check")
            batch_op.alter_column(
                "entity_type",
                existing_type=sa.String(length=19),
                type_=sa.String(length=17),
                existing_nullable=False,
            )
            batch_op.create_check_constraint(
                constraint_name,
                _expression(allowed_values),
            )
