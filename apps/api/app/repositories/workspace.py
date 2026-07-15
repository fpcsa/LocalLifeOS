from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, RevisionConflictError
from app.models import UserPreferences, Workspace
from app.models.common import utc_now


class WorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_current(self) -> Workspace | None:
        return self.session.exec(
            select(Workspace).where(
                col(Workspace.is_default).is_(True),
                col(Workspace.deleted_at).is_(None),
            )
        ).first()

    def update_current(self, expected_revision: int, values: dict[str, Any]) -> Workspace:
        current = self.get_current()
        if current is None:
            raise DomainNotFoundError("workspace", "current")

        result = self.session.execute(
            update(Workspace)
            .where(
                col(Workspace.id) == current.id,
                col(Workspace.revision) == expected_revision,
                col(Workspace.deleted_at).is_(None),
            )
            .values(
                **values,
                revision=expected_revision + 1,
                updated_at=utc_now(),
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            self.session.expire_all()
            latest = self.get_current()
            if latest is None:
                raise DomainNotFoundError("workspace", "current")
            raise RevisionConflictError("workspace", expected_revision, latest.revision)

        self.session.expire_all()
        updated = self.get_current()
        if updated is None:
            raise DomainNotFoundError("workspace", "current")
        return updated


class PreferencesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_workspace(self, workspace_id: UUID) -> UserPreferences | None:
        return self.session.exec(
            select(UserPreferences).where(col(UserPreferences.workspace_id) == workspace_id)
        ).first()

    def update(
        self,
        workspace_id: UUID,
        expected_revision: int,
        values: dict[str, Any],
    ) -> UserPreferences:
        result = self.session.execute(
            update(UserPreferences)
            .where(
                col(UserPreferences.workspace_id) == workspace_id,
                col(UserPreferences.revision) == expected_revision,
            )
            .values(
                **values,
                revision=expected_revision + 1,
                updated_at=utc_now(),
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            self.session.expire_all()
            latest = self.get_for_workspace(workspace_id)
            if latest is None:
                raise DomainNotFoundError("preferences", workspace_id)
            raise RevisionConflictError("preferences", expected_revision, latest.revision)

        self.session.expire_all()
        updated = self.get_for_workspace(workspace_id)
        if updated is None:
            raise DomainNotFoundError("preferences", workspace_id)
        return updated
