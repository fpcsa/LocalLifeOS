from __future__ import annotations

import json
import os
from pathlib import Path

from app import launcher
from typer.testing import CliRunner

runner = CliRunner()


def test_pid_liveness_handles_current_and_missing_processes() -> None:
    assert launcher._pid_alive(os.getpid()) is True
    assert launcher._pid_alive(2_147_483_647) is False


def test_launcher_status_reports_loopback_and_data_directory(database_path: Path) -> None:
    del database_path
    result = runner.invoke(launcher.app, ["status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["network_mode"] == "loopback-only"
    assert payload["api_url"].startswith("http://127.0.0.1:")
    assert payload["web_url"].startswith("http://127.0.0.1:")
    assert "0.0.0.0" not in result.output


def test_launcher_start_uses_loopback_and_opens_browser_only_when_requested(
    database_path: Path,
    monkeypatch,
) -> None:
    del database_path
    commands: list[list[str]] = []
    opened: list[str] = []
    pids = iter([101, 202, 303, 404])
    monkeypatch.setattr(
        launcher,
        "_running_status",
        lambda settings: {"api_process_running": False, "web_process_running": False},
    )
    monkeypatch.setattr(launcher, "_require_available_port", lambda port, label: None)
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "C:/node/node.exe")
    monkeypatch.setattr(launcher, "_wait_for_health", lambda url, timeout_seconds: True)
    monkeypatch.setattr(launcher, "_write_state", lambda settings, state: None)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url, new=0: opened.append(url))

    def fake_spawn(command, **kwargs):
        del kwargs
        commands.append(command)
        return next(pids)

    monkeypatch.setattr(launcher, "_spawn", fake_spawn)

    first = runner.invoke(launcher.app, ["start", "--development"])
    assert first.exit_code == 0, first.output
    assert opened == []
    assert all("0.0.0.0" not in command for command in commands)
    assert any("127.0.0.1" in command for command in commands)

    second = runner.invoke(launcher.app, ["start", "--development", "--open-browser"])
    assert second.exit_code == 0, second.output
    assert opened == ["http://127.0.0.1:3000"]


def test_launcher_stop_preserves_state_when_process_termination_fails(
    database_path: Path,
    monkeypatch,
) -> None:
    del database_path
    monkeypatch.setattr(
        launcher,
        "_read_state",
        lambda settings: {"api_pid": 101, "web_pid": 202, "api_port": 8000, "web_port": 3000},
    )
    monkeypatch.setattr(launcher, "_terminate_pid", lambda pid: False)
    monkeypatch.setattr(launcher, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(launcher, "_port_open", lambda port: True)

    result = runner.invoke(launcher.app, ["stop"])

    assert result.exit_code == 1
    assert "launcher state was preserved" in result.output
