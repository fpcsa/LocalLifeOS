from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePath
from uuid import UUID

from fastapi import UploadFile
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import Attachment, AttachmentEntityLink, DomainEntityType
from app.repositories.attachments import AttachmentRepository
from app.schemas.common import DeletedResource
from app.schemas.productivity import AttachmentResponse
from app.services.domain_links import require_active_entity
from app.services.events import emit_timeline_event
from app.services.workspace import get_current_workspace

CHUNK_SIZE = 1024 * 1024
SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


def _attachments_root() -> Path:
    root = get_settings().attachments_dir
    if root is None:
        raise RuntimeError("attachments directory was not configured")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def validate_filename(filename: str | None) -> str:
    if filename is None:
        raise DomainValidationError("invalid_filename", "An attachment filename is required.")
    candidate = filename.strip()
    if (
        not candidate
        or len(candidate) > 255
        or "\x00" in candidate
        or candidate in {".", ".."}
        or PurePath(candidate).name != candidate
        or "/" in candidate
        or "\\" in candidate
        or ":" in candidate
    ):
        raise DomainValidationError(
            "invalid_filename",
            "Attachment filenames must be plain local filenames up to 255 characters.",
        )
    return candidate


def resolve_attachment_path(storage_path: str) -> Path:
    relative = Path(storage_path)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise DomainValidationError(
            "unsafe_attachment_path",
            "Attachment storage path is outside the local attachment directory.",
        )
    root = _attachments_root()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise DomainValidationError(
            "unsafe_attachment_path",
            "Attachment storage path is outside the local attachment directory.",
        )
    return resolved


def _attachment_responses(
    repository: AttachmentRepository,
    attachments: list[Attachment],
) -> list[AttachmentResponse]:
    links = repository.links_for([attachment.id for attachment in attachments])
    responses: list[AttachmentResponse] = []
    for attachment in attachments:
        attachment_links = links.get(attachment.id, [])
        if not attachment_links:
            continue
        primary_link = attachment_links[0]
        values = attachment.model_dump(exclude={"deleted_at", "storage_path"})
        responses.append(
            AttachmentResponse(
                **values,
                entity_type=primary_link.entity_type,
                entity_id=primary_link.entity_id,
            )
        )
    return responses


def list_attachments(
    session: Session,
    *,
    page: int,
    page_size: int,
    entity_type: DomainEntityType | None,
    entity_id: UUID | None,
) -> tuple[list[AttachmentResponse], int]:
    workspace = get_current_workspace(session)
    repository = AttachmentRepository(session)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return _attachment_responses(repository, result.items), result.total


async def upload_attachment(
    session: Session,
    upload: UploadFile,
    entity_type: DomainEntityType,
    entity_id: UUID,
) -> AttachmentResponse:
    workspace = get_current_workspace(session)
    require_active_entity(session, workspace.id, entity_type, entity_id)
    filename = validate_filename(upload.filename)
    media_type = (upload.content_type or "application/octet-stream").strip()
    if not media_type or len(media_type) > 150:
        raise DomainValidationError(
            "invalid_media_type",
            "Attachment media type must contain between 1 and 150 characters.",
        )

    attachment = Attachment(
        workspace_id=workspace.id,
        storage_path="pending",
        original_filename=filename,
        media_type=media_type,
        size_bytes=0,
    )
    suffix = Path(filename).suffix
    safe_suffix = suffix.lower() if SAFE_SUFFIX.fullmatch(suffix) else ""
    relative_path = Path(workspace.id.hex) / f"{attachment.id.hex}{safe_suffix}"
    target_path = resolve_attachment_path(relative_path.as_posix())
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = resolve_attachment_path(
        (Path(workspace.id.hex) / f".{attachment.id.hex}.upload").as_posix()
    )
    digest = hashlib.sha256()
    size = 0
    max_bytes = get_settings().max_attachment_bytes
    try:
        with temporary_path.open("xb") as output:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise DomainValidationError(
                        "attachment_too_large",
                        f"Attachments cannot exceed {max_bytes} bytes.",
                        {"max_bytes": max_bytes},
                    )
                digest.update(chunk)
                output.write(chunk)
        temporary_path.replace(target_path)
        attachment.storage_path = relative_path.as_posix()
        attachment.size_bytes = size
        attachment.sha256 = digest.hexdigest()
        repository = AttachmentRepository(session)
        with transaction(session):
            attachment = repository.add(attachment)
            session.add(
                AttachmentEntityLink(
                    workspace_id=workspace.id,
                    attachment_id=attachment.id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.ATTACHMENT,
                entity_id=attachment.id,
                action="attachment_uploaded",
                title=f"Attachment uploaded: {filename}",
                payload={"entity_type": entity_type, "entity_id": str(entity_id)},
            )
    except Exception:
        temporary_path.unlink(missing_ok=True)
        target_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return _attachment_responses(repository, [attachment])[0]


def get_attachment_file(session: Session, attachment_id: UUID) -> tuple[Attachment, Path]:
    workspace = get_current_workspace(session)
    attachment = AttachmentRepository(session).get_active(workspace.id, attachment_id)
    if attachment is None:
        raise DomainNotFoundError("attachment", attachment_id)
    path = resolve_attachment_path(attachment.storage_path)
    if not path.is_file():
        raise DomainNotFoundError("attachment_file", attachment_id)
    return attachment, path


def delete_attachment(
    session: Session,
    attachment_id: UUID,
    revision: int,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = AttachmentRepository(session)
    attachment = repository.get_active(workspace.id, attachment_id)
    if attachment is None:
        raise DomainNotFoundError("attachment", attachment_id)
    path = resolve_attachment_path(attachment.storage_path)
    with transaction(session):
        links = session.exec(
            select(AttachmentEntityLink).where(
                col(AttachmentEntityLink.attachment_id) == attachment_id
            )
        ).all()
        for link in links:
            session.delete(link)
        deleted = repository.soft_delete(workspace.id, attachment_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.ATTACHMENT,
            entity_id=deleted.id,
            action="attachment_deleted",
            title=f"Attachment deleted: {deleted.original_filename}",
        )
    path.unlink(missing_ok=True)
    return DeletedResource(id=attachment_id)
