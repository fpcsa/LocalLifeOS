from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Text, UniqueConstraint, text
from sqlmodel import Field

from app.models.common import (
    BudgetPeriod,
    CategoryKind,
    CurrencyCodeType,
    FinancialAccountType,
    GoalStatus,
    PlannedTransactionStatus,
    RecurringTransactionStatus,
    SubscriptionStatus,
    TransactionType,
    UTCDateTime,
    WorkspaceLinkBase,
    WorkspaceSoftDeleteEntityBase,
    utc_now,
)

CURRENCY_CHECKS = (
    "length(currency_code) = 3",
    "currency_code = upper(currency_code)",
)


class FinancialAccount(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_accounts_name_nonempty"),
        CheckConstraint(
            "financial_buffer_minor >= 0",
            name="ck_accounts_financial_buffer_nonnegative",
        ),
        CheckConstraint(CURRENCY_CHECKS[0], name="ck_accounts_currency_length"),
        CheckConstraint(CURRENCY_CHECKS[1], name="ck_accounts_currency_upper"),
        CheckConstraint("revision >= 1", name="ck_accounts_revision_positive"),
        Index(
            "ux_accounts_workspace_name_active",
            "workspace_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    name: str = Field(max_length=160)
    account_type: FinancialAccountType = Field(default=FinancialAccountType.CHECKING)
    currency_code: str = Field(min_length=3, max_length=3, sa_type=CurrencyCodeType)
    opening_balance_minor: int = Field(default=0)
    financial_buffer_minor: int = Field(default=0, ge=0)


class TransactionCategory(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "transaction_categories"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_categories_name_nonempty"),
        CheckConstraint("revision >= 1", name="ck_categories_revision_positive"),
        Index(
            "ux_categories_workspace_kind_name_active",
            "workspace_id",
            "kind",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    name: str = Field(max_length=120)
    kind: CategoryKind
    is_default: bool = Field(default=False)


class Transaction(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(CURRENCY_CHECKS[0], name="ck_transactions_currency_length"),
        CheckConstraint(CURRENCY_CHECKS[1], name="ck_transactions_currency_upper"),
        CheckConstraint(
            "(transaction_type = 'TRANSFER' AND transfer_account_id IS NOT NULL "
            "AND transfer_account_id <> account_id AND category_id IS NULL) "
            "OR (transaction_type IN ('INCOME', 'EXPENSE') "
            "AND transfer_account_id IS NULL)",
            name="ck_transactions_transfer_shape",
        ),
        CheckConstraint("revision >= 1", name="ck_transactions_revision_positive"),
        UniqueConstraint("workspace_id", "external_id", name="uq_transaction_external_id"),
        Index(
            "ux_transactions_workspace_import_fingerprint",
            "workspace_id",
            "import_fingerprint",
            unique=True,
            sqlite_where=text("import_fingerprint IS NOT NULL"),
        ),
        Index(
            "ix_transactions_workspace_occurred",
            "workspace_id",
            "occurred_at",
            "id",
        ),
    )

    account_id: UUID = Field(
        foreign_key="financial_accounts.id",
        ondelete="RESTRICT",
        index=True,
    )
    transfer_account_id: UUID | None = Field(
        default=None,
        foreign_key="financial_accounts.id",
        ondelete="RESTRICT",
        index=True,
    )
    category_id: UUID | None = Field(
        default=None,
        foreign_key="transaction_categories.id",
        ondelete="SET NULL",
        index=True,
    )
    transaction_type: TransactionType
    amount_minor: int = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3, sa_type=CurrencyCodeType)
    occurred_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, sa_type=Text)
    external_id: str | None = Field(default=None, max_length=255)
    import_fingerprint: str | None = Field(default=None, max_length=128)


class Subscription(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_subscriptions_name_nonempty"),
        CheckConstraint("amount_minor > 0", name="ck_subscriptions_amount_positive"),
        CheckConstraint(CURRENCY_CHECKS[0], name="ck_subscriptions_currency_length"),
        CheckConstraint(CURRENCY_CHECKS[1], name="ck_subscriptions_currency_upper"),
        CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name="ck_subscriptions_date_range",
        ),
        CheckConstraint("revision >= 1", name="ck_subscriptions_revision_positive"),
        Index("ix_subscriptions_workspace_status", "workspace_id", "status"),
    )

    name: str = Field(max_length=160)
    account_id: UUID = Field(
        foreign_key="financial_accounts.id",
        ondelete="RESTRICT",
        index=True,
    )
    category_id: UUID | None = Field(
        default=None,
        foreign_key="transaction_categories.id",
        ondelete="SET NULL",
        index=True,
    )
    amount_minor: int = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3, sa_type=CurrencyCodeType)
    billing_rrule: str = Field(max_length=1000)
    starts_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    ends_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, sa_type=Text)


