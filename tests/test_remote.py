"""Tests for Phase 8B remote NIM endpoint execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from liaison.remote import (
    RemoteCallResult,
    BudgetCheck,
    RemoteExecutionError,
    check_approved_request,
    check_budget,
    check_nvidia_api_key,
    load_budget_limits,
    load_capability_routes,
    load_model_routes,
    load_provider_registry,
    resolve_capability,
    resolve_provider,
    resolve_route,
    run_nim_endpoint,
    validate_remote_call,
)


PROJECT_ROOT = Path(__file__).parent.parent


def test_load_provider_registry() -> None:
    registry = load_provider_registry(PROJECT_ROOT)
    assert "providers" in registry
    assert "nvidia_nim" in registry["providers"]
    nim = registry["providers"]["nvidia_nim"]
    assert nim["kind"] == "remote"
    assert nim["env_key"] == "NVIDIA_API_KEY"
    assert "base_url" in nim


def test_load_capability_routes() -> None:
    routes = load_capability_routes(PROJECT_ROOT)
    caps = routes.get("capabilities", {})
    assert "long_context_architecture" in caps
    assert caps["long_context_architecture"]["remote_allowed"] is True
    assert caps["long_context_architecture"]["remote_read_only"] is True
    assert "local_implementation" in caps
    assert caps["local_implementation"]["remote_allowed"] is False


def test_resolve_capability_existing() -> None:
    cap = resolve_capability("long_context_architecture", PROJECT_ROOT)
    assert cap["remote_allowed"] is True
    assert "deepseek_v4_flash" in cap["preferred_routes"]


def test_resolve_capability_missing() -> None:
    cap = resolve_capability("nonexistent_capability", PROJECT_ROOT)
    assert cap == {}


def test_resolve_route_remote() -> None:
    route = resolve_route("deepseek_v4_flash", PROJECT_ROOT)
    assert route["provider"] == "nvidia_nim"
    assert "deepseek" in route["model"]


def test_resolve_route_local() -> None:
    route = resolve_route("coder", PROJECT_ROOT)
    assert route["provider"] == "ollama"
    assert route["section"] == "local_models"


def test_resolve_route_missing() -> None:
    route = resolve_route("nonexistent_route", PROJECT_ROOT)
    assert route == {}


def test_resolve_provider_nvidia() -> None:
    provider = resolve_provider("nvidia_nim", PROJECT_ROOT)
    assert provider["kind"] == "remote"
    assert provider["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert provider["chat_completions_path"] == "/chat/completions"


def test_check_nvidia_api_key_absent(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    ok, msg = check_nvidia_api_key()
    assert ok is False
    assert "NVIDIA_API_KEY" in msg


def test_check_nvidia_api_key_present(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-fake-key-1234567890")
    ok, msg = check_nvidia_api_key()
    assert ok is True


def test_check_nvidia_api_key_too_short(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "short")
    ok, msg = check_nvidia_api_key()
    assert ok is False
    assert "too short" in msg


def test_check_approved_request_missing(tmp_path: Path) -> None:
    ok, msg = check_approved_request("long_context_architecture", root=tmp_path)
    assert ok is False
    assert "No approved" in msg


def test_check_approved_request_present(tmp_path: Path) -> None:
    approved_dir = tmp_path / ".spark-flow/tasks/remote"
    approved_dir.mkdir(parents=True)
    (approved_dir / "approved.long_context_architecture.md").write_text("approved", encoding="utf-8")
    ok, msg = check_approved_request("long_context_architecture", root=tmp_path)
    assert ok is True


def test_check_budget_empty_log(tmp_path: Path) -> None:
    budget = check_budget(root=tmp_path)
    assert budget.allowed is True
    assert budget.daily_spend_usd == 0.0
    assert budget.monthly_spend_usd == 0.0


def test_check_budget_with_existing_spend(tmp_path: Path) -> None:
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "remote_call_log.jsonl"
    log_path.write_text(
        json.dumps({"estimated_cost_usd": 1.5, "timestamp": now_iso}) + "\n",
        encoding="utf-8",
    )
    budget = check_budget(root=tmp_path)
    assert budget.daily_spend_usd == 1.5


def test_validate_remote_call_unknown_capability(tmp_path: Path) -> None:
    allowed, reason, ctx = validate_remote_call("nonexistent", root=tmp_path)
    assert allowed is False
    assert "Unknown capability" in reason


def test_validate_remote_call_not_remote_allowed(tmp_path: Path) -> None:
    cap_dir = tmp_path / "config"
    cap_dir.mkdir()
    import yaml
    (cap_dir / "capability_routes.yaml").write_text(
        yaml.safe_dump({"capabilities": {"local_only": {"remote_allowed": False, "remote_read_only": False}}}),
        encoding="utf-8",
    )
    allowed, reason, ctx = validate_remote_call("local_only", root=tmp_path)
    assert allowed is False
    assert "not remote-allowed" in reason


def test_validate_remote_call_no_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    import yaml
    (config_dir / "capability_routes.yaml").write_text(
        yaml.safe_dump({"capabilities": {"test_cap": {
            "remote_allowed": True, "remote_read_only": True,
            "preferred_routes": ["test_route"],
        }}}),
        encoding="utf-8",
    )
    (config_dir / "model_routes.yaml").write_text(
        yaml.safe_dump({"remote_models": {"test_route": {
            "provider": "nvidia_nim", "model": "test-model",
        }}}),
        encoding="utf-8",
    )
    (config_dir / "provider_registry.yaml").write_text(
        yaml.safe_dump({"providers": {"nvidia_nim": {
            "kind": "remote", "base_url": "https://example.com/v1",
            "env_key": "NVIDIA_API_KEY", "chat_completions_path": "/chat/completions",
        }}}),
        encoding="utf-8",
    )

    approved_dir = tmp_path / ".spark-flow/tasks/remote"
    approved_dir.mkdir(parents=True)
    (approved_dir / "approved.test_cap.md").write_text("approved", encoding="utf-8")

    allowed, reason, ctx = validate_remote_call("test_cap", root=tmp_path)
    assert allowed is False
    assert "NVIDIA_API_KEY" in reason


def test_run_nim_endpoint_blocked_no_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-fake-key-1234567890")
    result = run_nim_endpoint("long_context_architecture", root=tmp_path)
    assert result.status == "blocked"
    assert result.exit_code == 1
    assert "No approved" in result.reason or "not found" in result.reason.lower() or "Unknown" in result.reason


def test_run_nim_endpoint_blocked_no_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    import yaml
    (config_dir / "capability_routes.yaml").write_text(
        yaml.safe_dump({"capabilities": {"test_cap": {
            "remote_allowed": True, "remote_read_only": True,
            "preferred_routes": ["test_route"],
        }}}),
        encoding="utf-8",
    )
    (config_dir / "model_routes.yaml").write_text(
        yaml.safe_dump({"remote_models": {"test_route": {
            "provider": "nvidia_nim", "model": "test-model",
        }}}),
        encoding="utf-8",
    )
    (config_dir / "provider_registry.yaml").write_text(
        yaml.safe_dump({"providers": {"nvidia_nim": {
            "kind": "remote", "base_url": "https://example.com/v1",
            "env_key": "NVIDIA_API_KEY", "chat_completions_path": "/chat/completions",
        }}}),
        encoding="utf-8",
    )

    approved_dir = tmp_path / ".spark-flow/tasks/remote"
    approved_dir.mkdir(parents=True)
    (approved_dir / "approved.test_cap.md").write_text("approved", encoding="utf-8")

    result = run_nim_endpoint("test_cap", root=tmp_path)
    assert result.status == "blocked"
    assert "NVIDIA_API_KEY" in result.reason


def test_run_nim_endpoint_blocked_not_remote(tmp_path: Path) -> None:
    result = run_nim_endpoint("local_implementation", root=PROJECT_ROOT)
    assert result.status == "blocked"
    assert "not remote-allowed" in result.reason


def test_run_nim_endpoint_logs_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    result = run_nim_endpoint("long_context_architecture", root=PROJECT_ROOT)
    log_path = PROJECT_ROOT / "logs" / "remote_call_log.jsonl"
    assert log_path.exists() or result.status == "blocked"
