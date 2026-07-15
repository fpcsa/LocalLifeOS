from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    AutomationExecution,
    AutomationExecutionStatus,
    AutomationRule,
    AutomationTriggerType,
    LocalNotification,
)
from app.repositories.base import BaseRepository, PageResult
from app.repositories.revisioned import RevisionedRepository


class AutomationRuleRepository(RevisionedRepository[AutomationRule]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AutomationRule, "automation rule")

    def list_active(self, workspace_id: UUID) -> list[AutomationRule]:
        return list(
            self.session.exec(
                select(AutomationRule)
                .where(
                    col(AutomationRule.workspace_id) == workspace_id,
                    col(AutomationRule.deleted_at).is_(None),
                )
                .order_by(col(AutomationRule.name), col(AutomationRule.id))
            ).all()
        )

    def list_enabled_trigger(
        self, workspace_id: UUID, trigger_type: AutomationTriggerType
    ) -> list[AutomationRule]:
        candidates = self.session.exec(
            select(AutomationRule).where(
                col(AutomationRule.workspace_id) == workspace_id,
                col(AutomationRule.deleted_at).is_(None),
                col(AutomationRule.enabled).is_(True),
            )
        ).all()
        return [item for item in candidates if item.trigger.get("type") == trigger_type.value]


class AutomationExecutionRepository(BaseRepository[AutomationExecution]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AutomationExecution)

    def find_key(self, rule_id: UUID, idempotency_key: str) -> AutomationExecution | None:
        return self.session.exec(
            select(AutomationExecution).where(
                col(AutomationExecution.rule_id) == rule_id,
                col(AutomationExecution.idempotency_key) == idempotency_key,
            )
        ).first()

    def count_rule(self, rule_id: UUID) -> int:
        return self.session.exec(
            select(func.count())
            .select_from(AutomationExecution)
            .where(col(AutomationExecution.rule_id) == rule_id)
        ).one()

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        rule_id: UUID | None,
        status: AutomationExecutionStatus | None,
    ) -> PageResult[AutomationExecution]:
        filters = [col(AutomationExecution.workspace_id) == workspace_id]
        if rule_id is not None:
            filters.append(col(AutomationExecution.rule_id) == rule_id)
        if status is not None:
            filters.append(col(AutomationExecution.status) == status)
        total = self.session.exec(
            select(func.count()).select_from(AutomationExecution).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(AutomationExecution)
                .where(*filters)
                .order_by(
                    col(AutomationExecution.created_at).desc(),
                    col(AutomationExecution.id).desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)


class NotificationRepository(BaseRepository[LocalNotification]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, LocalNotification)

    def list_unread(self, workspace_id: UUID) -> list[LocalNotification]:
        return list(
            self.session.exec(
                select(LocalNotification)
                .where(
                    col(LocalNotification.workspace_id) == workspace_id,
                    col(LocalNotification.deleted_at).is_(None),
                    col(LocalNotification.read_at).is_(None),
                )
                .order_by(col(LocalNotification.created_at).desc())
            ).all()
        )
