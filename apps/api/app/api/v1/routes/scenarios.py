from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import SessionDependency
from app.schemas.common import DataEnvelope, DeletedResource
from app.schemas.scenarios import (
    ScenarioAcceptRequest,
    ScenarioAcceptResponse,
    ScenarioChangeCreateRequest,
    ScenarioChangeResponse,
    ScenarioChangeUpdateRequest,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioCreateRequest,
    ScenarioPreviewResponse,
    ScenarioResponse,
    ScenarioRevisionRequest,
    ScenarioUpdateRequest,
)
from app.services.scenarios import (
    accept_scenario,
    add_scenario_change,
    compare_scenarios,
    create_scenario,
    delete_scenario_change,
    discard_scenario,
    get_scenario,
    list_scenario_changes,
    list_scenarios,
    preview_scenario,
    update_scenario,
    update_scenario_change,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=DataEnvelope[list[ScenarioResponse]])
def read_scenarios(session: SessionDependency) -> DataEnvelope[list[ScenarioResponse]]:
    return DataEnvelope(data=list_scenarios(session))


@router.post(
    "",
    response_model=DataEnvelope[ScenarioResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_scenario(
    request: ScenarioCreateRequest, session: SessionDependency
) -> DataEnvelope[ScenarioResponse]:
    return DataEnvelope(data=create_scenario(session, request))


@router.post("/compare", response_model=DataEnvelope[ScenarioCompareResponse])
def post_scenario_compare(
    request: ScenarioCompareRequest, session: SessionDependency
) -> DataEnvelope[ScenarioCompareResponse]:
    return DataEnvelope(data=compare_scenarios(session, request.scenario_ids))


@router.get("/{scenario_id}", response_model=DataEnvelope[ScenarioResponse])
def read_scenario(scenario_id: UUID, session: SessionDependency) -> DataEnvelope[ScenarioResponse]:
    return DataEnvelope(data=get_scenario(session, scenario_id))


@router.patch("/{scenario_id}", response_model=DataEnvelope[ScenarioResponse])
def patch_scenario(
    scenario_id: UUID,
    request: ScenarioUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[ScenarioResponse]:
    return DataEnvelope(data=update_scenario(session, scenario_id, request))


@router.post("/{scenario_id}/discard", response_model=DataEnvelope[ScenarioResponse])
def post_scenario_discard(
    scenario_id: UUID,
    request: ScenarioRevisionRequest,
    session: SessionDependency,
) -> DataEnvelope[ScenarioResponse]:
    return DataEnvelope(data=discard_scenario(session, scenario_id, request.revision))


@router.get(
    "/{scenario_id}/changes",
    response_model=DataEnvelope[list[ScenarioChangeResponse]],
)
def read_scenario_changes(
    scenario_id: UUID, session: SessionDependency
) -> DataEnvelope[list[ScenarioChangeResponse]]:
    return DataEnvelope(data=list_scenario_changes(session, scenario_id))


@router.post(
    "/{scenario_id}/changes",
    response_model=DataEnvelope[ScenarioChangeResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_scenario_change(
    scenario_id: UUID,
    request: ScenarioChangeCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[ScenarioChangeResponse]:
    return DataEnvelope(data=add_scenario_change(session, scenario_id, request))


@router.patch(
    "/{scenario_id}/changes/{change_id}",
    response_model=DataEnvelope[ScenarioChangeResponse],
)
def patch_scenario_change(
    scenario_id: UUID,
    change_id: UUID,
    request: ScenarioChangeUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[ScenarioChangeResponse]:
    return DataEnvelope(data=update_scenario_change(session, scenario_id, change_id, request))


@router.delete(
    "/{scenario_id}/changes/{change_id}",
    response_model=DataEnvelope[DeletedResource],
)
def remove_scenario_change(
    scenario_id: UUID, change_id: UUID, session: SessionDependency
) -> DataEnvelope[DeletedResource]:
    deleted_id = delete_scenario_change(session, scenario_id, change_id)
    return DataEnvelope(data=DeletedResource(id=deleted_id))


@router.get(
    "/{scenario_id}/preview",
    response_model=DataEnvelope[ScenarioPreviewResponse],
)
def read_scenario_preview(
    scenario_id: UUID, session: SessionDependency
) -> DataEnvelope[ScenarioPreviewResponse]:
    return DataEnvelope(data=preview_scenario(session, scenario_id))


@router.post(
    "/{scenario_id}/accept",
    response_model=DataEnvelope[ScenarioAcceptResponse],
)
def post_scenario_accept(
    scenario_id: UUID,
    request: ScenarioAcceptRequest,
    session: SessionDependency,
) -> DataEnvelope[ScenarioAcceptResponse]:
    return DataEnvelope(data=accept_scenario(session, scenario_id, request))
