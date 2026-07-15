from __future__ import annotations

import pytest
from sqlmodel import Session

from app.core.exceptions import RevisionConflictError
from app.db.session import get_engine
from app.db.transactions import transaction
from app.repositories import WorkspaceRepository


def test_atomic_revision_check_rejects_stale_updates(db_session: Session) -> None:
    first_repository = WorkspaceRepository(db_session)
    original = first_repository.get_current()
    assert original is not None
    original_revision = original.revision

    with Session(get_engine()) as second_session:
        second_repository = WorkspaceRepository(second_session)
        stale = second_repository.get_current()
        assert stale is not None
        stale_revision = stale.revision

        with transaction(db_session):
            updated = first_repository.update_current(
                original.revision,
                {"name": "Updated once"},
            )
        assert updated.revision == original_revision + 1

        with pytest.raises(RevisionConflictError) as conflict, transaction(second_session):
            second_repository.update_current(
                stale.revision,
                {"name": "Stale update"},
            )

    assert conflict.value.details == {
        "expected_revision": stale_revision,
        "current_revision": updated.revision,
    }
