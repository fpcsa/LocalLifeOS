from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.core.exceptions import DomainConflictError, DomainNotFoundError
from app.models import SchedulingPreview
from app.models.common import utc_now


class SchedulingPreviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, preview: SchedulingPreview) -> SchedulingPreview:
        self.session.add(preview)
        self.session.flush()
        self.session.refresh(preview)
        return preview

    def get(self, workspace_id: UUID, preview_id: UUID) -> SchedulingPreview | None:
        return self.session.exec(
            select(SchedulingPreview).where(
                col(SchedulingPreview.id) == preview_id,
                col(SchedulingPreview.workspace_id) == workspace_id,
            )
        ).first()

    def mark_applied(
        self,
        workspace_id: UUID,
        preview_id: UUID,
        expected_revision: int,
        applied_at: datetime,
    ) -> SchedulingPreview:
        result = self.session.execute(
            update(SchedulingPreview)
            .where(
                col(SchedulingPreview.id) == preview_id,
                col(SchedulingPreview.workspace_id) == workspace_id,
                col(SchedulingPreview.revision) == expected_revision,
                col(SchedulingPreview.applied_at).is_(None),
            )
            .values(
                applied_at=applied_at,
                updated_at=utc_now(),
                revision=expected_revision + 1,
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            latest = self.get(workspace_id, preview_id)
            if latest is None:
                raise DomainNotFoundError("scheduling_preview", preview_id)
            raise DomainConflictError(
                "scheduling_preview_already_applied",
                "The scheduling preview has already been applied or changed.",
            )
        self.session.expire_all()
        updated = self.get(workspace_id, preview_id)
        if updated is None:
            raise DomainNotFoundError("scheduling_preview", preview_id)
        return updated
