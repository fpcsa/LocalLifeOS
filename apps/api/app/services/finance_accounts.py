from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    DomainEntityType,
    FinancialAccount,
    FinancialAccountType,
    PlannedTransaction,
    RecurringTransactionRule,
    SavingsGoal,
    Subscription,
    Transaction,
)
from app.repositories.finance_engine import FinanceAccountRepository, FinanceTransactionRepository
from app.schemas.common import DeletedResource
from app.schemas.finance import (
    AccountLedgerResponse,
    FinancialAccountCreateRequest,
    FinancialAccountResponse,
    FinancialAccountUpdateRequest,
    LedgerEntryResponse,
)
from app.services.events import emit_timeline_event
from app.services.finance_calculations import account_balances, transaction_effect
from app.services.workspace import get_current_workspace


def _account_responses(
    session: Session,
    accounts: list[FinancialAccount],
) -> list[FinancialAccountResponse]:
    if not accounts:
        return []
    workspace_id = accounts[0].workspace_id
    transactions = FinanceTransactionRepository(session).range(workspace_id)
    balances = account_balances(accounts, transactions)
    return [
        FinancialAccountResponse(
            **account.model_dump(exclude={"deleted_at"}),
            balance_minor=balances.get(account.id, account.opening_balance_minor),
            below_financial_buffer=(
                balances.get(account.id, account.opening_balance_minor)
                < account.financial_buffer_minor
            ),
        )
        for account in accounts
    ]


def list_accounts(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    currency: str | None,
    account_type: FinancialAccountType | None,
    order: str,
) -> tuple[list[FinancialAccountResponse], int]:
    workspace = get_current_workspace(session)
    repository = FinanceAccountRepository(session)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        currency=currency,
        account_type=account_type,
        order="asc" if order == "asc" else "desc",
    )
    return _account_responses(session, result.items), result.total


def get_account(session: Session, account_id: UUID) -> FinancialAccountResponse:
    workspace = get_current_workspace(session)
    account = FinanceAccountRepository(session).get_active(workspace.id, account_id)
    if account is None:
        raise DomainNotFoundError("financial_account", account_id)
    return _account_responses(session, [account])[0]


def create_account(
    session: Session,
    create_data: FinancialAccountCreateRequest,
) -> FinancialAccountResponse:
    workspace = get_current_workspace(session)
    repository = FinanceAccountRepository(session)
    with transaction(session):
        account = repository.add(
            FinancialAccount(workspace_id=workspace.id, **create_data.model_dump())
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.FINANCIAL_ACCOUNT,
            entity_id=account.id,
            action="financial_account_created",
            title=f"Financial account created: {account.name}",
        )
    return _account_responses(session, [account])[0]


def update_account(
    session: Session,
    account_id: UUID,
    update_data: FinancialAccountUpdateRequest,
) -> FinancialAccountResponse:
    workspace = get_current_workspace(session)
    repository = FinanceAccountRepository(session)
    if repository.get_active(workspace.id, account_id) is None:
        raise DomainNotFoundError("financial_account", account_id)
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one account field is required.")
    with transaction(session):
        account = repository.update(workspace.id, account_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.FINANCIAL_ACCOUNT,
            entity_id=account.id,
            action="financial_account_updated",
            title=f"Financial account updated: {account.name}",
            payload={"fields": sorted(values)},
        )
    return _account_responses(session, [account])[0]


def delete_account(session: Session, account_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = FinanceAccountRepository(session)
    account = repository.get_active(workspace.id, account_id)
    if account is None:
        raise DomainNotFoundError("financial_account", account_id)
    references = 0
    for model in (Transaction, PlannedTransaction, RecurringTransactionRule):
        references += session.exec(
            select(func.count())
            .select_from(model)
            .where(
                col(model.workspace_id) == workspace.id,
                col(model.deleted_at).is_(None),
                or_(
                    col(model.account_id) == account_id,
                    col(model.transfer_account_id) == account_id,
                ),
            )
        ).one()
    references += session.exec(
        select(func.count())
        .select_from(Subscription)
        .where(
            col(Subscription.workspace_id) == workspace.id,
            col(Subscription.deleted_at).is_(None),
            col(Subscription.account_id) == account_id,
        )
    ).one()
    references += session.exec(
        select(func.count())
        .select_from(SavingsGoal)
        .where(
            col(SavingsGoal.workspace_id) == workspace.id,
            col(SavingsGoal.deleted_at).is_(None),
            col(SavingsGoal.account_id) == account_id,
        )
    ).one()
    if references:
        raise DomainConflictError(
            "account_in_use",
            "The account cannot be deleted while active finance records reference it.",
            {"reference_count": references},
        )
    with transaction(session):
        deleted = repository.soft_delete(workspace.id, account_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.FINANCIAL_ACCOUNT,
            entity_id=deleted.id,
            action="financial_account_deleted",
            title=f"Financial account deleted: {deleted.name}",
        )
    return DeletedResource(id=account_id)


def get_account_ledger(session: Session, account_id: UUID) -> AccountLedgerResponse:
    workspace = get_current_workspace(session)
    account = FinanceAccountRepository(session).get_active(workspace.id, account_id)
    if account is None:
        raise DomainNotFoundError("financial_account", account_id)
    running = account.opening_balance_minor
    entries: list[LedgerEntryResponse] = []
    for item in FinanceTransactionRepository(session).for_account(workspace.id, account_id):
        effect = transaction_effect(item, account_id)
        running += effect
        entries.append(
            LedgerEntryResponse(
                transaction_id=item.id,
                transaction_type=item.transaction_type,
                occurred_at=item.occurred_at,
                payee=item.payee,
                effect_minor=effect,
                balance_after_minor=running,
            )
        )
    response = _account_responses(session, [account])[0]
    return AccountLedgerResponse(account=response, entries=entries)
