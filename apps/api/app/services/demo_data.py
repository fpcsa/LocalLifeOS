from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final
from uuid import UUID

from sqlmodel import Session, col, select

from app.core.config import REPOSITORY_ROOT, get_settings
from app.db.transactions import transaction
from app.models import (
    Attachment,
    AttachmentEntityLink,
    AutomationRule,
    Budget,
    BudgetCategoryLimit,
    BudgetPeriod,
    CalendarEvent,
    CalendarEventEntityLink,
    Commitment,
    CommitmentEntityLink,
    CommitmentEntityType,
    CommitmentStatus,
    DomainEntityType,
    FinancialAccount,
    FinancialAccountType,
    GoalStatus,
    Note,
    NoteEntityLink,
    NoteLink,
    PlannedTransaction,
    Project,
    ProjectStatus,
    RecurringTransactionRule,
    RecurringTransactionStatus,
    SavingsGoal,
    Scenario,
    ScenarioChange,
    ScenarioOperation,
    Subscription,
    SubscriptionStatus,
    Tag,
    TagEntityLink,
    Task,
    TaskDependency,
    TaskPriority,
    TaskStatus,
    TimelineEvent,
    Transaction,
    TransactionType,
    UserPreferences,
)
from app.schemas.demo import DemoDataResetSummary, DemoDataSummary
from app.services.seed import DEFAULT_CATEGORIES
from app.services.storage_lock import STORAGE_LOCK
from app.services.workspace import get_current_workspace

DATASET_VERSION: Final = "2026.07"
ANCHOR_DATE: Final = "2026-07-16"
CREATED_AT: Final = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
DEMO_PREFIX: Final = "12000000"


def _id(value: int) -> UUID:
    return UUID(f"{DEMO_PREFIX}-0000-4000-8000-{value:012d}")


IDS: Final = {
    "tag_demo": _id(1),
    "tag_build_week": _id(2),
    "tag_household": _id(3),
    "account_checking": _id(10),
    "account_savings": _id(11),
    "project_build_week": _id(20),
    "project_household": _id(21),
    "task_prototype": _id(30),
    "task_demo_script": _id(31),
    "task_backup": _id(32),
    "task_groceries": _id(33),
    "task_conference": _id(34),
    "task_dependency": _id(35),
    "note_daily": _id(40),
    "note_build_week": _id(41),
    "note_conference": _id(42),
    "note_link": _id(43),
    "note_entity_link": _id(44),
    "event_deep_work": _id(50),
    "event_dentist": _id(51),
    "event_briefing": _id(52),
    "event_review": _id(53),
    "event_build_week": _id(54),
    "event_reset": _id(55),
    "event_link": _id(56),
    "transaction_salary": _id(60),
    "transaction_rent": _id(61),
    "transaction_groceries": _id(62),
    "transaction_utilities": _id(63),
    "transaction_transport": _id(64),
    "subscription_video": _id(70),
    "subscription_cloud": _id(71),
    "recurring_salary": _id(72),
    "planned_laptop": _id(73),
    "budget_july": _id(74),
    "budget_food": _id(75),
    "budget_transport": _id(76),
    "savings_emergency": _id(77),
    "commitment_build_week": _id(80),
    "commitment_berlin": _id(81),
    "commitment_laptop": _id(82),
    "commitment_link_project": _id(83),
    "commitment_link_event": _id(84),
    "commitment_link_task": _id(85),
    "commitment_link_plan": _id(86),
    "commitment_link_note": _id(87),
    "automation_overdue": _id(90),
    "automation_backup": _id(91),
    "scenario_physical": _id(100),
    "scenario_remote": _id(101),
    "scenario_skip": _id(102),
    "scenario_laptop_august": _id(103),
    "scenario_laptop_october": _id(104),
    "scenario_change_physical": _id(110),
    "scenario_change_remote": _id(111),
    "scenario_change_skip": _id(112),
    "scenario_change_august": _id(113),
    "scenario_change_october": _id(114),
    "attachment_agenda": _id(120),
    "attachment_laptop": _id(121),
    "attachment_link_agenda": _id(122),
    "attachment_link_laptop": _id(123),
}

