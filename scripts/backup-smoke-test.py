from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="locallife-backup-smoke-") as temporary:
        data_dir = Path(temporary) / "data"
        os.environ.update(
            {
                "LOCALLIFE_ENV": "test",
                "LOCALLIFE_DATA_DIR": str(data_dir),
                "LOCALLIFE_DATABASE_URL": f"sqlite:///{(data_dir / 'smoke.db').as_posix()}",
                "LOCALLIFE_AUTOMATION_SCHEDULER_ENABLED": "false",
                "LOCALLIFE_BACKUP_ARGON2_MEMORY_KIB": "8192",
                "LOCALLIFE_BACKUP_ARGON2_TIME_COST": "1",
                "LOCALLIFE_BACKUP_ARGON2_PARALLELISM": "1",
            }
        )
        sys.path.insert(0, str(API_ROOT))
        from app.core.config import get_settings
        from app.db.session import get_engine, initialize_database
        from app.services.backups import create_backup, inspect_backup

        get_settings.cache_clear()
        get_engine.cache_clear()
        initialize_database()
        settings = get_settings()
        assert settings.attachments_dir is not None
        attachment = settings.attachments_dir / "smoke.txt"
        attachment.write_text("backup smoke proof", encoding="utf-8")
        created = create_backup(password="smoke-test-password", label="smoke")
        inspected = inspect_backup(created.summary.path, password="smoke-test-password")
        assert inspected.manifest == created.manifest
        assert created.summary.integrity_verified
        print(
            f"Backup smoke test passed: encrypted={created.summary.encrypted}, "
            f"files={len(created.manifest.files)}, integrity=verified"
        )
        get_engine().dispose()
        get_engine.cache_clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())
