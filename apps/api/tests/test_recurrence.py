from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from app.utils.recurrence import canonicalize_rrule, expand_recurrence


def test_rrule_canonicalization_and_timezone_aware_expansion() -> None:
    rule = canonicalize_rrule("rrule:FREQ=WEEKLY;COUNT=3;BYDAY=MO,WE")
    assert rule == "FREQ=WEEKLY;COUNT=3;BYDAY=MO,WE"

    rome = ZoneInfo("Europe/Rome")
    occurrences = expand_recurrence(
        rule,
        dtstart=datetime(2026, 7, 15, 9, tzinfo=rome),
        range_start=datetime(2026, 7, 1, tzinfo=rome),
        range_end=datetime(2026, 8, 1, tzinfo=rome),
    )
    assert [(item.weekday(), item.hour) for item in occurrences] == [(2, 9), (0, 9), (2, 9)]
    assert all(item.tzinfo is not None for item in occurrences)


@pytest.mark.parametrize(
    "rule",
    [
        "",
        "FREQ=NOTREAL",
        "DTSTART:20260715T090000Z\nRRULE:FREQ=DAILY",
    ],
)
def test_invalid_or_noncanonical_rrules_are_rejected(rule: str) -> None:
    with pytest.raises(ValueError):
        canonicalize_rrule(rule)
