from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import (
    DomainConflictError,
    DomainNotFoundError,
    DomainValidationError,
)
from app.db.transactions import transaction
from app.models import (
    AutomationTriggerType,
    CommitmentEntityType,
    DomainEntityType,
    PlannedTransaction,
    PlannedTransactionStatus,
    Transaction,
    TransactionType,
)
from app.repositories.finance_engine import (
    FinanceTransactionRepository,
    PlannedTransactionRepository,
)
from app.schemas.common import DeletedResource
from app.schemas.finance import (
    AccountEffectResponse,
    FulfillPlannedTransactionRequest,
    PlannedTransactionCreateRequest,
    PlannedTransactionResponse,
    PlannedTransactionUpdateRequest,
    TransactionCreateRequest,
    TransactionResponse,
    TransactionUpdateRequest,
    TransferCreateRequest,
)
from app.services.automation import dispatch_automation_event
from app.services.domain_links import remove_commitment_entity_links
from app.services.events import emit_timeline_event
from app.services.finance_validation import validate_transaction_relationships
from app.services.workspace import get_current_workspace


def _transaction_response(item: Transaction) -> TransactionResponse:
    effects = [
        AccountEffectResponse(
            account_id=item.account_id,
            effect_minor=(
                item.amount_minor
                if item.transaction_type == TransactionType.INCOME
                else -item.amount_minor
            ),
        )
    ]
    if item.transfer_account_id is not None:
        effects.append(
            AccountEffectResponse(
                account_id=item.transfer_account_id,
                effect_minor=item.amount_minor,
            )
        )
    return TransactionResponse(
        **item.model_dump(exclude={"deleted_at"}),
        account_effects=effects,
    )


def _planned_response(item: PlannedTransaction) -> PlannedTransactionResponse:
    return PlannedTransactionResponse.model_validate(item)


def _ensure_actual_fingerprint_available(
    repository: FinanceTransactionRepository,
    workspace_id: UUID,
    fingerprint: str | None,
    *,
    exclude_id: UUID | None = None,
) -> None:
    if fingerprint and repository.fingerprint_exists(
        workspace_id, fingerprint, exclude_id=exclude_id
    ):
        raise DomainConflictError(
            "duplicate_import_fingerprint",
            "A transaction with this import fingerprint already exists.",
        )


def _ensure_planned_fingerprint_available(
    repository: PlannedTransactionRepository,
    workspace_id: UUID,
    fingerprint: str | None,
    *,
    exclude_id: UUID | None = None,
) -> None:
    if fingerprint and repository.fingerprint_exists(
        workspace_id, fingerprint, exclude_id=exclude_id
    ):
        raise DomainConflictError(
            "duplicate_import_fingerprint",
            "A planned transaction with this import fingerprint already exists.",
        )


def list_transactions(
    session: Session,
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
    order: str,
) -> tuple[list[TransactionResponse], int]:
    workspace = get_current_workspace(session)
    result = FinanceTransactionRepository(session).list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        currency=currency,
        start=start,
        end=end,
        order="asc" if order == "asc" else "desc",
    )
    return [_transaction_response(item) for item in result.items], result.total


def get_transaction(session: Session, transaction_id: UUID) -> TransactionResponse:
    workspace = get_current_workspace(session)
    item = FinanceTransactionRepository(session).get_active(workspace.id, transaction_id)
    if item is None:
        raise DomainNotFoundError("transaction", transaction_id)
    return _transaction_response(item)


def create_finance_transaction(
    session: Session,
    create_data: TransactionCreateRequest,
) -> TransactionResponse:
    workspace = get_current_workspace(session)
    repository = FinanceTransactionRepository(session)
    validate_transaction_relationships(
        session,
        workspace.id,
        account_id=create_data.account_id,
        transfer_account_id=create_data.transfer_account_id,
        category_id=create_data.category_id,
        transaction_type=create_data.transaction_type,
        currency_code=create_data.currency_code,
    )
    _ensure_actual_fingerprint_available(repository, workspace.id, create_data.import_fingerprint)
    with transaction(session):
        item = repository.add(Transaction(workspace_id=workspace.id, **create_data.model_dump()))
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action=f"transaction_{item.transaction_type.value}_created",
            title=(
                f"{item.transaction_type.value.title()} recorded: "
                f"{item.amount_minor} {item.currency_code}"
            ),
            payload={"amount_minor": item.amount_minor, "currency": item.currency_code},
        )
    dispatch_automation_event(
        session,
        AutomationTriggerType.TRANSACTION_CREATED,
        context={
            "entity_type": DomainEntityType.TRANSACTION.value,
            "entity_id": str(item.id),
            "account_id": str(item.account_id),
            "category_id": str(item.category_id) if item.category_id else None,
            "transaction_type": item.transaction_type.value,
            "amount_minor": item.amount_minor,
            "currency_code": item.currency_code,
            "payee": item.payee,
        },
        source_key=f"transaction:{item.id}",
    )
    return _transaction_response(item)


