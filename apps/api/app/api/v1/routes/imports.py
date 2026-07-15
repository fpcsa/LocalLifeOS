from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import Response

from app.api.dependencies import SessionDependency
from app.models import ImportKind
from app.schemas.common import DataEnvelope, DeletedResource, ListEnvelope, PaginationMeta
from app.schemas.imports import (
    CsvMappingProfileCreateRequest,
    CsvMappingProfileResponse,
    CsvMappingProfileUpdateRequest,
    CsvMappingRequest,
    ImportApplyRequest,
    ImportBatchResponse,
    ImportPreviewResponse,
    ImportRowResponse,
    ImportRowSelectionRequest,
)
from app.services.calendar_imports import (
    apply_calendar_import,
    export_calendar_events,
    preview_calendar_import,
)
from app.services.csv_imports import apply_csv_import, map_csv_import, preview_csv_import
from app.services.imports import (
    create_mapping_profile,
    delete_mapping_profile,
    export_import_rows_csv,
    get_import_preview,
    list_import_batches,
    list_mapping_profiles,
    set_import_row_selection,
    update_mapping_profile,
)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("", response_model=ListEnvelope[ImportBatchResponse])
def read_import_batches(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    kind: ImportKind | None = None,
) -> ListEnvelope[ImportBatchResponse]:
    items, total = list_import_batches(session, page=page, page_size=page_size, kind=kind)
    return ListEnvelope(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/mapping-profiles", response_model=DataEnvelope[list[CsvMappingProfileResponse]])
def read_mapping_profiles(
    session: SessionDependency,
) -> DataEnvelope[list[CsvMappingProfileResponse]]:
    return DataEnvelope(data=list_mapping_profiles(session))


@router.post(
    "/mapping-profiles",
    response_model=DataEnvelope[CsvMappingProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_mapping_profile(
    request: CsvMappingProfileCreateRequest, session: SessionDependency
) -> DataEnvelope[CsvMappingProfileResponse]:
    return DataEnvelope(data=create_mapping_profile(session, request))


@router.patch(
    "/mapping-profiles/{profile_id}", response_model=DataEnvelope[CsvMappingProfileResponse]
)
def patch_mapping_profile(
    profile_id: UUID,
    request: CsvMappingProfileUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[CsvMappingProfileResponse]:
    return DataEnvelope(data=update_mapping_profile(session, profile_id, request))


@router.delete("/mapping-profiles/{profile_id}", response_model=DataEnvelope[DeletedResource])
def remove_mapping_profile(
    profile_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_mapping_profile(session, profile_id, revision))


@router.post(
    "/calendar/preview",
    response_model=DataEnvelope[ImportPreviewResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_calendar_preview(
    session: SessionDependency, file: Annotated[UploadFile, File()]
) -> DataEnvelope[ImportPreviewResponse]:
    return DataEnvelope(data=preview_calendar_import(session, file))


@router.post("/calendar/{batch_id}/apply", response_model=DataEnvelope[ImportBatchResponse])
def post_calendar_apply(
    batch_id: UUID, request: ImportApplyRequest, session: SessionDependency
) -> DataEnvelope[ImportBatchResponse]:
    return DataEnvelope(data=apply_calendar_import(session, batch_id, request))


@router.get("/calendar/export.ics", response_class=Response)
def download_calendar_export(
    session: SessionDependency,
    event_id: Annotated[list[UUID] | None, Query()] = None,
) -> Response:
    content = export_calendar_events(session, event_id)
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="locallife-calendar.ics"'},
    )


@router.post(
    "/csv/preview",
    response_model=DataEnvelope[ImportPreviewResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_csv_preview(
    session: SessionDependency, file: Annotated[UploadFile, File()]
) -> DataEnvelope[ImportPreviewResponse]:
    return DataEnvelope(data=preview_csv_import(session, file))


@router.post("/csv/{batch_id}/map", response_model=DataEnvelope[ImportPreviewResponse])
def post_csv_mapping(
    batch_id: UUID, request: CsvMappingRequest, session: SessionDependency
) -> DataEnvelope[ImportPreviewResponse]:
    return DataEnvelope(data=map_csv_import(session, batch_id, request))


@router.post("/csv/{batch_id}/apply", response_model=DataEnvelope[ImportBatchResponse])
def post_csv_apply(
    batch_id: UUID, request: ImportApplyRequest, session: SessionDependency
) -> DataEnvelope[ImportBatchResponse]:
    return DataEnvelope(data=apply_csv_import(session, batch_id, request))


@router.get("/{batch_id}", response_model=DataEnvelope[ImportPreviewResponse])
def read_import_batch(
    batch_id: UUID, session: SessionDependency
) -> DataEnvelope[ImportPreviewResponse]:
    return DataEnvelope(data=get_import_preview(session, batch_id))


@router.patch("/rows/{row_id}", response_model=DataEnvelope[ImportRowResponse])
def patch_import_row(
    row_id: UUID, request: ImportRowSelectionRequest, session: SessionDependency
) -> DataEnvelope[ImportRowResponse]:
    return DataEnvelope(data=set_import_row_selection(session, row_id, request))


@router.get("/{batch_id}/rows.csv", response_class=Response)
def download_import_rows(batch_id: UUID, session: SessionDependency) -> Response:
    return Response(
        content=export_import_rows_csv(session, batch_id),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="import-{batch_id}-review.csv"'},
    )
