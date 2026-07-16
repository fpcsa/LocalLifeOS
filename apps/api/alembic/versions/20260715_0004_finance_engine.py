"""Add deterministic finance engine records and safety metadata.

Revision ID: 20260715_0004
Revises: 20260715_0003
Create Date: 2026-07-15 18:00:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0004"
down_revision: str | None = "20260715_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def entity_columns() -> list[sa.Column]:
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
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


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


def currency_constraints(prefix: str) -> tuple[sa.CheckConstraint, sa.CheckConstraint]:
    return (
        sa.CheckConstraint(
            "length(currency_code) = 3",
            name=f"ck_{prefix}_currency_length",
        ),
        sa.CheckConstraint(
            "currency_code = upper(currency_code)",
            name=f"ck_{prefix}_currency_upper",
        ),
    )


def upgrade() -> None:
    op.add_column(
        "financial_accounts",
        sa.Column(
            "financial_buffer_minor",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("import_fingerprint", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ux_transactions_workspace_import_fingerprint",
        "transactions",
        ["workspace_id", "import_fingerprint"],
        unique=True,
        sqlite_where=sa.text("import_fingerprint IS NOT NULL"),
    )
    with op.batch_alter_table("savings_goals") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_savings_goals_account_id_financial_accounts",
            "financial_accounts",
            ["account_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_savings_goals_account_id", ["account_id"])

    op.create_table(
        "subscriptions",
        *entity_columns(),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("transaction_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("billing_rrule", sa.String(length=1000), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            enum_type("subscription_status", "ACTIVE", "PAUSED", "CANCELLED"),
            nullable=False,
        ),
        sa.Column("payee", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_subscriptions_name_nonempty"),
        sa.CheckConstraint("amount_minor > 0", name="ck_subscriptions_amount_positive"),
        *currency_constraints("subscriptions"),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name="ck_subscriptions_date_range",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_subscriptions_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_workspace_id", "subscriptions", ["workspace_id"])
    op.create_index("ix_subscriptions_account_id", "subscriptions", ["account_id"])
    op.create_index("ix_subscriptions_category_id", "subscriptions", ["category_id"])
    op.create_index(
        "ix_subscriptions_workspace_status",
        "subscriptions",
        ["workspace_id", "status"],
    )

    op.create_table(
        "subscription_price_changes",
        *link_columns(),
        sa.Column(
            "subscription_id",
            sa.Uuid(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_amount_minor", sa.Integer(), nullable=False),
        sa.Column("new_amount_minor", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "old_amount_minor > 0",
            name="ck_subscription_old_amount_positive",
        ),
        sa.CheckConstraint(
            "new_amount_minor > 0",
            name="ck_subscription_new_amount_positive",
        ),
        sa.CheckConstraint(
            "old_amount_minor <> new_amount_minor",
            name="ck_subscription_amount_changed",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscription_price_changes_workspace_id",
        "subscription_price_changes",
        ["workspace_id"],
    )
    op.create_index(
        "ix_subscription_price_changes_subscription_id",
        "subscription_price_changes",
        ["subscription_id"],
    )
    op.create_index(
        "ix_subscription_price_changes_subscription_detected",
        "subscription_price_changes",
        ["subscription_id", "detected_at"],
    )

    op.create_table(
        "recurring_transaction_rules",
        *entity_columns(),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "transfer_account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("transaction_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subscription_id",
            sa.Uuid(),
            sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "transaction_type",
            enum_type("recurring_transaction_type", "INCOME", "EXPENSE", "TRANSFER"),
            nullable=False,
        ),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("rrule", sa.String(length=1000), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            enum_type("recurring_transaction_status", "ACTIVE", "PAUSED", "ENDED"),
            nullable=False,
        ),
        sa.Column("payee", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_committed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_recurring_name_nonempty"),
        sa.CheckConstraint("amount_minor > 0", name="ck_recurring_amount_positive"),
        *currency_constraints("recurring"),
        sa.CheckConstraint(
            "(transaction_type = 'TRANSFER' AND transfer_account_id IS NOT NULL "
            "AND transfer_account_id <> account_id AND category_id IS NULL) "
            "OR (transaction_type IN ('INCOME', 'EXPENSE') AND transfer_account_id IS NULL)",
            name="ck_recurring_transaction_shape",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name="ck_recurring_date_range",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_recurring_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurring_transaction_rules_workspace_id",
        "recurring_transaction_rules",
        ["workspace_id"],
    )
    op.create_index(
        "ix_recurring_transaction_rules_account_id",
        "recurring_transaction_rules",
        ["account_id"],
    )
    op.create_index(
        "ix_recurring_transaction_rules_transfer_account_id",
        "recurring_transaction_rules",
        ["transfer_account_id"],
    )
    op.create_index(
        "ix_recurring_transaction_rules_category_id",
        "recurring_transaction_rules",
        ["category_id"],
    )
    op.create_index(
        "ix_recurring_transaction_rules_subscription_id",
        "recurring_transaction_rules",
        ["subscription_id"],
    )
    op.create_index(
        "ix_recurring_workspace_status",
        "recurring_transaction_rules",
        ["workspace_id", "status"],
    )

    op.create_table(
        "planned_transactions",
        *entity_columns(),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "transfer_account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("transaction_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recurring_rule_id",
            sa.Uuid(),
            sa.ForeignKey("recurring_transaction_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subscription_id",
            sa.Uuid(),
            sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actual_transaction_id",
            sa.Uuid(),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "transaction_type",
            enum_type("planned_transaction_type", "INCOME", "EXPENSE", "TRANSFER"),
            nullable=False,
        ),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("planned_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payee", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            enum_type("planned_transaction_status", "PLANNED", "FULFILLED", "CANCELLED"),
            nullable=False,
        ),
        sa.Column("is_committed", sa.Boolean(), nullable=False),
        sa.Column("occurrence_key", sa.String(length=255), nullable=True),
        sa.Column("import_fingerprint", sa.String(length=128), nullable=True),
        sa.CheckConstraint("amount_minor > 0", name="ck_planned_transactions_amount_positive"),
        *currency_constraints("planned_transactions"),
        sa.CheckConstraint(
            "(transaction_type = 'TRANSFER' AND transfer_account_id IS NOT NULL "
            "AND transfer_account_id <> account_id AND category_id IS NULL) "
            "OR (transaction_type IN ('INCOME', 'EXPENSE') AND transfer_account_id IS NULL)",
            name="ck_planned_transactions_shape",
        ),
        sa.CheckConstraint(
            "(status = 'FULFILLED' AND actual_transaction_id IS NOT NULL) "
            "OR (status IN ('PLANNED', 'CANCELLED') AND actual_transaction_id IS NULL)",
            name="ck_planned_transactions_fulfillment",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_planned_transactions_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "occurrence_key",
            name="uq_planned_occurrence_key",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "import_fingerprint",
            name="uq_planned_import_fingerprint",
        ),
        sa.UniqueConstraint(
            "actual_transaction_id",
            name="uq_planned_actual_transaction",
        ),
    )
    op.create_index(
        "ix_planned_transactions_workspace_id", "planned_transactions", ["workspace_id"]
    )
    op.create_index("ix_planned_transactions_account_id", "planned_transactions", ["account_id"])
    op.create_index(
        "ix_planned_transactions_transfer_account_id",
        "planned_transactions",
        ["transfer_account_id"],
    )
    op.create_index("ix_planned_transactions_category_id", "planned_transactions", ["category_id"])
    op.create_index(
        "ix_planned_transactions_recurring_rule_id",
        "planned_transactions",
        ["recurring_rule_id"],
    )
    op.create_index(
        "ix_planned_transactions_subscription_id",
        "planned_transactions",
        ["subscription_id"],
    )
    op.create_index(
        "ix_planned_workspace_date_status",
        "planned_transactions",
        ["workspace_id", "planned_for", "status"],
    )


def downgrade() -> None:
    op.drop_table("planned_transactions")
    op.drop_table("recurring_transaction_rules")
    op.drop_table("subscription_price_changes")
    op.drop_table("subscriptions")

    with op.batch_alter_table("savings_goals") as batch_op:
        batch_op.drop_index("ix_savings_goals_account_id")
        batch_op.drop_constraint(
            "fk_savings_goals_account_id_financial_accounts",
            type_="foreignkey",
        )
        batch_op.drop_column("account_id")

    op.drop_index(
        "ux_transactions_workspace_import_fingerprint",
        table_name="transactions",
    )
    op.drop_column("transactions", "import_fingerprint")
    op.drop_column("financial_accounts", "financial_buffer_minor")
