from __future__ import annotations

from threading import RLock

# File-backed mutations and backup snapshots share this process-local lock. SQLite still
# provides database concurrency; this lock keeps attachment bytes aligned with snapshot metadata.
STORAGE_LOCK = RLock()