class SubscriptionPriceChange(WorkspaceLinkBase, table=True):
    __tablename__ = "subscription_price_changes"
    __table_args__ = (
        CheckConstraint("old_amount_minor > 0", name="ck_subscription_old_amount_positive"),
        CheckConstraint("new_amount_minor > 0", name="ck_subscription_new_amount_positive"),
        CheckConstraint(
            "old_amount_minor <> new_amount_minor",
            name="ck_subscription_amount_changed",
        ),
        Index(
            "ix_subscription_price_changes_subscription_detected",
            "subscription_id",
            "detected_at",
        ),
    )

    subscription_id: UUID = Field(
        foreign_key="subscriptions.id",
        ondelete="CASCADE",
        index=True,
    )
    old_amount_minor: int = Field(gt=0)
    new_amount_minor: int = Field(gt=0)
    detected_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)


class RecurringTransactionRule(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "recurring_transaction_rules"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_recurring_name_nonempty"),
        CheckConstraint("amount_minor > 0", name="ck_recurring_amount_positive"),
        CheckConstraint(CURRENCY_CHECKS[0], name="ck_recurring_currency_length"),
        CheckConstraint(CURRENCY_CHECKS[1], name="ck_recurring_currency_upper"),
        CheckConstraint(
            "(transaction_type = 'TRANSFER' AND transfer_account_id IS NOT NULL "
            "AND transfer_account_id <> account_id AND category_id IS NULL) "
            "OR (transaction_type IN ('INCOME', 'EXPENSE') AND transfer_account_id IS NULL)",
            name="ck_recurring_transaction_shape",
        ),
        CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="ck_recurring_date_range"),
        CheckConstraint("revision >= 1", name="ck_recurring_revision_positive"),
        Index("ix_recurring_workspace_status", "workspace_id", "status"),
    )

    name: str = Field(max_length=160)
    account_id: UUID = Field(
        foreign_key="financial_accounts.id",
        ondelete="RESTRICT",
        index=True,
    )
    transfer_account_id: UUID | None = Field(
        default=None,
        foreign_key="financial_accounts.id",
        ondelete="RESTRICT",
        index=True,
    )
    category_id: UUID | None = Field(
        default=None,
        foreign_key="transaction_categories.id",
        ondelete="SET NULL",
        index=True,
    )
    subscription_id: UUID | None = Field(
        default=None,
        foreign_key="subscriptions.id",
        ondelete="SET NULL",
        index=True,
    )
    transaction_type: TransactionType
    amount_minor: int = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3, sa_type=CurrencyCodeType)
    rrule: str = Field(max_length=1000)
    starts_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    ends_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    status: RecurringTransactionStatus = Field(default=RecurringTransactionStatus.ACTIVE)
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, sa_type=Text)
    is_committed: bool = Field(default=True)


