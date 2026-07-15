from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.models import (
    Attachment,
    AutomationRule,
    Budget,
    CalendarEvent,
    CalendarEventEntityLink,
    Commitment,
    CommitmentEntityLink,
    CommitmentEntityType,
    DomainEntityType,
    FinancialAccount,
    Goal,
    Note,
    NoteEntityLink,
    Project,
    SavingsGoal,
    Scenario,
    Tag,
    TagEntityLink,
    Task,
    Transaction,
)
from app.models.common import WorkspaceSoftDeleteEntityBase
from app.schemas.productivity import DomainLinkRequest

DOMAIN_MODELS: dict[DomainEntityType, type[WorkspaceSoftDeleteEntityBase]] = {
    DomainEntityType.TAG: Tag,
    DomainEntityType.ATTACHMENT: Attachment,
    DomainEntityType.PROJECT: Project,
    DomainEntityType.TASK: Task,
    DomainEntityType.NOTE: Note,
    DomainEntityType.CALENDAR_EVENT: CalendarEvent,
    DomainEntityType.FINANCIAL_ACCOUNT: FinancialAccount,
    DomainEntityType.TRANSACTION: Transaction,
    DomainEntityType.BUDGET: Budget,
    DomainEntityType.SAVINGS_GOAL: SavingsGoal,
    DomainEntityType.COMMITMENT: Commitment,
    DomainEntityType.GOAL: Goal,
    DomainEntityType.AUTOMATION_RULE: AutomationRule,
    DomainEntityType.SCENARIO: Scenario,
}


def require_active_entity(
    session: Session,
    workspace_id: UUID,
    entity_type: DomainEntityType,
    entity_id: UUID,
) -> WorkspaceSoftDeleteEntityBase:
    model = DOMAIN_MODELS.get(entity_type)
    if model is None:
        raise DomainValidationError(
            "unsupported_entity_type",
            "This entity type cannot be linked.",
            {"entity_type": entity_type},
        )
    entity = session.get(model, entity_id)
    if entity is None or entity.workspace_id != workspace_id or entity.deleted_at is not None:
        raise DomainNotFoundError(entity_type.value, entity_id)
    return entity


