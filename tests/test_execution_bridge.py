#!/usr/bin/env python3
"""Execution bridge — task-scoped outcome recording."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.execution_bridge import (  # noqa: E402
    infer_outcome,
    record_executor_outcome,
    task_dir_for,
)


def test_infer_outcome():
    assert infer_outcome(0, None) == "success"
    assert infer_outcome(1, None) == "failure"
    assert infer_outcome(None, "failure") == "failure"


def test_record_failure_writes_artifacts(tmp_path):
    repo = tmp_path / "proj"
    task_id = "bridge-test-1"
    td = task_dir_for(repo, task_id)
    td.mkdir(parents=True)
    (td / "BRIEF.md").write_text("# brief\n", encoding="utf-8")

    result = record_executor_outcome(
        repo,
        task_id,
        agent="hermes",
        exit_code=1,
        excerpt="smoke failure excerpt",
        project_key="testproj",
    )
    assert result["outcome"] == "failure"
    assert result["wrote_evaluation"] is True
    assert result["wrote_learning"] is True
    assert (td / "OBSERVATIONS.md").exists()
    assert (td / "EVALUATIONS.md").read_text().lower().count("fail") >= 1
    assert (td / "LEARNINGS.md").exists()
    events = [json.loads(ln) for ln in (td / "events.jsonl").read_text().splitlines() if ln.strip()]
    assert any(e.get("event") == "executor_session_end" for e in events)


def test_record_success_no_eval(tmp_path):
    repo = tmp_path / "proj2"
    task_id = "bridge-test-2"
    td = task_dir_for(repo, task_id)
    td.mkdir(parents=True)
    (td / "BRIEF.md").write_text("# brief\n", encoding="utf-8")

    result = record_executor_outcome(
        repo,
        task_id,
        agent="hermes",
        exit_code=0,
        excerpt="ok",
    )
    assert result["outcome"] == "success"
    assert result["wrote_evaluation"] is False
    assert (td / "OBSERVATIONS.md").exists()


def test_attach_text_to_outbox(tmp_path):
    from dashboard.command_center.execution_bridge import attach_report_to_outbox

    repo = tmp_path / "proj3"
    task_id = "bridge-test-3"
    td = task_dir_for(repo, task_id)
    td.mkdir(parents=True)

    result = attach_report_to_outbox(
        repo,
        task_id,
        agent="hermes",
        text="report body",
        title="Smoke report",
    )
    artifact = Path(result["artifact"])
    assert artifact.exists()
    assert "report body" in artifact.read_text(encoding="utf-8")
    events = [json.loads(ln) for ln in (td / "events.jsonl").read_text().splitlines() if ln.strip()]
    assert any(e.get("event") == "attach" for e in events)


def test_detect_stale_session_hours(tmp_path, monkeypatch):
    from dashboard.command_center.execution_bridge import detect_stale_executor_sessions

    repo = tmp_path / "sigma"
    task_id = "stale-task"
    td = task_dir_for(repo, task_id)
    td.mkdir(parents=True)

    monkeypatch.setenv("LIAISON_TERMINAL_SESSIONS", str(tmp_path / "sessions.json"))
    sessions = [
        {
            "id": "s1",
            "status": "running",
            "task_id": task_id,
            "project_key": "",
            "repo_path": str(repo),
            "started_at": "2000-01-01T00:00:00",
            "alive": True,
            "pid": 12345,
        }
    ]
    stale = detect_stale_executor_sessions(sessions, stale_hours=1)
    assert len(stale) == 1
    assert stale[0]["stale_reason"].startswith("running>")


if __name__ == "__main__":
    test_infer_outcome()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_record_failure_writes_artifacts(Path(tmp))
        test_record_success_no_eval(Path(tmp))
        test_attach_text_to_outbox(Path(tmp))
    print("ok")
