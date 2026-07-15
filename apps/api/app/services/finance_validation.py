from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.models import (
    CategoryKind,
    FinancialAccount,
    Subscription,
    TransactionCategory,
    TransactionType,
)


def require_account(session: Session, workspace_id: UUID, account_id: UUID) -> FinancialAccount:
    account = session.get(FinancialAccount, account_id)
    if account is None or account.workspace_id != workspace_id or account.deleted_at is not None:
        raise DomainNotFoundError("financial_account", account_id)
    return account


def require_category(
    session: Session,
    workspace_id: UUID,
    category_id: UUID,
) -> TransactionCategory:
    category = session.get(TransactionCategory, category_id)
    if category is None or category.workspace_id != workspace_id or category.deleted_at is not None:
        raise DomainNotFoundError("transaction_category", category_id)
    return category


def require_subscription(
    session: Session,
    workspace_id: UUID,
    subscription_id: UUID,
) -> Subscription:
    subscription = session.get(Subscription, subscription_id)
    if (
        subscription is None
        or subscription.workspace_id != workspace_id
        or subscription.deleted_at is not None
    ):
        raise DomainNotFoundError("subscription", subscription_id)
    return subscription


def validate_transaction_relationships(
    session: Session,
    workspace_id: UUID,
    *,
    account_id: UUID,
    transfer_account_id: UUID | None,
    category_id: UUID | None,
    transaction_type: TransactionType,
    currency_code: str,
    subscription_id: UUID | None = None,
) -> None:
    account = require_account(session, workspace_id, account_id)
    if account.currency_code != currency_code:
        raise DomainValidationError(
            "currency_mismatch",
            "Transaction currency must match the source account.",
        )
    if transaction_type == TransactionType.TRANSFER:
        if transfer_account_id is None:
            raise DomainValidationError(
                "missing_transfer_account",
                "Transfers require a destination account.",
            )
        if transfer_account_id == account_id:
            raise DomainValidationError(
                "same_transfer_account",
                "Transfer accounts must be different.",
            )
        destination = require_account(session, workspace_id, transfer_account_id)
        if destination.currency_code != currency_code:
            raise DomainValidationError(
                "transfer_currency_mismatch",
                "Transfers require source and destination accounts with the same currency.",
            )
        if category_id is not None:
            raise DomainValidationError(
                "transfer_category",
                "Transfers cannot use an income or expense category.",
            )
    elif transfer_account_id is not None:
        raise DomainValidationError(
            "unexpected_transfer_account",
            "Only transfers can specify a destination account.",
        )
    if category_id is not None:
        category = require_category(session, workspace_id, category_id)
        expected = (
            CategoryKind.INCOME
            if transaction_type == TransactionType.INCOME
            else CategoryKind.EXPENSE
        )
        if category.kind != expected:
            raise DomainValidationError(
                "category_type_mismatch",
                "Transaction category does not match the transaction type.",
            )
    if subscription_id is not None:
        subscription = require_subscription(session, workspace_id, subscription_id)
        if subscription.account_id != account_id or subscription.currency_code != currency_code:
            raise DomainValidationError(
                "subscription_transaction_mismatch",
                "Subscription, source account, and currency must match.",
            )
        if transaction_type != TransactionType.EXPENSE:
            raise DomainValidationError(
                "subscription_transaction_type",
                "Subscription-linked records must be expenses.",
            )
        if subscription.category_id != category_id:
            raise DomainValidationError(
                "subscription_category_mismatch",
                "Subscription-linked records must use the subscription category.",
            )
