from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from dateutil.rrule import rrulebase, rrulestr

from app.models.common import RecurrenceFrequency

WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
VALIDATION_START = datetime(2000, 1, 3, tzinfo=UTC)
MAX_RRULE_LENGTH = 1000
MAX_OCCURRENCES = 1000


def canonicalize_rrule(value: str) -> str:
    """Validate one RFC 5545-compatible RRULE and return a stable representation."""

    candidate = value.strip()
    if candidate.upper().startswith("RRULE:"):
        candidate = candidate[6:]
    if not candidate or len(candidate) > MAX_RRULE_LENGTH:
        raise ValueError("rrule must contain between 1 and 1000 characters")
    if "\n" in candidate or "\r" in candidate:
        raise ValueError("rrule must contain exactly one recurrence rule")

    segments: list[str] = []
    for segment in candidate.split(";"):
        key, separator, raw_value = segment.partition("=")
        if not separator or not key or not raw_value:
            raise ValueError("rrule contains an invalid property")
        segments.append(f"{key.upper()}={raw_value.upper()}")
    canonical = ";".join(segments)
    if not canonical.startswith("FREQ=") and ";FREQ=" not in canonical:
        raise ValueError("rrule requires FREQ")

    try:
        parsed = rrulestr(canonical, dtstart=VALIDATION_START)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("rrule is not a valid recurrence rule") from exc
    if not isinstance(parsed, rrulebase):
        raise ValueError("rrule must describe one recurrence rule")
    return canonical


def build_rrule(
    frequency: RecurrenceFrequency,
    *,
    interval: int = 1,
    days_of_week: Iterable[int] | None = None,
    end_at: datetime | None = None,
) -> str:
    parts = [f"FREQ={frequency.value.upper()}", f"INTERVAL={interval}"]
    if days_of_week is not None:
        parts.append("BYDAY=" + ",".join(WEEKDAY_CODES[day] for day in days_of_week))
    if end_at is not None:
        normalized = end_at.astimezone(UTC)
        parts.append(normalized.strftime("UNTIL=%Y%m%dT%H%M%SZ"))
    return canonicalize_rrule(";".join(parts))


def expand_recurrence(
    rrule_value: str,
    *,
    dtstart: datetime,
    range_start: datetime,
    range_end: datetime,
    limit: int = MAX_OCCURRENCES,
) -> list[datetime]:
    if any(
        value.tzinfo is None or value.utcoffset() is None
        for value in (dtstart, range_start, range_end)
    ):
        raise ValueError("recurrence datetimes must include a timezone offset")
    if range_end <= range_start:
        raise ValueError("range_end must be after range_start")
    if limit < 1 or limit > MAX_OCCURRENCES:
        raise ValueError(f"limit must be between 1 and {MAX_OCCURRENCES}")

    canonical = canonicalize_rrule(rrule_value)
    try:
        parsed = rrulestr(canonical, dtstart=dtstart)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("rrule is incompatible with its start datetime") from exc

    occurrences: list[datetime] = []
    for occurrence in parsed.xafter(range_start, count=limit + 1, inc=True):
        if occurrence >= range_end:
            break
        if len(occurrences) == limit:
            raise ValueError(f"recurrence expands beyond the {limit}-occurrence limit")
        occurrences.append(occurrence)
    return occurrences
