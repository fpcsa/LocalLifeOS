from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import CsvMappingProfile, ImportBatch, ImportKind, ImportRow
from app.repositories.base import BaseRepository, PageResult
from app.repositories.revisioned import RevisionedRepository


class ImportBatchRepository(BaseRepository[ImportBatch]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ImportBatch)

    def find_source(
        self, workspace_id: UUID, kind: ImportKind, fingerprint: str
    ) -> ImportBatch | None:
        return self.session.exec(
            select(ImportBatch).where(
                col(ImportBatch.workspace_id) == workspace_id,
                col(ImportBatch.kind) == kind,
                col(ImportBatch.source_fingerprint) == fingerprint,
            )
        ).first()

    def get_workspace(self, workspace_id: UUID, batch_id: UUID) -> ImportBatch | None:
        return self.session.exec(
            select(ImportBatch).where(
                col(ImportBatch.workspace_id) == workspace_id,
                col(ImportBatch.id) == batch_id,
            )
        ).first()

    def list_page(
        self, workspace_id: UUID, *, page: int, page_size: int, kind: ImportKind | None
    ) -> PageResult[ImportBatch]:
        filters = [col(ImportBatch.workspace_id) == workspace_id]
        if kind is not None:
            filters.append(col(ImportBatch.kind) == kind)
        total = self.session.exec(
            select(func.count()).select_from(ImportBatch).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(ImportBatch)
                .where(*filters)
                .order_by(col(ImportBatch.created_at).desc(), col(ImportBatch.id).desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)


class ImportRowRepository(BaseRepository[ImportRow]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ImportRow)

    def list_batch(self, workspace_id: UUID, batch_id: UUID) -> list[ImportRow]:
        return list(
            self.session.exec(
                select(ImportRow)
                .where(
                    col(ImportRow.workspace_id) == workspace_id,
                    col(ImportRow.batch_id) == batch_id,
                )
                .order_by(col(ImportRow.row_number), col(ImportRow.id))
            ).all()
        )

    def get_workspace(self, workspace_id: UUID, row_id: UUID) -> ImportRow | None:
        return self.session.exec(
            select(ImportRow).where(
                col(ImportRow.workspace_id) == workspace_id,
                col(ImportRow.id) == row_id,
            )
        ).first()


class CsvMappingProfileRepository(RevisionedRepository[CsvMappingProfile]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CsvMappingProfile, "CSV mapping profile")

    def list_active(self, workspace_id: UUID) -> list[CsvMappingProfile]:
        return list(
            self.session.exec(
                select(CsvMappingProfile)
                .where(
                    col(CsvMappingProfile.workspace_id) == workspace_id,
                    col(CsvMappingProfile.deleted_at).is_(None),
                )
                .order_by(col(CsvMappingProfile.name), col(CsvMappingProfile.id))
            ).all()
        )

    def find_name(self, workspace_id: UUID, name: str) -> CsvMappingProfile | None:
        return self.session.exec(
            select(CsvMappingProfile).where(
                col(CsvMappingProfile.workspace_id) == workspace_id,
                col(CsvMappingProfile.deleted_at).is_(None),
                func.lower(col(CsvMappingProfile.name)) == name.casefold(),
            )
        ).first()
