"""Add persistence safeguards for account financial buffers.

Revision ID: 20260715_0005
Revises: 20260715_0004
Create Date: 2026-07-15 20:00:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0005"
down_revision: str | None = "20260715_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("financial_accounts") as batch_op:
        batch_op.create_check_constraint(
            "ck_accounts_financial_buffer_nonnegative",
            "financial_buffer_minor >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("financial_accounts") as batch_op:
        batch_op.drop_constraint(
            "ck_accounts_financial_buffer_nonnegative",
            type_="check",
        )
