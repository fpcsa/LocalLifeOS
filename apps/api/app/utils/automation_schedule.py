from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.schemas.automation import (
    AutomationSchedule,
    AutomationScheduleFrequency,
    AutomationTrigger,
)


def build_schedule_trigger(schedule: AutomationSchedule, *, now: datetime) -> BaseTrigger:
    timezone = ZoneInfo(schedule.timezone)
    if schedule.frequency == AutomationScheduleFrequency.INTERVAL:
        return IntervalTrigger(
            minutes=schedule.interval_minutes,
            timezone=timezone,
            start_date=now.replace(microsecond=0)
            + timedelta(minutes=schedule.interval_minutes or 1),
        )
    if schedule.local_time is None:
        raise ValueError("scheduled local time is required")
    day_of_week = None
    if schedule.frequency == AutomationScheduleFrequency.WEEKLY:
        day_of_week = ",".join(str(value) for value in schedule.weekdays)
    return CronTrigger(
        hour=schedule.local_time.hour,
        minute=schedule.local_time.minute,
        day_of_week=day_of_week,
        timezone=timezone,
    )


def next_scheduled_run(trigger: AutomationTrigger, *, now: datetime) -> datetime | None:
    if trigger.schedule is None:
        return None
    apscheduler_trigger = build_schedule_trigger(trigger.schedule, now=now)
    return cast(datetime | None, apscheduler_trigger.get_next_fire_time(None, now))
