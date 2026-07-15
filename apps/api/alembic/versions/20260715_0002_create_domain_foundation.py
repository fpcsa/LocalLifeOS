"""Create the LocalLife OS domain foundation.

Revision ID: 20260715_0002
Revises: 20260715_0001
Create Date: 2026-07-15 12:00:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "20260715_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def entity_columns(
    *,
    workspace: bool = False,
    revisioned: bool = False,
    soft_delete: bool = False,
) -> list[sa.Column]:
    columns = [sa.Column("id", sa.Uuid(), nullable=False)]
    if workspace:
        columns.append(
            sa.Column(
                "workspace_id",
                sa.Uuid(),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                nullable=False,
            )
        )
    columns.extend(
        [
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]
    )
    if revisioned:
        columns.append(sa.Column("revision", sa.Integer(), nullable=False))
    if soft_delete:
        columns.append(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    return columns


def currency_constraints(prefix: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "length(currency_code) = 3",
            name=f"ck_{prefix}_currency_length",
        ),
        sa.CheckConstraint(
            "currency_code = upper(currency_code)",
            name=f"ck_{prefix}_currency_upper",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "workspaces",
        *entity_columns(revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_workspaces_name_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_workspaces_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_workspaces_default_active",
        "workspaces",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1 AND deleted_at IS NULL"),
    )

    op.create_table(
        "user_preferences",
        *entity_columns(workspace=True, revisioned=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("week_starts_on", sa.Integer(), nullable=False),
        sa.Column(
            "theme",
            enum_type("theme_mode", "SYSTEM", "LIGHT", "DARK"),
            nullable=False,
        ),
        *currency_constraints("preferences"),
        sa.CheckConstraint("week_starts_on BETWEEN 0 AND 6", name="ck_preferences_week_start"),
        sa.CheckConstraint("revision >= 1", name="ck_preferences_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_user_preferences_workspace"),
    )
    op.create_index("ix_user_preferences_workspace_id", "user_preferences", ["workspace_id"])

    op.create_table(
        "tags",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_tags_name_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_tags_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tags_workspace_id", "tags", ["workspace_id"])
    op.create_index(
        "ux_tags_workspace_name_active",
        "tags",
        ["workspace_id", "name"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "projects",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=True),
        sa.Column(
            "status",
            enum_type("project_status", "ACTIVE", "ON_HOLD", "COMPLETED", "ARCHIVED"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_projects_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_index("ix_projects_workspace_status", "projects", ["workspace_id", "status"])

    op.create_table(
        "tasks",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parent_task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=True),
        sa.Column(
            "status",
            enum_type("task_status", "TODO", "IN_PROGRESS", "COMPLETED", "CANCELLED"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            enum_type("task_priority", "LOW", "MEDIUM", "HIGH", "URGENT"),
            nullable=False,
        ),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recurrence_frequency",
            enum_type("task_recurrence_frequency", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"),
            nullable=True,
        ),
        sa.Column("recurrence_interval", sa.Integer(), nullable=True),
        sa.Column("recurrence_days_of_week", sa.JSON(), nullable=True),
        sa.Column("recurrence_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_tasks_title_nonempty"),
        sa.CheckConstraint(
            "estimated_duration_minutes IS NULL OR estimated_duration_minutes >= 0",
            name="ck_tasks_duration_nonnegative",
        ),
        sa.CheckConstraint(
            "scheduled_start_at IS NULL OR scheduled_end_at IS NULL "
            "OR scheduled_end_at > scheduled_start_at",
            name="ck_tasks_scheduled_range",
        ),
        sa.CheckConstraint(
            "(recurrence_frequency IS NULL AND recurrence_interval IS NULL "
            "AND recurrence_days_of_week IS NULL AND recurrence_end_at IS NULL) "
            "OR (recurrence_frequency IS NOT NULL AND recurrence_interval >= 1)",
            name="ck_tasks_recurrence_shape",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_tasks_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_workspace_id", "tasks", ["workspace_id"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"])
    op.create_index("ix_tasks_workspace_status_due", "tasks", ["workspace_id", "status", "due_at"])

    op.create_table(
        "task_dependencies",
        *entity_columns(workspace=True),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dependency_type",
            enum_type("task_dependency_type", "FINISH_TO_START", "START_TO_START"),
            nullable=False,
        ),
        sa.CheckConstraint("task_id <> depends_on_task_id", name="ck_task_dependency_no_self"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "depends_on_task_id",
            "dependency_type",
            name="uq_task_dependency",
        ),
    )
    op.create_index("ix_task_dependencies_workspace_id", "task_dependencies", ["workspace_id"])
    op.create_index("ix_task_dependencies_task_id", "task_dependencies", ["task_id"])
    op.create_index(
        "ix_task_dependencies_depends_on_task_id",
        "task_dependencies",
        ["depends_on_task_id"],
    )

    op.create_table(
        "notes",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_notes_title_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_notes_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notes_workspace_id", "notes", ["workspace_id"])
    op.create_index("ix_notes_workspace_updated", "notes", ["workspace_id", "updated_at"])

    op.create_table(
        "note_links",
        *entity_columns(workspace=True),
        sa.Column(
            "source_note_id",
            sa.Uuid(),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_note_id",
            sa.Uuid(),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.CheckConstraint("source_note_id <> target_note_id", name="ck_note_link_no_self"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_note_id", "target_note_id", name="uq_note_link"),
    )
    op.create_index("ix_note_links_workspace_id", "note_links", ["workspace_id"])
    op.create_index("ix_note_links_source_note_id", "note_links", ["source_note_id"])
    op.create_index("ix_note_links_target_note_id", "note_links", ["target_note_id"])

    op.create_table(
        "calendar_events",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            enum_type("calendar_event_status", "CONFIRMED", "TENTATIVE", "CANCELLED"),
            nullable=False,
        ),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day_start", sa.Date(), nullable=True),
        sa.Column("all_day_end", sa.Date(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "recurrence_frequency",
            enum_type("event_recurrence_frequency", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"),
            nullable=True,
        ),
        sa.Column("recurrence_interval", sa.Integer(), nullable=True),
        sa.Column("recurrence_days_of_week", sa.JSON(), nullable=True),
        sa.Column("recurrence_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_events_title_nonempty"),
        sa.CheckConstraint(
            "(all_day = 1 AND all_day_start IS NOT NULL AND all_day_end IS NOT NULL "
            "AND all_day_end > all_day_start AND starts_at IS NULL AND ends_at IS NULL) "
            "OR (all_day = 0 AND starts_at IS NOT NULL AND ends_at IS NOT NULL "
            "AND ends_at > starts_at AND all_day_start IS NULL AND all_day_end IS NULL)",
            name="ck_events_time_shape",
        ),
        sa.CheckConstraint(
            "(recurrence_frequency IS NULL AND recurrence_interval IS NULL "
            "AND recurrence_days_of_week IS NULL AND recurrence_end_at IS NULL) "
            "OR (recurrence_frequency IS NOT NULL AND recurrence_interval >= 1)",
            name="ck_events_recurrence_shape",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_events_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calendar_events_workspace_id", "calendar_events", ["workspace_id"])
    op.create_index("ix_events_workspace_starts", "calendar_events", ["workspace_id", "starts_at"])
    op.create_index(
        "ix_events_workspace_all_day",
        "calendar_events",
        ["workspace_id", "all_day_start"],
    )

    op.create_table(
        "financial_accounts",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "account_type",
            enum_type(
                "financial_account_type",
                "CASH",
                "CHECKING",
                "SAVINGS",
                "CREDIT",
                "INVESTMENT",
                "OTHER",
            ),
            nullable=False,
        ),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("opening_balance_minor", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_accounts_name_nonempty"),
        *currency_constraints("accounts"),
        sa.CheckConstraint("revision >= 1", name="ck_accounts_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_accounts_workspace_id", "financial_accounts", ["workspace_id"])
    op.create_index(
        "ux_accounts_workspace_name_active",
        "financial_accounts",
        ["workspace_id", "name"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "transaction_categories",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", enum_type("category_kind", "INCOME", "EXPENSE"), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_categories_name_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_categories_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transaction_categories_workspace_id", "transaction_categories", ["workspace_id"]
    )
    op.create_index(
        "ux_categories_workspace_kind_name_active",
        "transaction_categories",
        ["workspace_id", "kind", "name"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "transactions",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "transfer_account_id",
            sa.Uuid(),
            sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("transaction_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "transaction_type",
            enum_type("transaction_type", "INCOME", "EXPENSE", "TRANSFER"),
            nullable=False,
        ),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payee", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.CheckConstraint("amount_minor > 0", name="ck_transactions_amount_positive"),
        *currency_constraints("transactions"),
        sa.CheckConstraint(
            "(transaction_type = 'TRANSFER' AND transfer_account_id IS NOT NULL "
            "AND transfer_account_id <> account_id AND category_id IS NULL) "
            "OR (transaction_type IN ('INCOME', 'EXPENSE') AND transfer_account_id IS NULL)",
            name="ck_transactions_transfer_shape",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_transactions_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "external_id", name="uq_transaction_external_id"),
    )
    op.create_index("ix_transactions_workspace_id", "transactions", ["workspace_id"])
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_transfer_account_id", "transactions", ["transfer_account_id"])
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index(
        "ix_transactions_workspace_occurred",
        "transactions",
        ["workspace_id", "occurred_at", "id"],
    )

    op.create_table(
        "budgets",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "period",
            enum_type("budget_period", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY", "CUSTOM"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_budgets_name_nonempty"),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="ck_budgets_date_range"
        ),
        *currency_constraints("budgets"),
        sa.CheckConstraint("revision >= 1", name="ck_budgets_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budgets_workspace_id", "budgets", ["workspace_id"])
    op.create_index(
        "ix_budgets_workspace_period", "budgets", ["workspace_id", "start_date", "end_date"]
    )

    op.create_table(
        "budget_category_limits",
        *entity_columns(workspace=True),
        sa.Column(
            "budget_id",
            sa.Uuid(),
            sa.ForeignKey("budgets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("transaction_categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("limit_minor", sa.Integer(), nullable=False),
        sa.CheckConstraint("limit_minor >= 0", name="ck_budget_limits_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("budget_id", "category_id", name="uq_budget_category_limit"),
    )
    op.create_index(
        "ix_budget_category_limits_workspace_id", "budget_category_limits", ["workspace_id"]
    )
    op.create_index("ix_budget_category_limits_budget_id", "budget_category_limits", ["budget_id"])
    op.create_index(
        "ix_budget_category_limits_category_id", "budget_category_limits", ["category_id"]
    )

    op.create_table(
        "savings_goals",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("target_minor", sa.Integer(), nullable=False),
        sa.Column("current_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            enum_type("savings_goal_status", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_savings_goals_name_nonempty"),
        sa.CheckConstraint("target_minor > 0", name="ck_savings_goals_target_positive"),
        sa.CheckConstraint("current_minor >= 0", name="ck_savings_goals_current_nonnegative"),
        *currency_constraints("savings_goals"),
        sa.CheckConstraint("revision >= 1", name="ck_savings_goals_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_savings_goals_workspace_id", "savings_goals", ["workspace_id"])
    op.create_index(
        "ix_savings_goals_workspace_status", "savings_goals", ["workspace_id", "status"]
    )

    op.create_table(
        "goals",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=True),
        sa.Column(
            "status",
            enum_type("goal_status", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"),
            nullable=False,
        ),
        sa.Column("progress_basis_points", sa.Integer(), nullable=False),
        sa.Column("target_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_goals_title_nonempty"),
        sa.CheckConstraint("progress_basis_points BETWEEN 0 AND 10000", name="ck_goals_progress"),
        sa.CheckConstraint("revision >= 1", name="ck_goals_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_goals_workspace_id", "goals", ["workspace_id"])
    op.create_index("ix_goals_workspace_status", "goals", ["workspace_id", "status"])

    op.create_table(
        "commitments",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=True),
        sa.Column(
            "status",
            enum_type("commitment_status", "DRAFT", "PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("planned_cost_minor", sa.Integer(), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=True),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_commitments_title_nonempty"),
        sa.CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="ck_commitments_date_range",
        ),
        sa.CheckConstraint(
            "estimated_duration_minutes IS NULL OR estimated_duration_minutes >= 0",
            name="ck_commitments_duration_nonnegative",
        ),
        sa.CheckConstraint(
            "(planned_cost_minor IS NULL AND currency_code IS NULL) "
            "OR (planned_cost_minor >= 0 AND length(currency_code) = 3 "
            "AND currency_code = upper(currency_code))",
            name="ck_commitments_money_shape",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_commitments_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commitments_workspace_id", "commitments", ["workspace_id"])
    op.create_index("ix_commitments_workspace_status", "commitments", ["workspace_id", "status"])

    op.create_table(
        "commitment_entity_links",
        *entity_columns(workspace=True),
        sa.Column(
            "commitment_id",
            sa.Uuid(),
            sa.ForeignKey("commitments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            enum_type(
                "commitment_entity_type",
                "TASK",
                "CALENDAR_EVENT",
                "NOTE",
                "TRANSACTION",
                "BUDGET",
                "GOAL",
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "commitment_id",
            "entity_type",
            "entity_id",
            name="uq_commitment_entity_link",
        ),
    )
    op.create_index(
        "ix_commitment_entity_links_workspace_id", "commitment_entity_links", ["workspace_id"]
    )
    op.create_index(
        "ix_commitment_entity_links_commitment_id", "commitment_entity_links", ["commitment_id"]
    )
    op.create_index(
        "ix_commitment_entity_links_entity_id", "commitment_entity_links", ["entity_id"]
    )

    op.create_table(
        "automation_rules",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("trigger", sa.JSON(), nullable=False),
        sa.Column("action", sa.JSON(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_rules_name_nonempty"),
        sa.CheckConstraint("revision >= 1", name="ck_rules_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_rules_workspace_id", "automation_rules", ["workspace_id"])
    op.create_index("ix_rules_workspace_enabled", "automation_rules", ["workspace_id", "enabled"])

    op.create_table(
        "scenarios",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=True),
        sa.Column(
            "status",
            enum_type("scenario_status", "DRAFT", "ACCEPTED", "DISCARDED"),
            nullable=False,
        ),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_scenarios_name_nonempty"),
        sa.CheckConstraint("base_revision >= 1", name="ck_scenarios_base_revision_positive"),
        sa.CheckConstraint("revision >= 1", name="ck_scenarios_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scenarios_workspace_id", "scenarios", ["workspace_id"])
    op.create_index("ix_scenarios_workspace_status", "scenarios", ["workspace_id", "status"])

    op.create_table(
        "scenario_changes",
        *entity_columns(workspace=True, revisioned=True),
        sa.Column(
            "scenario_id",
            sa.Uuid(),
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            enum_type("scenario_entity_type", *[item for item in _DOMAIN_ENTITY_VALUES]),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "operation",
            enum_type("scenario_operation", "CREATE", "UPDATE", "DELETE"),
            nullable=False,
        ),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_scenario_changes_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scenario_id",
            "entity_type",
            "entity_id",
            name="uq_scenario_entity_change",
        ),
    )
    op.create_index("ix_scenario_changes_workspace_id", "scenario_changes", ["workspace_id"])
    op.create_index("ix_scenario_changes_scenario_id", "scenario_changes", ["scenario_id"])
    op.create_index("ix_scenario_changes_entity_id", "scenario_changes", ["entity_id"])
    op.create_index(
        "ix_scenario_changes_scenario", "scenario_changes", ["scenario_id", "created_at"]
    )

    op.create_table(
        "attachments",
        *entity_columns(workspace=True, revisioned=True, soft_delete=True),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.CheckConstraint("length(trim(storage_path)) > 0", name="ck_attachments_path_nonempty"),
        sa.CheckConstraint("storage_path NOT LIKE '/%'", name="ck_attachments_path_relative"),
        sa.CheckConstraint("instr(storage_path, '..') = 0", name="ck_attachments_path_no_parent"),
        sa.CheckConstraint("instr(storage_path, ':') = 0", name="ck_attachments_path_no_drive"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_attachments_size_nonnegative"),
        sa.CheckConstraint("revision >= 1", name="ck_attachments_revision_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "storage_path", name="uq_attachment_storage_path"),
    )
    op.create_index("ix_attachments_workspace_id", "attachments", ["workspace_id"])

    op.create_table(
        "attachment_entity_links",
        *entity_columns(workspace=True),
        sa.Column(
            "attachment_id",
            sa.Uuid(),
            sa.ForeignKey("attachments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            enum_type("attachment_entity_type", *[item for item in _DOMAIN_ENTITY_VALUES]),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attachment_id",
            "entity_type",
            "entity_id",
            name="uq_attachment_entity_link",
        ),
    )
    op.create_index(
        "ix_attachment_entity_links_workspace_id", "attachment_entity_links", ["workspace_id"]
    )
    op.create_index(
        "ix_attachment_entity_links_attachment_id", "attachment_entity_links", ["attachment_id"]
    )
    op.create_index(
        "ix_attachment_entity_links_entity_id", "attachment_entity_links", ["entity_id"]
    )

    op.create_table(
        "tag_entity_links",
        *entity_columns(workspace=True),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            enum_type("tag_entity_type", *[item for item in _DOMAIN_ENTITY_VALUES]),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tag_id", "entity_type", "entity_id", name="uq_tag_entity_link"),
    )
    op.create_index("ix_tag_entity_links_workspace_id", "tag_entity_links", ["workspace_id"])
    op.create_index("ix_tag_entity_links_tag_id", "tag_entity_links", ["tag_id"])
    op.create_index("ix_tag_entity_links_entity_id", "tag_entity_links", ["entity_id"])

    op.create_table(
        "timeline_events",
        *entity_columns(workspace=True),
        sa.Column(
            "entity_type",
            enum_type("timeline_entity_type", *[item for item in _DOMAIN_ENTITY_VALUES]),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("length(trim(action)) > 0", name="ck_timeline_action_nonempty"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timeline_events_workspace_id", "timeline_events", ["workspace_id"])
    op.create_index("ix_timeline_events_entity_id", "timeline_events", ["entity_id"])
    op.create_index(
        "ix_timeline_workspace_occurred",
        "timeline_events",
        ["workspace_id", "occurred_at", "id"],
    )


_DOMAIN_ENTITY_VALUES = (
    "WORKSPACE",
    "USER_PREFERENCES",
    "TAG",
    "ATTACHMENT",
    "PROJECT",
    "TASK",
    "NOTE",
    "CALENDAR_EVENT",
    "FINANCIAL_ACCOUNT",
    "TRANSACTION",
    "BUDGET",
    "SAVINGS_GOAL",
    "COMMITMENT",
    "GOAL",
    "AUTOMATION_RULE",
    "SCENARIO",
)


def downgrade() -> None:
    for table_name in (
        "timeline_events",
        "tag_entity_links",
        "attachment_entity_links",
        "attachments",
        "scenario_changes",
        "scenarios",
        "automation_rules",
        "commitment_entity_links",
        "commitments",
        "goals",
        "savings_goals",
        "budget_category_limits",
        "budgets",
        "transactions",
        "transaction_categories",
        "financial_accounts",
        "calendar_events",
        "note_links",
        "notes",
        "task_dependencies",
        "tasks",
        "projects",
        "tags",
        "user_preferences",
        "workspaces",
    ):
        op.drop_table(table_name)
