from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from app.core.exceptions import DomainConflictError
from app.db.transactions import transaction
from app.models import DomainEntityType, Tag, TimelineEvent
from app.repositories import PageResult, TagRepository, TimelineRepository
from app.repositories.tag import TagSort
from app.schemas.common import DeletedResource, SortOrder
from app.schemas.resources import TagCreate
from app.services.workspace import get_current_workspace


def list_tags(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    sort: TagSort,
    order: SortOrder,
) -> PageResult[Tag]:
    workspace = get_current_workspace(session)
    return TagRepository(session).list(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        sort=sort,
        descending=order == SortOrder.DESC,
    )


def create_tag(session: Session, create_data: TagCreate) -> Tag:
    workspace = get_current_workspace(session)
    repository = TagRepository(session)
    normalized_name = create_data.name.strip()
    if repository.find_by_name(workspace.id, normalized_name) is not None:
        raise DomainConflictError(
            "duplicate_tag",
            "An active tag with this name already exists.",
            {"name": normalized_name},
        )

    with transaction(session):
        tag = repository.add(
            Tag(
                workspace_id=workspace.id,
                name=normalized_name,
                color=create_data.color,
            )
        )
        TimelineRepository(session).add(
            TimelineEvent(
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TAG,
                entity_id=tag.id,
                action="tag_created",
                title=f"Tag created: {tag.name}",
                payload={"tag_id": str(tag.id)},
            )
        )
    return tag


def delete_tag(session: Session, tag_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    with transaction(session):
        tag = TagRepository(session).soft_delete(workspace.id, tag_id, revision)
        TimelineRepository(session).add(
            TimelineEvent(
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TAG,
                entity_id=tag.id,
                action="tag_deleted",
                title=f"Tag deleted: {tag.name}",
                payload={"tag_id": str(tag.id)},
            )
        )
    return DeletedResource(id=tag.id)
