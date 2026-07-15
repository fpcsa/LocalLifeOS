from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    REPOSITORY_ROOT / "apps" / "web",
    REPOSITORY_ROOT / "packages" / "shared-types",
    REPOSITORY_ROOT / "packages" / "ui",
)
SCANNED_SUFFIXES = {".css", ".js", ".json", ".mjs", ".ts", ".tsx"}
IGNORED_PARTS = {".next", "coverage", "node_modules"}
ALLOWED_URL_HOSTS = {"127.0.0.1", "localhost", "::1", "www.w3.org"}
URL_PATTERN = re.compile(r"https?://[^\s'\"`)]+")
BANNED_IMPORTS = (
    "next/font/google",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "googletagmanager.com",
)


def source_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if (
                path.is_file()
                and path.suffix in SCANNED_SUFFIXES
                and path.name != "next-env.d.ts"
                and not any(part in IGNORED_PARTS for part in path.parts)
            ):
                files.append(path)
    return files


def verify_file(path: Path) -> list[str]:
    relative_path = path.relative_to(REPOSITORY_ROOT)
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    for banned_import in BANNED_IMPORTS:
        if banned_import in text:
            errors.append(f"{relative_path}: banned remote asset reference {banned_import!r}")

    for match in URL_PATTERN.finditer(text):
        url = match.group(0)
        hostname = urlsplit(url).hostname
        if hostname not in ALLOWED_URL_HOSTS:
            errors.append(f"{relative_path}: non-local URL {url!r}")

    return errors


def main() -> int:
    errors = [error for path in source_files() for error in verify_file(path)]
    if errors:
        print("Offline source verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    compose_file = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for mapping in ('"127.0.0.1:3000:3000"', '"127.0.0.1:8000:8000"'):
        if mapping not in compose_file:
            print(f"Offline source verification failed: missing loopback mapping {mapping}")
            return 1

    print("Offline source verification passed: no remote frontend assets or non-loopback ports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
