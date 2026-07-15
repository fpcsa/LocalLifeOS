from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session


@contextmanager
def transaction(session: Session) -> Iterator[Session]:
    """Commit one service operation atomically or roll it back completely."""

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
