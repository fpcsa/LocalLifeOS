from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from math import ceil, floor
from zoneinfo import ZoneInfo

from app.schemas.scheduling import SchedulingPolicyInput, WeeklyAvailabilityWindow
from app.services.scheduling_types import TimeInterval


def clip_interval(
    interval: TimeInterval,
    starts_at: datetime,
    ends_at: datetime,
) -> TimeInterval | None:
    clipped_start = max(interval.starts_at, starts_at)
    clipped_end = min(interval.ends_at, ends_at)
    if clipped_end <= clipped_start:
        return None
    return TimeInterval(clipped_start, clipped_end)


def merge_intervals(intervals: list[TimeInterval]) -> list[TimeInterval]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: (item.starts_at, item.ends_at))
    merged = [ordered[0]]
    for interval in ordered[1:]:
        previous = merged[-1]
        if interval.starts_at <= previous.ends_at:
            merged[-1] = TimeInterval(
                previous.starts_at,
                max(previous.ends_at, interval.ends_at),
            )
        else:
            merged.append(interval)
    return merged


def intersect_intervals(
    first: list[TimeInterval],
    second: list[TimeInterval],
) -> list[TimeInterval]:
    left = merge_intervals(first)
    right = merge_intervals(second)
    result: list[TimeInterval] = []
    left_index = right_index = 0
    while left_index < len(left) and right_index < len(right):
        starts_at = max(left[left_index].starts_at, right[right_index].starts_at)
        ends_at = min(left[left_index].ends_at, right[right_index].ends_at)
        if ends_at > starts_at:
            result.append(TimeInterval(starts_at, ends_at))
        if left[left_index].ends_at <= right[right_index].ends_at:
            left_index += 1
        else:
            right_index += 1
    return result


def subtract_intervals(
    bases: list[TimeInterval],
    exclusions: list[TimeInterval],
) -> list[TimeInterval]:
    remaining: list[TimeInterval] = []
    merged_exclusions = merge_intervals(exclusions)
    for base in merge_intervals(bases):
        cursor = base.starts_at
        for exclusion in merged_exclusions:
            if exclusion.ends_at <= cursor:
                continue
            if exclusion.starts_at >= base.ends_at:
                break
            if exclusion.starts_at > cursor:
                remaining.append(TimeInterval(cursor, min(exclusion.starts_at, base.ends_at)))
            cursor = max(cursor, exclusion.ends_at)
            if cursor >= base.ends_at:
                break
        if cursor < base.ends_at:
            remaining.append(TimeInterval(cursor, base.ends_at))
    return remaining


def _normalize_local_wall_time(local_date: date, wall_time: time, timezone: ZoneInfo) -> datetime:
    naive = datetime.combine(local_date, wall_time)
    candidate = naive.replace(tzinfo=timezone, fold=0)
    round_trip = candidate.astimezone(UTC).astimezone(timezone)
    if round_trip.replace(tzinfo=None) != naive:
        return round_trip
    return candidate


def local_wall_to_utc(local_date: date, wall_time: time, timezone_name: str) -> datetime:
    return _normalize_local_wall_time(local_date, wall_time, ZoneInfo(timezone_name)).astimezone(
        UTC
    )


def _weekly_window_interval(
    local_date: date,
    window: WeeklyAvailabilityWindow,
    timezone: ZoneInfo,
) -> TimeInterval:
    end_date = local_date + timedelta(days=window.end_time <= window.start_time)
    local_start = _normalize_local_wall_time(local_date, window.start_time, timezone)
    local_end = _normalize_local_wall_time(end_date, window.end_time, timezone)
    return TimeInterval(local_start.astimezone(UTC), local_end.astimezone(UTC))


def build_availability_intervals(
    planning_start_at: datetime,
    planning_end_at: datetime,
    timezone_name: str,
    policy: SchedulingPolicyInput,
) -> list[TimeInterval]:
    timezone = ZoneInfo(timezone_name)
    local_start = planning_start_at.astimezone(timezone).date() - timedelta(days=1)
    local_end = planning_end_at.astimezone(timezone).date() + timedelta(days=1)
    working: list[TimeInterval] = []
    cursor = local_start
    while cursor <= local_end:
        for window in policy.working_hours:
            if window.weekday == cursor.weekday():
                working.append(_weekly_window_interval(cursor, window, timezone))
        cursor += timedelta(days=1)
    personal = [
        TimeInterval(item.starts_at.astimezone(UTC), item.ends_at.astimezone(UTC))
        for item in policy.personal_availability_windows
    ]
    clipped = [
        result
        for interval in [*working, *personal]
        if (
            result := clip_interval(
                interval,
                planning_start_at.astimezone(UTC),
                planning_end_at.astimezone(UTC),
            )
        )
        is not None
    ]
    return merge_intervals(clipped)


def local_day_intervals(
    planning_start_at: datetime,
    planning_end_at: datetime,
    timezone_name: str,
) -> list[tuple[date, TimeInterval]]:
    timezone = ZoneInfo(timezone_name)
    start_date = planning_start_at.astimezone(timezone).date()
    end_date = (planning_end_at - timedelta(microseconds=1)).astimezone(timezone).date()
    result: list[tuple[date, TimeInterval]] = []
    cursor = start_date
    while cursor <= end_date:
        local_start = _normalize_local_wall_time(cursor, time.min, timezone).astimezone(UTC)
        local_end = _normalize_local_wall_time(
            cursor + timedelta(days=1),
            time.min,
            timezone,
        ).astimezone(UTC)
        clipped = clip_interval(
            TimeInterval(local_start, local_end),
            planning_start_at.astimezone(UTC),
            planning_end_at.astimezone(UTC),
        )
        if clipped is not None:
            result.append((cursor, clipped))
        cursor += timedelta(days=1)
    return result


def interval_minutes(intervals: list[TimeInterval]) -> int:
    return sum(item.duration_minutes for item in merge_intervals(intervals))


def ceil_minutes(value: datetime, origin: datetime) -> int:
    return int(ceil((value - origin).total_seconds() / 60))


def floor_minutes(value: datetime, origin: datetime) -> int:
    return int(floor((value - origin).total_seconds() / 60))
