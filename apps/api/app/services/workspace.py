from __future__ import annotations

from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import DomainEntityType, SystemSetting, TimelineEvent, UserPreferences, Workspace
from app.repositories import PreferencesRepository, TimelineRepository, WorkspaceRepository
from app.schemas.resources import PreferencesUpdate, WorkspaceUpdate


def get_current_workspace(session: Session) -> Workspace:
    workspace = WorkspaceRepository(session).get_current()
    if workspace is None:
        raise DomainNotFoundError("workspace", "current")
    return workspace


def update_current_workspace(session: Session, update_data: WorkspaceUpdate) -> Workspace:
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one workspace field is required.")

    with transaction(session):
        workspace = WorkspaceRepository(session).update_current(update_data.revision, values)
        TimelineRepository(session).add(
            TimelineEvent(
                workspace_id=workspace.id,
                entity_type=DomainEntityType.WORKSPACE,
                entity_id=workspace.id,
                action="updated",
                title="Workspace settings updated",
                payload={"fields": sorted(values)},
            )
        )
    return workspace


def get_preferences(session: Session) -> UserPreferences:
    workspace = get_current_workspace(session)
    preferences = PreferencesRepository(session).get_for_workspace(workspace.id)
    if preferences is None:
        raise DomainNotFoundError("preferences", workspace.id)
    return preferences


def update_preferences(session: Session, update_data: PreferencesUpdate) -> UserPreferences:
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one preference field is required.")

    workspace = get_current_workspace(session)
    with transaction(session):
        preferences = PreferencesRepository(session).update(
            workspace.id,
            update_data.revision,
            values,
        )
        if "timezone" in values:
            setting = session.exec(
                select(SystemSetting).where(col(SystemSetting.key) == "user.timezone")
            ).first()
            if setting is not None:
                setting.value = preferences.timezone
                session.add(setting)
        TimelineRepository(session).add(
            TimelineEvent(
                workspace_id=workspace.id,
                entity_type=DomainEntityType.USER_PREFERENCES,
                entity_id=preferences.id,
                action="preferences_updated",
                title="Preferences updated",
                payload={"fields": sorted(values)},
            )
        )
    return preferences