def replace_tag_links(
    session: Session,
    workspace_id: UUID,
    entity_type: DomainEntityType,
    entity_id: UUID,
    tag_ids: Iterable[UUID],
) -> None:
    requested = list(tag_ids)
    for tag_id in requested:
        require_active_entity(session, workspace_id, DomainEntityType.TAG, tag_id)
    existing = session.exec(
        select(TagEntityLink).where(
            col(TagEntityLink.workspace_id) == workspace_id,
            col(TagEntityLink.entity_type) == entity_type,
            col(TagEntityLink.entity_id) == entity_id,
        )
    ).all()
    for link in existing:
        session.delete(link)
    for tag_id in requested:
        session.add(
            TagEntityLink(
                workspace_id=workspace_id,
                tag_id=tag_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )


def replace_commitment_links(
    session: Session,
    workspace_id: UUID,
    entity_type: CommitmentEntityType,
    entity_id: UUID,
    commitment_ids: Iterable[UUID],
) -> None:
    requested = list(commitment_ids)
    for commitment_id in requested:
        require_active_entity(
            session,
            workspace_id,
            DomainEntityType.COMMITMENT,
            commitment_id,
        )
    existing = session.exec(
        select(CommitmentEntityLink).where(
            col(CommitmentEntityLink.workspace_id) == workspace_id,
            col(CommitmentEntityLink.entity_type) == entity_type,
            col(CommitmentEntityLink.entity_id) == entity_id,
        )
    ).all()
    for link in existing:
        session.delete(link)
    for commitment_id in requested:
        session.add(
            CommitmentEntityLink(
                workspace_id=workspace_id,
                commitment_id=commitment_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )


def replace_note_entity_links(
    session: Session,
    workspace_id: UUID,
    note_id: UUID,
    links: Iterable[DomainLinkRequest],
    allowed_types: frozenset[DomainEntityType],
) -> None:
    requested = list(links)
    keys = {(request_link.entity_type, request_link.entity_id) for request_link in requested}
    if len(keys) != len(requested):
        raise DomainConflictError("duplicate_entity_link", "Entity links cannot be duplicated.")
    for request_link in requested:
        if request_link.entity_type not in allowed_types:
            raise DomainValidationError(
                "unsupported_note_link",
                "This entity type cannot be linked to a note.",
                {"entity_type": request_link.entity_type},
            )
        require_active_entity(
            session, workspace_id, request_link.entity_type, request_link.entity_id
        )
    existing = session.exec(
        select(NoteEntityLink).where(
            col(NoteEntityLink.workspace_id) == workspace_id,
            col(NoteEntityLink.note_id) == note_id,
        )
    ).all()
    for existing_link in existing:
        session.delete(existing_link)
    for request_link in requested:
        session.add(
            NoteEntityLink(
                workspace_id=workspace_id,
                note_id=note_id,
                entity_type=request_link.entity_type,
                entity_id=request_link.entity_id,
                label=request_link.label,
            )
        )


def replace_calendar_entity_links(
    session: Session,
    workspace_id: UUID,
    event_id: UUID,
    links: Iterable[DomainLinkRequest],
    allowed_types: frozenset[DomainEntityType],
) -> None:
    requested = list(links)
    keys = {(request_link.entity_type, request_link.entity_id) for request_link in requested}
    if len(keys) != len(requested):
        raise DomainConflictError("duplicate_entity_link", "Entity links cannot be duplicated.")
    for request_link in requested:
        if request_link.entity_type not in allowed_types:
            raise DomainValidationError(
                "unsupported_calendar_link",
                "This entity type cannot be linked to a calendar event.",
                {"entity_type": request_link.entity_type},
            )
        require_active_entity(
            session, workspace_id, request_link.entity_type, request_link.entity_id
        )
    existing = session.exec(
        select(CalendarEventEntityLink).where(
            col(CalendarEventEntityLink.workspace_id) == workspace_id,
            col(CalendarEventEntityLink.calendar_event_id) == event_id,
        )
    ).all()
    for existing_link in existing:
        session.delete(existing_link)
    for request_link in requested:
        session.add(
            CalendarEventEntityLink(
                workspace_id=workspace_id,
                calendar_event_id=event_id,
                entity_type=request_link.entity_type,
                entity_id=request_link.entity_id,
            )
        )


def remove_generic_links(
    session: Session,
    workspace_id: UUID,
    entity_type: DomainEntityType,
    commitment_type: CommitmentEntityType | None,
    entity_id: UUID,
) -> None:
    tag_links = session.exec(
        select(TagEntityLink).where(
            col(TagEntityLink.workspace_id) == workspace_id,
            col(TagEntityLink.entity_type) == entity_type,
            col(TagEntityLink.entity_id) == entity_id,
        )
    ).all()
    for tag_link in tag_links:
        session.delete(tag_link)
    if commitment_type is not None:
        commitment_links = session.exec(
            select(CommitmentEntityLink).where(
                col(CommitmentEntityLink.workspace_id) == workspace_id,
                col(CommitmentEntityLink.entity_type) == commitment_type,
                col(CommitmentEntityLink.entity_id) == entity_id,
            )
        ).all()
        for link in commitment_links:
            session.delete(link)


def remove_commitment_entity_links(
    session: Session,
    workspace_id: UUID,
    entity_type: CommitmentEntityType,
    entity_id: UUID,
) -> None:
    links = session.exec(
        select(CommitmentEntityLink).where(
            col(CommitmentEntityLink.workspace_id) == workspace_id,
            col(CommitmentEntityLink.entity_type) == entity_type,
            col(CommitmentEntityLink.entity_id) == entity_id,
        )
    ).all()
    for link in links:
        session.delete(link)
