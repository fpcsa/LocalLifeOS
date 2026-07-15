from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class PreferredTimeOfDay(StrEnum):
    ANY = "any"
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class TaskDependencyType(StrEnum):
    FINISH_TO_START = "finish_to_start"
    START_TO_START = "start_to_start"


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class CalendarEventStatus(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class FinancialAccountType(StrEnum):
    CASH = "cash"
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"
    INVESTMENT = "investment"
    OTHER = "other"


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class PlannedTransactionStatus(StrEnum):
    PLANNED = "planned"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class RecurringTransactionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class CategoryKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class BudgetPeriod(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CommitmentStatus(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class CommitmentEntityType(StrEnum):
    TASK = "task"
    PROJECT = "project"
    CALENDAR_EVENT = "calendar_event"
    NOTE = "note"
    PLANNED_TRANSACTION = "planned_transaction"
    TRANSACTION = "transaction"
    BUDGET = "budget"
    SAVINGS_GOAL = "savings_goal"
    GOAL = "goal"


class DomainEntityType(StrEnum):
    WORKSPACE = "workspace"
    USER_PREFERENCES = "user_preferences"
    TAG = "tag"
    ATTACHMENT = "attachment"
    PROJECT = "project"
    TASK = "task"
    NOTE = "note"
    CALENDAR_EVENT = "calendar_event"
    FINANCIAL_ACCOUNT = "financial_account"
    TRANSACTION = "transaction"
    PLANNED_TRANSACTION = "planned_transaction"
    BUDGET = "budget"
    SAVINGS_GOAL = "savings_goal"
    COMMITMENT = "commitment"
    GOAL = "goal"
    AUTOMATION_RULE = "automation_rule"
    SCENARIO = "scenario"


class ScenarioStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    DISCARDED = "discarded"


class ScenarioOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ImportKind(StrEnum):
    CALENDAR_ICS = "calendar_ics"
    BANK_CSV = "bank_csv"


class ImportBatchStatus(StrEnum):
    PREVIEWED = "previewed"
    APPLIED = "applied"
    FAILED = "failed"


class ImportRowStatus(StrEnum):
    NEW = "new"
    CHANGED = "changed"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    IMPORTED = "imported"
    EXCLUDED = "excluded"


class AutomationTriggerType(StrEnum):
    TRANSACTION_CREATED = "transaction_created"
    SUBSCRIPTION_AMOUNT_CHANGED = "subscription_amount_changed"
    EVENT_CREATED = "event_created"
    EVENT_APPROACHING = "event_approaching"
    TASK_OVERDUE = "task_overdue"
    COMMITMENT_WARNING_CREATED = "commitment_warning_created"
    RECURRING_SCHEDULE = "recurring_schedule"


class AutomationActionType(StrEnum):
    CREATE_TASK = "create_task"
    CREATE_NOTE = "create_note"
    CREATE_PLANNED_TRANSACTION = "create_planned_transaction"
    ADD_TAG = "add_tag"
    CREATE_NOTIFICATION = "create_notification"
    REQUEST_LOCAL_BACKUP_REMINDER = "request_local_backup_reminder"


class AutomationExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"


class NotificationKind(StrEnum):
    INFORMATION = "information"
    BACKUP_REMINDER = "backup_reminder"


SUPPORTED_CURRENCY_CODES = frozenset(
    """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND
    BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU
    CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP
    GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES
    KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD
    MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR
    PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD
    SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS
    UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA XBB
    XBC XBD XCD XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG
    """.split()  # noqa: SIM905
)


def normalize_currency_code(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in SUPPORTED_CURRENCY_CODES:
        raise ValueError("currency_code must be a supported ISO 4217 code")
    return normalized


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC in SQLite and always return timezone-aware UTC datetimes."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        return dialect.type_descriptor(DateTime(timezone=dialect.name != "sqlite"))

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime values must include a timezone offset")
        normalized = value.astimezone(UTC)
        return normalized.replace(tzinfo=None) if dialect.name == "sqlite" else normalized

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class CurrencyCodeType(TypeDecorator[str]):
    """Normalize and validate ISO 4217 codes at the persistence boundary."""

    impl = String(3)
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        del dialect
        return normalize_currency_code(value) if value is not None else None

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        del dialect
        return normalize_currency_code(value) if value is not None else None


class EntityBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)


class RevisionEntityBase(EntityBase):
    revision: int = Field(default=1, ge=1, nullable=False)


class SoftDeleteEntityBase(RevisionEntityBase):
    deleted_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class WorkspaceEntityBase(RevisionEntityBase):
    workspace_id: UUID = Field(foreign_key="workspaces.id", ondelete="CASCADE", index=True)


class WorkspaceSoftDeleteEntityBase(SoftDeleteEntityBase):
    workspace_id: UUID = Field(foreign_key="workspaces.id", ondelete="CASCADE", index=True)


class WorkspaceLinkBase(EntityBase):
    workspace_id: UUID = Field(foreign_key="workspaces.id", ondelete="CASCADE", index=True)
