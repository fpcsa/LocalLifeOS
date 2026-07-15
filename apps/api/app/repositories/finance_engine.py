from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models import (
    Budget,
    BudgetCategoryLimit,
    BudgetPeriod,
    CategoryKind,
    FinancialAccount,
    FinancialAccountType,
    Goal,
    GoalStatus,
    PlannedTransaction,
    PlannedTransactionStatus,
    RecurringTransactionRule,
    RecurringTransactionStatus,
    SavingsGoal,
    Subscription,
    SubscriptionPriceChange,
    SubscriptionStatus,
    Transaction,
    TransactionCategory,
    TransactionType,
)
from app.repositories.base import PageResult
from app.repositories.revisioned import RevisionedRepository

SortDirection = Literal["asc", "desc"]


def _order(column: ColumnElement[Any], direction: SortDirection) -> ColumnElement[Any]:
    return desc(column) if direction == "desc" else asc(column)


class FinanceAccountRepository(RevisionedRepository[FinancialAccount]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, FinancialAccount, "financial_account")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        query: str | None,
        currency: str | None,
        account_type: FinancialAccountType | None,
        order: SortDirection,
    ) -> PageResult[FinancialAccount]:
        filters: list[ColumnElement[bool]] = [
            col(FinancialAccount.workspace_id) == workspace_id,
            col(FinancialAccount.deleted_at).is_(None),
        ]
        if query:
            filters.append(col(FinancialAccount.name).ilike(f"%{query.strip()}%"))
        if currency:
            filters.append(col(FinancialAccount.currency_code) == currency)
        if account_type is not None:
            filters.append(col(FinancialAccount.account_type) == account_type)
        total = self.session.exec(
            select(func.count()).select_from(FinancialAccount).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(FinancialAccount)
                .where(*filters)
                .order_by(
                    _order(func.lower(col(FinancialAccount.name)), order), col(FinancialAccount.id)
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def all_active(self, workspace_id: UUID) -> list[FinancialAccount]:
        return list(
            self.session.exec(
                select(FinancialAccount).where(
                    col(FinancialAccount.workspace_id) == workspace_id,
                    col(FinancialAccount.deleted_at).is_(None),
                )
            ).all()
        )


class FinanceCategoryRepository(RevisionedRepository[TransactionCategory]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, TransactionCategory, "transaction_category")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        query: str | None,
        kind: CategoryKind | None,
        order: SortDirection,
    ) -> PageResult[TransactionCategory]:
        filters: list[ColumnElement[bool]] = [
            col(TransactionCategory.workspace_id) == workspace_id,
            col(TransactionCategory.deleted_at).is_(None),
        ]
        if query:
            filters.append(col(TransactionCategory.name).ilike(f"%{query.strip()}%"))
        if kind is not None:
            filters.append(col(TransactionCategory.kind) == kind)
        total = self.session.exec(
            select(func.count()).select_from(TransactionCategory).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(TransactionCategory)
                .where(*filters)
                .order_by(
                    _order(func.lower(col(TransactionCategory.name)), order),
                    col(TransactionCategory.id),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def all_active(self, workspace_id: UUID) -> list[TransactionCategory]:
        return list(
            self.session.exec(
                select(TransactionCategory).where(
                    col(TransactionCategory.workspace_id) == workspace_id,
                    col(TransactionCategory.deleted_at).is_(None),
                )
            ).all()
        )


class FinanceTransactionRepository(RevisionedRepository[Transaction]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Transaction, "transaction")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        query: str | None,
        account_id: UUID | None,
        category_id: UUID | None,
        transaction_type: TransactionType | None,
        currency: str | None,
        start: datetime | None,
        end: datetime | None,
        order: SortDirection,
    ) -> PageResult[Transaction]:
        filters = self._filters(
            workspace_id,
            account_id=account_id,
            category_id=category_id,
            transaction_type=transaction_type,
            currency=currency,
            start=start,
            end=end,
        )
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(col(Transaction.payee).ilike(pattern), col(Transaction.note).ilike(pattern))
            )
        total = self.session.exec(
            select(func.count()).select_from(Transaction).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(Transaction)
                .where(*filters)
                .order_by(
                    _order(cast(ColumnElement[Any], col(Transaction.occurred_at)), order),
                    col(Transaction.id),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def range(
        self,
        workspace_id: UUID,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        currency: str | None = None,
    ) -> list[Transaction]:
        filters = self._filters(
            workspace_id,
            account_id=None,
            category_id=None,
            transaction_type=None,
            currency=currency,
            start=start,
            end=end,
        )
        return list(
            self.session.exec(
                select(Transaction)
                .where(*filters)
                .order_by(col(Transaction.occurred_at), col(Transaction.id))
            ).all()
        )

    def for_account(self, workspace_id: UUID, account_id: UUID) -> list[Transaction]:
        return list(
            self.session.exec(
                select(Transaction)
                .where(
                    col(Transaction.workspace_id) == workspace_id,
                    col(Transaction.deleted_at).is_(None),
                    (col(Transaction.account_id) == account_id)
                    | (col(Transaction.transfer_account_id) == account_id),
                )
                .order_by(col(Transaction.occurred_at), col(Transaction.id))
            ).all()
        )

    def fingerprint_exists(
        self,
        workspace_id: UUID,
        fingerprint: str,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        statement = select(Transaction.id).where(
            col(Transaction.workspace_id) == workspace_id,
            col(Transaction.import_fingerprint) == fingerprint,
        )
        if exclude_id is not None:
            statement = statement.where(col(Transaction.id) != exclude_id)
        return self.session.exec(statement).first() is not None

    @staticmethod
    def _filters(
        workspace_id: UUID,
        *,
        account_id: UUID | None,
        category_id: UUID | None,
        transaction_type: TransactionType | None,
        currency: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [
            col(Transaction.workspace_id) == workspace_id,
            col(Transaction.deleted_at).is_(None),
        ]
        if account_id is not None:
            filters.append(
                (col(Transaction.account_id) == account_id)
                | (col(Transaction.transfer_account_id) == account_id)
            )
        if category_id is not None:
            filters.append(col(Transaction.category_id) == category_id)
        if transaction_type is not None:
            filters.append(col(Transaction.transaction_type) == transaction_type)
        if currency is not None:
            filters.append(col(Transaction.currency_code) == currency)
        if start is not None:
            filters.append(col(Transaction.occurred_at) >= start)
        if end is not None:
            filters.append(col(Transaction.occurred_at) < end)
        return filters


class PlannedTransactionRepository(RevisionedRepository[PlannedTransaction]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PlannedTransaction, "planned_transaction")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        account_id: UUID | None,
        status: PlannedTransactionStatus | None,
        currency: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> PageResult[PlannedTransaction]:
        filters = self._filters(
            workspace_id,
            account_id=account_id,
            status=status,
            currency=currency,
            start=start,
            end=end,
        )
        total = self.session.exec(
            select(func.count()).select_from(PlannedTransaction).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(PlannedTransaction)
                .where(*filters)
                .order_by(col(PlannedTransaction.planned_for), col(PlannedTransaction.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def range(
        self,
        workspace_id: UUID,
        *,
        start: datetime,
        end: datetime,
        currency: str | None = None,
        status: PlannedTransactionStatus | None = PlannedTransactionStatus.PLANNED,
    ) -> list[PlannedTransaction]:
        return list(
            self.session.exec(
                select(PlannedTransaction)
                .where(
                    *self._filters(
                        workspace_id,
                        account_id=None,
                        status=status,
                        currency=currency,
                        start=start,
                        end=end,
                    )
                )
                .order_by(col(PlannedTransaction.planned_for), col(PlannedTransaction.id))
            ).all()
        )

    def occurrence_keys(self, workspace_id: UUID, rule_id: UUID) -> set[str]:
        keys = self.session.exec(
            select(PlannedTransaction.occurrence_key).where(
                col(PlannedTransaction.workspace_id) == workspace_id,
                col(PlannedTransaction.recurring_rule_id) == rule_id,
                col(PlannedTransaction.occurrence_key).is_not(None),
            )
        ).all()
        return {key for key in keys if key is not None}

    def fingerprint_exists(
        self,
        workspace_id: UUID,
        fingerprint: str,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        statement = select(PlannedTransaction.id).where(
            col(PlannedTransaction.workspace_id) == workspace_id,
            col(PlannedTransaction.import_fingerprint) == fingerprint,
        )
        if exclude_id is not None:
            statement = statement.where(col(PlannedTransaction.id) != exclude_id)
        return self.session.exec(statement).first() is not None

    @staticmethod
    def _filters(
        workspace_id: UUID,
        *,
        account_id: UUID | None,
        status: PlannedTransactionStatus | None,
        currency: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [
            col(PlannedTransaction.workspace_id) == workspace_id,
            col(PlannedTransaction.deleted_at).is_(None),
        ]
        if account_id is not None:
            filters.append(
                (col(PlannedTransaction.account_id) == account_id)
                | (col(PlannedTransaction.transfer_account_id) == account_id)
            )
        if status is not None:
            filters.append(col(PlannedTransaction.status) == status)
        if currency is not None:
            filters.append(col(PlannedTransaction.currency_code) == currency)
        if start is not None:
            filters.append(col(PlannedTransaction.planned_for) >= start)
        if end is not None:
            filters.append(col(PlannedTransaction.planned_for) < end)
        return filters


class RecurringTransactionRepository(RevisionedRepository[RecurringTransactionRule]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RecurringTransactionRule, "recurring_transaction")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        status: RecurringTransactionStatus | None,
        currency: str | None,
    ) -> PageResult[RecurringTransactionRule]:
        filters: list[ColumnElement[bool]] = [
            col(RecurringTransactionRule.workspace_id) == workspace_id,
            col(RecurringTransactionRule.deleted_at).is_(None),
        ]
        if status is not None:
            filters.append(col(RecurringTransactionRule.status) == status)
        if currency is not None:
            filters.append(col(RecurringTransactionRule.currency_code) == currency)
        total = self.session.exec(
            select(func.count()).select_from(RecurringTransactionRule).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(RecurringTransactionRule)
                .where(*filters)
                .order_by(col(RecurringTransactionRule.starts_at), col(RecurringTransactionRule.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def all_active(self, workspace_id: UUID) -> list[RecurringTransactionRule]:
        return list(
            self.session.exec(
                select(RecurringTransactionRule).where(
                    col(RecurringTransactionRule.workspace_id) == workspace_id,
                    col(RecurringTransactionRule.deleted_at).is_(None),
                    col(RecurringTransactionRule.status) == RecurringTransactionStatus.ACTIVE,
                )
            ).all()
        )


class BudgetRepository(RevisionedRepository[Budget]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Budget, "budget")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        period: BudgetPeriod | None,
        currency: str | None,
    ) -> PageResult[Budget]:
        filters: list[ColumnElement[bool]] = [
            col(Budget.workspace_id) == workspace_id,
            col(Budget.deleted_at).is_(None),
        ]
        if period is not None:
            filters.append(col(Budget.period) == period)
        if currency is not None:
            filters.append(col(Budget.currency_code) == currency)
        total = self.session.exec(select(func.count()).select_from(Budget).where(*filters)).one()
        items = list(
            self.session.exec(
                select(Budget)
                .where(*filters)
                .order_by(col(Budget.start_date).desc(), col(Budget.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def limits_for(self, budget_ids: list[UUID]) -> dict[UUID, list[BudgetCategoryLimit]]:
        result: dict[UUID, list[BudgetCategoryLimit]] = {budget_id: [] for budget_id in budget_ids}
        if not budget_ids:
            return result
        limits = self.session.exec(
            select(BudgetCategoryLimit)
            .where(col(BudgetCategoryLimit.budget_id).in_(budget_ids))
            .order_by(col(BudgetCategoryLimit.created_at), col(BudgetCategoryLimit.id))
        ).all()
        for limit in limits:
            result.setdefault(limit.budget_id, []).append(limit)
        return result


class SavingsGoalRepository(RevisionedRepository[SavingsGoal]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, SavingsGoal, "savings_goal")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        status: GoalStatus | None,
        currency: str | None,
    ) -> PageResult[SavingsGoal]:
        filters: list[ColumnElement[bool]] = [
            col(SavingsGoal.workspace_id) == workspace_id,
            col(SavingsGoal.deleted_at).is_(None),
        ]
        if status is not None:
            filters.append(col(SavingsGoal.status) == status)
        if currency is not None:
            filters.append(col(SavingsGoal.currency_code) == currency)
        total = self.session.exec(
            select(func.count()).select_from(SavingsGoal).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(SavingsGoal)
                .where(*filters)
                .order_by(col(SavingsGoal.target_date), col(SavingsGoal.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)


class GoalRepository(RevisionedRepository[Goal]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Goal, "goal")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        status: GoalStatus | None,
    ) -> PageResult[Goal]:
        filters: list[ColumnElement[bool]] = [
            col(Goal.workspace_id) == workspace_id,
            col(Goal.deleted_at).is_(None),
        ]
        if status is not None:
            filters.append(col(Goal.status) == status)
        total = self.session.exec(select(func.count()).select_from(Goal).where(*filters)).one()
        items = list(
            self.session.exec(
                select(Goal)
                .where(*filters)
                .order_by(col(Goal.target_at), col(Goal.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)


class SubscriptionRepository(RevisionedRepository[Subscription]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Subscription, "subscription")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        status: SubscriptionStatus | None,
        currency: str | None,
    ) -> PageResult[Subscription]:
        filters: list[ColumnElement[bool]] = [
            col(Subscription.workspace_id) == workspace_id,
            col(Subscription.deleted_at).is_(None),
        ]
        if status is not None:
            filters.append(col(Subscription.status) == status)
        if currency is not None:
            filters.append(col(Subscription.currency_code) == currency)
        total = self.session.exec(
            select(func.count()).select_from(Subscription).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(Subscription)
                .where(*filters)
                .order_by(col(Subscription.starts_at), col(Subscription.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def all_active(self, workspace_id: UUID) -> list[Subscription]:
        return list(
            self.session.exec(
                select(Subscription).where(
                    col(Subscription.workspace_id) == workspace_id,
                    col(Subscription.deleted_at).is_(None),
                    col(Subscription.status) == SubscriptionStatus.ACTIVE,
                )
            ).all()
        )

    def price_changes_for(
        self,
        subscription_ids: list[UUID],
    ) -> dict[UUID, list[SubscriptionPriceChange]]:
        result: dict[UUID, list[SubscriptionPriceChange]] = {
            subscription_id: [] for subscription_id in subscription_ids
        }
        if not subscription_ids:
            return result
        changes = self.session.exec(
            select(SubscriptionPriceChange)
            .where(col(SubscriptionPriceChange.subscription_id).in_(subscription_ids))
            .order_by(
                col(SubscriptionPriceChange.detected_at).desc(),
                col(SubscriptionPriceChange.id),
            )
        ).all()
        for change in changes:
            result.setdefault(change.subscription_id, []).append(change)
        return result