class PlannedTransaction(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "planned_transactions"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_planned_transactions_amount_positive"),
        CheckConstraint(CURRENCY_CHECKS[0], name="ck_planned_transactions_currency_length"),
        CheckConstraint(CURRENCY_CHECKS[1], name="ck_planned_transactions_currency_upper"),
        CheckConstraint(
            "(transaction_type = 'TRANSFER' AND transfer_account_id IS NOT NULL "
            "AND transfer_account_id <> account_id AND category_id IS NULL) "
            "OR (transaction_type IN ('INCOME', 'EXPENSE') AND transfer_account_id IS NULL)",
            name="ck_planned_transactions_shape",
        ),
        CheckConstraint(
            "(status = 'FULFILLED' AND actual_transaction_id IS NOT NULL) "
            "OR (status IN ('PLANNED', 'CANCELLED') AND actual_transaction_id IS NULL)",
            name="ck_planned_transactions_fulfillment",
        ),
        CheckConstraint("revision >= 1", name="ck_planned_transactions_revision_positive"),
        UniqueConstraint("workspace_id", "occurrence_key", name="uq_planned_occurrence_key"),
        UniqueConstraint(
            "workspace_id",
            "import_fingerprint",
            name="uq_planned_import_fingerprint",
        ),
        UniqueConstraint(
            "actual_transaction_id",
            name="uq_planned_actual_transaction",
        ),
        Index("ix_planned_workspace_date_status", "workspace_id", "planned_for", "status"),
    )

    account_id: UUID = Field(
        foreign_key="financial_accounts.id",
        ondelete="RESTRICT",
        index=True,
    )
    transfer_account_id: UUID | None = Field(
        default=None,
        foreign_key="financial_accounts.id",
        ondelete="RESTRICT",
        index=True,
    )
    category_id: UUID | None = Field(
        default=None,
        foreign_key="transaction_categories.id",
        ondelete="SET NULL",
        index=True,
    )
    recurring_rule_id: UUID | None = Field(
        default=None,
        foreign_key="recurring_transaction_rules.id",
        ondelete="SET NULL",
        index=True,
    )
    subscription_id: UUID | None = Field(
        default=None,
        foreign_key="subscriptions.id",
        ondelete="SET NULL",
        index=True,
    )
    actual_transaction_id: UUID | None = Field(
        default=None,
        foreign_key="transactions.id",
        ondelete="SET NULL",
    )
    transaction_type: TransactionType
    amount_minor: int = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3, sa_type=CurrencyCodeType)
    planned_for: datetime = Field(sa_type=UTCDateTime, nullable=False)
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, sa_type=Text)
    status: PlannedTransactionStatus = Field(default=PlannedTransactionStatus.PLANNED)
    is_committed: bool = Field(default=False)
    occurrence_key: str | None = Field(default=None, max_length=255)
    import_fingerprint: str | None = Field(default=None, max_length=128)


class Budget(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_budgets_name_nonempty"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_budgets_date_range"),
        CheckConstraint(CURRENCY_CHECKS[0], name="ck_budgets_currency_length"),
        CheckConstraint(CURRENCY_CHECKS[1], name="ck_budgets_currency_upper"),
        CheckConstraint("revision >= 1", name="ck_budgets_revision_positive"),
        Index("ix_budgets_workspace_period", "workspace_id", "start_date", "end_date"),
    )

    name: str = Field(max_length=160)
    period: BudgetPeriod = Field(default=BudgetPeriod.MONTHLY)
    start_date: date
    end_date: date | None = None
    currency_code: str = Field(min_length=3, max_length=3, sa_type=CurrencyCodeType)


class BudgetCategoryLimit(WorkspaceLinkBase, table=True):
    __tablename__ = "budget_category_limits"
    __table_args__ = (
        CheckConstraint("limit_minor >= 0", name="ck_budget_limits_nonnegative"),
        UniqueConstraint("budget_id", "category_id", name="uq_budget_category_limit"),
    )

    budget_id: UUID = Field(foreign_key="budgets.id", ondelete="CASCADE", index=True)
    category_id: UUID = Field(
        foreign_key="transaction_categories.id",
        ondelete="RESTRICT",
        index=True,
    )
    limit_minor: int = Field(ge=0)


class SavingsGoal(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "savings_goals"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_savings_goals_name_nonempty"),
        CheckConstraint("target_minor > 0", name="ck_savings_goals_target_positive"),
        CheckConstraint("current_minor >= 0", name="ck_savings_goals_current_nonnegative"),
        CheckConstraint(CURRENCY_CHECKS[0], name="ck_savings_goals_currency_length"),
        CheckConstraint(CURRENCY_CHECKS[1], name="ck_savings_goals_currency_upper"),
        CheckConstraint("revision >= 1", name="ck_savings_goals_revision_positive"),
        Index("ix_savings_goals_workspace_status", "workspace_id", "status"),
    )

    name: str = Field(max_length=160)
    account_id: UUID | None = Field(
        default=None,
        foreign_key="financial_accounts.id",
        ondelete="SET NULL",
        index=True,
    )
    target_minor: int = Field(gt=0)
    current_minor: int = Field(default=0, ge=0)
    currency_code: str = Field(min_length=3, max_length=3, sa_type=CurrencyCodeType)
    target_date: date | None = None
    status: GoalStatus = Field(default=GoalStatus.ACTIVE)
