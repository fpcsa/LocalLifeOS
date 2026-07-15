from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, col, select

from app.models import FinancialAccount, Transaction
from app.repositories.base import BaseRepository


class FinancialAccountRepository(BaseRepository[FinancialAccount]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, FinancialAccount)

    def get_active(self, workspace_id: UUID, account_id: UUID) -> FinancialAccount | None:
        return self.session.exec(
            select(FinancialAccount).where(
                col(FinancialAccount.id) == account_id,
                col(FinancialAccount.workspace_id) == workspace_id,
                col(FinancialAccount.deleted_at).is_(None),
            )
        ).first()


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Transaction)
