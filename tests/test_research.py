"""Tests for Phase 9 ML-Intern sandbox execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from liaison.research import (
    ResearchExecutionError,
    ResearchRunResult,
    check_executor_available,
    check_sandbox_safety,
    load_research_workers,
    resolve_research_worker,
    run_research_worker,
)


PROJECT_ROOT = Path(__file__).parent.parent


def test_load_research_workers() -> None:
    workers = load_research_workers(PROJECT_ROOT)
    assert "research_workers" in workers
    assert "ml_intern" in workers["research_workers"]
    ml = workers["research_workers"]["ml_intern"]
    assert ml["sandbox_only"] is True
    assert "publish_without_approval" in ml["forbidden"]


def test_resolve_research_worker_existing() -> None:
    config = resolve_research_worker("ml_intern", PROJECT_ROOT)
    assert config["sandbox_only"] is True
    assert "forbidden" in config


def test_resolve_research_worker_missing() -> None:
    config = resolve_research_worker("nonexistent", PROJECT_ROOT)
    assert config == {}


def test_check_sandbox_safety_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ML_INTERN_ALLOW_PUBLISH", raising=False)
    monkeypatch.delenv("ML_INTERN_ALLOW_PRIVATE_UPLOAD", raising=False)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "research_workers.yaml").write_text(
        yaml.safe_dump({"research_workers": {"ml_intern": {
            "sandbox_only": True,
            "forbidden": ["publish_without_approval", "upload_private_data"],
        }}}),
        encoding="utf-8",
    )
    ok, reason, checked = check_sandbox_safety("ml_intern", root=tmp_path)
    assert ok is True
    assert "publish_without_approval" in checked
    assert "upload_private_data" in checked


def test_check_sandbox_safety_publish_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ML_INTERN_ALLOW_PUBLISH", "true")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "research_workers.yaml").write_text(
        yaml.safe_dump({"research_workers": {"ml_intern": {
            "sandbox_only": True,
            "forbidden": ["publish_without_approval"],
        }}}),
        encoding="utf-8",
    )
    ok, reason, checked = check_sandbox_safety("ml_intern", root=tmp_path)
    assert ok is False
    assert "publish_without_approval" in reason


def test_check_sandbox_safety_upload_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ML_INTERN_ALLOW_PRIVATE_UPLOAD", "1")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "research_workers.yaml").write_text(
        yaml.safe_dump({"research_workers": {"ml_intern": {
            "sandbox_only": True,
            "forbidden": ["upload_private_data"],
        }}}),
        encoding="utf-8",
    )
    ok, reason, checked = check_sandbox_safety("ml_intern", root=tmp_path)
    assert ok is False
    assert "upload_private_data" in reason


def test_check_sandbox_safety_not_sandbox(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "research_workers.yaml").write_text(
        yaml.safe_dump({"research_workers": {"unsafe_worker": {
            "sandbox_only": False,
            "forbidden": [],
        }}}),
        encoding="utf-8",
    )
    ok, reason, checked = check_sandbox_safety("unsafe_worker", root=tmp_path)
    assert ok is False
    assert "sandbox_only" in reason


def test_check_sandbox_safety_unknown_worker(tmp_path: Path) -> None:
    ok, reason, checked = check_sandbox_safety("nonexistent", root=tmp_path)
    assert ok is False
    assert "Unknown" in reason


def test_check_executor_available_disabled(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "executors.yaml").write_text(
        yaml.safe_dump({"executors": {"ml_intern": {
            "enabled": False, "command": "ml-intern",
        }}}),
        encoding="utf-8",
    )
    ok, reason = check_executor_available("ml_intern", root=tmp_path)
    assert ok is False
    assert "disabled" in reason


def test_check_executor_available_not_in_path(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "executors.yaml").write_text(
        yaml.safe_dump({"executors": {"ml_intern": {
            "enabled": True, "command": "ml-intern-nonexistent-binary",
        }}}),
        encoding="utf-8",
    )
    ok, reason = check_executor_available("ml_intern", root=tmp_path)
    assert ok is False
    assert "not found" in reason.lower() or "PATH" in reason


def test_run_research_worker_blocked_unknown(tmp_path: Path) -> None:
    result = run_research_worker("nonexistent", root=tmp_path)
    assert result.status == "blocked"
    assert result.sandbox_enforced is True
    assert "Unknown" in result.reason


def test_run_research_worker_blocked_executor_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ML_INTERN_ALLOW_PUBLISH", raising=False)
    monkeypatch.delenv("ML_INTERN_ALLOW_PRIVATE_UPLOAD", raising=False)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "research_workers.yaml").write_text(
        yaml.safe_dump({"research_workers": {"ml_intern": {
            "sandbox_only": True,
            "forbidden": ["publish_without_approval"],
        }}}),
        encoding="utf-8",
    )
    (config_dir / "executors.yaml").write_text(
        yaml.safe_dump({"executors": {"ml_intern": {
            "enabled": False, "command": "ml-intern",
        }}}),
        encoding="utf-8",
    )
    result = run_research_worker("ml_intern", root=tmp_path)
    assert result.status == "blocked"
    assert "disabled" in result.reason
    assert result.sandbox_enforced is True


def test_run_research_worker_logs_blocked(tmp_path: Path) -> None:
    result = run_research_worker("nonexistent", root=tmp_path)
    log_path = tmp_path / "logs" / "ml_intern_runs.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert entry["status"] == "blocked"
    assert entry["worker_name"] == "nonexistent"


def test_research_result_to_json() -> None:
    result = ResearchRunResult(
        worker_name="ml_intern",
        status="success",
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_sec=1.5,
        output_path="/tmp/out.md",
        log_path="/tmp/log.jsonl",
        sandbox_enforced=True,
        forbidden_checked=["publish_without_approval"],
        reason="done",
    )
    j = result.to_json()
    assert j["worker_name"] == "ml_intern"
    assert j["sandbox_enforced"] is True
    assert j["status"] == "success"
