"""Tests for Phase 11 dashboard panel data helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard.command_center.panels import (
    build_all_panels,
    build_approvals_panel,
    build_budgets_panel,
    build_context_bundles_panel,
    build_logs_panel,
    build_routing_panel,
    build_tasks_panel,
    build_validation_panel,
)


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_build_tasks_panel_empty_state() -> None:
    data = build_tasks_panel(state={})
    assert data["total"] == 0
    assert data["open"] == 0
    assert data["closed"] == 0
    assert data["buckets"] == {"todo": 0, "in_progress": 0, "review": 0, "done": 0}
    assert data["by_project"] == {}
    assert data["recent"] == []


def test_build_tasks_panel_with_tasks() -> None:
    state = {
        "tasks": [
            {
                "task_id": "t1",
                "title": "Task 1",
                "priority": "high",
                "status": "backlog",
                "type": "audit",
                "repo": {"name": "alpha", "path": "/tmp/alpha"},
                "closed": False,
            },
            {
                "task_id": "t2",
                "title": "Task 2",
                "priority": "low",
                "status": "done",
                "type": "release",
                "repo": {"name": "beta", "path": "/tmp/beta"},
                "closed": True,
            },
        ],
        "open_tasks": [{"task_id": "t1"}],
        "kanban": {
            "todo": [{"task_id": "t1"}],
            "in_progress": [],
            "review": [],
            "done": [{"task_id": "t2"}],
        },
    }
    data = build_tasks_panel(state=state)
    assert data["total"] == 2
    assert data["open"] == 1
    assert data["closed"] == 1
    assert data["buckets"]["todo"] == 1
    assert data["buckets"]["done"] == 1
    assert data["by_project"]["alpha"] == 1
    assert data["by_project"]["beta"] == 1
    assert data["by_priority"]["high"] == 1
    assert data["by_priority"]["low"] == 1
    assert data["by_type"]["audit"] == 1
    assert len(data["recent"]) == 2


def test_build_approvals_panel_splits_by_status() -> None:
    state = {
        "handoffs": [
            {
                "task_id": "t1",
                "from_agent": "a",
                "to_agent": "b",
                "status": "pending_approval",
                "summary": "s1",
            },
            {
                "task_id": "t2",
                "from_agent": "c",
                "to_agent": "d",
                "status": "approved",
                "summary": "s2",
            },
            {
                "task_id": "t3",
                "from_agent": "e",
                "to_agent": "f",
                "status": "rejected",
                "summary": "s3",
            },
        ]
    }
    data = build_approvals_panel(state=state)
    assert data["total"] == 3
    assert data["pending"] == 1
    assert data["approved"] == 1
    assert data["rejected"] == 1
    assert len(data["rows"]) == 3
    assert data["rows"][0]["task_id"] == "t1"


def test_build_approvals_panel_empty() -> None:
    data = build_approvals_panel(state={})
    assert data["total"] == 0
    assert data["pending"] == 0
    assert data["rows"] == []


def test_build_validation_panel_reads_profiles(tmp_path: Path) -> None:
    config = tmp_path / "config"
    _write_yaml(
        config / "validation_profiles.yaml",
        {
            "profiles": {
                "python": {"checks_script": "checks/python.sh"},
                "rag": {"checks_script": "checks/rag.sh"},
            }
        },
    )
    _write_yaml(
        tmp_path / "registry" / "project_plans.yaml",
        {
            "projects": {
                "alpha": {"validation_profile": "python"},
                "beta": {"validation_profile": "rag"},
                "gamma": {"validation_profile": "python"},
            }
        },
    )
    data = build_validation_panel(state={}, root=tmp_path)
    assert sorted(data["profiles_defined"]) == ["python", "rag"]
    assert data["profile_count"] == 2
    assert data["profile_usage"]["python"] == 2
    assert data["profile_usage"]["rag"] == 1
    assert data["profile_check_scripts"]["python"] == "checks/python.sh"


def test_build_routing_panel(tmp_path: Path) -> None:
    config = tmp_path / "config"
    _write_yaml(
        config / "model_routes.yaml",
        {
            "routes": {
                "fast": {"provider": "ollama", "model": "llama3", "capabilities": ["fast"]},
                "smart": {"provider": "anthropic", "model": "claude", "capabilities": ["smart"]},
            }
        },
    )
    _write_yaml(
        config / "executors.yaml",
        {
            "executors": {
                "shell": {"type": "shell", "command": "bash", "enabled": True, "allow_execution": True},
                "opencode": {"type": "opencode", "command": "opencode", "enabled": True, "allow_execution": False},
            }
        },
    )
    _write_yaml(
        tmp_path / "registry" / "phase_routing.yaml",
        {
            "phases": {
                "plan": {"preferred_agent": "claude", "fallback_agent": "opencode", "validation": "optional"},
                "build": {"preferred_agent": "opencode", "validation": "required"},
            }
        },
    )
    data = build_routing_panel(state={}, root=tmp_path)
    assert len(data["model_routes"]) == 2
    assert data["model_routes"][0]["name"] in ("fast", "smart")
    assert len(data["executor_routes"]) == 2
    shell_route = next(r for r in data["executor_routes"] if r["name"] == "shell")
    assert shell_route["allow_execution"] is True
    assert len(data["phases"]) == 2


def test_build_context_bundles_panel_empty(tmp_path: Path) -> None:
    data = build_context_bundles_panel(state={}, root=tmp_path)
    assert data["count"] == 0
    assert data["bundles"] == []


def test_build_context_bundles_panel_with_active(tmp_path: Path) -> None:
    state = {"project_intake": {"bundle_id": "abc-123", "bundle_path": "/tmp/bundle"}}
    data = build_context_bundles_panel(state=state, root=tmp_path)
    assert data["count"] == 1
    assert data["bundles"][0]["name"] == "abc-123"
    assert data["bundles"][0]["kind"] == "active"


def test_build_logs_panel_with_runs(tmp_path: Path) -> None:
    runs = tmp_path / ".liaison" / "runs" / "20260101T000000Z-test-test"
    runs.mkdir(parents=True)
    (runs / "stdout.log").write_text("hello world\n", encoding="utf-8")
    (runs / "validation.log").write_text("passed\n", encoding="utf-8")
    data = build_logs_panel(state={}, root=tmp_path)
    assert data["count"] == 2
    log_names = {r["log"] for r in data["rows"]}
    assert log_names == {"stdout.log", "validation.log"}


def test_build_logs_panel_empty(tmp_path: Path) -> None:
    data = build_logs_panel(state={}, root=tmp_path)
    assert data["count"] == 0
    assert data["rows"] == []


def test_build_budgets_panel_reads_limits(tmp_path: Path) -> None:
    config = tmp_path / "config"
    _write_yaml(
        config / "budgets.yaml",
        {
            "budgets": {
                "fast": {"per_run": 100, "per_day": 1000, "currency": "usd"},
            }
        },
    )
    data = build_budgets_panel(state={}, root=tmp_path)
    assert data["limits_count"] == 1
    assert data["limits"][0]["name"] == "fast"
    assert data["limits"][0]["per_run"] == 100
    assert data["limits"][0]["per_day"] == 1000


def test_build_budgets_panel_with_recent_runs(tmp_path: Path) -> None:
    runs = tmp_path / ".liaison" / "runs" / "20260101T000000Z-test-test"
    runs.mkdir(parents=True)
    (runs / "run_metadata.json").write_text(
        json.dumps(
            {
                "task_id": "t1",
                "tool_execution": {
                    "shell_commands_run": True,
                    "model_calls_made": False,
                    "executor_invoked": True,
                },
            }
        ),
        encoding="utf-8",
    )
    data = build_budgets_panel(state={}, root=tmp_path)
    assert len(data["recent_runs"]) == 1
    assert data["recent_runs"][0]["task_id"] == "t1"
    assert data["recent_runs"][0]["shell_commands_executed"] is True
    assert data["recent_runs"][0]["executors_called"] is True


def test_build_all_panels_returns_all_keys() -> None:
    data = build_all_panels(state={}, root=None)
    assert set(data.keys()) == {
        "tasks",
        "approvals",
        "validation",
        "routing",
        "context_bundles",
        "logs",
        "budgets",
    }


def test_panel_helpers_are_pure() -> None:
    state = {"tasks": [], "handoffs": [], "kanban": {"todo": [], "in_progress": [], "review": [], "done": []}}
    out1 = build_all_panels(state=state, root=None)
    out2 = build_all_panels(state=state, root=None)
    assert out1 == out2
