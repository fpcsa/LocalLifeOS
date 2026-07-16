#!/usr/bin/env python3
"""Load LocalLife OS's deterministic, entirely synthetic judge dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.db.session import get_engine, initialize_database  # noqa: E402
from app.services.demo_data import load_demo_data  # noqa: E402
from sqlmodel import Session  # noqa: E402


def main() -> int:
    initialize_database()
    with Session(get_engine()) as session:
        summary = load_demo_data(session)
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
