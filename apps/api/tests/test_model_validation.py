from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from app.models import RecurrenceFrequency, ScenarioOperation, TransactionType
from app.schemas.common import MoneyAmount
from app.schemas.domain import (
    AttachmentCreate,
    BudgetCreate,
    CalendarEventCreate,
    RecurrenceInput,
    ScenarioChangeCreate,
    TaskCreate,
    TaskDependencyCreate,
    TransactionCreate,
)
from pydantic import ValidationError

NOW = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)


def test_task_constraints_reject_negative_duration_and_invalid_schedule() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="   ")

    with pytest.raises(ValidationError):
        TaskCreate(title="Invalid", estimated_duration_minutes=-1)

    with pytest.raises(ValidationError):
        TaskCreate(
            title="Invalid range",
            scheduled_start_at=NOW,
            scheduled_end_at=NOW - timedelta(minutes=1),
        )


def test_recurrence_requires_a_valid_explicit_shape() -> None:
    with pytest.raises(ValidationError):
        RecurrenceInput(frequency=RecurrenceFrequency.WEEKLY)

    with pytest.raises(ValidationError):
        RecurrenceInput(
            frequency=RecurrenceFrequency.DAILY,
            days_of_week=[1],
        )

    recurrence = RecurrenceInput(
        frequency=RecurrenceFrequency.WEEKLY,
        interval=2,
        days_of_week=[4, 1],
    )
    assert recurrence.days_of_week == [1, 4]


def test_calendar_supports_timed_and_all_day_events_with_valid_ranges() -> None:
    timed = CalendarEventCreate(
        title="Timed",
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        timezone="Europe/Rome",
    )
    assert timed.all_day is False

    all_day = CalendarEventCreate(
        title="All day",
        all_day=True,
        all_day_start=date(2026, 7, 15),
        all_day_end=date(2026, 7, 16),
        timezone="Europe/Rome",
    )
    assert all_day.all_day is True

    with pytest.raises(ValidationError):
        CalendarEventCreate(
            title="Naive",
            starts_at=datetime(2026, 7, 15, 10, 0),
            ends_at=datetime(2026, 7, 15, 11, 0),
        )


def test_transfer_and_dependency_shapes_prevent_self_relationships() -> None:
    account_id = uuid4()
    with pytest.raises(ValidationError):
        TransactionCreate(
            account_id=account_id,
            transfer_account_id=account_id,
            transaction_type=TransactionType.TRANSFER,
            amount_minor=100,
            currency_code="EUR",
            occurred_at=NOW,
        )

    task_id = uuid4()
    with pytest.raises(ValidationError):
        TaskDependencyCreate(task_id=task_id, depends_on_task_id=task_id)


def test_storage_paths_currency_and_date_ranges_are_validated() -> None:
    with pytest.raises(ValidationError):
        AttachmentCreate(
            storage_path="../secrets.txt",
            original_filename="secrets.txt",
            media_type="text/plain",
            size_bytes=1,
        )

    with pytest.raises(ValidationError):
        MoneyAmount(amount_minor=100, currency_code="ZZZ")

    with pytest.raises(ValidationError):
        BudgetCreate(
            name="Invalid",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 7, 1),
            currency_code="EUR",
        )


def test_scenario_change_shape_is_explicit() -> None:
    with pytest.raises(ValidationError):
        ScenarioChangeCreate(
            scenario_id=uuid4(),
            entity_type="task",
            entity_id=uuid4(),
            operation=ScenarioOperation.UPDATE,
            changes={},
        )
