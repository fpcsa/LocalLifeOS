from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlmodel import Session, select

from app.models.common import EntityBase


@dataclass(frozen=True)
class PageResult[ModelT: EntityBase]:
    items: list[ModelT]
    total: int


class BaseRepository[ModelT: EntityBase]:
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, entity_id: UUID) -> ModelT | None:
        return self.session.exec(select(self.model).where(self.model.id == entity_id)).first()

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)
        self.session.flush()
