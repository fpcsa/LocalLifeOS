from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from app.models import Budget, BudgetPeriod, FinancialAccount, Transaction, TransactionType


def transaction_effect(transaction: Transaction, account_id: UUID) -> int:
    if transaction.transaction_type == TransactionType.INCOME:
        return transaction.amount_minor if transaction.account_id == account_id else 0
    if transaction.transaction_type == TransactionType.EXPENSE:
        return -transaction.amount_minor if transaction.account_id == account_id else 0
    if transaction.account_id == account_id:
        return -transaction.amount_minor
    if transaction.transfer_account_id == account_id:
        return transaction.amount_minor
    return 0


def account_balances(
    accounts: list[FinancialAccount],
    transactions: list[Transaction],
) -> dict[UUID, int]:
    balances = {account.id: account.opening_balance_minor for account in accounts}
    for item in transactions:
        balances[item.account_id] = balances.get(item.account_id, 0) + transaction_effect(
            item, item.account_id
        )
        if item.transfer_account_id is not None:
            balances[item.transfer_account_id] = balances.get(
                item.transfer_account_id, 0
            ) + transaction_effect(item, item.transfer_account_id)
    return balances


def utc_date_bounds(
    start: date,
    end: date,
    timezone_name: str,
) -> tuple[datetime, datetime]:
    if end < start:
        raise ValueError("end date cannot be before start date")
    timezone = ZoneInfo(timezone_name)
    starts_at = datetime.combine(start, time.min, tzinfo=timezone).astimezone(UTC)
    ends_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone).astimezone(UTC)
    return starts_at, ends_at


def budget_end_date(budget: Budget) -> date:
    if budget.end_date is not None:
        return budget.end_date
    if budget.period == BudgetPeriod.WEEKLY:
        return budget.start_date + timedelta(days=6)
    if budget.period == BudgetPeriod.MONTHLY:
        return budget.start_date + relativedelta(months=1) - timedelta(days=1)
    if budget.period == BudgetPeriod.QUARTERLY:
        return budget.start_date + relativedelta(months=3) - timedelta(days=1)
    if budget.period == BudgetPeriod.YEARLY:
        return budget.start_date + relativedelta(years=1) - timedelta(days=1)
    raise ValueError("custom budgets require an end date")


def month_keys(start: date, end: date) -> list[str]:
    cursor = start.replace(day=1)
    end_month = end.replace(day=1)
    keys: list[str] = []
    while cursor <= end_month:
        keys.append(cursor.strftime("%Y-%m"))
        cursor += relativedelta(months=1)
    return keys
