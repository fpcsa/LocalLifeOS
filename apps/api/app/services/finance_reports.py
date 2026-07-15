from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.models import (
    Commitment,
    CommitmentStatus,
    RecurringTransactionRule,
    Subscription,
    TransactionType,
)
from app.models.common import utc_now
from app.repositories.finance_engine import (
    BudgetRepository,
    FinanceAccountRepository,
    FinanceCategoryRepository,
    FinanceTransactionRepository,
    PlannedTransactionRepository,
    RecurringTransactionRepository,
    SubscriptionRepository,
)
from app.schemas.finance import (
    BudgetCategoryConsumptionResponse,
    BudgetConsumptionResponse,
    CalculationRecord,
    CashFlowCurrencyGroup,
    CashFlowMonthResponse,
    CashFlowReportResponse,
    CommittedBalanceReportResponse,
    CommittedCurrencyGroup,
    ReportMetadata,
    SpendingByCategoryReportResponse,
    SpendingCategoryResponse,
    SpendingCurrencyGroup,
)
from app.services.finance_calculations import (
    account_balances,
    budget_end_date,
    month_keys,
    utc_date_bounds,
)
from app.services.workspace import get_current_workspace, get_preferences
from app.utils.recurrence import expand_recurrence


def _record(record_type: str, record_id: UUID, reason: str) -> CalculationRecord:
    return CalculationRecord(record_type=record_type, record_id=record_id, reason=reason)


def _metadata(
    *,
    start: date,
    end: date,
    currency: str | None,
    assumptions: list[str],
    included: list[CalculationRecord],
    excluded: list[CalculationRecord],
) -> ReportMetadata:
    return ReportMetadata(
        input_start=start,
        input_end=end,
        currency=currency,
        assumptions=assumptions,
        included_records=included,
        excluded_records=excluded,
        calculation_timestamp=utc_now(),
    )


def _expand_rule(
    rule: RecurringTransactionRule | Subscription,
    rrule: str,
    starts_at: datetime,
    ends_at: datetime | None,
    range_start: datetime,
    range_end: datetime,
) -> list[datetime]:
    try:
        occurrences = expand_recurrence(
            rrule,
            dtstart=starts_at,
            range_start=max(range_start, starts_at),
            range_end=range_end,
        )
    except ValueError as exc:
        raise DomainValidationError("invalid_recurrence", str(exc)) from exc
    if ends_at is not None:
        occurrences = [item for item in occurrences if item <= ends_at]
    return occurrences


