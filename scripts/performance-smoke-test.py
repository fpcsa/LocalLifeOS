#!/usr/bin/env python3
"""Run reproducible local API latency checks against an isolated demo workspace."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def _configure(data_dir: Path) -> None:
    os.environ.update(
        {
            "LOCALLIFE_ENV": "test",
            "LOCALLIFE_DATA_DIR": str(data_dir),
            "LOCALLIFE_DATABASE_URL": f"sqlite:///{(data_dir / 'performance.db').as_posix()}",
            "LOCALLIFE_AUTOMATION_SCHEDULER_ENABLED": "false",
            "LOCALLIFE_EXTERNAL_REQUESTS_ENABLED": "false",
            "LOCALLIFE_TELEMETRY_ENABLED": "false",
        }
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="locallife-performance-") as temporary_name:
        _configure(Path(temporary_name))
        from app.core.config import get_settings
        from app.db.session import get_engine
        from app.main import create_app
        from app.services.demo_data import IDS
        from fastapi.testclient import TestClient

        measurements: dict[str, dict[str, Any]] = {}
        with TestClient(create_app()) as client:
            loaded = client.post("/api/v1/demo/load")
            if loaded.status_code != 200:
                raise RuntimeError(loaded.text)
            checks = (
                ("health", "GET", "/api/v1/health", None, 0.25),
                (
                    "calendar_conflicts",
                    "GET",
                    "/api/v1/calendar/conflicts",
                    {
                        "start": "2026-07-19T00:00:00Z",
                        "end": "2026-07-23T00:00:00Z",
                        "timezone": "Europe/Rome",
                    },
                    1.0,
                ),
                (
                    "unified_timeline_page",
                    "GET",
                    "/api/v1/timeline/unified",
                    {"page": 1, "page_size": 20},
                    1.0,
                ),
                (
                    "scenario_comparison",
                    "POST",
                    "/api/v1/scenarios/compare",
                    {
                        "scenario_ids": [
                            str(IDS["scenario_physical"]),
                            str(IDS["scenario_remote"]),
                            str(IDS["scenario_skip"]),
                        ]
                    },
                    2.0,
                ),
            )
            failed = False
            for name, method, path, payload, threshold in checks:
                started = perf_counter()
                if method == "GET":
                    response = client.get(path, params=payload)
                else:
                    response = client.post(path, json=payload)
                elapsed = perf_counter() - started
                passed = response.status_code == 200 and elapsed <= threshold
                failed = failed or not passed
                measurements[name] = {
                    "elapsed_ms": round(elapsed * 1000, 1),
                    "threshold_ms": int(threshold * 1000),
                    "status_code": response.status_code,
                    "passed": passed,
                }
        get_engine().dispose()
        get_engine.cache_clear()
        get_settings.cache_clear()
        print(json.dumps(measurements, indent=2, sort_keys=True))
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
