from fastapi import APIRouter, status

from app.api.dependencies import SessionDependency
from app.schemas.common import DataEnvelope
from app.schemas.privacy import (
    BackupCreateRequest,
    BackupCreateResponse,
    DeleteAllLocalDataRequest,
    DeleteAllLocalDataResponse,
    PrivacyStatusResponse,
)
from app.services.backups import create_backup
from app.services.privacy import delete_all_local_data, privacy_status

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("/status", response_model=DataEnvelope[PrivacyStatusResponse])
def read_privacy_status(session: SessionDependency) -> DataEnvelope[PrivacyStatusResponse]:
    return DataEnvelope(data=privacy_status(session))


@router.post(
    "/backups",
    response_model=DataEnvelope[BackupCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_backup(request: BackupCreateRequest) -> DataEnvelope[BackupCreateResponse]:
    password = request.password.get_secret_value() if request.password is not None else None
    created = create_backup(password=password, label=request.label)
    return DataEnvelope(
        data=BackupCreateResponse(backup=created.summary, manifest=created.manifest)
    )


@router.post(
    "/delete-all",
    response_model=DataEnvelope[DeleteAllLocalDataResponse],
)
def post_delete_all(
    request: DeleteAllLocalDataRequest,
    session: SessionDependency,
) -> DataEnvelope[DeleteAllLocalDataResponse]:
    return DataEnvelope(
        data=delete_all_local_data(session, include_backups=request.include_backups)
    )
