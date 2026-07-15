from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Index, Text, UniqueConstraint, text
from sqlmodel import Field

from app.models.common import (
    AutomationActionType,
    AutomationExecutionStatus,
    AutomationTriggerType,
    CurrencyCodeType,
    ImportBatchStatus,
    ImportKind,
    ImportRowStatus,
    NotificationKind,
    UTCDateTime,
    WorkspaceEntityBase,
    WorkspaceSoftDeleteEntityBase,
)


class CsvMappingProfile(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "csv_mapping_profiles"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_csv_profiles_name_nonempty"),
        CheckConstraint("revision >= 1", name="ck_csv_profiles_revision_positive"),
        Index(
            "ux_csv_profiles_workspace_name_active",
            "workspace_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    name: str = Field(max_length=160)
    columns: dict[str, str | None] = Field(default_factory=dict, sa_type=JSON)
    date_format: str | None = Field(default=None, max_length=80)
    decimal_separator: str = Field(default=".", max_length=1)
    amount_positive_is_income: bool = Field(default=True)
    default_currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        sa_type=CurrencyCodeType,
    )
    default_account_id: UUID | None = Field(
        default=None,
        foreign_key="financial_accounts.id",
        ondelete="SET NULL",
    )
    default_category_id: UUID | None = Field(
        default=None,
        foreign_key="transaction_categories.id",
        ondelete="SET NULL",
    )
    delimiter: str | None = Field(default=None, max_length=1)
    encoding: str | None = Field(default=None, max_length=40)


class ImportBatch(WorkspaceEntityBase, table=True):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("total_rows >= 0", name="ck_import_batches_rows_nonnegative"),
        CheckConstraint("revision >= 1", name="ck_import_batches_revision_positive"),
        UniqueConstraint(
            "workspace_id",
            "kind",
            "source_fingerprint",
            name="uq_import_batch_source",
        ),
        Index("ix_import_batches_workspace_created", "workspace_id", "created_at", "id"),
    )

    kind: ImportKind
    status: ImportBatchStatus = Field(default=ImportBatchStatus.PREVIEWED)
    original_filename: str = Field(max_length=255)
    stored_path: str = Field(max_length=500)
    source_fingerprint: str = Field(min_length=64, max_length=64)
    detected_encoding: str | None = Field(default=None, max_length=40)
    detected_delimiter: str | None = Field(default=None, max_length=1)
    mapping_profile_id: UUID | None = Field(
        default=None,
        foreign_key="csv_mapping_profiles.id",
        ondelete="SET NULL",
        index=True,
    )
    total_rows: int = Field(default=0, ge=0)
    new_count: int = Field(default=0, ge=0)
    changed_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    invalid_count: int = Field(default=0, ge=0)
    imported_count: int = Field(default=0, ge=0)
    summary: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    applied_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class ImportRow(WorkspaceEntityBase, table=True):
    __tablename__ = "import_rows"
    __table_args__ = (
        CheckConstraint("row_number >= 1", name="ck_import_rows_number_positive"),
        CheckConstraint("revision >= 1", name="ck_import_rows_revision_positive"),
        UniqueConstraint("batch_id", "row_number", name="uq_import_batch_row"),
        Index("ix_import_rows_batch_status", "batch_id", "status", "row_number"),
    )

    batch_id: UUID = Field(foreign_key="import_batches.id", ondelete="CASCADE", index=True)
    row_number: int = Field(ge=1)
    status: ImportRowStatus
    included: bool = Field(default=True)
    fingerprint: str | None = Field(default=None, max_length=64)
    raw_data: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    normalized_data: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    issues: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    duplicate_kind: str | None = Field(default=None, max_length=20)
    duplicate_target_id: UUID | None = None
    target_id: UUID | None = None


class AutomationExecution(WorkspaceEntityBase, table=True):
    __tablename__ = "automation_executions"
    __table_args__ = (
        UniqueConstraint("rule_id", "idempotency_key", name="uq_automation_execution_key"),
        Index("ix_automation_executions_rule_created", "rule_id", "created_at", "id"),
        Index("ix_automation_executions_workspace_status", "workspace_id", "status"),
    )

    rule_id: UUID = Field(foreign_key="automation_rules.id", ondelete="CASCADE", index=True)
    trigger_type: AutomationTriggerType
    action_type: AutomationActionType
    status: AutomationExecutionStatus
    source_key: str = Field(max_length=500)
    idempotency_key: str = Field(min_length=64, max_length=64)
    trigger_context: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    action_result: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    error: str | None = Field(default=None, sa_type=Text)
    completed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class LocalNotification(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "local_notifications"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_notifications_title_nonempty"),
        CheckConstraint("revision >= 1", name="ck_notifications_revision_positive"),
        Index("ix_notifications_workspace_read", "workspace_id", "read_at", "created_at"),
    )

    source_rule_id: UUID | None = Field(
        default=None,
        foreign_key="automation_rules.id",
        ondelete="SET NULL",
        index=True,
    )
    kind: NotificationKind = Field(default=NotificationKind.INFORMATION)
    title: str = Field(max_length=255)
    message: str | None = Field(default=None, sa_type=Text)
    read_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
