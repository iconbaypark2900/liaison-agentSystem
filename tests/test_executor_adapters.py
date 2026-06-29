"""Tests for Liaison v0.2.0 executor adapters."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from liaison.executors import (
    EXECUTOR_CONFIG_PATH,
    ExecutorResult,
    build_executor_status,
    cmd_executor_list,
    cmd_executor_ping,
    cmd_executor_run,
    get_executor_capabilities,
    get_executor_config,
    is_executor_available,
    list_executors,
    load_executor_config,
    run_executor,
)


PROJECT_ROOT = Path(__file__).parent.parent


class MockArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_executor_config_loads() -> None:
    config = load_executor_config(PROJECT_ROOT)
    assert config["version"] == "0.2.0"
    assert "executors" in config
    assert "shell" in config["executors"]
    assert "opencode" in config["executors"]
    assert "codex" in config["executors"]
    assert "claude_code" in config["executors"]
    assert "ml_intern" in config["executors"]


def test_shell_executor_exists() -> None:
    config = get_executor_config("shell", PROJECT_ROOT)
    assert config is not None
    assert config["type"] == "shell"
    assert config["enabled"] is True
    assert config["command"] == "bash"


def test_opencode_executor_exists() -> None:
    config = get_executor_config("opencode", PROJECT_ROOT)
    assert config is not None
    assert config["type"] == "opencode"
    assert config["enabled"] is True
    assert config["command"] == "opencode"


def test_codex_executor_exists() -> None:
    config = get_executor_config("codex", PROJECT_ROOT)
    assert config is not None
    assert config["type"] == "codex"
    assert config["enabled"] is True
    assert config["command"] == "codex"


def test_claude_code_executor_exists() -> None:
    config = get_executor_config("claude_code", PROJECT_ROOT)
    assert config is not None
    assert config["type"] == "claude_code"
    assert config["enabled"] is True
    assert config["command"] == "claude"


def test_executor_ping_returns_normalized_status() -> None:
    status = build_executor_status("shell", PROJECT_ROOT)
    assert status.executor_id == "shell"
    assert status.enabled is True
    assert status.available is True  # bash should be available
    assert status.execution_allowed is True  # shell has allow_execution: true in config
    assert status.reason == "Ready"
    assert isinstance(status.capabilities, list)
    assert len(status.capabilities) > 0


def test_missing_binary_does_not_crash() -> None:
    # Create a fake executor config with a non-existent binary
    with patch("shutil.which", return_value=None):
        status = build_executor_status("shell", PROJECT_ROOT)
        # Should not crash, should report available=False
        assert status.available is False
        assert "not found" in status.reason.lower() or "path" in status.reason.lower()


def test_execution_allowed_by_config() -> None:
    for executor_id in ["opencode", "codex", "claude_code"]:
        status = build_executor_status(executor_id, PROJECT_ROOT)
        assert status.execution_allowed is False, f"{executor_id} should have execution_allowed=False"
    # shell is explicitly allowed in config
    status = build_executor_status("shell", PROJECT_ROOT)
    assert status.execution_allowed is True
    # ml_intern has allow_execution: true (Phase 9) but is still disabled
    status = build_executor_status("ml_intern", PROJECT_ROOT)
    assert status.execution_allowed is True
    assert status.enabled is False


def test_no_subprocess_task_execution_occurs() -> None:
    # Verify ping/list commands don't actually execute tasks
    args = MockArgs(json=False)
    rc = cmd_executor_list(args)
    assert rc == 0

    args = MockArgs(executor_id="shell", json=False)
    rc = cmd_executor_ping(args)
    assert rc == 0


def test_no_production_flags_changed() -> None:
    # shell and ml_intern have allow_execution: true; others remain locked
    for status in list_executors(PROJECT_ROOT):
        if status.executor_id == "shell":
            assert status.execution_allowed is True
        elif status.executor_id == "ml_intern":
            assert status.execution_allowed is True
            assert status.enabled is False
        else:
            assert status.execution_allowed is False


def test_json_output_format(capsys) -> None:
    args = MockArgs(json=True)
    rc = cmd_executor_list(args)
    output = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(output)
    assert "executors" in payload
    assert "count" in payload
    assert isinstance(payload["executors"], list)
    assert payload["count"] == len(payload["executors"])

    # Check each executor has required fields
    for exec_info in payload["executors"]:
        assert "executor_id" in exec_info
        assert "enabled" in exec_info
        assert "available" in exec_info
        assert "execution_allowed" in exec_info
        assert "command" in exec_info
        assert "reason" in exec_info
        assert "capabilities" in exec_info


def test_ping_json_output(capsys) -> None:
    args = MockArgs(executor_id="shell", json=True)
    rc = cmd_executor_ping(args)
    output = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(output)
    assert payload["executor_id"] == "shell"
    assert "available" in payload
    assert "execution_allowed" in payload
    assert payload["execution_allowed"] is True


def test_ml_intern_disabled_by_default() -> None:
    status = build_executor_status("ml_intern", PROJECT_ROOT)
    assert status.enabled is False
    assert status.execution_allowed is True  # allow_execution: true for Phase 9
    assert "disabled" in status.reason


def test_executor_capabilities() -> None:
    config = get_executor_config("shell", PROJECT_ROOT)
    caps = get_executor_capabilities("shell", config)
    assert "validation_commands" in caps
    assert "diagnostics" in caps
    assert "dry_run" in caps
    assert "placeholder" in caps

    config = get_executor_config("opencode", PROJECT_ROOT)
    caps = get_executor_capabilities("opencode", config)
    assert "code_generation" in caps
    assert "refactoring" in caps
    assert "litellm_route" in caps

    config = get_executor_config("codex", PROJECT_ROOT)
    caps = get_executor_capabilities("codex", config)
    assert "code_generation" in caps
    assert "refactoring" in caps
    assert "debugging" in caps
    assert "litellm_route" in caps

    config = get_executor_config("claude_code", PROJECT_ROOT)
    caps = get_executor_capabilities("claude_code", config)
    assert "code_review" in caps
    assert "repo_aware" in caps
    assert "refactoring" in caps


def test_run_executor_echo(capsys) -> None:
    result = run_executor("shell", ["-c", "echo hello world"], root=PROJECT_ROOT)
    assert result.exit_code == 0
    assert result.stdout.strip() == "hello world"
    assert result.duration_sec > 0
    assert result.executor_id == "shell"


def test_run_executor_exit_code(capsys) -> None:
    result = run_executor("shell", ["-c", "exit 42"], root=PROJECT_ROOT)
    assert result.exit_code == 42


def test_run_executor_stderr(capsys) -> None:
    result = run_executor("shell", ["-c", "echo err >&2"], root=PROJECT_ROOT)
    assert result.exit_code == 0
    assert result.stderr.strip() == "err"


def test_run_executor_timeout(capsys) -> None:
    result = run_executor("shell", ["-c", "sleep 10"], root=PROJECT_ROOT, timeout=1)
    assert result.exit_code == -1
    assert "TIMEOUT" in result.stderr


def test_run_executor_not_configured() -> None:
    try:
        run_executor("nonexistent", root=PROJECT_ROOT)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as exc:
        assert "not configured" in str(exc)


def test_run_executor_disabled() -> None:
    try:
        run_executor("ml_intern", ["--version"], root=PROJECT_ROOT)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as exc:
        assert "disabled" in str(exc) or "not allowed" in str(exc)


def test_cmd_executor_run_ok(capsys) -> None:
    args = MockArgs(executor_id="shell", command_args=["-c", "echo ok"], timeout=None, cwd=None, json=False)
    rc = cmd_executor_run(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Exit code: 0" in out
    assert "ok" in out


def test_cmd_executor_run_json(capsys) -> None:
    args = MockArgs(executor_id="shell", command_args=["-c", "echo json_test"], timeout=None, cwd=None, json=True)
    rc = cmd_executor_run(args)
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["exit_code"] == 0
    assert payload["stdout"].strip() == "json_test"
    assert payload["executor_id"] == "shell"


def test_cmd_executor_run_disabled_executor(capsys) -> None:
    args = MockArgs(executor_id="ml_intern", command_args=["--version"], timeout=None, cwd=None, json=False)
    rc = cmd_executor_run(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "Error:" in err


def test_unknown_executor_returns_error_status() -> None:
    status = build_executor_status("unknown_executor", PROJECT_ROOT)
    assert status.executor_id == "unknown_executor"
    assert status.enabled is False
    assert status.available is False
    assert status.execution_allowed is False
    assert "not configured" in status.reason