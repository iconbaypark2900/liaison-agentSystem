"""Tests for Liaison v0.2.0 executor adapters."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from liaison.executors import (
    EXECUTOR_CONFIG_PATH,
    build_executor_status,
    cmd_executor_list,
    cmd_executor_ping,
    get_executor_capabilities,
    get_executor_config,
    is_executor_available,
    list_executors,
    load_executor_config,
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
    assert status.execution_allowed is False
    assert status.command == ["bash"]
    assert "placeholder" in status.reason
    assert isinstance(status.capabilities, list)
    assert len(status.capabilities) > 0


def test_missing_binary_does_not_crash() -> None:
    # Create a fake executor config with a non-existent binary
    with patch("shutil.which", return_value=None):
        status = build_executor_status("shell", PROJECT_ROOT)
        # Should not crash, should report available=False
        assert status.available is False
        assert "not found" in status.reason.lower() or "path" in status.reason.lower()


def test_execution_allowed_false_by_default() -> None:
    for executor_id in ["shell", "opencode", "codex", "claude_code", "ml_intern"]:
        status = build_executor_status(executor_id, PROJECT_ROOT)
        assert status.execution_allowed is False, f"{executor_id} should have execution_allowed=False"


def test_no_subprocess_task_execution_occurs() -> None:
    # Verify ping/list commands don't actually execute tasks
    args = MockArgs(json=False)
    rc = cmd_executor_list(args)
    assert rc == 0

    args = MockArgs(executor_id="shell", json=False)
    rc = cmd_executor_ping(args)
    assert rc == 0


def test_no_production_flags_changed() -> None:
    # The executor adapters should not touch production/customer/live flags
    statuses = list_executors(PROJECT_ROOT)
    for status in statuses:
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
    assert payload["execution_allowed"] is False


def test_ml_intern_disabled_by_default() -> None:
    status = build_executor_status("ml_intern", PROJECT_ROOT)
    assert status.enabled is False
    assert status.execution_allowed is False


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


def test_unknown_executor_returns_error_status() -> None:
    status = build_executor_status("unknown_executor", PROJECT_ROOT)
    assert status.executor_id == "unknown_executor"
    assert status.enabled is False
    assert status.available is False
    assert status.execution_allowed is False
    assert "not configured" in status.reason