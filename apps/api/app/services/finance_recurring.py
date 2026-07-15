from __future__ import annotations

from datetime import UTC
from uuid import UUID

from sqlmodel import Session

from app.core.exceptions import (
    DomainConflictError,
    DomainNotFoundError,
    DomainValidationError,
)
from app.db.transactions import transaction
from app.models import (
    DomainEntityType,
    PlannedTransaction,
    PlannedTransactionStatus,
    RecurringTransactionRule,
    RecurringTransactionStatus,
    SubscriptionStatus,
    TransactionType,
)
from app.repositories.finance_engine import (
    PlannedTransactionRepository,
    RecurringTransactionRepository,
)
from app.schemas.common import DeletedResource
from app.schemas.finance import (
    PlannedTransactionResponse,
    RecurringGenerationRequest,
    RecurringTransactionCreateRequest,
    RecurringTransactionResponse,
    RecurringTransactionUpdateRequest,
)
from app.services.events import emit_timeline_event
from app.services.finance_validation import require_subscription, validate_transaction_relationships
from app.services.workspace import get_current_workspace
from app.utils.recurrence import expand_recurrence


def _response(item: RecurringTransactionRule) -> RecurringTransactionResponse:
    return RecurringTransactionResponse.model_validate(item)


def list_recurring_transactions(
    session: Session,
    *,
    page: int,
    page_size: int,
    status: RecurringTransactionStatus | None,
    currency: str | None,
) -> tuple[list[RecurringTransactionResponse], int]:
    workspace = get_current_workspace(session)
    result = RecurringTransactionRepository(session).list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        status=status,
        currency=currency,
    )
    return [_response(item) for item in result.items], result.total


def get_recurring_transaction(
    session: Session,
    rule_id: UUID,
) -> RecurringTransactionResponse:
    workspace = get_current_workspace(session)
    item = RecurringTransactionRepository(session).get_active(workspace.id, rule_id)
    if item is None:
        raise DomainNotFoundError("recurring_transaction", rule_id)
    return _response(item)


def create_recurring_transaction(
    session: Session,
    create_data: RecurringTransactionCreateRequest,
) -> RecurringTransactionResponse:
    workspace = get_current_workspace(session)
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
    repository = RecurringTransactionRepository(session)
    values = create_data.model_dump()
    if create_data.subscription_id is not None:
        subscription = require_subscription(session, workspace.id, create_data.subscription_id)
        values.update(
            account_id=subscription.account_id,
            transfer_account_id=None,
            category_id=subscription.category_id,
            transaction_type=TransactionType.EXPENSE,
            amount_minor=subscription.amount_minor,
            currency_code=subscription.currency_code,
            rrule=subscription.billing_rrule,
            starts_at=subscription.starts_at,
            ends_at=subscription.ends_at,
        )
    with transaction(session):
        item = repository.add(
            RecurringTransactionRule(
                workspace_id=workspace.id,
                status=RecurringTransactionStatus.ACTIVE,
                **values,
            )
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="recurring_transaction_created",
            title=f"Recurring transaction created: {item.name}",
            payload={"finance_resource": "recurring_transaction"},
        )
    return _response(item)


def update_recurring_transaction(
    session: Session,
    rule_id: UUID,
    update_data: RecurringTransactionUpdateRequest,
) -> RecurringTransactionResponse:
    workspace = get_current_workspace(session)
    repository = RecurringTransactionRepository(session)
    current = repository.get_active(workspace.id, rule_id)
    if current is None:
        raise DomainNotFoundError("recurring_transaction", rule_id)
    if current.status == RecurringTransactionStatus.ENDED:
        raise DomainConflictError(
            "recurring_transaction_ended",
            "Ended recurrence rules cannot be edited.",
        )
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError(
            "empty_update", "At least one recurring transaction field is required."
        )
    if current.subscription_id is not None and {
        "amount_minor",
        "rrule",
        "starts_at",
        "ends_at",
    }.intersection(values):
        raise DomainConflictError(
            "subscription_controls_recurrence",
            "Update the linked subscription to change its amount or billing schedule.",
        )
    starts_at = values.get("starts_at", current.starts_at)
    ends_at = values.get("ends_at", current.ends_at)
    if ends_at is not None and ends_at < starts_at:
        raise DomainValidationError(
            "invalid_recurrence_range", "ends_at cannot be before starts_at."
        )
    with transaction(session):
        item = repository.update(workspace.id, rule_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="recurring_transaction_updated",
            title=f"Recurring transaction updated: {item.name}",
            payload={"finance_resource": "recurring_transaction", "fields": sorted(values)},
        )
    return _response(item)


