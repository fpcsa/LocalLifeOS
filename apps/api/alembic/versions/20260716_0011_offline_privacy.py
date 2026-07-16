"""Add local privacy session preference.

Revision ID: 20260716_0011
Revises: 20260716_0010
Create Date: 2026-07-16 01:30:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0011"
down_revision: str | None = "20260716_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.add_column(
            sa.Column(
                "session_timeout_minutes",
                sa.Integer(),
                nullable=False,
                server_default="30",
            )
        )
        batch_op.create_check_constraint(
            "ck_preferences_session_timeout",
            "session_timeout_minutes BETWEEN 1 AND 1440",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.drop_constraint("ck_preferences_session_timeout", type_="check")
        batch_op.drop_column("session_timeout_minutes")
