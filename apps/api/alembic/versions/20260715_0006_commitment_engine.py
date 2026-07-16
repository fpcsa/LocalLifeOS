"""Expand commitments and their typed link coverage.

Revision ID: 20260715_0006
Revises: 20260715_0005
Create Date: 2026-07-15 21:00:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0006"
down_revision: str | None = "20260715_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


OLD_COMMITMENT_STATUS = enum_type(
    "commitment_status",
    "DRAFT",
    "PLANNED",
    "ACTIVE",
    "COMPLETED",
    "CANCELLED",
)
NEW_COMMITMENT_STATUS = enum_type(
    "commitment_status",
    "DRAFT",
    "PLANNED",
    "ACTIVE",
    "COMPLETED",
    "CANCELLED",
    "ARCHIVED",
)
OLD_LINK_TYPE = enum_type(
    "commitment_entity_type",
    "TASK",
    "CALENDAR_EVENT",
    "NOTE",
    "TRANSACTION",
    "BUDGET",
    "GOAL",
)
NEW_LINK_TYPE = enum_type(
    "commitment_entity_type",
    "TASK",
    "PROJECT",
    "CALENDAR_EVENT",
    "NOTE",
    "PLANNED_TRANSACTION",
    "TRANSACTION",
    "BUDGET",
    "SAVINGS_GOAL",
    "GOAL",
)


def upgrade() -> None:
    with op.batch_alter_table("commitments") as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(length=120), nullable=True))
        batch_op.add_column(
            sa.Column("decision_deadline_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("financial_buffer_requirement_minor", sa.Integer(), nullable=True)
        )
        batch_op.drop_constraint("ck_commitments_money_shape", type_="check")
        batch_op.alter_column(
            "status",
            existing_type=OLD_COMMITMENT_STATUS,
            type_=NEW_COMMITMENT_STATUS,
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_commitments_money_shape",
            "((planned_cost_minor IS NULL AND financial_buffer_requirement_minor IS NULL) "
            "AND currency_code IS NULL) OR ((planned_cost_minor IS NOT NULL "
            "OR financial_buffer_requirement_minor IS NOT NULL) "
            "AND (planned_cost_minor IS NULL OR planned_cost_minor >= 0) "
            "AND (financial_buffer_requirement_minor IS NULL "
            "OR financial_buffer_requirement_minor >= 0) "
            "AND length(currency_code) = 3 AND currency_code = upper(currency_code))",
        )
        batch_op.create_index(
            "ix_commitments_workspace_category",
            ["workspace_id", "category"],
        )
        batch_op.create_index(
            "ix_commitments_workspace_target",
            ["workspace_id", "ends_at"],
        )

    with op.batch_alter_table("commitment_entity_links") as batch_op:
        batch_op.alter_column(
            "entity_type",
            existing_type=OLD_LINK_TYPE,
            type_=NEW_LINK_TYPE,
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("commitment_entity_links") as batch_op:
        batch_op.alter_column(
            "entity_type",
            existing_type=NEW_LINK_TYPE,
            type_=OLD_LINK_TYPE,
            existing_nullable=False,
        )

    with op.batch_alter_table("commitments") as batch_op:
        batch_op.drop_index("ix_commitments_workspace_target")
        batch_op.drop_index("ix_commitments_workspace_category")
        batch_op.drop_constraint("ck_commitments_money_shape", type_="check")
        batch_op.alter_column(
            "status",
            existing_type=NEW_COMMITMENT_STATUS,
            type_=OLD_COMMITMENT_STATUS,
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_commitments_money_shape",
            "(planned_cost_minor IS NULL AND currency_code IS NULL) "
            "OR (planned_cost_minor >= 0 AND length(currency_code) = 3 "
            "AND currency_code = upper(currency_code))",
        )
        batch_op.drop_column("financial_buffer_requirement_minor")
        batch_op.drop_column("decision_deadline_at")
        batch_op.drop_column("category")
