from __future__ import annotations

from pathlib import Path

from app.db.session import get_engine, run_migrations
from sqlalchemy import inspect, text

EXPECTED_TABLES = {
    "alembic_version",
    "attachment_entity_links",
    "attachments",
    "automation_rules",
    "automation_executions",
    "budget_category_limits",
    "budgets",
    "calendar_events",
    "calendar_event_entity_links",
    "commitment_entity_links",
    "commitments",
    "csv_mapping_profiles",
    "financial_accounts",
    "goals",
    "import_batches",
    "import_rows",
    "local_notifications",
    "note_links",
    "note_entity_links",
    "notes",
    "notes_fts",
    "notes_fts_config",
    "notes_fts_content",
    "notes_fts_data",
    "notes_fts_docsize",
    "notes_fts_idx",
    "projects",
    "planned_transactions",
    "recurring_transaction_rules",
    "savings_goals",
    "scheduling_previews",
    "scenario_changes",
    "scenarios",
    "system_settings",
    "subscription_price_changes",
    "subscriptions",
    "tag_entity_links",
    "tags",
    "task_dependencies",
    "tasks",
    "timeline_events",
    "transaction_categories",
    "transactions",
    "user_preferences",
    "workspaces",
}


def test_alembic_upgrades_an_empty_database_to_the_complete_schema(
    database_path: Path,
) -> None:
    assert not database_path.exists()

    run_migrations()

    inspector = inspect(get_engine())
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    with get_engine().connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert revision == "20260716_0011"
