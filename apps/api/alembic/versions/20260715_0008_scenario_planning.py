"""Allow planned transactions in scenario overlays.

Revision ID: 20260715_0008
Revises: 20260715_0007
Create Date: 2026-07-15 23:30:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0008"
down_revision: str | None = "20260715_0007"
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


def _expression(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"entity_type IN ({quoted})"


def upgrade() -> None:
    with op.batch_alter_table("scenario_changes") as batch_op:
        batch_op.drop_constraint("scenario_entity_type", type_="check")
        batch_op.create_check_constraint(
            "scenario_entity_type",
            _expression((*BASE_VALUES[:10], "PLANNED_TRANSACTION", *BASE_VALUES[10:])),
        )


def downgrade() -> None:
    with op.batch_alter_table("scenario_changes") as batch_op:
        batch_op.drop_constraint("scenario_entity_type", type_="check")
        batch_op.create_check_constraint(
            "scenario_entity_type",
            _expression(BASE_VALUES),
        )
