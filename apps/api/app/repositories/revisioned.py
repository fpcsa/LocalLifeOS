from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, RevisionConflictError
from app.models.common import WorkspaceSoftDeleteEntityBase, utc_now


class RevisionedRepository[ModelT: WorkspaceSoftDeleteEntityBase]:
    def __init__(self, session: Session, model: type[ModelT], resource_name: str) -> None:
        self.session = session
        self.model = model
        self.resource_name = resource_name

    def get_active(self, workspace_id: UUID, entity_id: UUID) -> ModelT | None:
        return self.session.exec(
            select(self.model).where(
                col(self.model.id) == entity_id,
                col(self.model.workspace_id) == workspace_id,
                col(self.model.deleted_at).is_(None),
            )
        ).first()

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def update(
        self,
        workspace_id: UUID,
        entity_id: UUID,
        expected_revision: int,
        values: dict[str, Any],
    ) -> ModelT:
        result = self.session.execute(
            update(self.model)
            .where(
                col(self.model.id) == entity_id,
                col(self.model.workspace_id) == workspace_id,
                col(self.model.revision) == expected_revision,
                col(self.model.deleted_at).is_(None),
            )
            .values(
                **values,
                revision=expected_revision + 1,
                updated_at=utc_now(),
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            self._raise_write_error(workspace_id, entity_id, expected_revision)
        self.session.expire_all()
        updated = self.get_active(workspace_id, entity_id)
        if updated is None:
            raise DomainNotFoundError(self.resource_name, entity_id)
        return updated

    def soft_delete(
        self,
        workspace_id: UUID,
        entity_id: UUID,
        expected_revision: int,
    ) -> ModelT:
        now = utc_now()
        result = self.session.execute(
            update(self.model)
            .where(
                col(self.model.id) == entity_id,
                col(self.model.workspace_id) == workspace_id,
                col(self.model.revision) == expected_revision,
                col(self.model.deleted_at).is_(None),
            )
            .values(
                deleted_at=now,
                updated_at=now,
                revision=expected_revision + 1,
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            self._raise_write_error(workspace_id, entity_id, expected_revision)
        self.session.expire_all()
        deleted = self.session.get(self.model, entity_id)
        if deleted is None:
            raise DomainNotFoundError(self.resource_name, entity_id)
        return deleted

    def _raise_write_error(
        self,
        workspace_id: UUID,
        entity_id: UUID,
        expected_revision: int,
    ) -> None:
        self.session.expire_all()
        latest = self.session.get(self.model, entity_id)
        if latest is None or latest.workspace_id != workspace_id or latest.deleted_at is not None:
            raise DomainNotFoundError(self.resource_name, entity_id)
        raise RevisionConflictError(self.resource_name, expected_revision, latest.revision)
