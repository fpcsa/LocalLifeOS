from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.schemas.scheduling import CapacityDay, CapacityReport, CapacityWeek, SchedulingPolicyInput
from app.services.scheduling_intervals import (
    intersect_intervals,
    interval_minutes,
    local_day_intervals,
    subtract_intervals,
)
from app.services.scheduling_types import SchedulingEvidence, TimeInterval


def _week_start(local_date: date, week_starts_on: int) -> date:
    return local_date - timedelta(days=(local_date.weekday() - week_starts_on) % 7)


def calculate_capacity(
    evidence: SchedulingEvidence,
    *,
    planning_start_at: datetime,
    planning_end_at: datetime,
    policy: SchedulingPolicyInput,
    availability: list[TimeInterval],
    required_task_minutes: int,
    suggested_by_local_date: dict[date, int] | None = None,
    commitment_id: UUID | None = None,
) -> CapacityReport:
    suggestions = suggested_by_local_date or {}
    busy = [TimeInterval(item.starts_at, item.ends_at) for item in evidence.all_busy]
    task_busy = [TimeInterval(item.starts_at, item.ends_at) for item in evidence.task_busy]
    days: list[CapacityDay] = []
    available_before_suggestions = 0
    for local_date, day_interval in local_day_intervals(
        planning_start_at,
        planning_end_at,
        evidence.timezone_name,
    ):
        day_bounds = [day_interval]
        day_busy = intersect_intervals(day_bounds, busy)
        day_task_busy = intersect_intervals(day_bounds, task_busy)
        raw_free = day_interval.duration_minutes - interval_minutes(day_busy)
        eligible_windows = intersect_intervals(day_bounds, availability)
        eligible_free = subtract_intervals(eligible_windows, day_busy)
        eligible_minutes = interval_minutes(eligible_free)
        focus_minutes = sum(
            interval.duration_minutes
            for interval in eligible_free
            if interval.duration_minutes >= policy.minimum_focus_block_minutes
        )
        committed = interval_minutes(day_busy)
        scheduled_tasks = interval_minutes(day_task_busy)
        suggested = suggestions.get(local_date, 0)
        workload_headroom = max(
            0,
            policy.maximum_scheduled_minutes_per_day - committed,
        )
        available_today = min(focus_minutes, workload_headroom)
        available_before_suggestions += available_today
        remaining = max(0, available_today - suggested)
        overload = max(
            0,
            committed + suggested - policy.maximum_scheduled_minutes_per_day,
        )
        days.append(
            CapacityDay(
                local_date=local_date,
                raw_free_minutes=max(0, raw_free),
                eligible_schedulable_minutes=eligible_minutes,
                focus_capable_minutes=focus_minutes,
                already_committed_minutes=committed,
                existing_scheduled_task_minutes=scheduled_tasks,
                suggested_task_minutes=suggested,
                remaining_capacity_minutes=remaining,
                overload_minutes=overload,
            )
        )

    grouped: dict[date, list[CapacityDay]] = defaultdict(list)
    for day in days:
        grouped[_week_start(day.local_date, evidence.week_starts_on)].append(day)
    weeks = [
        CapacityWeek(
            week_start_date=week_start,
            week_end_date=week_start + timedelta(days=6),
            raw_free_minutes=sum(item.raw_free_minutes for item in week_days),
            eligible_schedulable_minutes=sum(
                item.eligible_schedulable_minutes for item in week_days
            ),
            focus_capable_minutes=sum(item.focus_capable_minutes for item in week_days),
            already_committed_minutes=sum(item.already_committed_minutes for item in week_days),
            suggested_task_minutes=sum(item.suggested_task_minutes for item in week_days),
            remaining_capacity_minutes=sum(item.remaining_capacity_minutes for item in week_days),
            overload_minutes=max(
                0,
                sum(
                    item.already_committed_minutes + item.suggested_task_minutes
                    for item in week_days
                )
                - policy.maximum_scheduled_minutes_per_day * len(week_days),
            ),
        )
        for week_start, week_days in sorted(grouped.items())
    ]
    return CapacityReport(
        timezone=evidence.timezone_name,
        planning_start_at=planning_start_at,
        planning_end_at=planning_end_at,
        commitment_id=commitment_id,
        required_task_minutes=required_task_minutes,
        available_focus_minutes=available_before_suggestions,
        remaining_capacity_minutes=sum(item.remaining_capacity_minutes for item in days),
        required_minus_available_minutes=max(
            0,
            required_task_minutes - available_before_suggestions,
        ),
        days=days,
        weeks=weeks,
        assumptions=[
            (
                "Raw free time is local clock time minus the union of hard calendar "
                "and task intervals."
            ),
            (
                "Eligible time is the union of weekly working hours and explicit personal "
                "availability, minus hard intervals."
            ),
            (
                "Focus-capable time counts only eligible free intervals at least as long as "
                f"the {policy.minimum_focus_block_minutes}-minute focus minimum."
            ),
            (
                "Remaining daily capacity is capped by both focus-capable time and the "
                f"{policy.maximum_scheduled_minutes_per_day}-minute workload limit."
            ),
            "Overlapping hard commitments are counted once when calculating occupied time.",
            (
                "A suggested task crossing local midnight is charged to its local start day "
                "for workload-limit accounting."
            ),
        ],
    )


def suggestion_minutes_by_local_date(
    placements: list[tuple[datetime, int]],
    timezone_name: str,
) -> dict[date, int]:
    timezone = ZoneInfo(timezone_name)
    result: dict[date, int] = defaultdict(int)
    for starts_at, duration in placements:
        result[starts_at.astimezone(timezone).date()] += duration
    return dict(result)
