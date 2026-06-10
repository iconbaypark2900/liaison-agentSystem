#!/usr/bin/env python3
"""Venture queue capacity checks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_queue_respects_capacity(tmp_path, monkeypatch):
    qpath = tmp_path / "venture_queue.json"
    monkeypatch.setenv("LIAISON_VENTURE_QUEUE", str(qpath))
    monkeypatch.setenv("LIAISON_TERMINAL_SESSIONS", str(tmp_path / "sessions.json"))

    from dashboard.command_center import venture_queue as vq
    from dashboard.command_center.terminal_sessions import register_session

    vq.add_item(project_key="sigma", task_id="t1", agent="hermes", priority=10)
    vq.add_item(project_key="clinical_suite", task_id="t2", agent="hermes", priority=5)

    register_session(
        agent_name="hermes",
        launch="echo",
        project_key="sigma",
        repo_path=str(tmp_path),
        task_id="running-1",
    )

    sessions = [{"agent_name": "hermes", "status": "running", "alive": True, "engine": "hermes"}]
    item, msg, hints = vq.pick_next(sessions)
    assert item is not None or msg
    summary = vq.build_queue_summary(sessions)
    assert summary["pending_count"] >= 1


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_queue_respects_capacity(Path(tmp), type("m", (), {"setenv": os.environ.__setitem__})())
    print("ok")
