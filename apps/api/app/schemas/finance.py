from __future__ import annotations

from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models import (
    BudgetPeriod,
    CategoryKind,
    FinancialAccountType,
    GoalStatus,
    PlannedTransactionStatus,
    RecurringTransactionStatus,
    SubscriptionStatus,
    TransactionType,
)
from app.schemas.common import ApiModel, AwareDateTime, CurrencyCode
from app.utils.recurrence import canonicalize_rrule


def _validate_transaction_shape(
    transaction_type: TransactionType,
    account_id: UUID,
    transfer_account_id: UUID | None,
    category_id: UUID | None,
) -> None:
    if transaction_type == TransactionType.TRANSFER:
        if transfer_account_id is None:
            raise ValueError("transfers require transfer_account_id")
        if transfer_account_id == account_id:
            raise ValueError("transfer accounts must be different")
        if category_id is not None:
            raise ValueError("transfers cannot have a category")
    elif transfer_account_id is not None:
        raise ValueError("only transfers can specify transfer_account_id")


class FinanceRevisionRequest(ApiModel):
    revision: int = Field(ge=1)


class FinancialAccountCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    account_type: FinancialAccountType = FinancialAccountType.CHECKING
    currency_code: CurrencyCode
    opening_balance_minor: int = 0
    financial_buffer_minor: int = Field(default=0, ge=0)


class FinancialAccountUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    account_type: FinancialAccountType | None = None
    financial_buffer_minor: int | None = Field(default=None, ge=0)


class FinancialAccountResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    account_type: FinancialAccountType
    currency_code: str
    opening_balance_minor: int
    financial_buffer_minor: int
    balance_minor: int
    below_financial_buffer: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class LedgerEntryResponse(ApiModel):
    transaction_id: UUID
    transaction_type: TransactionType
    occurred_at: datetime
    payee: str | None
    effect_minor: int
    balance_after_minor: int


class AccountLedgerResponse(ApiModel):
    account: FinancialAccountResponse
    entries: list[LedgerEntryResponse]


class TransactionCategoryCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    kind: CategoryKind


class TransactionCategoryUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)


class TransactionCategoryResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    kind: CategoryKind
    is_default: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class TransactionCreateRequest(ApiModel):
    account_id: UUID
    transfer_account_id: UUID | None = None
    category_id: UUID | None = None
    transaction_type: TransactionType
    amount_minor: int = Field(gt=0)
    currency_code: CurrencyCode
    occurred_at: AwareDateTime
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    import_fingerprint: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        _validate_transaction_shape(
            self.transaction_type,
            self.account_id,
            self.transfer_account_id,
            self.category_id,
        )
        return self


