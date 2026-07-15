from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.transactions import transaction
from app.models import Tag
from app.repositories import TagRepository
from app.services.seed import DEFAULT_WORKSPACE_ID


def test_tag_repository_crud_and_pagination(db_session: Session) -> None:
    repository = TagRepository(db_session)
    with transaction(db_session):
        created = repository.add(
            Tag(workspace_id=DEFAULT_WORKSPACE_ID, name="Focus", color="#334455")
        )

    found = repository.get(DEFAULT_WORKSPACE_ID, created.id)
    assert found is not None
    assert found.name == "Focus"

    page = repository.list(
        DEFAULT_WORKSPACE_ID,
        page=1,
        page_size=10,
        query="foc",
        sort="name",
        descending=False,
    )
    assert page.total == 1
    assert [tag.id for tag in page.items] == [created.id]

    with transaction(db_session):
        repository.soft_delete(DEFAULT_WORKSPACE_ID, created.id, created.revision)
    assert repository.get(DEFAULT_WORKSPACE_ID, created.id) is None


def test_transaction_helper_rolls_back_every_write(db_session: Session) -> None:
    tag_id = uuid4()
    with pytest.raises(RuntimeError, match="force rollback"), transaction(db_session):
        db_session.add(Tag(id=tag_id, workspace_id=DEFAULT_WORKSPACE_ID, name="Rolled back"))
        db_session.flush()
        raise RuntimeError("force rollback")

    count = db_session.exec(select(func.count()).select_from(Tag).where(Tag.id == tag_id)).one()
    assert count == 0
