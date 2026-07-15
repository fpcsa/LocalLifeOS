from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import CategoryKind, DomainEntityType, TransactionCategory
from app.repositories.finance_engine import FinanceCategoryRepository
from app.schemas.common import DeletedResource
from app.schemas.finance import (
    TransactionCategoryCreateRequest,
    TransactionCategoryResponse,
    TransactionCategoryUpdateRequest,
)
from app.services.events import emit_timeline_event
from app.services.workspace import get_current_workspace


def _response(category: TransactionCategory) -> TransactionCategoryResponse:
    return TransactionCategoryResponse.model_validate(category)


def list_categories(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    kind: CategoryKind | None,
    order: str,
) -> tuple[list[TransactionCategoryResponse], int]:
    workspace = get_current_workspace(session)
    result = FinanceCategoryRepository(session).list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        kind=kind,
        order="asc" if order == "asc" else "desc",
    )
    return [_response(item) for item in result.items], result.total


def get_category(session: Session, category_id: UUID) -> TransactionCategoryResponse:
    workspace = get_current_workspace(session)
    category = FinanceCategoryRepository(session).get_active(workspace.id, category_id)
    if category is None:
        raise DomainNotFoundError("transaction_category", category_id)
    return _response(category)


def create_category(
    session: Session,
    create_data: TransactionCategoryCreateRequest,
) -> TransactionCategoryResponse:
    workspace = get_current_workspace(session)
    repository = FinanceCategoryRepository(session)
    with transaction(session):
        category = repository.add(
            TransactionCategory(
                workspace_id=workspace.id,
                is_default=False,
                **create_data.model_dump(),
            )
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=category.id,
            action="transaction_category_created",
            title=f"Transaction category created: {category.name}",
            payload={"finance_resource": "transaction_category"},
        )
    return _response(category)


def update_category(
    session: Session,
    category_id: UUID,
    update_data: TransactionCategoryUpdateRequest,
) -> TransactionCategoryResponse:
    workspace = get_current_workspace(session)
    repository = FinanceCategoryRepository(session)
    if repository.get_active(workspace.id, category_id) is None:
        raise DomainNotFoundError("transaction_category", category_id)
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one category field is required.")
    with transaction(session):
        category = repository.update(workspace.id, category_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=category.id,
            action="transaction_category_updated",
            title=f"Transaction category updated: {category.name}",
            payload={"finance_resource": "transaction_category"},
        )
    return _response(category)


def delete_category(session: Session, category_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = FinanceCategoryRepository(session)
    category = repository.get_active(workspace.id, category_id)
    if category is None:
        raise DomainNotFoundError("transaction_category", category_id)
    if category.is_default:
        raise DomainConflictError(
            "default_category",
            "Seeded default categories cannot be deleted.",
        )
    with transaction(session):
        deleted = repository.soft_delete(workspace.id, category_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TRANSACTION,
            entity_id=deleted.id,
            action="transaction_category_deleted",
            title=f"Transaction category deleted: {deleted.name}",
            payload={"finance_resource": "transaction_category"},
        )
    return DeletedResource(id=category_id)
