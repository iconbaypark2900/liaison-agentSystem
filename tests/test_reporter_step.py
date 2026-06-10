"""Reporter step machine — CLI state file and merge with probe_reporter_steps."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.command_center.data import (  # noqa: E402
    REPORTER_STEP_KEYS,
    merge_reporter_step_state,
    probe_reporter_steps,
    reporter_step_advance,
    reporter_step_set,
    reporter_step_state_path,
    run_reporter_step_advance_browser,
    save_reporter_step_state_file,
)


def _task_fixture(base: Path, task_id: str = "task-reporter") -> Path:
    td = base / ".spark-flow" / "tasks" / task_id
    td.mkdir(parents=True, exist_ok=True)
    (td / "BRIEF.md").write_text("# brief\n", encoding="utf-8")
    return td


def test_default_merge_starts_at_init():
    with tempfile.TemporaryDirectory() as tmp:
        td = _task_fixture(Path(tmp))
        merged = merge_reporter_step_state(td)
        assert merged["current_step_id"] == "init"
        assert "init" in merged["completed_steps"]
        assert merged["allowed_next"] == ["snapshot"]


def test_advance_requires_complete_or_force():
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp) / ".spark-flow" / "tasks" / "bare"
        td.mkdir(parents=True)
        reporter_step_set(td, "init", mark_complete=False)
        try:
            reporter_step_advance(td, force=False)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "not complete" in str(exc)
        merged = reporter_step_advance(td, force=True)
        assert merged["current_step_id"] == "snapshot"


def test_set_and_advance_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        td = _task_fixture(Path(tmp))
        reporter_step_set(td, "init", mark_complete=True)
        merged = reporter_step_advance(td)
        assert merged["current_step_id"] == "snapshot"
        state_path = reporter_step_state_path(td)
        assert state_path.exists()
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        assert raw["current_step_id"] == "snapshot"
        assert "init" in raw["completed_steps"]


def test_idempotent_save_skips_rewrite():
    with tempfile.TemporaryDirectory() as tmp:
        td = _task_fixture(Path(tmp))
        state = {"current_step_id": "init", "completed_steps": ["init"]}
        save_reporter_step_state_file(td, state)
        path = reporter_step_state_path(td)
        mtime_first = path.stat().st_mtime
        save_reporter_step_state_file(td, state)
        mtime_second = path.stat().st_mtime
        assert mtime_first == mtime_second


def test_probe_syncs_completed_steps():
    with tempfile.TemporaryDirectory() as tmp:
        td = _task_fixture(Path(tmp))
        (td / "CONTEXT.md").write_text("# ctx\n", encoding="utf-8")
        merged = merge_reporter_step_state(td)
        assert "init" in merged["completed_steps"]
        assert "snapshot" in merged["completed_steps"]


def test_cli_show_subprocess():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _task_fixture(base, "cli-task")
        (base / ".spark-flow" / "current").write_text("cli-task\n", encoding="utf-8")
        spark_flow = ROOT / "bin" / "spark-flow"
        proc = subprocess.run(
            [sys.executable, str(spark_flow), "reporter-step", "show"],
            capture_output=True,
            text=True,
            cwd=base,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Current step: init" in proc.stdout
        assert "init" in proc.stdout


def test_reporter_step_keys_align_with_probe():
    steps = probe_reporter_steps(Path("/nonexistent"))
    assert set(steps.keys()) == set(REPORTER_STEP_KEYS)


def test_browser_advance_requires_opt_in(monkeypatch, tmp_path):
    td = _task_fixture(tmp_path)
    reporter_step_set(td, "init", mark_complete=True)

    monkeypatch.setattr(
        "dashboard.command_center.data._repo_cwd_for_project",
        lambda _project: tmp_path,
    )
    monkeypatch.setattr(
        "dashboard.command_center.project_plans.load_project_plan",
        lambda _key: {"reporter_auto_advance": False},
    )
    blocked = run_reporter_step_advance_browser("demo", task_id=td.name)
    assert blocked["ok"] is False
    assert "reporter_auto_advance" in blocked["output"]

    monkeypatch.setattr(
        "dashboard.command_center.project_plans.load_project_plan",
        lambda _key: {"reporter_auto_advance": True},
    )
    ok = run_reporter_step_advance_browser("demo", task_id=td.name)
    assert ok["ok"] is True
    assert "advanced" in ok["output"].lower()


if __name__ == "__main__":
    test_default_merge_starts_at_init()
    test_advance_requires_complete_or_force()
    test_set_and_advance_round_trip()
    test_idempotent_save_skips_rewrite()
    test_probe_syncs_completed_steps()
    test_cli_show_subprocess()
    test_reporter_step_keys_align_with_probe()
    print("ok")
