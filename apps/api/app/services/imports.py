from __future__ import annotations

import csv
import io
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.core.exceptions import DomainConflictError, DomainNotFoundError
from app.db.transactions import transaction
from app.models import CsvMappingProfile, ImportBatch, ImportKind, ImportRow, ImportRowStatus
from app.repositories.imports import (
    CsvMappingProfileRepository,
    ImportBatchRepository,
    ImportRowRepository,
)
from app.schemas.common import DeletedResource
from app.schemas.imports import (
    CsvMappingProfileCreateRequest,
    CsvMappingProfileResponse,
    CsvMappingProfileUpdateRequest,
    ImportBatchResponse,
    ImportPreviewResponse,
    ImportRowResponse,
    ImportRowSelectionRequest,
)
from app.services.import_files import sanitize_spreadsheet_cell
from app.services.workspace import get_current_workspace


def batch_response(item: ImportBatch) -> ImportBatchResponse:
    return ImportBatchResponse.model_validate(item)


def row_response(item: ImportRow) -> ImportRowResponse:
    return ImportRowResponse.model_validate(item)


def preview_response(session: Session, batch: ImportBatch) -> ImportPreviewResponse:
    rows = ImportRowRepository(session).list_batch(batch.workspace_id, batch.id)
    columns_value = batch.summary.get("columns", [])
    columns = [str(value) for value in columns_value] if isinstance(columns_value, list) else []
    return ImportPreviewResponse(
        batch=batch_response(batch),
        columns=columns,
        rows=[row_response(item) for item in rows],
    )


def list_import_batches(
    session: Session, *, page: int, page_size: int, kind: ImportKind | None
) -> tuple[list[ImportBatchResponse], int]:
    workspace = get_current_workspace(session)
    result = ImportBatchRepository(session).list_page(
        workspace.id, page=page, page_size=page_size, kind=kind
    )
    return [batch_response(item) for item in result.items], result.total


def get_import_preview(session: Session, batch_id: UUID) -> ImportPreviewResponse:
    workspace = get_current_workspace(session)
    batch = ImportBatchRepository(session).get_workspace(workspace.id, batch_id)
    if batch is None:
        raise DomainNotFoundError("import batch", batch_id)
    return preview_response(session, batch)


def set_import_row_selection(
    session: Session, row_id: UUID, request: ImportRowSelectionRequest
) -> ImportRowResponse:
    workspace = get_current_workspace(session)
    row = ImportRowRepository(session).get_workspace(workspace.id, row_id)
    if row is None:
        raise DomainNotFoundError("import row", row_id)
    batch = ImportBatchRepository(session).get_workspace(workspace.id, row.batch_id)
    if batch is None:
        raise DomainNotFoundError("import batch", row.batch_id)
    if batch.applied_at is not None:
        raise DomainConflictError(
            "import_already_applied", "Applied import rows cannot be changed."
        )
    if row.status == ImportRowStatus.INVALID or row.duplicate_kind == "exact":
        raise DomainConflictError(
            "import_row_not_selectable", "Invalid and exact duplicate rows cannot be included."
        )
    if row.revision != request.revision:
        raise DomainConflictError(
            "revision_conflict",
            "import row changed since it was read.",
            {"expected_revision": request.revision, "current_revision": row.revision},
        )
    with transaction(session):
        row.included = request.included
        row.revision += 1
        session.add(row)
    return row_response(row)


def _profile_response(item: CsvMappingProfile) -> CsvMappingProfileResponse:
    return CsvMappingProfileResponse.model_validate(item)


def list_mapping_profiles(session: Session) -> list[CsvMappingProfileResponse]:
    workspace = get_current_workspace(session)
    return [
        _profile_response(item)
        for item in CsvMappingProfileRepository(session).list_active(workspace.id)
    ]


def create_mapping_profile(
    session: Session, request: CsvMappingProfileCreateRequest
) -> CsvMappingProfileResponse:
    workspace = get_current_workspace(session)
    repository = CsvMappingProfileRepository(session)
    if repository.find_name(workspace.id, request.name) is not None:
        raise DomainConflictError(
            "mapping_profile_name", "A mapping profile already uses this name."
        )
    values = request.model_dump(exclude={"save_profile", "profile_name"})
    values["columns"] = request.columns.model_dump()
    with transaction(session):
        item = repository.add(CsvMappingProfile(workspace_id=workspace.id, **values))
    return _profile_response(item)


def update_mapping_profile(
    session: Session, profile_id: UUID, request: CsvMappingProfileUpdateRequest
) -> CsvMappingProfileResponse:
    workspace = get_current_workspace(session)
    values = request.model_dump(exclude={"revision"}, exclude_unset=True)
    if request.columns is not None:
        values["columns"] = request.columns.model_dump()
    with transaction(session):
        item = CsvMappingProfileRepository(session).update(
            workspace.id, profile_id, request.revision, values
        )
    return _profile_response(item)


def delete_mapping_profile(session: Session, profile_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    with transaction(session):
        CsvMappingProfileRepository(session).soft_delete(workspace.id, profile_id, revision)
    return DeletedResource(id=profile_id)


def export_import_rows_csv(session: Session, batch_id: UUID) -> bytes:
    preview = get_import_preview(session, batch_id)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(
        ["row", "status", "included", "description", "date", "amount_minor", "currency", "issues"]
    )
    for row in preview.rows:
        normalized: dict[str, Any] = row.normalized_data
        writer.writerow(
            [
                row.row_number,
                row.status.value,
                row.included,
                sanitize_spreadsheet_cell(normalized.get("description")),
                sanitize_spreadsheet_cell(normalized.get("occurred_at")),
                sanitize_spreadsheet_cell(normalized.get("amount_minor")),
                sanitize_spreadsheet_cell(normalized.get("currency_code")),
                sanitize_spreadsheet_cell("; ".join(issue.message for issue in row.issues)),
            ]
        )
    return output.getvalue().encode("utf-8-sig")
