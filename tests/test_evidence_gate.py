"""Evidence and promotion-gate command tests for Liaison v0.2.0."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from liaison.portfolio import main
from liaison.worker import REQUIRED_RUN_ARTIFACTS, ensure_queue_dirs, run_once


def write_task(root: Path) -> None:
    path = root / ".liaison" / "tasks" / "backlog" / "high-clinical-suite-audit-001.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "clinical-suite-audit-001",
        "project": "clinical-suite",
        "title": "Test task for clinical-suite",
        "type": "project_audit",
        "priority": "high",
        "status": "backlog",
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:00Z",
        "repo": {"path": "/tmp/clinical-suite"},
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
        "safety": {
            "production_allowed": False,
            "customer_release_allowed": False,
            "live_allowed": False,
            "requires_human_approval": True,
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def create_run(tmp_path: Path, monkeypatch) -> tuple[str, Path]:
    monkeypatch.chdir(tmp_path)
    ensure_queue_dirs()
    write_task(tmp_path)
    result = run_once(project="clinical-suite")
    assert result.run_id is not None
    assert result.run_dir is not None
    return result.run_id, result.run_dir


def write_calibration_task(root: Path) -> None:
    path = root / ".liaison" / "tasks" / "backlog" / "critical-sigma-calibration-gate-001.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "sigma-calibration-gate-001",
        "project": "sigma",
        "title": "Confidence calibration gate for sigma",
        "type": "calibration",
        "priority": "critical",
        "status": "backlog",
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:00Z",
        "repo": {"path": "/tmp/sigma"},
        "routing": {
            "preferred_host": "dgx_spark",
            "model_route": "local_critic",
            "executor": "opencode",
            "fallback_executor": "shell",
        },
        "required_artifacts": [
            "task.yaml",
            "context.md",
            "command.txt",
            "stdout.log",
            "stderr.log",
            "patch.diff",
            "validation.log",
            "security.log",
            "data_quality.log",
            "compliance.md",
            "debrief.md",
            "promotion_gate.json",
            "run_metadata.json",
        ],
        "calibration_required_artifacts": [
            "fabricated_edge_scan.json",
            "reliability_report.json",
            "confidence_calibration_gate.json",
        ],
        "safety": {
            "production_allowed": False,
            "customer_release_allowed": False,
            "live_allowed": False,
            "requires_human_approval": True,
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def create_calibration_run(tmp_path: Path, monkeypatch) -> tuple[str, Path]:
    monkeypatch.chdir(tmp_path)
    ensure_queue_dirs()
    write_calibration_task(tmp_path)
    result = run_once(project="sigma")
    assert result.run_id is not None
    assert result.run_dir is not None
    return result.run_id, result.run_dir


def test_evidence_show_human_output(tmp_path: Path, monkeypatch, capsys) -> None:
    run_id, _ = create_run(tmp_path, monkeypatch)

    rc = main(["evidence", "show", run_id])

    output = capsys.readouterr().out
    assert rc == 0
    assert f"Evidence for {run_id}" in output
    assert "task_id: clinical-suite-audit-001" in output
    assert "project: clinical-suite" in output
    assert "status: review_required" in output
    assert "artifact_dir: .liaison/runs/" in output
    assert "present: task.yaml" in output
    assert "not_applicable: patch.diff" in output
    assert "production_allowed: false" in output
    assert "customer_release_allowed: false" in output
    assert "live_allowed: false" in output
    assert "production/customer/live approval: false" in output


def test_evidence_show_json_output(tmp_path: Path, monkeypatch, capsys) -> None:
    run_id, _ = create_run(tmp_path, monkeypatch)

    rc = main(["evidence", "show", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    statuses = {artifact["name"]: artifact["status"] for artifact in payload["artifacts"]}
    assert rc == 0
    assert payload["run_id"] == run_id
    assert payload["task_id"] == "clinical-suite-audit-001"
    assert payload["project"] == "clinical-suite"
    assert payload["status"] == "review_required"
    assert payload["missing_evidence"] == []
    assert statuses["task.yaml"] == "present"
    assert statuses["patch.diff"] == "not_applicable"
    assert payload["promotion_gate_summary"]["production_allowed"] is False
    assert payload["promotion_gate_summary"]["customer_release_allowed"] is False
    assert payload["promotion_gate_summary"]["live_allowed"] is False


def test_gate_evaluate_complete_evidence(tmp_path: Path, monkeypatch, capsys) -> None:
    run_id, run_dir = create_run(tmp_path, monkeypatch)

    rc = main(["gate", "evaluate", run_id])

    output = capsys.readouterr().out
    gate = json.loads((run_dir / "promotion_gate.json").read_text(encoding="utf-8"))
    assert rc == 0
    assert f"Gate for {run_id}: review_required" in output
    assert "missing_evidence: 0" in output
    assert gate["status"] == "review_required"
    assert gate["missing_evidence"] == []
    assert gate["production_allowed"] is False
    assert gate["customer_release_allowed"] is False
    assert gate["live_allowed"] is False


def test_gate_evaluate_missing_evidence_blocks(tmp_path: Path, monkeypatch, capsys) -> None:
    run_id, run_dir = create_run(tmp_path, monkeypatch)
    (run_dir / "stdout.log").unlink()

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    gate = json.loads((run_dir / "promotion_gate.json").read_text(encoding="utf-8"))
    assert rc == 1
    assert payload["status"] == "blocked"
    assert "stdout.log" in payload["missing_evidence"]
    assert gate["status"] == "blocked"
    assert "stdout.log" in gate["missing_evidence"]
    assert gate["production_allowed"] is False
    assert gate["customer_release_allowed"] is False
    assert gate["live_allowed"] is False


def test_gate_evaluate_never_sets_production_customer_live_true(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, run_dir = create_run(tmp_path, monkeypatch)
    gate_path = run_dir / "promotion_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["production_allowed"] = True
    gate["customer_release_allowed"] = True
    gate["live_allowed"] = True
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    saved = json.loads(gate_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["production_allowed"] is False
    assert payload["customer_release_allowed"] is False
    assert payload["live_allowed"] is False
    assert saved["production_allowed"] is False
    assert saved["customer_release_allowed"] is False
    assert saved["live_allowed"] is False


def test_gate_evaluate_preserves_human_approval_requirement(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, run_dir = create_run(tmp_path, monkeypatch)
    gate_path = run_dir / "promotion_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["required_human_approval"] = False
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    saved = json.loads(gate_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["required_human_approval"] is True
    assert saved["required_human_approval"] is True

def test_calibration_task_creates_fabricated_edge_scan_json(tmp_path: Path, monkeypatch) -> None:
    _, run_dir = create_calibration_run(tmp_path, monkeypatch)

    payload = json.loads((run_dir / "fabricated_edge_scan.json").read_text(encoding="utf-8"))

    assert payload["status"] == "not_run"
    assert payload["fabricated_edge_scan_run"] is False
    assert payload["production_allowed"] is False
    assert payload["live_allowed"] is False


def test_calibration_task_creates_reliability_report_json(tmp_path: Path, monkeypatch) -> None:
    _, run_dir = create_calibration_run(tmp_path, monkeypatch)

    payload = json.loads((run_dir / "reliability_report.json").read_text(encoding="utf-8"))

    assert payload["status"] == "not_run"
    assert payload["reliability_analysis_run"] is False
    assert payload["shell_commands_run"] is False


def test_calibration_task_creates_confidence_calibration_gate_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, run_dir = create_calibration_run(tmp_path, monkeypatch)

    payload = json.loads((run_dir / "confidence_calibration_gate.json").read_text(encoding="utf-8"))

    assert payload["status"] in {"blocked", "review_required"}
    assert payload["confidence_calibration_passed"] is False
    assert payload["requires_human_approval"] is True


def test_gate_blocks_if_calibration_required_artifacts_are_missing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, run_dir = create_calibration_run(tmp_path, monkeypatch)
    (run_dir / "reliability_report.json").unlink()

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    gate = json.loads((run_dir / "promotion_gate.json").read_text(encoding="utf-8"))
    assert rc == 1
    assert payload["status"] == "blocked"
    assert "reliability_report.json" in payload["missing_evidence"]
    assert gate["production_allowed"] is False
    assert gate["customer_release_allowed"] is False
    assert gate["live_allowed"] is False
    assert gate["required_human_approval"] is True


def test_evidence_show_includes_calibration_required_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, _ = create_calibration_run(tmp_path, monkeypatch)

    rc = main(["evidence", "show", run_id])

    output = capsys.readouterr().out
    assert rc == 0
    assert "task_specific_artifacts:" in output
    assert "calibration_required_artifacts:" in output
    assert "fabricated_edge_scan.json" in output
    assert "reliability_report.json" in output
    assert "confidence_calibration_gate.json" in output


def test_generic_audit_task_uses_normal_required_artifacts_only(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, _ = create_run(tmp_path, monkeypatch)

    rc = main(["evidence", "show", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["task_specific_artifacts"] == []
    assert payload["task_specific_artifact_groups"] == []
    assert {artifact["name"] for artifact in payload["artifacts"]} == set(REQUIRED_RUN_ARTIFACTS)
    assert payload["missing_evidence"] == []

def test_confidence_calibration_gate_blocked_blocks_promotion(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, run_dir = create_calibration_run(tmp_path, monkeypatch)

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    gate = json.loads((run_dir / "promotion_gate.json").read_text(encoding="utf-8"))
    assert rc == 1
    assert payload["status"] == "blocked"
    assert gate["status"] == "blocked"
    assert any("confidence_calibration_gate.json" in check for check in payload["failed_checks"])
    assert payload["missing_evidence"] == []


def test_task_specific_artifact_failed_blocks_promotion(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, run_dir = create_calibration_run(tmp_path, monkeypatch)
    reliability_path = run_dir / "reliability_report.json"
    reliability = json.loads(reliability_path.read_text(encoding="utf-8"))
    reliability["status"] = "failed"
    reliability_path.write_text(json.dumps(reliability), encoding="utf-8")
    confidence_path = run_dir / "confidence_calibration_gate.json"
    confidence = json.loads(confidence_path.read_text(encoding="utf-8"))
    confidence["status"] = "review_required"
    confidence_path.write_text(json.dumps(confidence), encoding="utf-8")

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["status"] == "blocked"
    assert any("reliability_report.json" in check for check in payload["failed_checks"])
    assert payload["production_allowed"] is False
    assert payload["customer_release_allowed"] is False
    assert payload["live_allowed"] is False


def test_task_specific_artifact_not_run_does_not_pass_promotion(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, run_dir = create_calibration_run(tmp_path, monkeypatch)
    confidence_path = run_dir / "confidence_calibration_gate.json"
    confidence = json.loads(confidence_path.read_text(encoding="utf-8"))
    confidence["status"] = "review_required"
    confidence_path.write_text(json.dumps(confidence), encoding="utf-8")

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "review_required"
    assert payload["status"] != "passed"
    assert any(
        finding["artifact"] == "fabricated_edge_scan.json" and finding["status"] == "not_run"
        for finding in payload["task_specific_artifact_findings"]
    )


def test_complete_audit_task_can_remain_review_required(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, _ = create_run(tmp_path, monkeypatch)

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "review_required"
    assert payload["task_specific_artifact_findings"] == []


def test_blocking_artifact_preserves_safety_and_human_approval(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id, _ = create_calibration_run(tmp_path, monkeypatch)

    rc = main(["gate", "evaluate", run_id, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["production_allowed"] is False
    assert payload["customer_release_allowed"] is False
    assert payload["live_allowed"] is False
    assert payload["required_human_approval"] is True

