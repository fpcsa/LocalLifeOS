from __future__ import annotations

from enum import StrEnum

from app.models.common import (
    BudgetPeriod,
    CalendarEventStatus,
    CategoryKind,
    CommitmentEntityType,
    CommitmentStatus,
    DomainEntityType,
    FinancialAccountType,
    GoalStatus,
    PlannedTransactionStatus,
    PreferredTimeOfDay,
    ProjectStatus,
    RecurrenceFrequency,
    RecurringTransactionStatus,
    ScenarioOperation,
    ScenarioStatus,
    SubscriptionStatus,
    TaskDependencyType,
    TaskPriority,
    TaskStatus,
    ThemeMode,
    TransactionType,
)

ENUM_TYPES: dict[str, type[StrEnum]] = {
    "budget_period": BudgetPeriod,
    "calendar_event_status": CalendarEventStatus,
    "category_kind": CategoryKind,
    "commitment_entity_type": CommitmentEntityType,
    "commitment_status": CommitmentStatus,
    "domain_entity_type": DomainEntityType,
    "financial_account_type": FinancialAccountType,
    "goal_status": GoalStatus,
    "planned_transaction_status": PlannedTransactionStatus,
    "preferred_time_of_day": PreferredTimeOfDay,
    "project_status": ProjectStatus,
    "recurrence_frequency": RecurrenceFrequency,
    "recurring_transaction_status": RecurringTransactionStatus,
    "scenario_operation": ScenarioOperation,
    "scenario_status": ScenarioStatus,
    "subscription_status": SubscriptionStatus,
    "task_dependency_type": TaskDependencyType,
    "task_priority": TaskPriority,
    "task_status": TaskStatus,
    "theme_mode": ThemeMode,
    "transaction_type": TransactionType,
}


def get_enum_values() -> dict[str, list[str]]:
    return {name: [item.value for item in enum_type] for name, enum_type in ENUM_TYPES.items()}
