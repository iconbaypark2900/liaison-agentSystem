"""Tests for Liaison v0.2.0 safe placeholder worker runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from liaison.worker import (
    REQUIRED_RUN_ARTIFACTS,
    ensure_queue_dirs,
    evaluate_promotion_gate,
    evidence_summary,
    run_once,
    worker_status,
)


def write_task(
    root: Path,
    *,
    filename: str,
    task_id: str,
    project: str = "clinical-suite",
    priority: str = "high",
    created_at: str = "2026-06-10T00:00:00Z",
    task_type: str = "project_audit",
) -> Path:
    path = root / ".liaison" / "tasks" / "backlog" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": task_id,
        "project": project,
        "title": f"Test task for {project}",
        "type": task_type,
        "priority": priority,
        "status": "backlog",
        "created_at": created_at,
        "updated_at": created_at,
        "repo": {"path": f"/tmp/{project}"},
        "routing": {
            "preferred_host": "dgx_spark",
            "model_route": "local_critic",
            "executor": "opencode",
            "fallback_executor": "shell",
        },
        "validation": [
            {
                "name": "unit",
                "command": "python -m pytest",
                "required": True,
            }
        ],
        "forbidden_actions": [
            "push_main",
            "deploy_production",
            "customer_release",
            "live_trade",
            "read_secrets",
            "approve_own_work",
        ],
        "safety": {
            "production_allowed": False,
            "customer_release_allowed": False,
            "live_allowed": False,
            "requires_human_approval": True,
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_task_queue_directories_exist(tmp_path: Path) -> None:
    ensure_queue_dirs(tmp_path)

    for state in [
        "backlog",
        "active",
        "review_required",
        "blocked",
        "failed",
        "done",
        "cancelled",
    ]:
        assert (tmp_path / ".liaison" / "tasks" / state).is_dir()
    assert (tmp_path / ".liaison" / "runs").is_dir()


def test_run_once_selects_one_task_and_creates_run_artifacts(tmp_path: Path) -> None:
    ensure_queue_dirs(tmp_path)
    selected = write_task(
        tmp_path,
        filename="critical-clinical-suite-audit-002.yaml",
        task_id="clinical-suite-audit-002",
        priority="critical",
        created_at="2026-06-10T02:00:00Z",
    )
    write_task(
        tmp_path,
        filename="high-clinical-suite-audit-001.yaml",
        task_id="clinical-suite-audit-001",
        priority="high",
        created_at="2026-06-10T01:00:00Z",
    )
    write_task(
        tmp_path,
        filename="critical-other-project-audit-001.yaml",
        task_id="other-project-audit-001",
        project="other-project",
        priority="critical",
    )

    result = run_once(
        project="clinical-suite",
        root=tmp_path,
        now=datetime(2026, 6, 10, 12, 30, 0, tzinfo=timezone.utc),
    )

    assert result.ran is True
    assert result.task_id == "clinical-suite-audit-002"
    assert result.run_id == "20260610T123000Z-clinical-suite-clinical-suite-audit-002"
    assert result.run_dir is not None
    assert result.run_dir.is_dir()
    assert not selected.exists()

    for artifact in REQUIRED_RUN_ARTIFACTS:
        assert (result.run_dir / artifact).exists()
    assert (result.run_dir / "validation_plan.json").exists()
    assert (result.run_dir / "validation_plan.md").exists()


def test_run_once_moves_task_to_review_required_never_done(tmp_path: Path) -> None:
    ensure_queue_dirs(tmp_path)
    write_task(
        tmp_path,
        filename="high-clinical-suite-audit-001.yaml",
        task_id="clinical-suite-audit-001",
    )

    result = run_once(project="clinical-suite", root=tmp_path)

    assert result.ran is True
    assert result.review_path is not None
    assert result.review_path.exists()
    assert not (
        tmp_path / ".liaison" / "tasks" / "backlog" / "high-clinical-suite-audit-001.yaml"
    ).exists()
    assert not (
        tmp_path / ".liaison" / "tasks" / "active" / "high-clinical-suite-audit-001.yaml"
    ).exists()
    assert not (
        tmp_path / ".liaison" / "tasks" / "done" / "high-clinical-suite-audit-001.yaml"
    ).exists()

    status = worker_status(tmp_path)
    assert status["queues"]["review_required"] == 1
    assert status["queues"]["done"] == 0


def test_promotion_gate_keeps_production_customer_live_false(tmp_path: Path) -> None:
    ensure_queue_dirs(tmp_path)
    write_task(
        tmp_path,
        filename="high-clinical-suite-audit-001.yaml",
        task_id="clinical-suite-audit-001",
    )

    result = run_once(project="clinical-suite", root=tmp_path)
    assert result.run_dir is not None

    gate = json.loads((result.run_dir / "promotion_gate.json").read_text(encoding="utf-8"))
    assert gate["status"] == "review_required"
    assert gate["production_allowed"] is False
    assert gate["customer_release_allowed"] is False
    assert gate["live_allowed"] is False
    assert gate["required_human_approval"] is True
    assert gate["missing_evidence"] == []

    evaluated = evaluate_promotion_gate(result.run_id or "", root=tmp_path)
    assert evaluated["production_allowed"] is False
    assert evaluated["customer_release_allowed"] is False
    assert evaluated["live_allowed"] is False


def test_no_executor_model_or_shell_calls_occur(tmp_path: Path) -> None:
    ensure_queue_dirs(tmp_path)
    write_task(
        tmp_path,
        filename="high-clinical-suite-audit-001.yaml",
        task_id="clinical-suite-audit-001",
    )

    result = run_once(project="clinical-suite", root=tmp_path)
    assert result.run_dir is not None

    metadata = json.loads((result.run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    executor_result = json.loads((result.run_dir / "executor_result.json").read_text(encoding="utf-8"))
    model_line = (result.run_dir / "model_calls.jsonl").read_text(encoding="utf-8").strip()
    model_event = json.loads(model_line)
    command_text = (result.run_dir / "command.txt").read_text(encoding="utf-8")
    validation_plan = json.loads((result.run_dir / "validation_plan.json").read_text(encoding="utf-8"))

    assert metadata["shell_commands_executed"] is False
    assert metadata["models_called"] is False
    assert metadata["executors_called"] is False
    assert metadata["validation_execution_allowed"] is False
    assert metadata["tool_execution"]["executor_invoked"] is False
    assert metadata["tool_execution"]["model_calls_made"] is False
    assert metadata["tool_execution"]["shell_commands_run"] is False
    assert metadata["tool_execution"]["validation_commands_run"] is False
    assert metadata["tool_execution"]["opencode_invoked"] is False
    assert metadata["tool_execution"]["codex_invoked"] is False
    assert metadata["tool_execution"]["claude_code_invoked"] is False
    assert metadata["tool_execution"]["litellm_invoked"] is False
    assert metadata["tool_execution"]["ollama_invoked"] is False
    assert executor_result["executed"] is False
    assert executor_result["shell_commands_run"] == []
    assert model_event["model_calls_made"] is False
    assert "placeholder mode: no commands executed" in command_text
    assert validation_plan["shell_commands_executed"] is False
    assert validation_plan["validation_execution_allowed"] is False
    assert validation_plan["commands"][0]["status"] == "planned"
    assert validation_plan["commands"][0]["execution_allowed"] is False


def test_evidence_show_reports_all_required_artifacts(tmp_path: Path) -> None:
    ensure_queue_dirs(tmp_path)
    write_task(
        tmp_path,
        filename="high-clinical-suite-audit-001.yaml",
        task_id="clinical-suite-audit-001",
    )

    result = run_once(project="clinical-suite", root=tmp_path)
    summary = evidence_summary(result.run_id or "", root=tmp_path)

    assert summary["exists"] is True
    assert summary["missing_evidence"] == []
    assert {artifact["name"] for artifact in summary["artifacts"]} == {
        *REQUIRED_RUN_ARTIFACTS,
        "validation_plan.json",
        "validation_plan.md",
    }
