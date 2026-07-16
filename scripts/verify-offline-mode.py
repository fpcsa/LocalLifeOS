from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify LocalLife OS offline and loopback runtime contracts."
    )
    parser.add_argument(
        "--runtime-url",
        help="Optionally inspect the running web app on a loopback URL.",
    )
    args = parser.parse_args()
    command = [sys.executable, str(REPOSITORY_ROOT / "scripts" / "check-external-assets.py")]
    if args.runtime_url:
        command.extend(["--runtime-url", args.runtime_url])
    external_check = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    if external_check.returncode != 0:
        return external_check.returncode

    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    required_mappings = ('"127.0.0.1:3000:3000"', '"127.0.0.1:8000:8000"')
    for mapping in required_mappings:
        if mapping not in compose:
            print(f"Offline verification failed: missing loopback mapping {mapping}")
            return 1
    if 'LOCALLIFE_CONTAINER_MODE: "true"' not in compose:
        print("Offline verification failed: container public bind was not explicitly scoped.")
        return 1

    outbound_guard = REPOSITORY_ROOT / "apps" / "api" / "app" / "core" / "network.py"
    if not outbound_guard.is_file():
        print("Offline verification failed: outbound network guard is missing.")
        return 1
    guard_text = outbound_guard.read_text(encoding="utf-8")
    if "configure_outbound_network_guard" not in guard_text or "socket.connect" not in guard_text:
        print("Offline verification failed: outbound network guard is incomplete.")
        return 1

    web_package = (REPOSITORY_ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    for native_script in (
        '"dev": "next dev --hostname 127.0.0.1',
        '"start": "next start --hostname 127.0.0.1',
    ):
        if native_script not in web_package:
            print("Offline verification failed: native frontend command is not loopback-only.")
            return 1

    service_worker = REPOSITORY_ROOT / "apps" / "web" / "public" / "sw.js"
    if not service_worker.is_file():
        print("Offline verification failed: service worker is missing.")
        return 1
    worker_text = service_worker.read_text(encoding="utf-8")
    if "url.origin !== self.location.origin" not in worker_text:
        print("Offline verification failed: service worker lacks cross-origin cache exclusion.")
        return 1
    if 'url.pathname.startsWith("/api/")' not in worker_text:
        print("Offline verification failed: service worker lacks API cache exclusion.")
        return 1

    print(
        "Offline verification passed: loopback ports, local assets, outbound boundaries, "
        "and network-only API caching are configured."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
