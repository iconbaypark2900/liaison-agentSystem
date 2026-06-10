#!/usr/bin/env python3
"""Tests for project intake readiness."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.project_intake import (  # noqa: E402
    build_project_intake,
    format_intake_report,
    write_intake_report,
)


def _minimal_repo(tmp_path: Path) -> Path:
    mem = tmp_path / ".spark-flow" / "memory"
    mem.mkdir(parents=True)
    (mem / "project_brief.md").write_text(
        "# Project brief\n\n## Purpose\n\nBuild a real widget API for operators.\n\n"
        "## Non-goals\n\nNo multi-tenant billing in v1.\n",
        encoding="utf-8",
    )
    (mem / "current_state.md").write_text(
        "# Current state\n\n## Built\n\n- CLI skeleton\n\n## Next\n\n- Wire intake\n",
        encoding="utf-8",
    )
    (mem / "decisions.md").write_text(
        "# Decisions\n\n- 2026-05-01: Use file-backed intake first.\n",
        encoding="utf-8",
    )
    (mem / "ASSESSMENT.md").write_text("# Project assessment\n\nRecommended: prototype\n", encoding="utf-8")
    (mem / "project_phase.json").write_text(
        '{"phase": "prototype", "lifecycle_status": "classified"}\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 't'\n", encoding="utf-8")
    return tmp_path


def test_intake_ready_with_minimal_repo(tmp_path):
    repo = _minimal_repo(tmp_path)
    intake = build_project_intake("test-proj", str(repo), open_tasks=[])
    assert intake["intake_ready"] is True
    assert intake["recommended_lane"] in ("execute", "scaffold", "classify", "research")
    assert any(c["id"] == "project_brief" and c["pass"] for c in intake["checks"])


def test_intake_blocked_without_brief(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".spark-flow" / "memory").mkdir(parents=True)
    intake = build_project_intake("empty", str(repo), [])
    assert intake["intake_ready"] is False
    assert intake["ready_to_build"] is False
    assert any(b["id"] == "project_brief" for b in intake["blockers"])


def test_task_hygiene_blocks(tmp_path):
    repo = _minimal_repo(tmp_path)
    tasks = repo / ".spark-flow" / "tasks" / "t1"
    tasks.mkdir(parents=True)
    (tasks / "STATE.txt").write_text("CURRENT_PHASE: plan\n", encoding="utf-8")
    intake = build_project_intake(
        "test-proj",
        str(repo),
        open_tasks=[{"task_id": "t1", "path": str(tasks), "closed": False}],
    )
    assert intake["intake_ready"] is False
    assert any(c["id"] == "task_hygiene" and not c["pass"] for c in intake["checks"])


def test_soft_ready_with_warnings_only(tmp_path):
    repo = _minimal_repo(tmp_path)
    intake = build_project_intake("test-proj", str(repo), open_tasks=[])
    assert intake["intake_ready"] is True
    assert intake["ready_to_build_strict"] is True
    assert intake["ready_to_build_soft"] is True


def test_soft_ready_without_full_strict(tmp_path):
    repo = _minimal_repo(tmp_path)
    mem = repo / ".spark-flow" / "memory"
    (mem / "project_phase.json").write_text(
        '{"phase": "unassessed", "lifecycle_status": "registered"}\n',
        encoding="utf-8",
    )
    (mem / "ASSESSMENT.md").unlink(missing_ok=True)
    intake = build_project_intake("test-proj", str(repo), open_tasks=[])
    assert intake["intake_ready"] is True
    assert intake["ready_to_build_strict"] is False
    assert intake["ready_to_build_soft"] is True


def test_write_intake_report(tmp_path):
    repo = _minimal_repo(tmp_path)
    intake = build_project_intake("test-proj", str(repo), [])
    path = write_intake_report(str(repo), intake)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "intake" in text.lower()
    assert format_intake_report(intake) in text or "Intake ready" in text


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        test_intake_ready_with_minimal_repo(p / "a")
        test_intake_blocked_without_brief(p / "b")
        test_task_hygiene_blocks(p / "c")
        test_soft_ready_with_warnings_only(p / "e")
        test_soft_ready_without_full_strict(p / "f")
        test_write_intake_report(p / "d")
    print("ok")
