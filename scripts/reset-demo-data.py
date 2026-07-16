#!/usr/bin/env python3
"""Remove or deterministically reload only LocalLife OS reserved demo records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.db.session import get_engine, initialize_database  # noqa: E402
from app.services.demo_data import load_demo_data, reset_demo_data  # noqa: E402
from sqlmodel import Session  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset only the deterministic LocalLife OS demo dataset."
    )
    parser.add_argument(
        "--empty",
        action="store_true",
        help="leave demo records removed instead of immediately reloading them",
    )
    args = parser.parse_args()

    initialize_database()
    with Session(get_engine()) as session:
        removed = reset_demo_data(session)
        result: dict[str, object] = {"reset": removed.model_dump(mode="json")}
        if not args.empty:
            result["loaded"] = load_demo_data(session).model_dump(mode="json")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