def create_transfer(
    session: Session,
    create_data: TransferCreateRequest,
) -> TransactionResponse:
    return create_finance_transaction(
        session,
        TransactionCreateRequest(
            account_id=create_data.source_account_id,
            transfer_account_id=create_data.destination_account_id,
            transaction_type=TransactionType.TRANSFER,
            amount_minor=create_data.amount_minor,
            currency_code=create_data.currency_code,
            occurred_at=create_data.occurred_at,
            payee=create_data.payee,
            note=create_data.note,
            external_id=create_data.external_id,
            import_fingerprint=create_data.import_fingerprint,
        ),
    )


def update_finance_transaction(
    session: Session,
    transaction_id: UUID,
    update_data: TransactionUpdateRequest,
) -> TransactionResponse:
    workspace = get_current_workspace(session)
    repository = FinanceTransactionRepository(session)
    current = repository.get_active(workspace.id, transaction_id)
    if current is None:
        raise DomainNotFoundError("transaction", transaction_id)
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one transaction field is required.")
    if current.transaction_type == TransactionType.TRANSFER and "category_id" in values:
        raise DomainValidationError("transfer_category", "Transfers cannot have a category.")
    category_id = values.get("category_id", current.category_id)
    validate_transaction_relationships(
        session,
        workspace.id,
        account_id=current.account_id,
        transfer_account_id=current.transfer_account_id,
        category_id=category_id,
        transaction_type=current.transaction_type,
        currency_code=current.currency_code,
    )
    fingerprint = values.get("import_fingerprint", current.import_fingerprint)
    _ensure_actual_fingerprint_available(
        repository,
        workspace.id,
        fingerprint,
        exclude_id=transaction_id,
    )
    with transaction(session):
        item = repository.update(workspace.id, transaction_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="transaction_updated",
            title=f"Transaction updated: {item.amount_minor} {item.currency_code}",
            payload={"fields": sorted(values)},
        )
    return _transaction_response(item)


def delete_finance_transaction(
    session: Session,
    transaction_id: UUID,
    revision: int,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = FinanceTransactionRepository(session)
    current = repository.get_active(workspace.id, transaction_id)
    if current is None:
        raise DomainNotFoundError("transaction", transaction_id)
    fulfilled_plan = session.exec(
        select(PlannedTransaction.id).where(
            col(PlannedTransaction.workspace_id) == workspace.id,
            col(PlannedTransaction.deleted_at).is_(None),
            col(PlannedTransaction.actual_transaction_id) == transaction_id,
        )
    ).first()
    if fulfilled_plan is not None:
        raise DomainConflictError(
            "transaction_fulfills_plan",
            "A transaction that fulfills a planned transaction is retained for auditability.",
            {"planned_transaction_id": str(fulfilled_plan)},
        )
    with transaction(session):
        remove_commitment_entity_links(
            session,
            workspace.id,
            CommitmentEntityType.TRANSACTION,
            transaction_id,
        )
        item = repository.soft_delete(workspace.id, transaction_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="transaction_deleted",
            title=f"Transaction deleted: {item.amount_minor} {item.currency_code}",
        )
    return DeletedResource(id=transaction_id)


def list_planned_transactions(
    session: Session,
    *,
    page: int,
    page_size: int,
    account_id: UUID | None,
    status: PlannedTransactionStatus | None,
    currency: str | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[PlannedTransactionResponse], int]:
    workspace = get_current_workspace(session)
    result = PlannedTransactionRepository(session).list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        account_id=account_id,
        status=status,
        currency=currency,
        start=start,
        end=end,
    )
    return [_planned_response(item) for item in result.items], result.total


def get_planned_transaction(
    session: Session,
    planned_id: UUID,
) -> PlannedTransactionResponse:
    workspace = get_current_workspace(session)
    item = PlannedTransactionRepository(session).get_active(workspace.id, planned_id)
    if item is None:
        raise DomainNotFoundError("planned_transaction", planned_id)
    return _planned_response(item)


def create_planned_transaction(
    session: Session,
    create_data: PlannedTransactionCreateRequest,
) -> PlannedTransactionResponse:
    workspace = get_current_workspace(session)
    repository = PlannedTransactionRepository(session)
    validate_transaction_relationships(
        session,
        workspace.id,
        account_id=create_data.account_id,
        transfer_account_id=create_data.transfer_account_id,
        category_id=create_data.category_id,
        transaction_type=create_data.transaction_type,
        currency_code=create_data.currency_code,
        subscription_id=create_data.subscription_id,
    )
    _ensure_planned_fingerprint_available(repository, workspace.id, create_data.import_fingerprint)
    with transaction(session):
        item = repository.add(
            PlannedTransaction(
                workspace_id=workspace.id,
                status=PlannedTransactionStatus.PLANNED,
                **create_data.model_dump(),
            )
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="planned_transaction_created",
            title=f"Planned transaction created: {item.amount_minor} {item.currency_code}",
            payload={"finance_resource": "planned_transaction"},
        )
    return _planned_response(item)


