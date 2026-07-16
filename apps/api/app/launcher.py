from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import webbrowser
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

import typer

from app.core.config import REPOSITORY_ROOT, Settings, get_settings
from app.core.exceptions import DomainError
from app.services.backups import (
    ENCRYPTED_MAGIC,
    create_backup,
    current_schema_revision,
    database_path,
    inspect_backup,
    restore_backup,
)

app = typer.Typer(
    name="locallife",
    help="Run and protect the LocalLife OS workspace on this device.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
API_ROOT = REPOSITORY_ROOT / "apps" / "api"


def _runtime_root(settings: Settings) -> Path:
    if settings.runtime_dir is None:
        raise RuntimeError("runtime directory was not configured")
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    return settings.runtime_dir


def _state_path(settings: Settings) -> Path:
    return _runtime_root(settings) / "launcher.json"


def _read_state(settings: Settings) -> dict[str, Any]:
    path = _state_path(settings)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(settings: Settings, state: dict[str, Any]) -> None:
    path = _state_path(settings)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8") as output:
        json.dump(state, output, indent=2, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        open_process.restype = ctypes.c_void_p
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        get_exit_code.restype = ctypes.c_int
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        try:
            return bool(get_exit_code(handle, ctypes.byref(exit_code))) and exit_code.value == 259
        finally:
            close_handle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def _require_available_port(port: int, label: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        try:
            candidate.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"{label} port {port} is already in use on loopback") from exc


def _spawn(command: list[str], *, cwd: Path, log_path: Path, env: dict[str, str]) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = 0
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            **kwargs,
        )
    return process.pid


def _wait_for_health(url: str, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310 - URL is fixed loopback.
                if 200 <= response.status < 400:
                    return True
        except (OSError, URLError):
            time.sleep(0.2)
    return False


def _terminate_pid(pid: int) -> bool:
    if not _pid_alive(pid):
        return True
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return not _pid_alive(pid)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _pid_alive(pid):
        time.sleep(0.1)
    if _pid_alive(pid):
        with suppress(OSError):
            os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    return not _pid_alive(pid)


def _running_status(settings: Settings) -> dict[str, Any]:
    state = _read_state(settings)
    api_pid = int(state.get("api_pid", 0) or 0)
    web_pid = int(state.get("web_pid", 0) or 0)
    api_port = int(state.get("api_port", settings.port) or settings.port)
    web_port = int(state.get("web_port", 3000) or 3000)
    return {
        **state,
        "api_pid": api_pid,
        "web_pid": web_pid,
        "api_process_running": _pid_alive(api_pid),
        "web_process_running": _pid_alive(web_pid),
        "api_reachable": _port_open(api_port),
        "web_reachable": _port_open(web_port),
        "api_url": f"http://127.0.0.1:{api_port}",
        "web_url": f"http://127.0.0.1:{web_port}",
        "data_directory": str(settings.data_dir),
        "network_mode": "loopback-only",
    }


def _password_from_file(path: Path) -> str:
    resolved = path.expanduser().resolve()
    value = resolved.read_text(encoding="utf-8").rstrip("\r\n")
    if not value:
        raise RuntimeError("The password file is empty")
    return value


def _domain_failure(error: DomainError) -> None:
    typer.secho(f"{error.code}: {error.message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@app.command()
def start(
    api_port: Annotated[int, typer.Option(min=1, max=65_535)] = 8000,
    web_port: Annotated[int, typer.Option(min=1, max=65_535)] = 3000,
    open_browser: Annotated[
        bool,
        typer.Option("--open-browser", help="Open the local UI after both services are ready."),
    ] = False,
    development: Annotated[
        bool,
        typer.Option("--development", help="Run the Next.js development server."),
    ] = False,
) -> None:
    """Start the API and web application on 127.0.0.1."""

    settings = get_settings()
    settings.ensure_directories()
    current = _running_status(settings)
    if current["api_process_running"] or current["web_process_running"]:
        typer.echo("LocalLife OS is already running. Use `locallife status` for details.")
        return
    try:
        _require_available_port(api_port, "API")
        _require_available_port(web_port, "Web")
        node = shutil.which("node")
        next_cli = REPOSITORY_ROOT / "node_modules" / "next" / "dist" / "bin" / "next"
        if node is None or not next_cli.is_file():
            raise RuntimeError("Node.js dependencies are missing; run `npm install` first")
        env = os.environ.copy()
        env.update(
            {
                "LOCALLIFE_HOST": "127.0.0.1",
                "LOCALLIFE_PORT": str(api_port),
                "LOCALLIFE_CONTAINER_MODE": "false",
                "NEXT_PUBLIC_API_BASE_URL": f"http://127.0.0.1:{api_port}/api/v1",
                "NEXT_TELEMETRY_DISABLED": "1",
            }
        )
        runtime = _runtime_root(settings)
        api_pid = _spawn(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
                "--no-access-log",
            ],
            cwd=API_ROOT,
            log_path=runtime / "api.log",
            env=env,
        )
        production_ready = (REPOSITORY_ROOT / "apps" / "web" / ".next" / "BUILD_ID").is_file()
        next_mode = "dev" if development or not production_ready else "start"
        web_pid = _spawn(
            [
                node,
                str(next_cli),
                next_mode,
                "--hostname",
                "127.0.0.1",
                "--port",
                str(web_port),
            ],
            cwd=REPOSITORY_ROOT / "apps" / "web",
            log_path=runtime / "web.log",
            env=env,
        )
        state = {
            "api_pid": api_pid,
            "web_pid": web_pid,
            "api_port": api_port,
            "web_port": web_port,
            "web_mode": next_mode,
            "started_at": datetime.now(UTC).isoformat(),
        }
        _write_state(settings, state)
        api_ready = _wait_for_health(
            f"http://127.0.0.1:{api_port}/api/v1/health", timeout_seconds=45
        )
        web_ready = _wait_for_health(f"http://127.0.0.1:{web_port}", timeout_seconds=60)
        if not api_ready or not web_ready:
            _terminate_pid(web_pid)
            _terminate_pid(api_pid)
            _state_path(settings).unlink(missing_ok=True)
            raise RuntimeError(
                f"Startup did not become ready (API={api_ready}, web={web_ready}); "
                f"inspect {runtime / 'api.log'} and {runtime / 'web.log'}"
            )
    except (OSError, RuntimeError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    url = f"http://127.0.0.1:{web_port}"
    typer.echo(f"LocalLife OS is ready at {url}")
    if open_browser:
        webbrowser.open(url, new=2)


@app.command()
def stop() -> None:
    """Stop processes started by the native launcher."""

    settings = get_settings()
    state = _read_state(settings)
    if not state:
        typer.echo("No native launcher state was found.")
        return
    web_stopped = _terminate_pid(int(state.get("web_pid", 0) or 0))
    api_stopped = _terminate_pid(int(state.get("api_pid", 0) or 0))
    if not web_stopped or not api_stopped:
        typer.secho(
            "LocalLife OS could not stop every tracked process; launcher state was preserved.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    deadline = time.monotonic() + 5
    api_port = int(state.get("api_port", settings.port) or settings.port)
    web_port = int(state.get("web_port", 3000) or 3000)
    while time.monotonic() < deadline and (_port_open(api_port) or _port_open(web_port)):
        time.sleep(0.1)
    if _port_open(api_port) or _port_open(web_port):
        typer.secho(
            "Tracked processes exited, but a LocalLife OS port remains occupied; "
            "launcher state was preserved.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    _state_path(settings).unlink(missing_ok=True)
    typer.echo("LocalLife OS stopped.")


@app.command("status")
def show_status(
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable JSON.")
    ] = False,
) -> None:
    """Show process, port, network, and data-directory status."""

    status_value = _running_status(get_settings())
    if json_output:
        typer.echo(json.dumps(status_value, indent=2, sort_keys=True))
        return
    overall = (
        "running"
        if status_value["api_reachable"] and status_value["web_reachable"]
        else "stopped or incomplete"
    )
    typer.echo(f"Status: {overall}")
    typer.echo(f"Web: {status_value['web_url']} (reachable={status_value['web_reachable']})")
    typer.echo(f"API: {status_value['api_url']} (reachable={status_value['api_reachable']})")
    typer.echo(f"Network: {status_value['network_mode']}")
    typer.echo(f"Data: {status_value['data_directory']}")


@app.command()
def backup(
    encrypt: Annotated[
        bool, typer.Option("--encrypt", help="Protect the backup with Argon2id and AES-256-GCM.")
    ] = False,
    password_file: Annotated[
        Path | None,
        typer.Option(help="Read the encryption password from a local file, not command history."),
    ] = None,
    label: Annotated[str | None, typer.Option(help="Optional filename-safe backup label.")] = None,
) -> None:
    """Create and verify a full local workspace backup."""

    password: str | None = None
    try:
        if password_file is not None:
            password = _password_from_file(password_file)
            encrypt = True
        elif encrypt:
            password = typer.prompt("Backup password", hide_input=True, confirmation_prompt=True)
        from app.db.session import initialize_database

        initialize_database()
        created = create_backup(password=password, label=label)
    except DomainError as exc:
        _domain_failure(exc)
    except (OSError, RuntimeError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Backup verified: {created.summary.path}")


@app.command()
def restore(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    password_file: Annotated[
        Path | None,
        typer.Option(help="Read the backup password from a local file, not command history."),
    ] = None,
) -> None:
    """Verify, preview, safety-backup, and restore a compatible workspace."""

    settings = get_settings()
    running = _running_status(settings)
    if running["api_process_running"] or running["web_process_running"]:
        typer.secho("Stop LocalLife OS before restoring a backup.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    password: str | None = None
    try:
        with source.open("rb") as input_file:
            encrypted = input_file.read(len(ENCRYPTED_MAGIC)) == ENCRYPTED_MAGIC
        if password_file is not None:
            password = _password_from_file(password_file)
        elif encrypted:
            password = typer.prompt("Backup password", hide_input=True)
        inspection = inspect_backup(source.expanduser().resolve(), password=password)
        typer.echo(
            f"Restore preview: {inspection.manifest.created_at.isoformat()}, "
            f"schema {inspection.manifest.schema_revision}, encrypted={inspection.encrypted}"
        )
        if not typer.confirm("Restore this backup after creating a safety backup?"):
            typer.echo("Restore cancelled.")
            return
        result = restore_backup(source, password=password)
    except DomainError as exc:
        _domain_failure(exc)
    except (OSError, RuntimeError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Restore complete. Safety backup: {result.safety_backup}")


@app.command()
def doctor() -> None:
    """Check native prerequisites, storage, schema, ports, and loopback policy."""

    settings = get_settings()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python", sys.version_info >= (3, 12), sys.version.split()[0]))
    node = shutil.which("node")
    checks.append(("Node.js", node is not None, node or "not found"))
    next_cli = REPOSITORY_ROOT / "node_modules" / "next" / "dist" / "bin" / "next"
    checks.append(("Frontend dependencies", next_cli.is_file(), str(next_cli)))
    checks.append(
        ("Native bind", settings.host in {"127.0.0.1", "localhost", "::1", "[::1]"}, settings.host)
    )
    try:
        settings.ensure_directories()
        probe = _runtime_root(settings) / f".doctor-{uuid4().hex}"
        probe.touch(exist_ok=False)
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    checks.append(("Data directory writable", writable, str(settings.data_dir)))
    db_path = database_path(settings)
    if db_path.is_file():
        try:
            connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            connection.close()
            schema = str(row[0]) if row else "missing"
            database_ok = schema == current_schema_revision() and integrity == ("ok",)
            database_detail = (
                f"schema={schema}, integrity={integrity[0] if integrity else 'missing'}"
            )
        except sqlite3.DatabaseError as exc:
            database_ok = False
            database_detail = type(exc).__name__
    else:
        database_ok = True
        database_detail = "not initialized; first start will create it"
    checks.append(("Database", database_ok, database_detail))
    checks.append(("API port", not _port_open(settings.port), str(settings.port)))
    checks.append(("Web port", not _port_open(3000), "3000"))
    for label, passed, detail in checks:
        marker = "OK" if passed else "FAIL"
        typer.echo(f"[{marker}] {label}: {detail}")
    if not all(passed for _, passed, _ in checks):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
