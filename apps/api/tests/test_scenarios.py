from __future__ import annotations

from sqlmodel import Session

from app.db.transactions import transaction
from app.models import (
    DomainEntityType,
    Scenario,
    ScenarioChange,
    ScenarioOperation,
    Task,
)
from app.repositories import ScenarioChangeRepository, ScenarioRepository
from app.services.scenarios import preview_overlay
from app.services.seed import DEFAULT_WORKSPACE_ID


def test_scenario_preview_is_isolated_from_primary_records(db_session: Session) -> None:
    task = Task(workspace_id=DEFAULT_WORKSPACE_ID, title="Primary title")
    scenario = Scenario(workspace_id=DEFAULT_WORKSPACE_ID, name="Alternative")
    with transaction(db_session):
        db_session.add(task)
        ScenarioRepository(db_session).add(scenario)
        change = ScenarioChangeRepository(db_session).add(
            ScenarioChange(
                workspace_id=DEFAULT_WORKSPACE_ID,
                scenario_id=scenario.id,
                entity_type=DomainEntityType.TASK,
                entity_id=task.id,
                operation=ScenarioOperation.UPDATE,
                changes={"title": "Scenario title", "estimated_duration_minutes": 45},
            )
        )

    primary = {"id": str(task.id), "title": task.title, "estimated_duration_minutes": None}
    preview = preview_overlay(primary, change)

    assert preview == {
        "id": str(task.id),
        "title": "Scenario title",
        "estimated_duration_minutes": 45,
    }
    assert primary["title"] == "Primary title"
    persisted = db_session.get(Task, task.id)
    assert persisted is not None
    assert persisted.title == "Primary title"
