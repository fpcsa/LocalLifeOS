from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
OPENAPI_OUTPUT = REPOSITORY_ROOT / "packages" / "shared-types" / "src" / "openapi.json"


def main() -> int:
    sys.path.insert(0, str(API_ROOT))

    from app.main import create_app

    schema = create_app().openapi()
    OPENAPI_OUTPUT.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Exported {len(schema['paths'])} paths and "
        f"{len(schema['components']['schemas'])} schemas to "
        f"{OPENAPI_OUTPUT.relative_to(REPOSITORY_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