def cash_flow_report(
    session: Session,
    *,
    start_date: date,
    months: int,
    currency: str | None,
) -> CashFlowReportResponse:
    workspace = get_current_workspace(session)
    timezone_name = get_preferences(session).timezone
    local_timezone = ZoneInfo(timezone_name)
    end_date = start_date + relativedelta(months=months) - timedelta(days=1)
    range_start, range_end = utc_date_bounds(start_date, end_date, timezone_name)
    account_repository = FinanceAccountRepository(session)
    transaction_repository = FinanceTransactionRepository(session)
    planned_repository = PlannedTransactionRepository(session)

    accounts = account_repository.all_active(workspace.id)
    if currency is not None:
        accounts = [account for account in accounts if account.currency_code == currency]
    before = transaction_repository.range(workspace.id, end=range_start, currency=currency)
    opening_balances = account_balances(accounts, before)
    opening_by_currency: dict[str, int] = defaultdict(int)
    for account in accounts:
        opening_by_currency[account.currency_code] += opening_balances.get(
            account.id, account.opening_balance_minor
        )

    keys = month_keys(start_date, end_date)
    buckets: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {
            key: {
                "actual_income": 0,
                "actual_expense": 0,
                "planned_income": 0,
                "planned_expense": 0,
                "recurring_income": 0,
                "recurring_expense": 0,
            }
            for key in keys
        }
    )
    included: list[CalculationRecord] = []
    excluded: list[CalculationRecord] = []

    actual = transaction_repository.range(
        workspace.id,
        start=range_start,
        end=range_end,
        currency=currency,
    )
    for actual_item in actual:
        if actual_item.transaction_type == TransactionType.TRANSFER:
            excluded.append(
                _record("transaction", actual_item.id, "transfers are cash-flow neutral")
            )
            continue
        key = actual_item.occurred_at.astimezone(local_timezone).strftime("%Y-%m")
        field = (
            "actual_income"
            if actual_item.transaction_type == TransactionType.INCOME
            else "actual_expense"
        )
        buckets[actual_item.currency_code][key][field] += actual_item.amount_minor
        included.append(
            _record(
                "transaction",
                actual_item.id,
                f"actual {actual_item.transaction_type.value}",
            )
        )

    planned = planned_repository.range(
        workspace.id,
        start=range_start,
        end=range_end,
        currency=currency,
    )
    planned_rule_occurrences: set[tuple[UUID, datetime]] = set()
    planned_subscription_occurrences: set[tuple[UUID, datetime]] = set()
    for planned_item in planned:
        normalized = planned_item.planned_for.astimezone(UTC)
        if planned_item.recurring_rule_id is not None:
            planned_rule_occurrences.add((planned_item.recurring_rule_id, normalized))
        if planned_item.subscription_id is not None:
            planned_subscription_occurrences.add((planned_item.subscription_id, normalized))
        if planned_item.transaction_type == TransactionType.TRANSFER:
            excluded.append(
                _record("planned_transaction", planned_item.id, "transfers are cash-flow neutral")
            )
            continue
        key = planned_item.planned_for.astimezone(local_timezone).strftime("%Y-%m")
        field = (
            "planned_income"
            if planned_item.transaction_type == TransactionType.INCOME
            else "planned_expense"
        )
        buckets[planned_item.currency_code][key][field] += planned_item.amount_minor
        included.append(
            _record(
                "planned_transaction",
                planned_item.id,
                f"planned {planned_item.transaction_type.value}",
            )
        )

    rules = RecurringTransactionRepository(session).all_active(workspace.id)
    for rule in rules:
        if rule.subscription_id is not None:
            excluded.append(
                _record("recurring_transaction", rule.id, "projected by linked subscription")
            )
            continue
        if currency is not None and rule.currency_code != currency:
            excluded.append(_record("recurring_transaction", rule.id, "currency filter"))
            continue
        if rule.transaction_type == TransactionType.TRANSFER:
            excluded.append(
                _record("recurring_transaction", rule.id, "transfers are cash-flow neutral")
            )
            continue
        for occurrence in _expand_rule(
            rule,
            rule.rrule,
            rule.starts_at,
            rule.ends_at,
            range_start,
            range_end,
        ):
            normalized = occurrence.astimezone(UTC)
            if (rule.id, normalized) in planned_rule_occurrences:
                continue
            key = occurrence.astimezone(local_timezone).strftime("%Y-%m")
            field = (
                "recurring_income"
                if rule.transaction_type == TransactionType.INCOME
                else "recurring_expense"
            )
            buckets[rule.currency_code][key][field] += rule.amount_minor
        included.append(_record("recurring_transaction", rule.id, "projected recurrence"))

    for subscription in SubscriptionRepository(session).all_active(workspace.id):
        if currency is not None and subscription.currency_code != currency:
            excluded.append(_record("subscription", subscription.id, "currency filter"))
            continue
        for occurrence in _expand_rule(
            subscription,
            subscription.billing_rrule,
            subscription.starts_at,
            subscription.ends_at,
            range_start,
            range_end,
        ):
            normalized = occurrence.astimezone(UTC)
            if (subscription.id, normalized) in planned_subscription_occurrences:
                continue
            buckets[subscription.currency_code][
                occurrence.astimezone(local_timezone).strftime("%Y-%m")
            ]["recurring_expense"] += subscription.amount_minor
        included.append(_record("subscription", subscription.id, "projected billing schedule"))

    currencies = sorted(
        set(opening_by_currency) | set(buckets) | ({currency} if currency else set())
    )
    groups: list[CashFlowCurrencyGroup] = []
    for currency_code in currencies:
        running = opening_by_currency.get(currency_code, 0)
        months_out: list[CashFlowMonthResponse] = []
        for key in keys:
            values = buckets[currency_code][key]
            net = (
                values["actual_income"]
                + values["planned_income"]
                + values["recurring_income"]
                - values["actual_expense"]
                - values["planned_expense"]
                - values["recurring_expense"]
            )
            running += net
            months_out.append(
                CashFlowMonthResponse(
                    month=key,
                    actual_income_minor=values["actual_income"],
                    actual_expense_minor=values["actual_expense"],
                    planned_income_minor=values["planned_income"],
                    planned_expense_minor=values["planned_expense"],
                    recurring_income_minor=values["recurring_income"],
                    recurring_expense_minor=values["recurring_expense"],
                    net_minor=net,
                    projected_ending_balance_minor=running,
                )
            )
        groups.append(
            CashFlowCurrencyGroup(
                currency=currency_code,
                opening_balance_minor=opening_by_currency.get(currency_code, 0),
                months=months_out,
            )
        )
    return CashFlowReportResponse(
        metadata=_metadata(
            start=start_date,
            end=end_date,
            currency=currency,
            assumptions=[
                "opening balance includes posted transactions before input_start",
                "transfers are cash-flow neutral",
                "generated planned occurrences replace matching recurrence projections",
                "no exchange-rate conversion is performed",
            ],
            included=included,
            excluded=excluded,
        ),
        groups=groups,
    )


