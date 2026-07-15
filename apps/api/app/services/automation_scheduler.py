from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.db.session import get_engine
from app.db.transactions import transaction
from app.models import (
    AutomationRule,
    AutomationTriggerType,
    CalendarEvent,
    CalendarEventStatus,
    Task,
    TaskStatus,
)
from app.models.common import utc_now
from app.repositories.automation import AutomationRuleRepository
from app.schemas.automation import AutomationTrigger, SchedulerStatusResponse
from app.services.automation import execute_automation_rule
from app.services.workspace import get_current_workspace
from app.utils.automation_schedule import build_schedule_trigger, next_scheduled_run

RULE_JOB_PREFIX = "automation-rule:"
SCAN_JOB_ID = "automation-time-driven-scan"

_scheduler: BackgroundScheduler | None = None
_scheduler_lock = threading.RLock()


def _scheduled_rule_job(rule_id: UUID, scheduled_at: str | None = None) -> None:
    with Session(get_engine()) as session:
        workspace = get_current_workspace(session)
        rule = AutomationRuleRepository(session).get_active(workspace.id, rule_id)
        if rule is None or not rule.enabled:
            return
        trigger = AutomationTrigger.model_validate(rule.trigger)
        if trigger.type != AutomationTriggerType.RECURRING_SCHEDULE:
            return
        run_at = datetime.fromisoformat(scheduled_at) if scheduled_at else utc_now()
        execute_automation_rule(
            session,
            rule,
            context={"scheduled_at": run_at.isoformat()},
            source_key=run_at.replace(second=0, microsecond=0).isoformat(),
        )
        with transaction(session):
            rule.next_run_at = next_scheduled_run(
                trigger, now=max(utc_now(), run_at) + timedelta(seconds=1)
            )
            session.add(rule)


def _scan_time_driven_automations() -> None:
    with Session(get_engine()) as session:
        workspace = get_current_workspace(session)
        now = utc_now()
        repository = AutomationRuleRepository(session)

        for rule in repository.list_enabled_trigger(
            workspace.id, AutomationTriggerType.EVENT_APPROACHING
        ):
            trigger = AutomationTrigger.model_validate(rule.trigger)
            lookahead = trigger.lookahead_minutes or 1_440
            events = session.exec(
                select(CalendarEvent).where(
                    col(CalendarEvent.workspace_id) == workspace.id,
                    col(CalendarEvent.deleted_at).is_(None),
                    col(CalendarEvent.all_day).is_(False),
                    col(CalendarEvent.status) != CalendarEventStatus.CANCELLED,
                    col(CalendarEvent.starts_at).is_not(None),
                    col(CalendarEvent.starts_at) >= now,
                    col(CalendarEvent.starts_at) <= now + timedelta(minutes=lookahead),
                )
            ).all()
            for event in events:
                if event.starts_at is None:
                    continue
                execute_automation_rule(
                    session,
                    rule,
                    context={
                        "entity_type": "calendar_event",
                        "entity_id": str(event.id),
                        "title": event.title,
                        "category": event.category,
                        "location": event.location,
                        "status": event.status.value,
                        "timezone": event.timezone,
                        "minutes_until": max(0, int((event.starts_at - now).total_seconds() // 60)),
                    },
                    source_key=f"event:{event.id}:{event.starts_at.isoformat()}",
                )

        terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
        overdue_tasks = session.exec(
            select(Task).where(
                col(Task.workspace_id) == workspace.id,
                col(Task.deleted_at).is_(None),
                col(Task.due_at).is_not(None),
                col(Task.due_at) < now,
                col(Task.status).not_in(terminal_statuses),
            )
        ).all()
        for rule in repository.list_enabled_trigger(
            workspace.id, AutomationTriggerType.TASK_OVERDUE
        ):
            for task in overdue_tasks:
                if task.due_at is None:
                    continue
                execute_automation_rule(
                    session,
                    rule,
                    context={
                        "entity_type": "task",
                        "entity_id": str(task.id),
                        "title": task.title,
                        "status": task.status.value,
                        "priority": task.priority.value,
                        "project_id": str(task.project_id) if task.project_id else None,
                        "overdue_days": max(1, (now.date() - task.due_at.date()).days),
                    },
                    source_key=f"task:{task.id}:{task.due_at.isoformat()}",
                )


def reconcile_scheduler(
    session: Session,
    scheduler: BaseScheduler,
    *,
    run_catch_up: bool,
) -> list[UUID]:
    workspace = get_current_workspace(session)
    now = utc_now()
    desired: dict[str, AutomationRule] = {}
    for rule in AutomationRuleRepository(session).list_enabled_trigger(
        workspace.id, AutomationTriggerType.RECURRING_SCHEDULE
    ):
        desired[f"{RULE_JOB_PREFIX}{rule.id}"] = rule

    for job in scheduler.get_jobs():
        if job.id.startswith(RULE_JOB_PREFIX) and job.id not in desired:
            scheduler.remove_job(job.id)

    scheduled_ids: list[UUID] = []
    for job_id, rule in desired.items():
        trigger = AutomationTrigger.model_validate(rule.trigger)
        if run_catch_up and rule.next_run_at is not None and rule.next_run_at <= now:
            scheduled_at = rule.next_run_at
            execute_automation_rule(
                session,
                rule,
                context={"scheduled_at": scheduled_at.isoformat()},
                source_key=scheduled_at.replace(second=0, microsecond=0).isoformat(),
            )
        schedule = trigger.schedule
        if schedule is None:
            continue
        scheduler.add_job(
            _scheduled_rule_job,
            trigger=build_schedule_trigger(schedule, now=now),
            args=[rule.id],
            id=job_id,
            name=rule.name,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3_600,
        )
        next_run = next_scheduled_run(trigger, now=now)
        if rule.next_run_at != next_run:
            with transaction(session):
                rule.next_run_at = next_run
                session.add(rule)
        scheduled_ids.append(rule.id)
    return scheduled_ids


def request_scheduler_sync() -> None:
    scheduler = _scheduler
    if scheduler is None or not scheduler.running:
        return
    with _scheduler_lock, Session(get_engine()) as session:
        reconcile_scheduler(session, scheduler, run_catch_up=False)


def start_automation_scheduler() -> None:
    global _scheduler
    if not get_settings().automation_scheduler_enabled:
        return
    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            return
        scheduler = BackgroundScheduler(timezone=UTC)
        scheduler.start(paused=True)
        with Session(get_engine()) as session:
            reconcile_scheduler(session, scheduler, run_catch_up=True)
        scheduler.add_job(
            _scan_time_driven_automations,
            trigger=IntervalTrigger(minutes=1, timezone=UTC),
            id=SCAN_JOB_ID,
            name="LocalLife time-driven automation scan",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.resume()
        _scheduler = scheduler


def stop_automation_scheduler() -> None:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None


def scheduler_status() -> SchedulerStatusResponse:
    scheduler = _scheduler
    if scheduler is None or not scheduler.running:
        return SchedulerStatusResponse(running=False, scheduled_rule_ids=[], next_wakeup_at=None)
    jobs = scheduler.get_jobs()
    rule_ids = [
        UUID(job.id.removeprefix(RULE_JOB_PREFIX))
        for job in jobs
        if job.id.startswith(RULE_JOB_PREFIX)
    ]
    next_runs = [job.next_run_time for job in jobs if job.next_run_time is not None]
    return SchedulerStatusResponse(
        running=True,
        scheduled_rule_ids=sorted(rule_ids, key=str),
        next_wakeup_at=min(next_runs) if next_runs else None,
    )