CATEGORY_IDS: Final = {name: category_id for category_id, name, _ in DEFAULT_CATEGORIES}


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, day, hour, minute, tzinfo=UTC)


def _entity(model: type, key: str, workspace_id: UUID, **values: object):  # type: ignore[no-untyped-def]
    return model(
        id=IDS[key],
        workspace_id=workspace_id,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        **values,
    )


def _attachment_source(filename: str) -> Path:
    candidates = (
        REPOSITORY_ROOT / "data" / "demo" / "attachments" / filename,
        REPOSITORY_ROOT / "apps" / "api" / "demo-assets" / filename,
    )
    for source in candidates:
        if source.is_file():
            return source
    raise RuntimeError(f"Demo attachment is missing: {filename}")


def _attachment_target(workspace_id: UUID, attachment_id: UUID, suffix: str) -> tuple[str, Path]:
    settings = get_settings()
    if settings.attachments_dir is None:
        raise RuntimeError("attachments directory was not configured")
    relative = Path(workspace_id.hex) / f"{attachment_id.hex}{suffix}"
    root = settings.attachments_dir.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise RuntimeError("demo attachment path escaped the attachments directory")
    return relative.as_posix(), target


def _copy_demo_attachments(workspace_id: UUID) -> tuple[list[Attachment], list[Path]]:
    specifications = (
        ("attachment_agenda", "build-week-agenda.txt", ".txt", "text/plain"),
        ("attachment_laptop", "laptop-comparison.md", ".md", "text/markdown"),
    )
    attachments: list[Attachment] = []
    written: list[Path] = []
    with STORAGE_LOCK:
        for key, filename, suffix, media_type in specifications:
            content = _attachment_source(filename).read_bytes()
            storage_path, target = _attachment_target(workspace_id, IDS[key], suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.demo-load")
            temporary.write_bytes(content)
            temporary.replace(target)
            written.append(target)
            attachments.append(
                _entity(
                    Attachment,
                    key,
                    workspace_id,
                    storage_path=storage_path,
                    original_filename=filename,
                    media_type=media_type,
                    size_bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                )
            )
    return attachments, written


def _timeline_events(workspace_id: UUID) -> list[TimelineEvent]:
    rows = (
        (
            200,
            DomainEntityType.PROJECT,
            "project_build_week",
            "project_created",
            "Project created: OpenAI Build Week project",
        ),
        (
            201,
            DomainEntityType.TASK,
            "task_prototype",
            "task_created",
            "Task created: Finish local-first prototype",
        ),
        (
            202,
            DomainEntityType.NOTE,
            "note_build_week",
            "note_created",
            "Note created: Build Week working notes",
        ),
        (
            203,
            DomainEntityType.CALENDAR_EVENT,
            "event_deep_work",
            "calendar_event_created",
            "Calendar event created: Prototype deep work",
        ),
        (
            204,
            DomainEntityType.TRANSACTION,
            "transaction_salary",
            "transaction_created",
            "Income recorded: Synthetic salary",
        ),
        (
            205,
            DomainEntityType.BUDGET,
            "budget_july",
            "budget_created",
            "Budget created: July household budget",
        ),
        (
            206,
            DomainEntityType.SAVINGS_GOAL,
            "savings_emergency",
            "savings_goal_created",
            "Savings goal created: Emergency fund",
        ),
        (
            207,
            DomainEntityType.COMMITMENT,
            "commitment_build_week",
            "commitment_created",
            "Commitment created: OpenAI Build Week",
        ),
        (
            208,
            DomainEntityType.COMMITMENT,
            "commitment_berlin",
            "commitment_created",
            "Commitment created: Berlin conference",
        ),
        (
            209,
            DomainEntityType.COMMITMENT,
            "commitment_laptop",
            "commitment_created",
            "Commitment created: Laptop purchase",
        ),
        (
            210,
            DomainEntityType.SCENARIO,
            "scenario_physical",
            "scenario_created",
            "Scenario created: Berlin · physical attendance",
        ),
        (
            211,
            DomainEntityType.AUTOMATION_RULE,
            "automation_backup",
            "automation_rule_created",
            "Automation rule created: Weekly backup reminder",
        ),
    )
    return [
        TimelineEvent(
            id=_id(number),
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=IDS[entity_key],
            action=action,
            title=title,
            occurred_at=CREATED_AT,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
            payload={"demo": True, "dataset_version": DATASET_VERSION},
        )
        for number, entity_type, entity_key, action, title in rows
    ]


def _records(workspace_id: UUID) -> list[object]:
    tags = [
        _entity(Tag, "tag_demo", workspace_id, name="demo", color="#475569"),
        _entity(Tag, "tag_build_week", workspace_id, name="build-week", color="#2563eb"),
        _entity(Tag, "tag_household", workspace_id, name="household", color="#15803d"),
    ]
    accounts = [
        _entity(
            FinancialAccount,
            "account_checking",
            workspace_id,
            name="Everyday checking · synthetic",
            account_type=FinancialAccountType.CHECKING,
            currency_code="EUR",
            opening_balance_minor=420_000,
            financial_buffer_minor=100_000,
        ),
        _entity(
            FinancialAccount,
            "account_savings",
            workspace_id,
            name="Emergency savings · synthetic",
            account_type=FinancialAccountType.SAVINGS,
            currency_code="EUR",
            opening_balance_minor=250_000,
            financial_buffer_minor=200_000,
        ),
    ]
    projects = [
        _entity(
            Project,
            "project_build_week",
            workspace_id,
            name="OpenAI Build Week project",
            description_markdown="Ship a private, local-first life planning demo.",
            status=ProjectStatus.ACTIVE,
            target_start_date=date(2026, 7, 13),
            target_end_date=date(2026, 7, 24),
        ),
        _entity(
            Project,
            "project_household",
            workspace_id,
            name="Household reset",
            description_markdown="Routine home administration for the demo household.",
            status=ProjectStatus.ACTIVE,
            target_end_date=date(2026, 7, 31),
        ),
    ]
    tasks = [
        _entity(
            Task,
            "task_prototype",
            workspace_id,
            project_id=IDS["project_build_week"],
            title="Finish local-first prototype",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.URGENT,
            estimated_duration_minutes=180,
            due_at=_at(20, 16),
            scheduled_start_at=_at(20, 9),
            scheduled_end_at=_at(20, 12),
        ),
        _entity(
            Task,
            "task_demo_script",
            workspace_id,
            project_id=IDS["project_build_week"],
            parent_task_id=IDS["task_prototype"],
            title="Rehearse the three-minute demo",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            estimated_duration_minutes=45,
            due_at=_at(21, 17),
        ),
        _entity(
            Task,
            "task_backup",
            workspace_id,
            project_id=IDS["project_build_week"],
            title="Create encrypted judge backup",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            estimated_duration_minutes=30,
            due_at=_at(22, 17),
        ),
        _entity(
            Task,
            "task_groceries",
            workspace_id,
            project_id=IDS["project_household"],
            title="Plan weekly groceries",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.MEDIUM,
            estimated_duration_minutes=25,
            actual_duration_minutes=20,
            completed_at=_at(15, 18),
            due_at=_at(15, 17),
        ),
        _entity(
            Task,
            "task_conference",
            workspace_id,
            title="Choose Berlin attendance mode",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            estimated_duration_minutes=60,
            due_at=_at(24, 12),
        ),
    ]
    dependencies = [
        _entity(
            TaskDependency,
            "task_dependency",
            workspace_id,
            task_id=IDS["task_backup"],
            depends_on_task_id=IDS["task_demo_script"],
        )
    ]
    notes = [
        _entity(
            Note,
            "note_daily",
            workspace_id,
            title="Daily note · 16 July 2026",
            markdown="## Today\n\nReview cash flow, calendar conflicts, and the judge path.",
            daily_note_date=date(2026, 7, 16),
        ),
        _entity(
            Note,
            "note_build_week",
            workspace_id,
            title="Build Week working notes",
            markdown="The demo must prove local storage, offline reload, and reversible planning.",
        ),
        _entity(
            Note,
            "note_conference",
            workspace_id,
            title="Berlin conference decision notes",
            markdown=(
                "Compare **physical**, **remote**, and **skip** before committing money or time."
            ),
        ),
    ]
    note_links = [
        _entity(
            NoteLink,
            "note_link",
            workspace_id,
            source_note_id=IDS["note_conference"],
            target_note_id=IDS["note_daily"],
            label="decision context",
        ),
        _entity(
            NoteEntityLink,
            "note_entity_link",
            workspace_id,
            note_id=IDS["note_build_week"],
            entity_type=DomainEntityType.PROJECT,
            entity_id=IDS["project_build_week"],
            label="working note",
        ),
    ]
    events = [
        _entity(
            CalendarEvent,
            "event_deep_work",
            workspace_id,
            title="Prototype deep work",
            all_day=False,
            starts_at=_at(20, 9),
            ends_at=_at(20, 10, 30),
            timezone="Europe/Rome",
            category="focus",
            preparation_buffer_minutes=15,
        ),
        _entity(
            CalendarEvent,
            "event_dentist",
            workspace_id,
            title="Dentist appointment",
            location="Demo clinic, local data only",
            all_day=False,
            starts_at=_at(20, 10, 30),
            ends_at=_at(20, 11, 15),
            timezone="Europe/Rome",
            category="personal",
            travel_buffer_minutes=20,
            recovery_buffer_minutes=10,
        ),
        _entity(
            CalendarEvent,
            "event_briefing",
            workspace_id,
            title="Berlin travel briefing",
            all_day=False,
            starts_at=_at(21, 14),
            ends_at=_at(21, 15),
            timezone="Europe/Rome",
            category="commitment",
            preparation_buffer_minutes=15,
            travel_buffer_minutes=15,
        ),
        _entity(
            CalendarEvent,
            "event_review",
            workspace_id,
            title="Weekly household review",
            all_day=False,
            starts_at=_at(21, 14, 45),
            ends_at=_at(21, 15, 30),
            timezone="Europe/Rome",
            category="household",
        ),
        _entity(
            CalendarEvent,
            "event_build_week",
            workspace_id,
            title="OpenAI Build Week demo rehearsal",
            all_day=False,
            starts_at=_at(22, 15),
            ends_at=_at(22, 16),
            timezone="Europe/Rome",
            category="build-week",
            preparation_buffer_minutes=15,
            recurrence_rrule="FREQ=DAILY;COUNT=2",
        ),
        _entity(
            CalendarEvent,
            "event_reset",
            workspace_id,
            title="Local reset day",
            all_day=True,
            all_day_start=date(2026, 7, 26),
            all_day_end=date(2026, 7, 27),
            timezone="Europe/Rome",
            category="personal",
        ),
    ]
    transactions = [
        _entity(
            Transaction,
            "transaction_salary",
            workspace_id,
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Salary"],
            transaction_type=TransactionType.INCOME,
            amount_minor=320_000,
            currency_code="EUR",
            occurred_at=_at(1, 7),
            payee="Example Employer S.p.A. (synthetic)",
            note="Synthetic monthly salary",
            external_id="demo-salary-2026-07",
        ),
        _entity(
            Transaction,
            "transaction_rent",
            workspace_id,
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Housing"],
            transaction_type=TransactionType.EXPENSE,
            amount_minor=125_000,
            currency_code="EUR",
            occurred_at=_at(2, 8),
            payee="Example Property Cooperative",
            external_id="demo-rent-2026-07",
        ),
        _entity(
            Transaction,
            "transaction_groceries",
            workspace_id,
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Food"],
            transaction_type=TransactionType.EXPENSE,
            amount_minor=41_000,
            currency_code="EUR",
            occurred_at=_at(12, 17),
            payee="Example Neighbourhood Market",
            external_id="demo-food-2026-07",
        ),
        _entity(
            Transaction,
            "transaction_utilities",
            workspace_id,
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Utilities"],
            transaction_type=TransactionType.EXPENSE,
            amount_minor=13_800,
            currency_code="EUR",
            occurred_at=_at(8, 9),
            payee="Example Local Energy",
            external_id="demo-utilities-2026-07",
        ),
        _entity(
            Transaction,
            "transaction_transport",
            workspace_id,
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Transport"],
            transaction_type=TransactionType.EXPENSE,
            amount_minor=8_900,
            currency_code="EUR",
            occurred_at=_at(10, 8),
            payee="Example Transit Pass",
            external_id="demo-transport-2026-07",
        ),
    ]
    subscriptions = [
        _entity(
            Subscription,
            "subscription_video",
            workspace_id,
            name="Example Video Plan",
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Other expense"],
            amount_minor=1_299,
            currency_code="EUR",
            billing_rrule="FREQ=MONTHLY;BYMONTHDAY=18",
            starts_at=datetime(2026, 1, 18, 8, tzinfo=UTC),
            status=SubscriptionStatus.ACTIVE,
            payee="Example Video Service",
            note="Synthetic subscription; no external account exists.",
        ),
        _entity(
            Subscription,
            "subscription_cloud",
            workspace_id,
            name="Example Local Sync Plan",
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Other expense"],
            amount_minor=699,
            currency_code="EUR",
            billing_rrule="FREQ=MONTHLY;BYMONTHDAY=25",
            starts_at=datetime(2026, 1, 25, 8, tzinfo=UTC),
            status=SubscriptionStatus.ACTIVE,
            payee="Example Storage Service",
            note="Synthetic billing record only; LocalLife makes no remote request.",
        ),
    ]
    finance_planning = [
        _entity(
            RecurringTransactionRule,
            "recurring_salary",
            workspace_id,
            name="Monthly synthetic salary",
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Salary"],
            transaction_type=TransactionType.INCOME,
            amount_minor=320_000,
            currency_code="EUR",
            rrule="FREQ=MONTHLY;BYMONTHDAY=1",
            starts_at=datetime(2026, 1, 1, 7, tzinfo=UTC),
            status=RecurringTransactionStatus.ACTIVE,
            payee="Example Employer S.p.A. (synthetic)",
            is_committed=True,
        ),
        _entity(
            PlannedTransaction,
            "planned_laptop",
            workspace_id,
            account_id=IDS["account_checking"],
            category_id=CATEGORY_IDS["Other expense"],
            transaction_type=TransactionType.EXPENSE,
            amount_minor=150_000,
            currency_code="EUR",
            planned_for=datetime(2026, 10, 5, 10, tzinfo=UTC),
            payee="Example Electronics Cooperative",
            note="Laptop purchase under scenario review",
            is_committed=False,
            occurrence_key="demo-laptop-purchase",
        ),
        _entity(
            Budget,
            "budget_july",
            workspace_id,
            name="July household budget",
            period=BudgetPeriod.MONTHLY,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            currency_code="EUR",
        ),
        _entity(
            SavingsGoal,
            "savings_emergency",
            workspace_id,
            name="Emergency fund",
            account_id=IDS["account_savings"],
            target_minor=600_000,
            current_minor=250_000,
            currency_code="EUR",
            target_date=date(2027, 6, 30),
            status=GoalStatus.ACTIVE,
        ),
    ]
    budget_limits = [
        _entity(
            BudgetCategoryLimit,
            "budget_food",
            workspace_id,
            budget_id=IDS["budget_july"],
            category_id=CATEGORY_IDS["Food"],
            limit_minor=35_000,
        ),
        _entity(
            BudgetCategoryLimit,
            "budget_transport",
            workspace_id,
            budget_id=IDS["budget_july"],
            category_id=CATEGORY_IDS["Transport"],
            limit_minor=15_000,
        ),
    ]
    commitments = [
        _entity(
            Commitment,
            "commitment_build_week",
            workspace_id,
            title="OpenAI Build Week",
            description_markdown="Deliver the LocalLife OS local-first judge demo.",
            status=CommitmentStatus.ACTIVE,
            category="build-week",
            starts_at=datetime(2026, 7, 13, 8, tzinfo=UTC),
            ends_at=datetime(2026, 7, 24, 17, tzinfo=UTC),
            decision_deadline_at=datetime(2026, 7, 20, 17, tzinfo=UTC),
            estimated_duration_minutes=1200,
        ),
        _entity(
            Commitment,
            "commitment_berlin",
            workspace_id,
            title="Berlin conference",
            description_markdown="Decide whether to attend physically, remotely, or skip.",
            status=CommitmentStatus.PLANNED,
            category="conference",
            starts_at=datetime(2026, 9, 16, 7, tzinfo=UTC),
            ends_at=datetime(2026, 9, 18, 18, tzinfo=UTC),
            decision_deadline_at=datetime(2026, 7, 31, 17, tzinfo=UTC),
            estimated_duration_minutes=480,
            planned_cost_minor=65_000,
            financial_buffer_requirement_minor=100_000,
            currency_code="EUR",
        ),
        _entity(
            Commitment,
            "commitment_laptop",
            workspace_id,
            title="Laptop purchase",
            description_markdown="Compare an August purchase with waiting until October.",
            status=CommitmentStatus.PLANNED,
            category="purchase",
            starts_at=datetime(2026, 10, 5, 10, tzinfo=UTC),
            ends_at=datetime(2026, 10, 5, 11, tzinfo=UTC),
            decision_deadline_at=datetime(2026, 8, 1, 17, tzinfo=UTC),
            estimated_duration_minutes=60,
            planned_cost_minor=150_000,
            financial_buffer_requirement_minor=100_000,
            currency_code="EUR",
        ),
    ]
    commitment_links = [
        _entity(
            CommitmentEntityLink,
            "commitment_link_project",
            workspace_id,
            commitment_id=IDS["commitment_build_week"],
            entity_type=CommitmentEntityType.PROJECT,
            entity_id=IDS["project_build_week"],
            role="delivery",
        ),
        _entity(
            CommitmentEntityLink,
            "commitment_link_event",
            workspace_id,
            commitment_id=IDS["commitment_build_week"],
            entity_type=CommitmentEntityType.CALENDAR_EVENT,
            entity_id=IDS["event_build_week"],
            role="rehearsal",
        ),
        _entity(
            CommitmentEntityLink,
            "commitment_link_task",
            workspace_id,
            commitment_id=IDS["commitment_berlin"],
            entity_type=CommitmentEntityType.TASK,
            entity_id=IDS["task_conference"],
            role="decision",
        ),
        _entity(
            CommitmentEntityLink,
            "commitment_link_plan",
            workspace_id,
            commitment_id=IDS["commitment_laptop"],
            entity_type=CommitmentEntityType.PLANNED_TRANSACTION,
            entity_id=IDS["planned_laptop"],
            role="purchase-cost",
        ),
        _entity(
            CommitmentEntityLink,
            "commitment_link_note",
            workspace_id,
            commitment_id=IDS["commitment_berlin"],
            entity_type=CommitmentEntityType.NOTE,
            entity_id=IDS["note_conference"],
            role="decision-notes",
        ),
    ]
    automation_rules = [
        _entity(
            AutomationRule,
            "automation_overdue",
            workspace_id,
            name="Overdue task review note",
            description="Create a local review note when a task becomes overdue.",
            enabled=True,
            trigger={"type": "task_overdue", "conditions": []},
            action={"type": "create_note", "title": "Review overdue task"},
        ),
        _entity(
            AutomationRule,
            "automation_backup",
            workspace_id,
            name="Weekly backup reminder",
            description="Request a local encrypted-backup reminder every Friday.",
            enabled=True,
            trigger={
                "type": "recurring_schedule",
                "conditions": [],
                "schedule": {
                    "frequency": "weekly",
                    "timezone": "Europe/Rome",
                    "local_time": "09:00:00",
                    "weekdays": [4],
                },
            },
            action={
                "type": "request_local_backup_reminder",
                "title": "Create an encrypted local backup",
            },
            next_run_at=datetime(2026, 7, 17, 8, tzinfo=UTC),
        ),
    ]
    scenarios = [
        _entity(
            Scenario,
            "scenario_physical",
            workspace_id,
            name="Berlin · physical attendance",
            description_markdown="Travel to Berlin for the full conference.",
            base_revision=1,
        ),
        _entity(
            Scenario,
            "scenario_remote",
            workspace_id,
            name="Berlin · remote attendance",
            description_markdown="Attend selected sessions remotely.",
            base_revision=1,
        ),
        _entity(
            Scenario,
            "scenario_skip",
            workspace_id,
            name="Berlin · skip conference",
            description_markdown="Protect time and budget by declining this year.",
            base_revision=1,
        ),
        _entity(
            Scenario,
            "scenario_laptop_august",
            workspace_id,
            name="Laptop purchase · August",
            description_markdown="Buy before the autumn workload.",
            base_revision=1,
        ),
        _entity(
            Scenario,
            "scenario_laptop_october",
            workspace_id,
            name="Laptop purchase · October",
            description_markdown="Wait for two additional salary cycles.",
            base_revision=1,
        ),
    ]
    scenario_changes = [
        _entity(
            ScenarioChange,
            "scenario_change_physical",
            workspace_id,
            scenario_id=IDS["scenario_physical"],
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=IDS["commitment_berlin"],
            operation=ScenarioOperation.UPDATE,
            changes={
                "planned_cost_minor": 145000,
                "time_capacity_requirement_minutes": 1200,
                "__expected_revision": 1,
            },
        ),
        _entity(
            ScenarioChange,
            "scenario_change_remote",
            workspace_id,
            scenario_id=IDS["scenario_remote"],
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=IDS["commitment_berlin"],
            operation=ScenarioOperation.UPDATE,
            changes={
                "planned_cost_minor": 12000,
                "time_capacity_requirement_minutes": 360,
                "__expected_revision": 1,
            },
        ),
        _entity(
            ScenarioChange,
            "scenario_change_skip",
            workspace_id,
            scenario_id=IDS["scenario_skip"],
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=IDS["commitment_berlin"],
            operation=ScenarioOperation.UPDATE,
            changes={
                "status": "cancelled",
                "planned_cost_minor": 0,
                "time_capacity_requirement_minutes": 0,
                "__expected_revision": 1,
            },
        ),
        _entity(
            ScenarioChange,
            "scenario_change_august",
            workspace_id,
            scenario_id=IDS["scenario_laptop_august"],
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=IDS["commitment_laptop"],
            operation=ScenarioOperation.UPDATE,
            changes={
                "target_start_at": "2026-08-05T10:00:00Z",
                "target_end_at": "2026-08-05T11:00:00Z",
                "__expected_revision": 1,
            },
        ),
        _entity(
            ScenarioChange,
            "scenario_change_october",
            workspace_id,
            scenario_id=IDS["scenario_laptop_october"],
            entity_type=DomainEntityType.COMMITMENT,
            entity_id=IDS["commitment_laptop"],
            operation=ScenarioOperation.UPDATE,
            changes={
                "target_start_at": "2026-10-05T10:00:00Z",
                "target_end_at": "2026-10-05T11:00:00Z",
                "__expected_revision": 1,
            },
        ),
    ]
    links = [
        _entity(
            TagEntityLink,
            "event_link",
            workspace_id,
            tag_id=IDS["tag_build_week"],
            entity_type=DomainEntityType.PROJECT,
            entity_id=IDS["project_build_week"],
        ),
        _entity(
            CalendarEventEntityLink,
            "event_link",
            workspace_id,
            calendar_event_id=IDS["event_build_week"],
            entity_type=DomainEntityType.PROJECT,
            entity_id=IDS["project_build_week"],
        ),
    ]
    return [
        *tags,
        *accounts,
        *projects,
        *tasks,
        *dependencies,
        *notes,
        *note_links,
        *events,
        *transactions,
        *subscriptions,
        *finance_planning,
        *budget_limits,
        *commitments,
        *commitment_links,
        *automation_rules,
        *scenarios,
        *scenario_changes,
        *links,
        *_timeline_events(workspace_id),
    ]


DEMO_MODELS: Final = (
    AttachmentEntityLink,
    TagEntityLink,
    CalendarEventEntityLink,
    NoteEntityLink,
    NoteLink,
    TaskDependency,
    CommitmentEntityLink,
    BudgetCategoryLimit,
    ScenarioChange,
    Attachment,
    Scenario,
    AutomationRule,
    Commitment,
    SavingsGoal,
    Budget,
    PlannedTransaction,
    RecurringTransactionRule,
    Subscription,
    Transaction,
    FinancialAccount,
    CalendarEvent,
    Note,
    Task,
    Project,
    Tag,
)


def _remove_demo_rows(session: Session) -> int:
    demo_ids = set(IDS.values()) | {_id(value) for value in range(200, 212)}
    removed = 0
    timeline = session.exec(
        select(TimelineEvent).where(col(TimelineEvent.entity_id).in_(demo_ids))
    ).all()
    for timeline_record in timeline:
        session.delete(timeline_record)
        removed += 1
    for model in DEMO_MODELS:
        for identifier in demo_ids:
            demo_record = session.get(model, identifier)
            if demo_record is not None:
                session.delete(demo_record)
                removed += 1
        session.flush()
    return removed


def _remove_demo_files(workspace_id: UUID) -> int:
    removed = 0
    with STORAGE_LOCK:
        for key, suffix in (("attachment_agenda", ".txt"), ("attachment_laptop", ".md")):
            _, target = _attachment_target(workspace_id, IDS[key], suffix)
            if target.is_file():
                target.unlink()
                removed += 1
    return removed


def reset_demo_data(session: Session) -> DemoDataResetSummary:
    workspace = get_current_workspace(session)
    with transaction(session):
        removed = _remove_demo_rows(session)
    files_removed = _remove_demo_files(workspace.id)
    return DemoDataResetSummary(
        dataset_version=DATASET_VERSION,
        records_removed=removed,
        attachment_files_removed=files_removed,
    )


def _counts(records: Iterable[object], attachments: list[Attachment]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in [*records, *attachments]:
        key = record.__class__.__name__
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def load_demo_data(session: Session) -> DemoDataSummary:
    workspace = get_current_workspace(session)
    records = _records(workspace.id)
    attachments: list[Attachment] = []
    written: list[Path] = []
    try:
        attachments, written = _copy_demo_attachments(workspace.id)
        attachment_links = [
            _entity(
                AttachmentEntityLink,
                "attachment_link_agenda",
                workspace.id,
                attachment_id=IDS["attachment_agenda"],
                entity_type=DomainEntityType.NOTE,
                entity_id=IDS["note_build_week"],
            ),
            _entity(
                AttachmentEntityLink,
                "attachment_link_laptop",
                workspace.id,
                attachment_id=IDS["attachment_laptop"],
                entity_type=DomainEntityType.NOTE,
                entity_id=IDS["note_conference"],
            ),
        ]
        with transaction(session):
            _remove_demo_rows(session)
            for record in [*records, *attachments, *attachment_links]:
                session.add(record)
            preferences = session.exec(
                select(UserPreferences).where(col(UserPreferences.workspace_id) == workspace.id)
            ).one()
            preferences.timezone = "Europe/Rome"
            preferences.currency_code = "EUR"
            preferences.revision += 1
            preferences.updated_at = CREATED_AT
            session.add(preferences)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return DemoDataSummary(
        dataset_version=DATASET_VERSION,
        anchor_date=ANCHOR_DATE,
        records_created=_counts([*records, *attachment_links], attachments),
        scenario_labels=[
            "Berlin · physical attendance",
            "Berlin · remote attendance",
            "Berlin · skip conference",
            "Laptop purchase · August",
            "Laptop purchase · October",
        ],
        attachment_labels=["build-week-agenda.txt", "laptop-comparison.md"],
        conflict_count=2,
        budget_shortfall_count=1,
    )
