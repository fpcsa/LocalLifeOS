from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    Budget,
    BudgetCategoryLimit,
    BudgetPeriod,
    CategoryKind,
    CommitmentEntityType,
    DomainEntityType,
)
from app.repositories.finance_engine import BudgetRepository
from app.schemas.common import DeletedResource
from app.schemas.finance import (
    BudgetCreateRequest,
    BudgetLimitInput,
    BudgetLimitResponse,
    BudgetResponse,
    BudgetUpdateRequest,
)
from app.services.domain_links import remove_commitment_entity_links
from app.services.events import emit_timeline_event
from app.services.finance_calculations import budget_end_date
from app.services.finance_validation import require_category
from app.services.workspace import get_current_workspace


def _validate_limits(
    session: Session,
    workspace_id: UUID,
    limits: list[BudgetLimitInput],
) -> None:
    for limit in limits:
        category = require_category(session, workspace_id, limit.category_id)
        if category.kind != CategoryKind.EXPENSE:
            raise DomainValidationError(
                "budget_category_kind",
                "Budget limits can only reference expense categories.",
                {"category_id": str(category.id)},
            )


def _replace_limits(
    session: Session,
    workspace_id: UUID,
    budget_id: UUID,
    limits: list[BudgetLimitInput],
) -> None:
    existing = session.exec(
        select(BudgetCategoryLimit).where(col(BudgetCategoryLimit.budget_id) == budget_id)
    ).all()
    for existing_limit in existing:
        session.delete(existing_limit)
    for limit in limits:
        session.add(
            BudgetCategoryLimit(
                workspace_id=workspace_id,
                budget_id=budget_id,
                category_id=limit.category_id,
                limit_minor=limit.limit_minor,
            )
        )


def _responses(repository: BudgetRepository, budgets: list[Budget]) -> list[BudgetResponse]:
    by_budget = repository.limits_for([budget.id for budget in budgets])
    return [
        BudgetResponse(
            **budget.model_dump(exclude={"deleted_at"}),
            limits=[
                BudgetLimitResponse(
                    id=item.id,
                    category_id=item.category_id,
                    limit_minor=item.limit_minor,
                )
                for item in by_budget.get(budget.id, [])
            ],
        )
        for budget in budgets
    ]


def list_budgets(
    session: Session,
    *,
    page: int,
    page_size: int,
    period: BudgetPeriod | None,
    currency: str | None,
) -> tuple[list[BudgetResponse], int]:
    workspace = get_current_workspace(session)
    repository = BudgetRepository(session)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        period=period,
        currency=currency,
    )
    return _responses(repository, result.items), result.total


def get_budget(session: Session, budget_id: UUID) -> BudgetResponse:
    workspace = get_current_workspace(session)
    repository = BudgetRepository(session)
    budget = repository.get_active(workspace.id, budget_id)
    if budget is None:
        raise DomainNotFoundError("budget", budget_id)
    return _responses(repository, [budget])[0]


def create_budget(session: Session, create_data: BudgetCreateRequest) -> BudgetResponse:
    workspace = get_current_workspace(session)
    repository = BudgetRepository(session)
    _validate_limits(session, workspace.id, create_data.limits)
    values = create_data.model_dump(exclude={"limits"})
    with transaction(session):
        budget = repository.add(Budget(workspace_id=workspace.id, **values))
        budget_end_date(budget)
        _replace_limits(session, workspace.id, budget.id, create_data.limits)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.BUDGET,
            entity_id=budget.id,
            action="budget_created",
            title=f"Budget created: {budget.name}",
        )
    return _responses(repository, [budget])[0]


def update_budget(
    session: Session,
    budget_id: UUID,
    update_data: BudgetUpdateRequest,
) -> BudgetResponse:
    workspace = get_current_workspace(session)
    repository = BudgetRepository(session)
    current = repository.get_active(workspace.id, budget_id)
    if current is None:
        raise DomainNotFoundError("budget", budget_id)
    values = update_data.model_dump(exclude={"revision", "limits"}, exclude_unset=True)
    limits_supplied = "limits" in update_data.model_fields_set
    if not values and not limits_supplied:
        raise DomainValidationError("empty_update", "At least one budget field is required.")
    start = values.get("start_date", current.start_date)
    end = values.get("end_date", current.end_date)
    if end is not None and end < start:
        raise DomainValidationError("invalid_budget_range", "end_date cannot be before start_date.")
    if limits_supplied:
        _validate_limits(session, workspace.id, update_data.limits or [])
    with transaction(session):
        budget = repository.update(workspace.id, budget_id, update_data.revision, values)
        budget_end_date(budget)
        if limits_supplied:
            _replace_limits(session, workspace.id, budget.id, update_data.limits or [])
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.BUDGET,
            entity_id=budget.id,
            action="budget_updated",
            title=f"Budget updated: {budget.name}",
            payload={"fields": sorted(update_data.model_fields_set - {"revision"})},
        )
    return _responses(repository, [budget])[0]


def delete_budget(session: Session, budget_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = BudgetRepository(session)
    current = repository.get_active(workspace.id, budget_id)
    if current is None:
        raise DomainNotFoundError("budget", budget_id)
    with transaction(session):
        remove_commitment_entity_links(
            session,
            workspace.id,
            CommitmentEntityType.BUDGET,
            budget_id,
        )
        deleted = repository.soft_delete(workspace.id, budget_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.BUDGET,
            entity_id=deleted.id,
            action="budget_deleted",
            title=f"Budget deleted: {deleted.name}",
        )
    return DeletedResource(id=budget_id)
