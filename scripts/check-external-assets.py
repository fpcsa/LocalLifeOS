from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (
    REPOSITORY_ROOT / "apps" / "api" / "app",
    REPOSITORY_ROOT / "apps" / "web",
    REPOSITORY_ROOT / "packages" / "ui",
    REPOSITORY_ROOT / "packages" / "shared-types",
)
SCANNED_SUFFIXES = {".css", ".html", ".js", ".json", ".mjs", ".py", ".svg", ".ts", ".tsx"}
IGNORED_PARTS = {".next", "coverage", "node_modules"}
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "www.w3.org"}
URL_PATTERN = re.compile(r"(?:https?|wss?)://[^\s'\"`)<>]+")
BANNED_RUNTIME_REFERENCES = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "googletagmanager.com",
    "google-analytics.com",
    "segment.com",
    "sentry.io",
    "next/font/google",
)


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


def _source_files() -> list[Path]:
    return [
        path
        for root in SOURCE_ROOTS
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in SCANNED_SUFFIXES
        and path.name != "next-env.d.ts"
        and not any(part in IGNORED_PARTS for part in path.parts)
    ]


def _validate_url(value: str, label: str) -> list[str]:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https", "ws", "wss"}:
        return []
    if parsed.hostname not in ALLOWED_HOSTS:
        return [f"{label}: unexpected runtime host {parsed.hostname!r} in {value!r}"]
    return []


def scan_sources() -> list[str]:
    errors: list[str] = []
    for path in _source_files():
        relative = path.relative_to(REPOSITORY_ROOT)
        text = path.read_text(encoding="utf-8")
        lower = text.casefold()
        for banned in BANNED_RUNTIME_REFERENCES:
            if banned.casefold() in lower:
                errors.append(f"{relative}: banned runtime reference {banned!r}")
        for match in URL_PATTERN.finditer(text):
            errors.extend(_validate_url(match.group(0), str(relative)))
    return errors


def scan_runtime(base_url: str) -> list[str]:
    errors: list[str] = []
    parsed_base = urlsplit(base_url)
    if parsed_base.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return ["Runtime verification URL must use a loopback host."]
    with urlopen(base_url, timeout=5) as response:  # noqa: S310 - validated loopback URL.
        html = response.read().decode("utf-8")
        csp = response.headers.get("Content-Security-Policy", "")
    if not csp:
        errors.append("runtime: Content-Security-Policy header is missing")
    for match in URL_PATTERN.finditer(csp):
        errors.extend(_validate_url(match.group(0), "runtime CSP"))
    parser = AssetParser()
    parser.feed(html)
    for reference in parser.references:
        absolute = urljoin(base_url, reference)
        errors.extend(_validate_url(absolute, "runtime HTML"))
        parsed = urlsplit(absolute)
        if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
            with urlopen(absolute, timeout=5) as asset_response:  # noqa: S310 - loopback only.
                redirected = asset_response.geturl()
            errors.extend(_validate_url(redirected, "runtime redirect"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject remote frontend assets and unexpected runtime URL references."
    )
    parser.add_argument(
        "--runtime-url",
        help="Optionally inspect live loopback HTML, CSP, assets, and redirects.",
    )
    args = parser.parse_args()
    errors = scan_sources()
    if args.runtime_url:
        errors.extend(scan_runtime(args.runtime_url))
    if errors:
        print("External asset verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    mode = "source and runtime" if args.runtime_url else "source"
    print(f"External asset verification passed ({mode}): only local runtime hosts are referenced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
