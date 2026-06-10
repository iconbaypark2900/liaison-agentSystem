#!/usr/bin/env python3
"""Terminal session venture binding."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_register_and_complete(tmp_path, monkeypatch):
    monkeypatch.setenv("LIAISON_TERMINAL_SESSIONS", str(tmp_path / "sessions.json"))

    from dashboard.command_center.terminal_sessions import (
        complete_session,
        list_sessions,
        register_session,
    )

    repo = tmp_path / "repo"
    task_id = "sess-test-1"
    td = repo / ".spark-flow" / "tasks" / task_id
    td.mkdir(parents=True)
    (td / "BRIEF.md").write_text("# b\n", encoding="utf-8")

    entry = register_session(
        agent_name="hermes",
        launch="echo test",
        project_key="testproj",
        repo_path=str(repo),
        task_id=task_id,
    )
    assert entry["project_key"] == "testproj"
    assert entry["task_id"] == task_id
    assert entry["status"] == "running"

    result = complete_session(
        session_id=entry["id"],
        exit_code=1,
        log_excerpt="failed smoke",
    )
    assert result["outcome"] == "failure"
    assert (td / "OBSERVATIONS.md").exists()

    ended = [s for s in list_sessions() if s.get("id") == entry["id"]]
    assert ended and ended[0]["status"] == "ended"


if __name__ == "__main__":
    import tempfile

    class Monkey:
        @staticmethod
        def setenv(k, v):
            os.environ[k] = v

    with tempfile.TemporaryDirectory() as tmp:
        test_register_and_complete(Path(tmp), Monkey())
    print("ok")
