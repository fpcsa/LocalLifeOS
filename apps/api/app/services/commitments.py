from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import (
    DomainConflictError,
    DomainNotFoundError,
    DomainValidationError,
)
from app.db.transactions import transaction
from app.models import (
    Budget,
    CalendarEvent,
    Commitment,
    CommitmentEntityLink,
    CommitmentEntityType,
    CommitmentStatus,
    DomainEntityType,
    Goal,
    Note,
    PlannedTransaction,
    Project,
    SavingsGoal,
    Task,
    Transaction,
)
from app.models.common import WorkspaceSoftDeleteEntityBase
from app.schemas.domain import CommitmentLinkCreate
from app.services.events import emit_timeline_event

TARGET_MODELS: dict[
    CommitmentEntityType,
    type[WorkspaceSoftDeleteEntityBase],
] = {
    CommitmentEntityType.TASK: Task,
    CommitmentEntityType.PROJECT: Project,
    CommitmentEntityType.CALENDAR_EVENT: CalendarEvent,
    CommitmentEntityType.NOTE: Note,
    CommitmentEntityType.PLANNED_TRANSACTION: PlannedTransaction,
    CommitmentEntityType.TRANSACTION: Transaction,
    CommitmentEntityType.BUDGET: Budget,
    CommitmentEntityType.SAVINGS_GOAL: SavingsGoal,
    CommitmentEntityType.GOAL: Goal,
}


def add_commitment_link(
    session: Session,
    workspace_id: UUID,
    create_data: CommitmentLinkCreate,
) -> CommitmentEntityLink:
    commitment = session.get(Commitment, create_data.commitment_id)
    if (
        commitment is None
        or commitment.workspace_id != workspace_id
        or commitment.deleted_at is not None
    ):
        raise DomainNotFoundError("commitment", create_data.commitment_id)
    if commitment.status == CommitmentStatus.ARCHIVED:
        raise DomainConflictError(
            "commitment_archived",
            "Archived commitments cannot receive new links.",
        )

    target_model = TARGET_MODELS[create_data.entity_type]
    target = session.get(target_model, create_data.entity_id)
    if target is None or target.workspace_id != workspace_id or target.deleted_at is not None:
        raise DomainValidationError(
            "invalid_commitment_target",
            "The linked entity must be active and belong to the same workspace.",
            {
                "entity_type": create_data.entity_type,
                "entity_id": str(create_data.entity_id),
            },
        )

    existing = session.exec(
        select(CommitmentEntityLink).where(
            col(CommitmentEntityLink.workspace_id) == workspace_id,
            col(CommitmentEntityLink.commitment_id) == create_data.commitment_id,
            col(CommitmentEntityLink.entity_type) == create_data.entity_type,
            col(CommitmentEntityLink.entity_id) == create_data.entity_id,
        )
    ).first()
    if existing is not None:
        raise DomainConflictError(
            "duplicate_commitment_link",
            "This commitment link already exists.",
        )

    link = CommitmentEntityLink(
        workspace_id=workspace_id,
        **create_data.model_dump(),
    )
    with transaction(session):
        session.add(link)
        session.flush()
        session.refresh(link)
        emit_timeline_event(
            session,
            workspace_id=workspace_id,
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=commitment.id,
            action="commitment_link_added",
            title=f"Linked {create_data.entity_type.value}: {commitment.title}",
            payload={
                "link_id": str(link.id),
                "entity_type": create_data.entity_type.value,
                "entity_id": str(create_data.entity_id),
            },
        )
    return link


def remove_commitment_link(
    session: Session,
    workspace_id: UUID,
    link_id: UUID,
) -> None:
    link = session.exec(
        select(CommitmentEntityLink).where(
            col(CommitmentEntityLink.id) == link_id,
            col(CommitmentEntityLink.workspace_id) == workspace_id,
        )
    ).first()
    if link is None:
        raise DomainNotFoundError("commitment_link", link_id)

    commitment = session.get(Commitment, link.commitment_id)
    if commitment is None or commitment.deleted_at is not None:
        raise DomainNotFoundError("commitment", link.commitment_id)
    if commitment.status == CommitmentStatus.ARCHIVED:
        raise DomainConflictError(
            "commitment_archived",
            "Archived commitment links are retained as an audit snapshot.",
        )

    with transaction(session):
        session.delete(link)
        emit_timeline_event(
            session,
            workspace_id=workspace_id,
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=commitment.id,
            action="commitment_link_removed",
            title=f"Unlinked {link.entity_type.value}: {commitment.title}",
            payload={
                "link_id": str(link.id),
                "entity_type": link.entity_type.value,
                "entity_id": str(link.entity_id),
            },
        )
