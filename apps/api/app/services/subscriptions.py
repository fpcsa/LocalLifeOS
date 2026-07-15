from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    AutomationTriggerType,
    CategoryKind,
    DomainEntityType,
    RecurringTransactionRule,
    RecurringTransactionStatus,
    Subscription,
    SubscriptionPriceChange,
    SubscriptionStatus,
)
from app.repositories.finance_engine import RecurringTransactionRepository, SubscriptionRepository
from app.schemas.common import DeletedResource
from app.schemas.finance import (
    SubscriptionCreateRequest,
    SubscriptionPriceChangeResponse,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
)
from app.services.automation import dispatch_automation_event
from app.services.events import emit_timeline_event
from app.services.finance_validation import require_account, require_category
from app.services.workspace import get_current_workspace


def _validate_relationships(
    session: Session,
    workspace_id: UUID,
    *,
    account_id: UUID,
    category_id: UUID | None,
    currency_code: str,
) -> None:
    account = require_account(session, workspace_id, account_id)
    if account.currency_code != currency_code:
        raise DomainValidationError(
            "subscription_currency_mismatch",
            "Subscription and account must use the same currency.",
        )
    if category_id is not None:
        category = require_category(session, workspace_id, category_id)
        if category.kind != CategoryKind.EXPENSE:
            raise DomainValidationError(
                "subscription_category_kind",
                "Subscriptions can only use expense categories.",
            )


def _responses(
    repository: SubscriptionRepository,
    subscriptions: list[Subscription],
) -> list[SubscriptionResponse]:
    changes = repository.price_changes_for([item.id for item in subscriptions])
    return [
        SubscriptionResponse(
            **item.model_dump(exclude={"deleted_at"}),
            price_changes=[
                SubscriptionPriceChangeResponse(
                    id=change.id,
                    old_amount_minor=change.old_amount_minor,
                    new_amount_minor=change.new_amount_minor,
                    delta_minor=change.new_amount_minor - change.old_amount_minor,
                    detected_at=change.detected_at,
                )
                for change in changes.get(item.id, [])
            ],
        )
        for item in subscriptions
    ]


def list_subscriptions(
    session: Session,
    *,
    page: int,
    page_size: int,
    status: SubscriptionStatus | None,
    currency: str | None,
) -> tuple[list[SubscriptionResponse], int]:
    workspace = get_current_workspace(session)
    repository = SubscriptionRepository(session)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        status=status,
        currency=currency,
    )
    return _responses(repository, result.items), result.total


def get_subscription(session: Session, subscription_id: UUID) -> SubscriptionResponse:
    workspace = get_current_workspace(session)
    repository = SubscriptionRepository(session)
    item = repository.get_active(workspace.id, subscription_id)
    if item is None:
        raise DomainNotFoundError("subscription", subscription_id)
    return _responses(repository, [item])[0]


def create_subscription(
    session: Session,
    create_data: SubscriptionCreateRequest,
) -> SubscriptionResponse:
    workspace = get_current_workspace(session)
    _validate_relationships(
        session,
        workspace.id,
        account_id=create_data.account_id,
        category_id=create_data.category_id,
        currency_code=create_data.currency_code,
    )
    repository = SubscriptionRepository(session)
    with transaction(session):
        item = repository.add(Subscription(workspace_id=workspace.id, **create_data.model_dump()))
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=item.id,
            action="subscription_created",
            title=f"Subscription created: {item.name}",
            payload={"finance_resource": "subscription"},
        )
    return _responses(repository, [item])[0]


def update_subscription(
    session: Session,
    subscription_id: UUID,
    update_data: SubscriptionUpdateRequest,
) -> SubscriptionResponse:
    workspace = get_current_workspace(session)
    repository = SubscriptionRepository(session)
    current = repository.get_active(workspace.id, subscription_id)
    if current is None:
        raise DomainNotFoundError("subscription", subscription_id)
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one subscription field is required.")
    starts_at = values.get("starts_at", current.starts_at)
    ends_at = values.get("ends_at", current.ends_at)
    if ends_at is not None and ends_at < starts_at:
        raise DomainValidationError(
            "invalid_subscription_range", "ends_at cannot be before starts_at."
        )
    category_id = values.get("category_id", current.category_id)
    _validate_relationships(
        session,
        workspace.id,
        account_id=current.account_id,
        category_id=category_id,
        currency_code=current.currency_code,
    )
    old_amount = current.amount_minor
    new_amount = values.get("amount_minor", old_amount)
    with transaction(session):
        item = repository.update(workspace.id, subscription_id, update_data.revision, values)
        recurring_repository = RecurringTransactionRepository(session)
        linked_rules = session.exec(
            select(RecurringTransactionRule).where(
                col(RecurringTransactionRule.workspace_id) == workspace.id,
                col(RecurringTransactionRule.subscription_id) == item.id,
                col(RecurringTransactionRule.deleted_at).is_(None),
                col(RecurringTransactionRule.status) != RecurringTransactionStatus.ENDED,
            )
        ).all()
        controlled_values = {
            "account_id": item.account_id,
            "transfer_account_id": None,
            "category_id": item.category_id,
            "amount_minor": item.amount_minor,
            "currency_code": item.currency_code,
            "rrule": item.billing_rrule,
            "starts_at": item.starts_at,
            "ends_at": item.ends_at,
        }
        for linked_rule in linked_rules:
            changed_values = {
                field: value
                for field, value in controlled_values.items()
                if getattr(linked_rule, field) != value
            }
            if changed_values:
                recurring_repository.update(
                    workspace.id,
                    linked_rule.id,
                    linked_rule.revision,
                    changed_values,
                )
        if new_amount != old_amount:
            session.add(
                SubscriptionPriceChange(
                    workspace_id=workspace.id,
                    subscription_id=item.id,
                    old_amount_minor=old_amount,
                    new_amount_minor=new_amount,
                )
            )
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TRANSACTION,
                entity_id=item.id,
                action="subscription_price_changed",
                title=f"Subscription price changed: {item.name}",
                payload={
                    "finance_resource": "subscription",
                    "old_amount_minor": old_amount,
                    "new_amount_minor": new_amount,
                    "currency": item.currency_code,
                },
            )
        else:
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TRANSACTION,
                entity_id=item.id,
                action="subscription_updated",
                title=f"Subscription updated: {item.name}",
                payload={"finance_resource": "subscription", "fields": sorted(values)},
            )
    if new_amount != old_amount:
        dispatch_automation_event(
            session,
            AutomationTriggerType.SUBSCRIPTION_AMOUNT_CHANGED,
            context={
                "entity_type": "subscription",
                "entity_id": str(item.id),
                "name": item.name,
                "old_amount_minor": old_amount,
                "new_amount_minor": new_amount,
                "delta_minor": new_amount - old_amount,
                "delta_percent": (
                    round((new_amount - old_amount) * 100 / old_amount, 4) if old_amount else None
                ),
                "currency_code": item.currency_code,
            },
            source_key=f"subscription:{item.id}:{item.revision}",
        )
    return _responses(repository, [item])[0]


def delete_subscription(
    session: Session,
    subscription_id: UUID,
    revision: int,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = SubscriptionRepository(session)
    current = repository.get_active(workspace.id, subscription_id)
    if current is None:
        raise DomainNotFoundError("subscription", subscription_id)
    with transaction(session):
        deleted = repository.soft_delete(workspace.id, subscription_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=deleted.id,
            action="subscription_deleted",
            title=f"Subscription deleted: {deleted.name}",
            payload={"finance_resource": "subscription"},
        )
    return DeletedResource(id=subscription_id)