def spending_by_category_report(
    session: Session,
    *,
    start_date: date,
    end_date: date,
    currency: str | None,
) -> SpendingByCategoryReportResponse:
    workspace = get_current_workspace(session)
    timezone_name = get_preferences(session).timezone
    try:
        range_start, range_end = utc_date_bounds(start_date, end_date, timezone_name)
    except ValueError as exc:
        raise DomainValidationError("invalid_report_range", str(exc)) from exc
    categories = {
        item.id: item.name for item in FinanceCategoryRepository(session).all_active(workspace.id)
    }
    values: dict[str, dict[UUID | None, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"actual": 0, "planned": 0})
    )
    included: list[CalculationRecord] = []
    excluded: list[CalculationRecord] = []
    actual = FinanceTransactionRepository(session).range(
        workspace.id,
        start=range_start,
        end=range_end,
        currency=currency,
    )
    for actual_item in actual:
        if actual_item.transaction_type != TransactionType.EXPENSE:
            excluded.append(_record("transaction", actual_item.id, "not an expense"))
            continue
        values[actual_item.currency_code][actual_item.category_id]["actual"] += (
            actual_item.amount_minor
        )
        included.append(_record("transaction", actual_item.id, "actual category spending"))
    planned = PlannedTransactionRepository(session).range(
        workspace.id,
        start=range_start,
        end=range_end,
        currency=currency,
    )
    for planned_item in planned:
        if planned_item.transaction_type != TransactionType.EXPENSE:
            excluded.append(_record("planned_transaction", planned_item.id, "not an expense"))
            continue
        values[planned_item.currency_code][planned_item.category_id]["planned"] += (
            planned_item.amount_minor
        )
        included.append(
            _record("planned_transaction", planned_item.id, "planned category spending")
        )

    currencies = sorted(set(values) | ({currency} if currency else set()))
    groups: list[SpendingCurrencyGroup] = []
    for currency_code in currencies:
        category_rows = [
            SpendingCategoryResponse(
                category_id=category_id,
                category_name=categories.get(category_id, "Uncategorized")
                if category_id is not None
                else "Uncategorized",
                actual_minor=amounts["actual"],
                planned_minor=amounts["planned"],
            )
            for category_id, amounts in sorted(
                values[currency_code].items(),
                key=lambda row: (
                    categories.get(row[0], "Uncategorized")
                    if row[0] is not None
                    else "Uncategorized",
                    str(row[0]),
                ),
            )
        ]
        groups.append(
            SpendingCurrencyGroup(
                currency=currency_code,
                total_actual_minor=sum(item.actual_minor for item in category_rows),
                total_planned_minor=sum(item.planned_minor for item in category_rows),
                categories=category_rows,
            )
        )
    return SpendingByCategoryReportResponse(
        metadata=_metadata(
            start=start_date,
            end=end_date,
            currency=currency,
            assumptions=[
                "only expense records contribute to category spending",
                "planned and actual spending are reported separately",
                "no exchange-rate conversion is performed",
            ],
            included=included,
            excluded=excluded,
        ),
        groups=groups,
    )


