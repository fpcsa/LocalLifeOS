from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    Commitment,
    CommitmentEntityLink,
    CommitmentStatus,
    DomainEntityType,
)
from app.repositories.commitments import CommitmentRepository
from app.schemas.commitments import (
    CommitmentCreateRequest,
    CommitmentLinkCreateRequest,
    CommitmentLinkResponse,
    CommitmentResponse,
    CommitmentUpdateRequest,
)
from app.schemas.common import DeletedResource
from app.schemas.domain import CommitmentLinkCreate
from app.services.commitments import add_commitment_link, remove_commitment_link
from app.services.events import emit_timeline_event
from app.services.workspace import get_current_workspace


def _link_response(link: CommitmentEntityLink) -> CommitmentLinkResponse:
    return CommitmentLinkResponse.model_validate(link)


def commitment_responses(
    repository: CommitmentRepository,
    commitments: list[Commitment],
) -> list[CommitmentResponse]:
    links = repository.links_for([item.id for item in commitments])
    return [
        CommitmentResponse(
            id=item.id,
            workspace_id=item.workspace_id,
            title=item.title,
            description_markdown=item.description_markdown,
            status=item.status,
            category=item.category,
            target_start_at=item.starts_at,
            target_end_at=item.ends_at,
            decision_deadline_at=item.decision_deadline_at,
            time_capacity_requirement_minutes=item.estimated_duration_minutes,
            planned_cost_minor=item.planned_cost_minor,
            financial_buffer_requirement_minor=item.financial_buffer_requirement_minor,
            currency_code=item.currency_code,
            links=[_link_response(link) for link in links.get(item.id, [])],
            revision=item.revision,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in commitments
    ]


def list_commitments(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    status: CommitmentStatus | None,
    category: str | None,
    target_before: datetime | None,
    include_archived: bool,
) -> tuple[list[CommitmentResponse], int]:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        status=status,
        category=category,
        target_before=target_before,
        include_archived=include_archived,
    )
    return commitment_responses(repository, result.items), result.total


def get_commitment(session: Session, commitment_id: UUID) -> CommitmentResponse:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    item = repository.get_active(workspace.id, commitment_id)
    if item is None:
        raise DomainNotFoundError("commitment", commitment_id)
    return commitment_responses(repository, [item])[0]


def create_commitment(
    session: Session,
    create_data: CommitmentCreateRequest,
) -> CommitmentResponse:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    item = Commitment(
        workspace_id=workspace.id,
        title=create_data.title,
        description_markdown=create_data.description_markdown,
        status=create_data.status,
        category=create_data.category,
        starts_at=create_data.target_start_at,
        ends_at=create_data.target_end_at,
        decision_deadline_at=create_data.decision_deadline_at,
        estimated_duration_minutes=create_data.time_capacity_requirement_minutes,
        planned_cost_minor=create_data.planned_cost_minor,
        financial_buffer_requirement_minor=create_data.financial_buffer_requirement_minor,
        currency_code=create_data.currency_code,
    )
    with transaction(session):
        repository.add(item)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=item.id,
            action="commitment_created",
            title=f"Commitment created: {item.title}",
            payload={"status": item.status.value, "category": item.category},
        )
    return commitment_responses(repository, [item])[0]


def _prospective_values(
    current: Commitment,
    update_data: CommitmentUpdateRequest,
) -> dict[str, Any]:
    fields = update_data.model_fields_set - {"revision"}
    if not fields:
        raise DomainValidationError("empty_update", "At least one commitment field is required.")
    if update_data.status == CommitmentStatus.ARCHIVED:
        raise DomainValidationError(
            "archive_action_required",
            "Use the archive action to archive a commitment.",
        )
    mapping = {
        "target_start_at": "starts_at",
        "target_end_at": "ends_at",
        "time_capacity_requirement_minutes": "estimated_duration_minutes",
    }
    raw = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    values = {mapping.get(key, key): value for key, value in raw.items()}
    if (
        {"financial_buffer_requirement_minor", "planned_cost_minor"} & values.keys()
        and values.get(
            "financial_buffer_requirement_minor",
            current.financial_buffer_requirement_minor,
        )
        is None
        and values.get("planned_cost_minor", current.planned_cost_minor) is None
        and "currency_code" not in values
    ):
        values["currency_code"] = None
    starts_at = values.get("starts_at", current.starts_at)
    ends_at = values.get("ends_at", current.ends_at)
    decision_deadline = values.get("decision_deadline_at", current.decision_deadline_at)
    buffer_requirement = values.get(
        "financial_buffer_requirement_minor",
        current.financial_buffer_requirement_minor,
    )
    planned_cost = values.get("planned_cost_minor", current.planned_cost_minor)
    currency = values.get("currency_code", current.currency_code)
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise DomainValidationError(
            "invalid_commitment_range",
            "target_end_at must be after target_start_at.",
        )
    if decision_deadline is not None and ends_at is not None and decision_deadline > ends_at:
        raise DomainValidationError(
            "invalid_decision_deadline",
            "decision_deadline_at cannot be after target_end_at.",
        )
    has_money = buffer_requirement is not None or planned_cost is not None
    if has_money != (currency is not None):
        raise DomainValidationError(
            "commitment_currency_shape",
            "Money fields require a currency, and currency requires a money field.",
        )
    return values


