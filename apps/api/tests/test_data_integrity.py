from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.core.exceptions import DomainConflictError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    Commitment,
    CommitmentEntityType,
    FinancialAccount,
    FinancialAccountType,
    Task,
    TaskDependency,
    Transaction,
    TransactionType,
    Workspace,
)
from app.schemas.domain import CommitmentLinkCreate, TransactionCreate
from app.services.commitments import add_commitment_link, remove_commitment_link
from app.services.finance import create_transaction
from app.services.seed import DEFAULT_WORKSPACE_ID
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, StatementError
from sqlmodel import Session, select


def test_database_prevents_negative_durations_and_self_dependencies(
    db_session: Session,
) -> None:
    invalid_task = Task(
        workspace_id=DEFAULT_WORKSPACE_ID,
        title="Invalid duration",
        estimated_duration_minutes=-1,
    )
    db_session.add(invalid_task)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    task = Task(workspace_id=DEFAULT_WORKSPACE_ID, title="Dependency target")
    with transaction(db_session):
        db_session.add(task)
        db_session.flush()

    db_session.add(
        TaskDependency(
            workspace_id=DEFAULT_WORKSPACE_ID,
            task_id=task.id,
            depends_on_task_id=task.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_commitment_links_are_unique_and_deleting_a_link_preserves_records(
    db_session: Session,
) -> None:
    task = Task(workspace_id=DEFAULT_WORKSPACE_ID, title="Linked task")
    commitment = Commitment(workspace_id=DEFAULT_WORKSPACE_ID, title="Linked commitment")
    with transaction(db_session):
        db_session.add_all([task, commitment])
        db_session.flush()
    link = add_commitment_link(
        db_session,
        DEFAULT_WORKSPACE_ID,
        CommitmentLinkCreate(
            commitment_id=commitment.id,
            entity_type=CommitmentEntityType.TASK,
            entity_id=task.id,
        ),
    )

    remove_commitment_link(db_session, DEFAULT_WORKSPACE_ID, link.id)

    assert db_session.get(Task, task.id) is not None
    assert db_session.get(Commitment, commitment.id) is not None

    first = add_commitment_link(
        db_session,
        DEFAULT_WORKSPACE_ID,
        CommitmentLinkCreate(
            commitment_id=commitment.id,
            entity_type=CommitmentEntityType.TASK,
            entity_id=task.id,
        ),
    )
    assert first.entity_id == task.id
    with pytest.raises(DomainConflictError, match="already exists"):
        add_commitment_link(
            db_session,
            DEFAULT_WORKSPACE_ID,
            CommitmentLinkCreate(
                commitment_id=commitment.id,
                entity_type=CommitmentEntityType.TASK,
                entity_id=task.id,
            ),
        )

    with pytest.raises(DomainValidationError, match="same workspace"):
        add_commitment_link(
            db_session,
            DEFAULT_WORKSPACE_ID,
            CommitmentLinkCreate(
                commitment_id=commitment.id,
                entity_type=CommitmentEntityType.NOTE,
                entity_id=task.id,
            ),
        )

    other_workspace = Workspace(name="Other local workspace")
    other_task = Task(workspace_id=other_workspace.id, title="Other workspace task")
    with transaction(db_session):
        db_session.add_all([other_workspace, other_task])
        db_session.flush()
    with pytest.raises(DomainValidationError, match="same workspace"):
        add_commitment_link(
            db_session,
            DEFAULT_WORKSPACE_ID,
            CommitmentLinkCreate(
                commitment_id=commitment.id,
                entity_type=CommitmentEntityType.TASK,
                entity_id=other_task.id,
            ),
        )


def test_transfer_service_enforces_account_and_currency_relationships(
    db_session: Session,
) -> None:
    euro_source = FinancialAccount(
        workspace_id=DEFAULT_WORKSPACE_ID,
        name="EUR source",
        account_type=FinancialAccountType.CHECKING,
        currency_code="EUR",
    )
    euro_destination = FinancialAccount(
        workspace_id=DEFAULT_WORKSPACE_ID,
        name="EUR destination",
        account_type=FinancialAccountType.SAVINGS,
        currency_code="EUR",
    )
    usd_destination = FinancialAccount(
        workspace_id=DEFAULT_WORKSPACE_ID,
        name="USD destination",
        account_type=FinancialAccountType.SAVINGS,
        currency_code="USD",
    )
    with transaction(db_session):
        db_session.add_all([euro_source, euro_destination, usd_destination])
        db_session.flush()

    with pytest.raises(DomainValidationError, match="same currency"):
        create_transaction(
            db_session,
            DEFAULT_WORKSPACE_ID,
            TransactionCreate(
                account_id=euro_source.id,
                transfer_account_id=usd_destination.id,
                transaction_type=TransactionType.TRANSFER,
                amount_minor=2_500,
                currency_code="EUR",
                occurred_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
            ),
        )

    transfer = create_transaction(
        db_session,
        DEFAULT_WORKSPACE_ID,
        TransactionCreate(
            account_id=euro_source.id,
            transfer_account_id=euro_destination.id,
            transaction_type=TransactionType.TRANSFER,
            amount_minor=2_500,
            currency_code="EUR",
            occurred_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        ),
    )
    persisted = db_session.exec(select(Transaction).where(Transaction.id == transfer.id)).one()
    assert persisted.transfer_account_id == euro_destination.id
    assert persisted.amount_minor == 2_500

    with pytest.raises(ValidationError):
        TransactionCreate(
            account_id=euro_source.id,
            transaction_type=TransactionType.EXPENSE,
            amount_minor=100,
            currency_code="NOT",
            occurred_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        )


def test_persistence_boundary_rejects_invalid_iso_currency(db_session: Session) -> None:
    db_session.add(
        FinancialAccount(
            workspace_id=DEFAULT_WORKSPACE_ID,
            name="Invalid currency",
            account_type=FinancialAccountType.CASH,
            currency_code="ZZZ",
        )
    )
    with pytest.raises(StatementError, match="supported ISO 4217"):
        db_session.commit()
    db_session.rollback()
