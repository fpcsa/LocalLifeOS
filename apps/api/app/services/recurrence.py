from __future__ import annotations

from typing import Any

from app.schemas.domain import RecurrenceInput
from app.utils.recurrence import build_rrule


def recurrence_values(recurrence: RecurrenceInput | None) -> dict[str, Any]:
    if recurrence is None:
        return {
            "recurrence_frequency": None,
            "recurrence_interval": None,
            "recurrence_days_of_week": None,
            "recurrence_end_at": None,
            "recurrence_rrule": None,
        }
    if recurrence.rrule is not None:
        return {
            "recurrence_frequency": None,
            "recurrence_interval": None,
            "recurrence_days_of_week": None,
            "recurrence_end_at": None,
            "recurrence_rrule": recurrence.rrule,
        }
    if recurrence.frequency is None:
        raise ValueError("explicit recurrence requires frequency")
    return {
        "recurrence_frequency": recurrence.frequency,
        "recurrence_interval": recurrence.interval,
        "recurrence_days_of_week": recurrence.days_of_week,
        "recurrence_end_at": recurrence.end_at,
        "recurrence_rrule": build_rrule(
            recurrence.frequency,
            interval=recurrence.interval,
            days_of_week=recurrence.days_of_week,
            end_at=recurrence.end_at,
        ),
    }