def update_planned_transaction(
    session: Session,
    planned_id: UUID,
    update_data: PlannedTransactionUpdateRequest,
) -> PlannedTransactionResponse:
    workspace = get_current_workspace(session)
    repository = PlannedTransactionRepository(session)
    current = repository.get_active(workspace.id, planned_id)
    if current is None:
        raise DomainNotFoundError("planned_transaction", planned_id)
    if current.status != PlannedTransactionStatus.PLANNED:
        raise DomainConflictError(
            "planned_transaction_closed",
            "Only planned transactions can be edited.",
        )
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError(
            "empty_update", "At least one planned transaction field is required."
        )
    category_id = values.get("category_id", current.category_id)
    validate_transaction_relationships(
        session,
        workspace.id,
        account_id=current.account_id,
        transfer_account_id=current.transfer_account_id,
        category_id=category_id,
        transaction_type=current.transaction_type,
        currency_code=current.currency_code,
        subscription_id=current.subscription_id,
    )
    fingerprint = values.get("import_fingerprint", current.import_fingerprint)
    _ensure_planned_fingerprint_available(
        repository,
        workspace.id,
        fingerprint,
        exclude_id=planned_id,
    )
    with transaction(session):
        item = repository.update(workspace.id, planned_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="planned_transaction_updated",
            title=f"Planned transaction updated: {item.amount_minor} {item.currency_code}",
            payload={"finance_resource": "planned_transaction", "fields": sorted(values)},
        )
    return _planned_response(item)


def cancel_planned_transaction(
    session: Session,
    planned_id: UUID,
    revision: int,
) -> PlannedTransactionResponse:
    workspace = get_current_workspace(session)
    repository = PlannedTransactionRepository(session)
    current = repository.get_active(workspace.id, planned_id)
    if current is None:
        raise DomainNotFoundError("planned_transaction", planned_id)
    if current.status != PlannedTransactionStatus.PLANNED:
        raise DomainConflictError(
            "planned_transaction_closed",
            "Only planned transactions can be cancelled.",
        )
    with transaction(session):
        item = repository.update(
            workspace.id,
            planned_id,
            revision,
            {"status": PlannedTransactionStatus.CANCELLED},
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="planned_transaction_cancelled",
            title=f"Planned transaction cancelled: {item.amount_minor} {item.currency_code}",
            payload={"finance_resource": "planned_transaction"},
        )
    return _planned_response(item)


def fulfill_planned_transaction(
    session: Session,
    planned_id: UUID,
    request: FulfillPlannedTransactionRequest,
) -> tuple[PlannedTransactionResponse, TransactionResponse]:
    workspace = get_current_workspace(session)
    planned_repository = PlannedTransactionRepository(session)
    current = planned_repository.get_active(workspace.id, planned_id)
    if current is None:
        raise DomainNotFoundError("planned_transaction", planned_id)
    if current.status != PlannedTransactionStatus.PLANNED:
        raise DomainConflictError(
            "planned_transaction_closed",
            "Only planned transactions can be fulfilled.",
        )
    actual_repository = FinanceTransactionRepository(session)
    amount = request.amount_minor or current.amount_minor
    with transaction(session):
        actual = actual_repository.add(
            Transaction(
                workspace_id=workspace.id,
                account_id=current.account_id,
                transfer_account_id=current.transfer_account_id,
                category_id=current.category_id,
                transaction_type=current.transaction_type,
                amount_minor=amount,
                currency_code=current.currency_code,
                occurred_at=request.occurred_at,
                payee=request.payee if request.payee is not None else current.payee,
                note=request.note if request.note is not None else current.note,
            )
        )
        planned = planned_repository.update(
            workspace.id,
            planned_id,
            request.revision,
            {
                "status": PlannedTransactionStatus.FULFILLED,
                "actual_transaction_id": actual.id,
            },
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=actual.id,
            action="planned_transaction_fulfilled",
            title=f"Planned transaction fulfilled: {amount} {actual.currency_code}",
            payload={"planned_transaction_id": str(planned_id)},
        )
    return _planned_response(planned), _transaction_response(actual)


def delete_planned_transaction(
    session: Session,
    planned_id: UUID,
    revision: int,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = PlannedTransactionRepository(session)
    current = repository.get_active(workspace.id, planned_id)
    if current is None:
        raise DomainNotFoundError("planned_transaction", planned_id)
    if current.status == PlannedTransactionStatus.FULFILLED:
        raise DomainConflictError(
            "planned_transaction_fulfilled",
            "Fulfilled planned transactions are retained for auditability.",
        )
    with transaction(session):
        remove_commitment_entity_links(
            session,
            workspace.id,
            CommitmentEntityType.PLANNED_TRANSACTION,
            planned_id,
        )
        deleted = repository.soft_delete(workspace.id, planned_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=deleted.id,
            action="planned_transaction_deleted",
            title=f"Planned transaction deleted: {deleted.amount_minor} {deleted.currency_code}",
            payload={"finance_resource": "planned_transaction"},
        )
    return DeletedResource(id=planned_id)
