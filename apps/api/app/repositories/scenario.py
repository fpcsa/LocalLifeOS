from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import DomainEntityType, Scenario, ScenarioChange
from app.repositories.base import BaseRepository


class ScenarioRepository(BaseRepository[Scenario]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Scenario)

    def get_active(self, workspace_id: UUID, scenario_id: UUID) -> Scenario | None:
        return self.session.exec(
            select(Scenario).where(
                col(Scenario.id) == scenario_id,
                col(Scenario.workspace_id) == workspace_id,
                col(Scenario.deleted_at).is_(None),
            )
        ).first()

    def list_active(self, workspace_id: UUID) -> list[Scenario]:
        return list(
            self.session.exec(
                select(Scenario)
                .where(
                    col(Scenario.workspace_id) == workspace_id,
                    col(Scenario.deleted_at).is_(None),
                )
                .order_by(col(Scenario.updated_at).desc(), col(Scenario.id))
            ).all()
        )

    def change_counts(self, scenario_ids: list[UUID]) -> dict[UUID, int]:
        if not scenario_ids:
            return {}
        rows = self.session.exec(
            select(col(ScenarioChange.scenario_id), func.count(col(ScenarioChange.id)))
            .where(col(ScenarioChange.scenario_id).in_(scenario_ids))
            .group_by(col(ScenarioChange.scenario_id))
        ).all()
        return {scenario_id: int(count) for scenario_id, count in rows}


class ScenarioChangeRepository(BaseRepository[ScenarioChange]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ScenarioChange)

    def get_for_entity(
        self,
        scenario_id: UUID,
        entity_type: DomainEntityType,
        entity_id: UUID,
    ) -> ScenarioChange | None:
        return self.session.exec(
            select(ScenarioChange).where(
                col(ScenarioChange.scenario_id) == scenario_id,
                col(ScenarioChange.entity_type) == entity_type,
                col(ScenarioChange.entity_id) == entity_id,
            )
        ).first()

    def list_for_scenario(self, scenario_id: UUID) -> list[ScenarioChange]:
        return list(
            self.session.exec(
                select(ScenarioChange)
                .where(col(ScenarioChange.scenario_id) == scenario_id)
                .order_by(col(ScenarioChange.created_at), col(ScenarioChange.id))
            ).all()
        )