def set_recurring_status(
    session: Session,
    rule_id: UUID,
    revision: int,
    status: RecurringTransactionStatus,
) -> RecurringTransactionResponse:
    workspace = get_current_workspace(session)
    repository = RecurringTransactionRepository(session)
    current = repository.get_active(workspace.id, rule_id)
    if current is None:
        raise DomainNotFoundError("recurring_transaction", rule_id)
    if current.status == RecurringTransactionStatus.ENDED:
        raise DomainConflictError(
            "recurring_transaction_ended",
            "Ended recurrence rules cannot be resumed or paused.",
        )
    if status == RecurringTransactionStatus.ENDED or status in {
        RecurringTransactionStatus.ACTIVE,
        RecurringTransactionStatus.PAUSED,
    }:
        with transaction(session):
            item = repository.update(workspace.id, rule_id, revision, {"status": status})
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TRANSACTION,
                entity_id=item.id,
                action=f"recurring_transaction_{status.value}",
                title=f"Recurring transaction {status.value}: {item.name}",
                payload={"finance_resource": "recurring_transaction"},
            )
        return _response(item)
    raise DomainValidationError("invalid_recurring_status", "Unsupported recurrence status.")


def generate_recurring_occurrences(
    session: Session,
    rule_id: UUID,
    request: RecurringGenerationRequest,
) -> list[PlannedTransactionResponse]:
    workspace = get_current_workspace(session)
    rule = RecurringTransactionRepository(session).get_active(workspace.id, rule_id)
    if rule is None:
        raise DomainNotFoundError("recurring_transaction", rule_id)
    if rule.status != RecurringTransactionStatus.ACTIVE:
        raise DomainConflictError(
            "recurring_transaction_inactive",
            "Only active recurrence rules generate planned transactions.",
        )
    subscription = None
    if rule.subscription_id is not None:
        subscription = require_subscription(session, workspace.id, rule.subscription_id)
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise DomainConflictError(
                "subscription_inactive",
                "A recurrence linked to an inactive subscription cannot generate plans.",
            )
    recurrence_rule = subscription.billing_rrule if subscription is not None else rule.rrule
    recurrence_start = subscription.starts_at if subscription is not None else rule.starts_at
    recurrence_end = subscription.ends_at if subscription is not None else rule.ends_at
    try:
        occurrences = expand_recurrence(
            recurrence_rule,
            dtstart=recurrence_start,
            range_start=max(request.start, recurrence_start),
            range_end=request.end,
        )
    except ValueError as exc:
        raise DomainValidationError("invalid_recurrence", str(exc)) from exc
    if recurrence_end is not None:
        occurrences = [occurrence for occurrence in occurrences if occurrence <= recurrence_end]

    planned_repository = PlannedTransactionRepository(session)
    existing_keys = planned_repository.occurrence_keys(workspace.id, rule.id)
    created: list[PlannedTransaction] = []
    with transaction(session):
        for occurrence in occurrences:
            key = f"{rule.id}:{occurrence.astimezone(UTC).isoformat()}"
            if key in existing_keys:
                continue
            item = planned_repository.add(
                PlannedTransaction(
                    workspace_id=workspace.id,
                    account_id=subscription.account_id
                    if subscription is not None
                    else rule.account_id,
                    transfer_account_id=None
                    if subscription is not None
                    else rule.transfer_account_id,
                    category_id=subscription.category_id
                    if subscription is not None
                    else rule.category_id,
                    recurring_rule_id=rule.id,
                    subscription_id=rule.subscription_id,
                    transaction_type=(
                        TransactionType.EXPENSE
                        if subscription is not None
                        else rule.transaction_type
                    ),
                    amount_minor=subscription.amount_minor
                    if subscription is not None
                    else rule.amount_minor,
                    currency_code=(
                        subscription.currency_code
                        if subscription is not None
                        else rule.currency_code
                    ),
                    planned_for=occurrence,
                    payee=rule.payee,
                    note=rule.note,
                    status=PlannedTransactionStatus.PLANNED,
                    is_committed=rule.is_committed,
                    occurrence_key=key,
                )
            )
            created.append(item)
            existing_keys.add(key)
        if created:
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TRANSACTION,
                entity_id=rule.id,
                action="recurring_transactions_generated",
                title=f"Generated {len(created)} occurrences: {rule.name}",
                payload={
                    "finance_resource": "recurring_transaction",
                    "planned_transaction_ids": [str(item.id) for item in created],
                },
            )
    return [PlannedTransactionResponse.model_validate(item) for item in created]


def delete_recurring_transaction(
    session: Session,
    rule_id: UUID,
    revision: int,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = RecurringTransactionRepository(session)
    current = repository.get_active(workspace.id, rule_id)
    if current is None:
        raise DomainNotFoundError("recurring_transaction", rule_id)
    with transaction(session):
        deleted = repository.soft_delete(workspace.id, rule_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=deleted.id,
            action="recurring_transaction_deleted",
            title=f"Recurring transaction deleted: {deleted.name}",
            payload={"finance_resource": "recurring_transaction"},
        )
    return DeletedResource(id=rule_id)
