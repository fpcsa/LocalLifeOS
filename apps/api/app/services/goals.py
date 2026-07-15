from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    CommitmentEntityType,
    DomainEntityType,
    Goal,
    GoalStatus,
    SavingsGoal,
)
from app.repositories.finance_engine import GoalRepository, SavingsGoalRepository
from app.schemas.common import DeletedResource
from app.schemas.finance import (
    GoalCreateRequest,
    GoalResponse,
    GoalUpdateRequest,
    SavingsGoalContributionRequest,
    SavingsGoalCreateRequest,
    SavingsGoalResponse,
    SavingsGoalUpdateRequest,
)
from app.services.domain_links import remove_commitment_entity_links
from app.services.events import emit_timeline_event
from app.services.finance_validation import require_account
from app.services.workspace import get_current_workspace


def _savings_response(item: SavingsGoal) -> SavingsGoalResponse:
    progress = min(10_000, item.current_minor * 10_000 // item.target_minor)
    return SavingsGoalResponse(
        **item.model_dump(exclude={"deleted_at"}),
        remaining_minor=max(0, item.target_minor - item.current_minor),
        progress_basis_points=progress,
    )


def list_savings_goals(
    session: Session,
    *,
    page: int,
    page_size: int,
    status: GoalStatus | None,
    currency: str | None,
) -> tuple[list[SavingsGoalResponse], int]:
    workspace = get_current_workspace(session)
    result = SavingsGoalRepository(session).list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        status=status,
        currency=currency,
    )
    return [_savings_response(item) for item in result.items], result.total


def get_savings_goal(session: Session, goal_id: UUID) -> SavingsGoalResponse:
    workspace = get_current_workspace(session)
    item = SavingsGoalRepository(session).get_active(workspace.id, goal_id)
    if item is None:
        raise DomainNotFoundError("savings_goal", goal_id)
    return _savings_response(item)


def _validate_savings_account(
    session: Session,
    workspace_id: UUID,
    account_id: UUID | None,
    currency: str,
) -> None:
    if account_id is None:
        return
    account = require_account(session, workspace_id, account_id)
    if account.currency_code != currency:
        raise DomainValidationError(
            "savings_goal_currency_mismatch",
            "Savings goal and linked account must use the same currency.",
        )


def create_savings_goal(
    session: Session,
    create_data: SavingsGoalCreateRequest,
) -> SavingsGoalResponse:
    workspace = get_current_workspace(session)
    _validate_savings_account(
        session, workspace.id, create_data.account_id, create_data.currency_code
    )
    repository = SavingsGoalRepository(session)
    with transaction(session):
        item = repository.add(SavingsGoal(workspace_id=workspace.id, **create_data.model_dump()))
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.SAVINGS_GOAL,
            entity_id=item.id,
            action="savings_goal_created",
            title=f"Savings goal created: {item.name}",
        )
    return _savings_response(item)


def update_savings_goal(
    session: Session,
    goal_id: UUID,
    update_data: SavingsGoalUpdateRequest,
) -> SavingsGoalResponse:
    workspace = get_current_workspace(session)
    repository = SavingsGoalRepository(session)
    current = repository.get_active(workspace.id, goal_id)
    if current is None:
        raise DomainNotFoundError("savings_goal", goal_id)
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one savings goal field is required.")
    account_id = values.get("account_id", current.account_id)
    _validate_savings_account(session, workspace.id, account_id, current.currency_code)
    with transaction(session):
        item = repository.update(workspace.id, goal_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.SAVINGS_GOAL,
            entity_id=item.id,
            action="savings_goal_updated",
            title=f"Savings goal updated: {item.name}",
            payload={"fields": sorted(values)},
        )
    return _savings_response(item)


def contribute_to_savings_goal(
    session: Session,
    goal_id: UUID,
    request: SavingsGoalContributionRequest,
) -> SavingsGoalResponse:
    workspace = get_current_workspace(session)
    repository = SavingsGoalRepository(session)
    current = repository.get_active(workspace.id, goal_id)
    if current is None:
        raise DomainNotFoundError("savings_goal", goal_id)
    new_value = current.current_minor + request.amount_minor
    status = GoalStatus.COMPLETED if new_value >= current.target_minor else current.status
    with transaction(session):
        item = repository.update(
            workspace.id,
            goal_id,
            request.revision,
            {"current_minor": new_value, "status": status},
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.SAVINGS_GOAL,
            entity_id=item.id,
            action="savings_goal_contribution",
            title=f"Savings goal contribution: {item.name}",
            payload={"amount_minor": request.amount_minor, "currency": item.currency_code},
        )
    return _savings_response(item)


def delete_savings_goal(session: Session, goal_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = SavingsGoalRepository(session)
    current = repository.get_active(workspace.id, goal_id)
    if current is None:
        raise DomainNotFoundError("savings_goal", goal_id)
    with transaction(session):
        remove_commitment_entity_links(
            session,
            workspace.id,
            CommitmentEntityType.SAVINGS_GOAL,
            goal_id,
        )
        deleted = repository.soft_delete(workspace.id, goal_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.SAVINGS_GOAL,
            entity_id=deleted.id,
            action="savings_goal_deleted",
            title=f"Savings goal deleted: {deleted.name}",
        )
    return DeletedResource(id=goal_id)


def list_goals(
    session: Session,
    *,
    page: int,
    page_size: int,
    status: GoalStatus | None,
) -> tuple[list[GoalResponse], int]:
    workspace = get_current_workspace(session)
    result = GoalRepository(session).list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return [GoalResponse.model_validate(item) for item in result.items], result.total


def get_goal(session: Session, goal_id: UUID) -> GoalResponse:
    workspace = get_current_workspace(session)
    item = GoalRepository(session).get_active(workspace.id, goal_id)
    if item is None:
        raise DomainNotFoundError("goal", goal_id)
    return GoalResponse.model_validate(item)


def create_goal(session: Session, create_data: GoalCreateRequest) -> GoalResponse:
    workspace = get_current_workspace(session)
    repository = GoalRepository(session)
    with transaction(session):
        item = repository.add(Goal(workspace_id=workspace.id, **create_data.model_dump()))
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.GOAL,
            entity_id=item.id,
            action="goal_created",
            title=f"Goal created: {item.title}",
        )
    return GoalResponse.model_validate(item)


def update_goal(
    session: Session,
    goal_id: UUID,
    update_data: GoalUpdateRequest,
) -> GoalResponse:
    workspace = get_current_workspace(session)
    repository = GoalRepository(session)
    if repository.get_active(workspace.id, goal_id) is None:
        raise DomainNotFoundError("goal", goal_id)
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one goal field is required.")
    if values.get("progress_basis_points") == 10_000 and "status" not in values:
        values["status"] = GoalStatus.COMPLETED
    with transaction(session):
        item = repository.update(workspace.id, goal_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.GOAL,
            entity_id=item.id,
            action="goal_updated",
            title=f"Goal updated: {item.title}",
            payload={"fields": sorted(values)},
        )
    return GoalResponse.model_validate(item)


def delete_goal(session: Session, goal_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = GoalRepository(session)
    current = repository.get_active(workspace.id, goal_id)
    if current is None:
        raise DomainNotFoundError("goal", goal_id)
    with transaction(session):
        remove_commitment_entity_links(
            session,
            workspace.id,
            CommitmentEntityType.GOAL,
            goal_id,
        )
        deleted = repository.soft_delete(workspace.id, goal_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.GOAL,
            entity_id=deleted.id,
            action="goal_deleted",
            title=f"Goal deleted: {deleted.title}",
        )
    return DeletedResource(id=goal_id)
