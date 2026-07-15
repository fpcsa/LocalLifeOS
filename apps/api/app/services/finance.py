from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import CategoryKind, Transaction, TransactionCategory, TransactionType
from app.repositories import FinancialAccountRepository, TransactionRepository
from app.schemas.domain import TransactionCreate


def create_transaction(
    session: Session,
    workspace_id: UUID,
    create_data: TransactionCreate,
) -> Transaction:
    account_repository = FinancialAccountRepository(session)
    source = account_repository.get_active(workspace_id, create_data.account_id)
    if source is None:
        raise DomainNotFoundError("financial_account", create_data.account_id)
    if source.currency_code != create_data.currency_code:
        raise DomainValidationError(
            "currency_mismatch",
            "Transaction currency must match the source account.",
        )

    if create_data.transaction_type == TransactionType.TRANSFER:
        destination_id = create_data.transfer_account_id
        if destination_id is None:
            raise DomainValidationError(
                "missing_transfer_account",
                "Transfers require a destination account.",
            )
        destination = account_repository.get_active(
            workspace_id,
            destination_id,
        )
        if destination is None:
            raise DomainNotFoundError("financial_account", create_data.transfer_account_id)
        if destination.currency_code != source.currency_code:
            raise DomainValidationError(
                "transfer_currency_mismatch",
                "Transfers require source and destination accounts with the same currency.",
            )

    if create_data.category_id is not None:
        category = session.exec(
            select(TransactionCategory).where(
                col(TransactionCategory.id) == create_data.category_id,
                col(TransactionCategory.workspace_id) == workspace_id,
                col(TransactionCategory.deleted_at).is_(None),
            )
        ).first()
        if category is None:
            raise DomainNotFoundError("transaction_category", create_data.category_id)
        expected_kind = (
            CategoryKind.INCOME
            if create_data.transaction_type == TransactionType.INCOME
            else CategoryKind.EXPENSE
        )
        if category.kind != expected_kind:
            raise DomainValidationError(
                "category_type_mismatch",
                "Transaction category does not match the transaction type.",
            )

    values = create_data.model_dump()
    with transaction(session):
        created = TransactionRepository(session).add(
            Transaction(workspace_id=workspace_id, **values)
        )
    return created
