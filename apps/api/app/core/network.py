from __future__ import annotations

import ipaddress
import sys
from collections.abc import Sequence
from typing import Any

_audit_hook_installed = False
_outbound_blocked = True


def _is_loopback_host(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="ignore")
    if not isinstance(value, str):
        return False
    host = value.strip().strip("[]").split("%", 1)[0]
    if host.casefold() == "localhost":
        return True
    if "/" in host or "\\" in host:
        return True  # Unix-domain or local named socket path.
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _audit_outbound_network(event: str, args: Sequence[Any]) -> None:
    if not _outbound_blocked:
        return
    host: object | None = None
    if event == "socket.connect" and len(args) >= 2:
        address = args[1]
        host = address[0] if isinstance(address, tuple) and address else address
    elif event == "socket.getaddrinfo" and args:
        host = args[0]
    else:
        return
    if not _is_loopback_host(host):
        raise PermissionError("Outbound network access is disabled for LocalLife OS")


def configure_outbound_network_guard(*, external_requests_enabled: bool) -> None:
    """Block non-loopback Python sockets unless the operator explicitly opts out."""

    global _audit_hook_installed, _outbound_blocked
    _outbound_blocked = not external_requests_enabled
    if not _audit_hook_installed:
        sys.addaudithook(_audit_outbound_network)
        _audit_hook_installed = True
