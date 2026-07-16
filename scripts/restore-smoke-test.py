from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"


def _workspace_name(database: Path) -> str:
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            "SELECT name FROM workspaces WHERE is_default = 1 AND deleted_at IS NULL"
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return str(row[0])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="locallife-restore-smoke-") as temporary:
        data_dir = Path(temporary) / "data"
        database = data_dir / "smoke.db"
        os.environ.update(
            {
                "LOCALLIFE_ENV": "test",
                "LOCALLIFE_DATA_DIR": str(data_dir),
                "LOCALLIFE_DATABASE_URL": f"sqlite:///{database.as_posix()}",
                "LOCALLIFE_AUTOMATION_SCHEDULER_ENABLED": "false",
                "LOCALLIFE_BACKUP_ARGON2_MEMORY_KIB": "8192",
                "LOCALLIFE_BACKUP_ARGON2_TIME_COST": "1",
                "LOCALLIFE_BACKUP_ARGON2_PARALLELISM": "1",
            }
        )
        sys.path.insert(0, str(API_ROOT))
        from app.core.config import get_settings
        from app.db.session import get_engine, initialize_database
        from app.services.backups import create_backup, restore_backup

        get_settings.cache_clear()
        get_engine.cache_clear()
        initialize_database()
        connection = sqlite3.connect(database)
        connection.execute("UPDATE workspaces SET name = 'Backup state' WHERE is_default = 1")
        connection.commit()
        connection.close()
        created = create_backup(label="restore-smoke")
        connection = sqlite3.connect(database)
        connection.execute("UPDATE workspaces SET name = 'Changed state' WHERE is_default = 1")
        connection.commit()
        connection.close()
        get_engine().dispose()
        restored = restore_backup(created.summary.path)
        assert _workspace_name(database) == "Backup state"
        assert restored.safety_backup.is_file()
        print(
            "Restore smoke test passed: integrity checked, schema compatible, "
            "safety backup created, workspace restored"
        )
        get_engine().dispose()
        get_engine.cache_clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())