def update_commitment(
    session: Session,
    commitment_id: UUID,
    update_data: CommitmentUpdateRequest,
) -> CommitmentResponse:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    current = repository.get_active(workspace.id, commitment_id)
    if current is None:
        raise DomainNotFoundError("commitment", commitment_id)
    if current.status == CommitmentStatus.ARCHIVED:
        raise DomainConflictError(
            "commitment_archived",
            "Archived commitments are immutable.",
        )
    values = _prospective_values(current, update_data)
    with transaction(session):
        item = repository.update(workspace.id, commitment_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=item.id,
            action="commitment_updated",
            title=f"Commitment updated: {item.title}",
            payload={"fields": sorted(update_data.model_fields_set - {"revision"})},
        )
    return commitment_responses(repository, [item])[0]


def archive_commitment(
    session: Session,
    commitment_id: UUID,
    revision: int,
) -> CommitmentResponse:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    current = repository.get_active(workspace.id, commitment_id)
    if current is None:
        raise DomainNotFoundError("commitment", commitment_id)
    if current.status == CommitmentStatus.ARCHIVED:
        raise DomainConflictError("commitment_archived", "The commitment is already archived.")
    with transaction(session):
        item = repository.update(
            workspace.id,
            commitment_id,
            revision,
            {"status": CommitmentStatus.ARCHIVED},
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=item.id,
            action="commitment_archived",
            title=f"Commitment archived: {item.title}",
        )
    return commitment_responses(repository, [item])[0]


def delete_commitment(session: Session, commitment_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    current = repository.get_active(workspace.id, commitment_id)
    if current is None:
        raise DomainNotFoundError("commitment", commitment_id)
    links = session.exec(
        select(CommitmentEntityLink).where(
            col(CommitmentEntityLink.workspace_id) == workspace.id,
            col(CommitmentEntityLink.commitment_id) == commitment_id,
        )
    ).all()
    with transaction(session):
        for link in links:
            session.delete(link)
        deleted = repository.soft_delete(workspace.id, commitment_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=deleted.id,
            action="commitment_deleted",
            title=f"Commitment deleted: {deleted.title}",
        )
    return DeletedResource(id=commitment_id)


def list_commitment_links(
    session: Session,
    commitment_id: UUID,
) -> list[CommitmentLinkResponse]:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    if repository.get_active(workspace.id, commitment_id) is None:
        raise DomainNotFoundError("commitment", commitment_id)
    return [
        _link_response(link)
        for link in repository.links_for([commitment_id]).get(commitment_id, [])
    ]


def create_commitment_link(
    session: Session,
    commitment_id: UUID,
    create_data: CommitmentLinkCreateRequest,
) -> CommitmentLinkResponse:
    workspace = get_current_workspace(session)
    link = add_commitment_link(
        session,
        workspace.id,
        CommitmentLinkCreate(
            commitment_id=commitment_id,
            entity_type=create_data.entity_type,
            entity_id=create_data.entity_id,
            role=create_data.role,
        ),
    )
    return _link_response(link)


def delete_commitment_link(
    session: Session,
    commitment_id: UUID,
    link_id: UUID,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    if repository.link(workspace.id, commitment_id, link_id) is None:
        raise DomainNotFoundError("commitment_link", link_id)
    remove_commitment_link(session, workspace.id, link_id)
    return DeletedResource(id=link_id)
