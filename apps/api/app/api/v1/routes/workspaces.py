from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.schemas.common import DataEnvelope
from app.schemas.resources import (
    PreferencesResponse,
    PreferencesUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace import (
    get_current_workspace,
    get_preferences,
    update_current_workspace,
    update_preferences,
)

router = APIRouter(tags=["workspace"])


@router.get(
    "/workspaces/current",
    response_model=DataEnvelope[WorkspaceResponse],
)
def read_current_workspace(session: SessionDependency) -> DataEnvelope[WorkspaceResponse]:
    workspace = get_current_workspace(session)
    return DataEnvelope(data=WorkspaceResponse.model_validate(workspace))


@router.patch(
    "/workspaces/current",
    response_model=DataEnvelope[WorkspaceResponse],
)
def patch_current_workspace(
    update_data: WorkspaceUpdate,
    session: SessionDependency,
) -> DataEnvelope[WorkspaceResponse]:
    workspace = update_current_workspace(session, update_data)
    return DataEnvelope(data=WorkspaceResponse.model_validate(workspace))


@router.get(
    "/preferences",
    response_model=DataEnvelope[PreferencesResponse],
)
def read_preferences(session: SessionDependency) -> DataEnvelope[PreferencesResponse]:
    preferences = get_preferences(session)
    return DataEnvelope(data=PreferencesResponse.model_validate(preferences))


@router.patch(
    "/preferences",
    response_model=DataEnvelope[PreferencesResponse],
)
def patch_preferences(
    update_data: PreferencesUpdate,
    session: SessionDependency,
) -> DataEnvelope[PreferencesResponse]:
    preferences = update_preferences(session, update_data)
    return DataEnvelope(data=PreferencesResponse.model_validate(preferences))
