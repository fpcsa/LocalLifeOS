"""Add local imports and deterministic automation execution.

Revision ID: 20260716_0010
Revises: 20260715_0009
Create Date: 2026-07-16 00:15:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0010"
down_revision: str | None = "20260715_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def audit_columns(*, revisioned: bool = True, soft_delete: bool = False) -> list[sa.Column]:
    columns = [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]
    if revisioned:
        columns.append(sa.Column("revision", sa.Integer(), nullable=False))
    if soft_delete:
        columns.append(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    return columns


def upgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch_op:
        batch_op.add_column(sa.Column("external_uid", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("source_sequence", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("import_fingerprint", sa.String(length=64), nullable=True))
        batch_op.create_check_constraint(
            "ck_events_source_sequence_nonnegative", "source_sequence >= 0"
        )
        batch_op.create_index(
            "ux_events_workspace_external_uid_active",
            ["workspace_id", "external_uid"],
            unique=True,
            sqlite_where=sa.text("external_uid IS NOT NULL AND deleted_at IS NULL"),
        )
        batch_op.create_index(
            "ix_events_workspace_import_fingerprint",
            ["workspace_id", "import_fingerprint"],
            unique=False,
        )

    with op.batch_alter_table("automation_rules") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "csv_mapping_profiles",
        *audit_columns(soft_delete=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("date_format", sa.String(length=80), nullable=True),
        sa.Column("decimal_separator", sa.String(length=1), nullable=False),
        sa.Column("amount_positive_is_income", sa.Boolean(), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=True),
        sa.Column(
            "default_account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "default_category_id",
            sa.Uuid(),
            sa.ForeignKey("transaction_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("delimiter", sa.String(length=1), nullable=True),
        sa.Column("encoding", sa.String(length=40), nullable=True),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_csv_profiles_name_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_csv_profiles_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_csv_mapping_profiles_workspace_id", "csv_mapping_profiles", ["workspace_id"]
    )
    op.create_index(
        "ux_csv_profiles_workspace_name_active",
        "csv_mapping_profiles",
        ["workspace_id", "name"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "import_batches",
        *audit_columns(),
        sa.Column(
            "kind",
            enum_type("importkind", "CALENDAR_ICS", "BANK_CSV"),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum_type("importbatchstatus", "PREVIEWED", "APPLIED", "FAILED"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("detected_encoding", sa.String(length=40), nullable=True),
        sa.Column("detected_delimiter", sa.String(length=1), nullable=True),
        sa.Column(
            "mapping_profile_id",
            sa.Uuid(),
            sa.ForeignKey("csv_mapping_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("changed_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("total_rows >= 0", name="ck_import_batches_rows_nonnegative"),
        sa.CheckConstraint("revision >= 1", name="ck_import_batches_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "kind", "source_fingerprint", name="uq_import_batch_source"
        ),
    )
    op.create_index("ix_import_batches_workspace_id", "import_batches", ["workspace_id"])
    op.create_index(
        "ix_import_batches_mapping_profile_id", "import_batches", ["mapping_profile_id"]
    )
    op.create_index(
        "ix_import_batches_workspace_created",
        "import_batches",
        ["workspace_id", "created_at", "id"],
    )

    op.create_table(
        "import_rows",
        *audit_columns(),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "importrowstatus",
                "NEW",
                "CHANGED",
                "DUPLICATE",
                "INVALID",
                "IMPORTED",
                "EXCLUDED",
            ),
            nullable=False,
        ),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("duplicate_kind", sa.String(length=20), nullable=True),
        sa.Column("duplicate_target_id", sa.Uuid(), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("row_number >= 1", name="ck_import_rows_number_positive"),
        sa.CheckConstraint("revision >= 1", name="ck_import_rows_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_import_batch_row"),
    )
    op.create_index("ix_import_rows_workspace_id", "import_rows", ["workspace_id"])
    op.create_index("ix_import_rows_batch_id", "import_rows", ["batch_id"])
    op.create_index(
        "ix_import_rows_batch_status", "import_rows", ["batch_id", "status", "row_number"]
    )

    op.create_table(
        "automation_executions",
        *audit_columns(),
        sa.Column(
            "rule_id",
            sa.Uuid(),
            sa.ForeignKey("automation_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trigger_type",
            enum_type(
                "automationtriggertype",
                "TRANSACTION_CREATED",
                "SUBSCRIPTION_AMOUNT_CHANGED",
                "EVENT_CREATED",
                "EVENT_APPROACHING",
                "TASK_OVERDUE",
                "COMMITMENT_WARNING_CREATED",
                "RECURRING_SCHEDULE",
            ),
            nullable=False,
        ),
        sa.Column(
            "action_type",
            enum_type(
                "automationactiontype",
                "CREATE_TASK",
                "CREATE_NOTE",
                "CREATE_PLANNED_TRANSACTION",
                "ADD_TAG",
                "CREATE_NOTIFICATION",
                "REQUEST_LOCAL_BACKUP_REMINDER",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum_type("automationexecutionstatus", "SUCCEEDED", "SKIPPED", "FAILED"),
            nullable=False,
        ),
        sa.Column("source_key", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("trigger_context", sa.JSON(), nullable=False),
        sa.Column("action_result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "idempotency_key", name="uq_automation_execution_key"),
    )
    op.create_index(
        "ix_automation_executions_workspace_id", "automation_executions", ["workspace_id"]
    )
    op.create_index("ix_automation_executions_rule_id", "automation_executions", ["rule_id"])
    op.create_index(
        "ix_automation_executions_rule_created",
        "automation_executions",
        ["rule_id", "created_at", "id"],
    )
    op.create_index(
        "ix_automation_executions_workspace_status",
        "automation_executions",
        ["workspace_id", "status"],
    )

    op.create_table(
        "local_notifications",
        *audit_columns(soft_delete=True),
        sa.Column(
            "source_rule_id",
            sa.Uuid(),
            sa.ForeignKey("automation_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "kind",
            enum_type("notificationkind", "INFORMATION", "BACKUP_REMINDER"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_notifications_title_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_notifications_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_local_notifications_workspace_id", "local_notifications", ["workspace_id"])
    op.create_index(
        "ix_local_notifications_source_rule_id", "local_notifications", ["source_rule_id"]
    )
    op.create_index(
        "ix_notifications_workspace_read",
        "local_notifications",
        ["workspace_id", "read_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("local_notifications")
    op.drop_table("automation_executions")
    op.drop_table("import_rows")
    op.drop_table("import_batches")
    op.drop_table("csv_mapping_profiles")
    with op.batch_alter_table("automation_rules") as batch_op:
        batch_op.drop_column("next_run_at")
        batch_op.drop_column("last_run_at")
        batch_op.drop_column("description")
    with op.batch_alter_table("calendar_events") as batch_op:
        batch_op.drop_index("ix_events_workspace_import_fingerprint")
        batch_op.drop_index("ux_events_workspace_external_uid_active")
        batch_op.drop_constraint("ck_events_source_sequence_nonnegative", type_="check")
        batch_op.drop_column("import_fingerprint")
        batch_op.drop_column("source_sequence")
        batch_op.drop_column("external_uid")