def committed_balance_report(
    session: Session,
    *,
    as_of: date,
    end_date: date,
    currency: str | None,
) -> CommittedBalanceReportResponse:
    if end_date < as_of:
        raise DomainValidationError("invalid_report_range", "end_date cannot be before as_of.")
    workspace = get_current_workspace(session)
    timezone_name = get_preferences(session).timezone
    range_start, range_end = utc_date_bounds(as_of, end_date, timezone_name)
    _, ledger_end = utc_date_bounds(as_of, as_of, timezone_name)
    accounts = FinanceAccountRepository(session).all_active(workspace.id)
    if currency is not None:
        accounts = [item for item in accounts if item.currency_code == currency]
    posted = FinanceTransactionRepository(session).range(
        workspace.id,
        end=ledger_end,
        currency=currency,
    )
    balances = account_balances(accounts, posted)
    group_values: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "ledger": 0,
            "planned": 0,
            "recurring": 0,
            "subscription": 0,
            "commitment": 0,
            "buffer": 0,
        }
    )
    included: list[CalculationRecord] = []
    excluded: list[CalculationRecord] = []
    for account in accounts:
        group_values[account.currency_code]["ledger"] += balances.get(
            account.id, account.opening_balance_minor
        )
        group_values[account.currency_code]["buffer"] += account.financial_buffer_minor
        included.append(_record("financial_account", account.id, "ledger and buffer"))

    planned = PlannedTransactionRepository(session).range(
        workspace.id,
        start=range_start,
        end=range_end,
        currency=currency,
    )
    planned_rule_occurrences: set[tuple[UUID, datetime]] = set()
    planned_subscription_occurrences: set[tuple[UUID, datetime]] = set()
    for planned_item in planned:
        normalized = planned_item.planned_for.astimezone(UTC)
        if planned_item.recurring_rule_id is not None:
            planned_rule_occurrences.add((planned_item.recurring_rule_id, normalized))
        if planned_item.subscription_id is not None:
            planned_subscription_occurrences.add((planned_item.subscription_id, normalized))
        if planned_item.transaction_type == TransactionType.EXPENSE and planned_item.is_committed:
            group_values[planned_item.currency_code]["planned"] += planned_item.amount_minor
            included.append(
                _record("planned_transaction", planned_item.id, "committed planned expense")
            )
        else:
            excluded.append(
                _record(
                    "planned_transaction",
                    planned_item.id,
                    "not a committed expense",
                )
            )

    all_recurring_rules = RecurringTransactionRepository(session).all_active(workspace.id)
    for linked_rule in all_recurring_rules:
        if linked_rule.subscription_id is not None:
            excluded.append(
                _record(
                    "recurring_transaction",
                    linked_rule.id,
                    "represented by linked subscription",
                )
            )
    recurring_rules = [
        rule
        for rule in all_recurring_rules
        if rule.is_committed
        and rule.transaction_type == TransactionType.EXPENSE
        and rule.subscription_id is None
    ]
    for rule in recurring_rules:
        if currency is not None and rule.currency_code != currency:
            excluded.append(_record("recurring_transaction", rule.id, "currency filter"))
            continue
        amount = sum(
            rule.amount_minor
            for occurrence in _expand_rule(
                rule,
                rule.rrule,
                rule.starts_at,
                rule.ends_at,
                range_start,
                range_end,
            )
            if (rule.id, occurrence.astimezone(UTC)) not in planned_rule_occurrences
        )
        group_values[rule.currency_code]["recurring"] += amount
        included.append(
            _record("recurring_transaction", rule.id, f"committed recurrence total {amount}")
        )

    for subscription in SubscriptionRepository(session).all_active(workspace.id):
        if currency is not None and subscription.currency_code != currency:
            excluded.append(_record("subscription", subscription.id, "currency filter"))
            continue
        amount = sum(
            subscription.amount_minor
            for occurrence in _expand_rule(
                subscription,
                subscription.billing_rrule,
                subscription.starts_at,
                subscription.ends_at,
                range_start,
                range_end,
            )
            if (subscription.id, occurrence.astimezone(UTC)) not in planned_subscription_occurrences
        )
        group_values[subscription.currency_code]["subscription"] += amount
        included.append(_record("subscription", subscription.id, f"subscription total {amount}"))

    commitments = session.exec(
        select(Commitment).where(
            col(Commitment.workspace_id) == workspace.id,
            col(Commitment.deleted_at).is_(None),
            col(Commitment.status).in_((CommitmentStatus.PLANNED, CommitmentStatus.ACTIVE)),
            col(Commitment.planned_cost_minor).is_not(None),
        )
    ).all()
    for commitment in commitments:
        if commitment.currency_code is None or commitment.planned_cost_minor is None:
            continue
        if currency is not None and commitment.currency_code != currency:
            excluded.append(_record("commitment", commitment.id, "currency filter"))
            continue
        if commitment.starts_at is not None and not (
            range_start <= commitment.starts_at < range_end
        ):
            excluded.append(_record("commitment", commitment.id, "outside input date range"))
            continue
        group_values[commitment.currency_code]["commitment"] += commitment.planned_cost_minor
        included.append(_record("commitment", commitment.id, "active planned cost"))

    currencies = sorted(set(group_values) | ({currency} if currency else set()))
    groups: list[CommittedCurrencyGroup] = []
    for currency_code in currencies:
        values = group_values[currency_code]
        total = (
            values["planned"] + values["recurring"] + values["subscription"] + values["commitment"]
        )
        available = values["ledger"] - total
        groups.append(
            CommittedCurrencyGroup(
                currency=currency_code,
                ledger_balance_minor=values["ledger"],
                committed_planned_minor=values["planned"],
                committed_recurring_minor=values["recurring"],
                committed_subscription_minor=values["subscription"],
                committed_commitment_minor=values["commitment"],
                committed_total_minor=total,
                effectively_available_minor=available,
                financial_buffer_minor=values["buffer"],
                buffer_violation=available < values["buffer"],
            )
        )
    return CommittedBalanceReportResponse(
        metadata=_metadata(
            start=as_of,
            end=end_date,
            currency=currency,
            assumptions=[
                "ledger balance includes posted transactions through the as_of date",
                (
                    "committed amount includes flagged plans, active recurring expenses, "
                    "subscriptions, and active commitment costs"
                ),
                "unallocated commitment costs reduce the workspace currency balance",
                "no exchange-rate conversion is performed",
            ],
            included=included,
            excluded=excluded,
        ),
        groups=groups,
    )