class TransferCreateRequest(ApiModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount_minor: int = Field(gt=0)
    currency_code: CurrencyCode
    occurred_at: AwareDateTime
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    import_fingerprint: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_accounts(self) -> Self:
        if self.source_account_id == self.destination_account_id:
            raise ValueError("transfer accounts must be different")
        return self


class TransactionUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    category_id: UUID | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    occurred_at: AwareDateTime | None = None
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    import_fingerprint: str | None = Field(default=None, min_length=1, max_length=128)


class AccountEffectResponse(ApiModel):
    account_id: UUID
    effect_minor: int


class TransactionResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    transfer_account_id: UUID | None
    category_id: UUID | None
    transaction_type: TransactionType
    amount_minor: int
    currency_code: str
    occurred_at: datetime
    payee: str | None
    note: str | None
    external_id: str | None
    import_fingerprint: str | None
    account_effects: list[AccountEffectResponse]
    revision: int
    created_at: datetime
    updated_at: datetime


class PlannedTransactionCreateRequest(ApiModel):
    account_id: UUID
    transfer_account_id: UUID | None = None
    category_id: UUID | None = None
    transaction_type: TransactionType
    amount_minor: int = Field(gt=0)
    currency_code: CurrencyCode
    planned_for: AwareDateTime
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    is_committed: bool = False
    subscription_id: UUID | None = None
    import_fingerprint: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        _validate_transaction_shape(
            self.transaction_type,
            self.account_id,
            self.transfer_account_id,
            self.category_id,
        )
        return self


class PlannedTransactionUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    category_id: UUID | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    planned_for: AwareDateTime | None = None
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    is_committed: bool | None = None
    import_fingerprint: str | None = Field(default=None, min_length=1, max_length=128)


class PlannedTransactionResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    transfer_account_id: UUID | None
    category_id: UUID | None
    recurring_rule_id: UUID | None
    subscription_id: UUID | None
    actual_transaction_id: UUID | None
    transaction_type: TransactionType
    amount_minor: int
    currency_code: str
    planned_for: datetime
    payee: str | None
    note: str | None
    status: PlannedTransactionStatus
    is_committed: bool
    occurrence_key: str | None
    import_fingerprint: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class FulfillPlannedTransactionRequest(ApiModel):
    revision: int = Field(ge=1)
    occurred_at: AwareDateTime
    amount_minor: int | None = Field(default=None, gt=0)
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None


class PlannedFulfillmentResponse(ApiModel):
    planned: PlannedTransactionResponse
    actual: TransactionResponse


class RecurringTransactionCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    account_id: UUID
    transfer_account_id: UUID | None = None
    category_id: UUID | None = None
    subscription_id: UUID | None = None
    transaction_type: TransactionType
    amount_minor: int = Field(gt=0)
    currency_code: CurrencyCode
    rrule: str
    starts_at: AwareDateTime
    ends_at: AwareDateTime | None = None
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    is_committed: bool = True

    _validate_rrule = field_validator("rrule")(canonicalize_rrule)

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        _validate_transaction_shape(
            self.transaction_type,
            self.account_id,
            self.transfer_account_id,
            self.category_id,
        )
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at cannot be before starts_at")
        return self


class RecurringTransactionUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    amount_minor: int | None = Field(default=None, gt=0)
    rrule: str | None = None
    starts_at: AwareDateTime | None = None
    ends_at: AwareDateTime | None = None
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    is_committed: bool | None = None

    _validate_rrule = field_validator("rrule")(
        lambda value: canonicalize_rrule(value) if value is not None else value
    )


class RecurringTransactionResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    account_id: UUID
    transfer_account_id: UUID | None
    category_id: UUID | None
    subscription_id: UUID | None
    transaction_type: TransactionType
    amount_minor: int
    currency_code: str
    rrule: str
    starts_at: datetime
    ends_at: datetime | None
    status: RecurringTransactionStatus
    payee: str | None
    note: str | None
    is_committed: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class RecurringGenerationRequest(ApiModel):
    start: AwareDateTime
    end: AwareDateTime

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class BudgetLimitInput(ApiModel):
    category_id: UUID
    limit_minor: int = Field(ge=0)


class BudgetCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    start_date: date
    end_date: date | None = None
    currency_code: CurrencyCode
    limits: list[BudgetLimitInput] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        if self.period == BudgetPeriod.CUSTOM and self.end_date is None:
            raise ValueError("custom budgets require end_date")
        ids = [item.category_id for item in self.limits]
        if len(ids) != len(set(ids)):
            raise ValueError("budget categories cannot be duplicated")
        return self


class BudgetUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    limits: list[BudgetLimitInput] | None = Field(default=None, max_length=200)

    @field_validator("limits")
    @classmethod
    def validate_limits(cls, value: list[BudgetLimitInput] | None) -> list[BudgetLimitInput] | None:
        if value is not None:
            ids = [item.category_id for item in value]
            if len(ids) != len(set(ids)):
                raise ValueError("budget categories cannot be duplicated")
        return value


class BudgetLimitResponse(ApiModel):
    id: UUID
    category_id: UUID
    limit_minor: int


class BudgetResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    period: BudgetPeriod
    start_date: date
    end_date: date | None
    currency_code: str
    limits: list[BudgetLimitResponse]
    revision: int
    created_at: datetime
    updated_at: datetime


class SavingsGoalCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    account_id: UUID | None = None
    target_minor: int = Field(gt=0)
    current_minor: int = Field(default=0, ge=0)
    currency_code: CurrencyCode
    target_date: date | None = None


class SavingsGoalUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    account_id: UUID | None = None
    target_minor: int | None = Field(default=None, gt=0)
    current_minor: int | None = Field(default=None, ge=0)
    target_date: date | None = None
    status: GoalStatus | None = None


class SavingsGoalContributionRequest(ApiModel):
    revision: int = Field(ge=1)
    amount_minor: int = Field(gt=0)


class SavingsGoalResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    account_id: UUID | None
    target_minor: int
    current_minor: int
    remaining_minor: int
    progress_basis_points: int
    currency_code: str
    target_date: date | None
    status: GoalStatus
    revision: int
    created_at: datetime
    updated_at: datetime


class GoalCreateRequest(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    description_markdown: str | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    progress_basis_points: int = Field(default=0, ge=0, le=10_000)
    target_at: AwareDateTime | None = None


class GoalUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description_markdown: str | None = None
    status: GoalStatus | None = None
    progress_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    target_at: AwareDateTime | None = None


class GoalResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    title: str
    description_markdown: str | None
    status: GoalStatus
    progress_basis_points: int
    target_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime


class SubscriptionCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    account_id: UUID
    category_id: UUID | None = None
    amount_minor: int = Field(gt=0)
    currency_code: CurrencyCode
    billing_rrule: str
    starts_at: AwareDateTime
    ends_at: AwareDateTime | None = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None

    _validate_rrule = field_validator("billing_rrule")(canonicalize_rrule)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at cannot be before starts_at")
        return self


class SubscriptionUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category_id: UUID | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    billing_rrule: str | None = None
    starts_at: AwareDateTime | None = None
    ends_at: AwareDateTime | None = None
    status: SubscriptionStatus | None = None
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None

    _validate_rrule = field_validator("billing_rrule")(
        lambda value: canonicalize_rrule(value) if value is not None else value
    )


class SubscriptionPriceChangeResponse(ApiModel):
    id: UUID
    old_amount_minor: int
    new_amount_minor: int
    delta_minor: int
    detected_at: datetime


class SubscriptionResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    account_id: UUID
    category_id: UUID | None
    amount_minor: int
    currency_code: str
    billing_rrule: str
    starts_at: datetime
    ends_at: datetime | None
    status: SubscriptionStatus
    payee: str | None
    note: str | None
    price_changes: list[SubscriptionPriceChangeResponse]
    revision: int
    created_at: datetime
    updated_at: datetime


class CalculationRecord(ApiModel):
    record_type: str
    record_id: UUID
    reason: str


class ReportMetadata(ApiModel):
    input_start: date
    input_end: date
    currency: str | None
    assumptions: list[str]
    included_records: list[CalculationRecord]
    excluded_records: list[CalculationRecord]
    calculation_timestamp: datetime


class CashFlowMonthResponse(ApiModel):
    month: str
    actual_income_minor: int
    actual_expense_minor: int
    planned_income_minor: int
    planned_expense_minor: int
    recurring_income_minor: int
    recurring_expense_minor: int
    net_minor: int
    projected_ending_balance_minor: int


class CashFlowCurrencyGroup(ApiModel):
    currency: str
    opening_balance_minor: int
    months: list[CashFlowMonthResponse]


class CashFlowReportResponse(ApiModel):
    metadata: ReportMetadata
    groups: list[CashFlowCurrencyGroup]


class SpendingCategoryResponse(ApiModel):
    category_id: UUID | None
    category_name: str
    actual_minor: int
    planned_minor: int


class SpendingCurrencyGroup(ApiModel):
    currency: str
    total_actual_minor: int
    total_planned_minor: int
    categories: list[SpendingCategoryResponse]


class SpendingByCategoryReportResponse(ApiModel):
    metadata: ReportMetadata
    groups: list[SpendingCurrencyGroup]


class CommittedCurrencyGroup(ApiModel):
    currency: str
    ledger_balance_minor: int
    committed_planned_minor: int
    committed_recurring_minor: int
    committed_subscription_minor: int
    committed_commitment_minor: int
    committed_total_minor: int
    effectively_available_minor: int
    financial_buffer_minor: int
    buffer_violation: bool


class CommittedBalanceReportResponse(ApiModel):
    metadata: ReportMetadata
    groups: list[CommittedCurrencyGroup]


class BudgetCategoryConsumptionResponse(ApiModel):
    category_id: UUID
    category_name: str
    limit_minor: int
    actual_minor: int
    planned_minor: int
    remaining_after_actual_minor: int
    remaining_after_planned_minor: int
    consumption_basis_points: int


class BudgetConsumptionResponse(ApiModel):
    budget_id: UUID
    metadata: ReportMetadata
    total_limit_minor: int
    total_actual_minor: int
    total_planned_minor: int
    categories: list[BudgetCategoryConsumptionResponse]