def budget_consumption_report(
    session: Session,
    budget_id: UUID,
) -> BudgetConsumptionResponse:
    workspace = get_current_workspace(session)
    repository = BudgetRepository(session)
    budget = repository.get_active(workspace.id, budget_id)
    if budget is None:
        raise DomainNotFoundError("budget", budget_id)
    end_date = budget_end_date(budget)
    timezone_name = get_preferences(session).timezone
    range_start, range_end = utc_date_bounds(budget.start_date, end_date, timezone_name)
    limits = repository.limits_for([budget.id]).get(budget.id, [])
    limit_ids = {item.category_id for item in limits}
    categories = {
        item.id: item.name for item in FinanceCategoryRepository(session).all_active(workspace.id)
    }
    actual_by_category: dict[UUID, int] = defaultdict(int)
    planned_by_category: dict[UUID, int] = defaultdict(int)
    included: list[CalculationRecord] = []
    excluded: list[CalculationRecord] = []
    actual = FinanceTransactionRepository(session).range(
        workspace.id,
        start=range_start,
        end=range_end,
        currency=budget.currency_code,
    )
    for actual_item in actual:
        if (
            actual_item.transaction_type == TransactionType.EXPENSE
            and actual_item.category_id in limit_ids
        ):
            assert actual_item.category_id is not None
            actual_by_category[actual_item.category_id] += actual_item.amount_minor
            included.append(_record("transaction", actual_item.id, "budget actual spending"))
        else:
            excluded.append(_record("transaction", actual_item.id, "not covered by a budget limit"))
    planned = PlannedTransactionRepository(session).range(
        workspace.id,
        start=range_start,
        end=range_end,
        currency=budget.currency_code,
    )
    for planned_item in planned:
        if (
            planned_item.transaction_type == TransactionType.EXPENSE
            and planned_item.category_id in limit_ids
        ):
            assert planned_item.category_id is not None
            planned_by_category[planned_item.category_id] += planned_item.amount_minor
            included.append(
                _record("planned_transaction", planned_item.id, "budget planned spending")
            )
        else:
            excluded.append(
                _record(
                    "planned_transaction",
                    planned_item.id,
                    "not covered by a budget limit",
                )
            )
    rows: list[BudgetCategoryConsumptionResponse] = []
    for limit in limits:
        actual_amount = actual_by_category[limit.category_id]
        planned_amount = planned_by_category[limit.category_id]
        consumption = (
            actual_amount * 10_000 // limit.limit_minor
            if limit.limit_minor > 0
            else 10_000
            if actual_amount > 0
            else 0
        )
        rows.append(
            BudgetCategoryConsumptionResponse(
                category_id=limit.category_id,
                category_name=categories.get(limit.category_id, "Deleted category"),
                limit_minor=limit.limit_minor,
                actual_minor=actual_amount,
                planned_minor=planned_amount,
                remaining_after_actual_minor=limit.limit_minor - actual_amount,
                remaining_after_planned_minor=limit.limit_minor - actual_amount - planned_amount,
                consumption_basis_points=consumption,
            )
        )
    return BudgetConsumptionResponse(
        budget_id=budget.id,
        metadata=_metadata(
            start=budget.start_date,
            end=end_date,
            currency=budget.currency_code,
            assumptions=[
                "only expense categories with explicit limits are included",
                "actual and planned consumption are reported separately",
                "remaining values may be negative when a limit is exceeded",
            ],
            included=included,
            excluded=excluded,
        ),
        total_limit_minor=sum(item.limit_minor for item in rows),
        total_actual_minor=sum(item.actual_minor for item in rows),
        total_planned_minor=sum(item.planned_minor for item in rows),
        categories=rows,
    )
