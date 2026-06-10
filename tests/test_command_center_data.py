#!/usr/bin/env python3
"""Minimal tests for command center data loader."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.data import (  # noqa: E402
    HANDOFF_CHAINS,
    build_debrief_staleness,
    build_engineering_metrics,
    build_reporter_step_state_for_task,
    build_suggested_workflow_commands,
    build_workflow_next_action,
    collect_command_center_state,
    enrich_hub_agents,
    enrich_task_with_reporter_steps,
    format_gate_strip_tui,
    liaison_cmd_is_allowlisted,
    liaison_cmd_is_readonly,
    probe_reporter_steps,
    resolve_workload_id,
)
from dashboard.command_center.hub_groups import group_agent_rows, HUB_AGENT_GROUPS  # noqa: E402


def test_collect_state_has_hub_agents():
    state = collect_command_center_state(refresh=False)
    assert "agent_rows" in state
    assert len(state["agent_rows"]) >= 8
    names = {row["name"] for row in state["agent_rows"]}
    for required in ("liaison", "hermes", "qca", "ml_intern", "unsloth_studio", "codex", "opencode", "claude"):
        assert required in names, f"missing hub agent: {required}"


def test_engineering_metrics_keys():
    state = collect_command_center_state(refresh=False)
    eng = state["engineering_metrics"]
    for key in (
        "open_by_repo",
        "open_by_phase",
        "gate_failures",
        "pending_handoffs",
        "promoted_learnings",
        "reporter_tasks",
        "executor_tasks",
    ):
        assert key in eng


def test_handoff_chains_nonempty():
    assert len(HANDOFF_CHAINS) >= 3


def test_enrich_hub_agents_status():
    raw = {"hermes": {"role": "engineer", "output_contract": "report"}}
    out = enrich_hub_agents(raw)
    assert out["hermes"]["status"] == "ready"


def test_project_agent_patterns_in_state():
    state = collect_command_center_state(refresh=False)
    patterns = state.get("project_agent_patterns", [])
    assert len(patterns) >= 1
    first = patterns[0]
    for key in ("id", "label", "agents", "when", "steps"):
        assert key in first


def test_probe_reporter_steps_fixture(tmp_path):
    task_dir = tmp_path / "task-1"
    task_dir.mkdir()
    (task_dir / "BRIEF.md").write_text("# brief\n", encoding="utf-8")
    steps = probe_reporter_steps(task_dir)
    assert steps["init"] is True
    assert steps["snapshot"] is False
    enriched = enrich_task_with_reporter_steps({"task_id": "task-1", "path": str(task_dir)})
    assert enriched["reporter_steps"]["init"] is True


def test_hub_agent_groups_constants():
    assert len(HUB_AGENT_GROUPS) >= 3
    state = collect_command_center_state(refresh=False)
    grouped = group_agent_rows(state["agent_rows"])
    assert len(grouped) >= 1


def test_active_task_id_in_state():
    state = collect_command_center_state(refresh=False, active_task_id="nonexistent-task")
    assert "active_task_id" in state


def test_project_intake_key_in_summary():
    state = collect_command_center_state(refresh=False)
    assert "intake_ready" in state["summary"]
    assert "ready_to_build" in state["summary"]
    assert "ready_to_build_soft" in state["summary"]
    assert "executor_launch_ready" in state["summary"]
    assert "intake_blockers" in state["summary"]
    assert state.get("project_intake") is None or isinstance(state["project_intake"], dict)


def test_resolve_workload_id_env(monkeypatch):
    monkeypatch.setenv("LIAISON_WORKLOAD_ID", "sigma-calibration-v1")
    assert resolve_workload_id(None) == "sigma-calibration-v1"
    monkeypatch.delenv("LIAISON_WORKLOAD_ID", raising=False)


def test_resolve_workload_id_from_project_phase(tmp_path, monkeypatch):
    monkeypatch.delenv("LIAISON_WORKLOAD_ID", raising=False)
    monkeypatch.delenv("FLYWHEEL_WORKLOAD_ID", raising=False)
    memory = tmp_path / ".spark-flow" / "memory"
    memory.mkdir(parents=True)
    (memory / "PROJECT_PHASE.md").write_text(
        "workload_id: sigma-calibration-v1\n",
        encoding="utf-8",
    )
    assert resolve_workload_id(str(tmp_path)) == "sigma-calibration-v1"


def test_workload_id_in_summary(monkeypatch):
    monkeypatch.setenv("LIAISON_WORKLOAD_ID", "test-workload")
    state = collect_command_center_state(refresh=False)
    assert state["summary"].get("workload_id") == "test-workload"
    monkeypatch.delenv("LIAISON_WORKLOAD_ID", raising=False)


def test_format_gate_strip_tui_includes_workload(monkeypatch):
    monkeypatch.setenv("LIAISON_WORKLOAD_ID", "wf-chip-test")
    state = collect_command_center_state(refresh=False)
    text = format_gate_strip_tui(state)
    assert "GATES" in text
    assert "wf-chip-test" in text
    monkeypatch.delenv("LIAISON_WORKLOAD_ID", raising=False)


def test_reporter_step_state_merge(tmp_path):
    td = tmp_path / "task-rs"
    td.mkdir()
    (td / "BRIEF.md").write_text("# brief\n", encoding="utf-8")
    merged = build_reporter_step_state_for_task({"task_id": "task-rs", "path": str(td)})
    assert merged is not None
    assert merged["current_step_id"] == "init"
    assert "init" in merged["completed_steps"]
    assert merged["allowed_next"] == ["snapshot"]


def test_reporter_step_state_in_json(tmp_path, monkeypatch):
    td = tmp_path / "open-task"
    td.mkdir()
    (td / "BRIEF.md").write_text("# brief\n", encoding="utf-8")
    state = build_reporter_step_state_for_task({"task_id": "open-task", "path": str(td)})
    assert state.get("task_id") == "open-task"
    assert "allowed_next" in state


def test_suggested_workflow_commands_from_next_step():
    step = {
        "id": "observe",
        "label": "Observe",
        "suggested_liaison_commands": ["liaison snapshot --show", "liaison observe logs"],
    }
    assert build_suggested_workflow_commands(step) == step["suggested_liaison_commands"]
    assert build_suggested_workflow_commands(None) == []


def test_workflow_phases_with_sigma():
    state = collect_command_center_state(refresh=False, selected_project="sigma")
    if state.get("project_plan"):
        assert isinstance(state.get("workflow_phases"), list)
        assert len(state["workflow_phases"]) >= 1
        if state.get("next_workflow_step"):
            assert isinstance(state.get("suggested_workflow_commands"), list)


def test_project_plan_key_in_state():
    state = collect_command_center_state(refresh=False, selected_project="sigma")
    assert "has_project_plan" in state["summary"]
    if state.get("focus") and state["focus"].get("path"):
        assert state.get("project_plan") is None or isinstance(state["project_plan"], dict)
        if state.get("project_plan"):
            assert state["project_plan"].get("workflow") == "sigma-integration"


def test_ops_signoff_in_state():
    state = collect_command_center_state(refresh=False)
    assert isinstance(state.get("ops_signoff"), dict)
    assert isinstance(state.get("overview_actions"), list)
    assert isinstance(state.get("projects_registry"), list)


def test_projects_portfolio_detail_in_state():
    state = collect_command_center_state(refresh=False)
    detail = state.get("projects_portfolio_detail")
    assert isinstance(detail, list)
    if detail:
        row = detail[0]
        for key in (
            "project_key",
            "intake_ready",
            "ready_to_build",
            "has_plan",
            "corpus_trace_count",
        ):
            assert key in row


def test_debrief_staleness_keys():
    meta = build_debrief_staleness()
    for key in ("last_debrief_age", "debrief_age_days", "debrief_stale", "debrief_stale_days"):
        assert key in meta
    state = collect_command_center_state(refresh=False)
    assert "debrief_stale" in state["summary"]
    assert "debrief_stale_days" in state["engineering_metrics"]
    signoff = state["ops_signoff"]
    assert "debrief_stale" in signoff


def test_flywheel_phases_when_open(monkeypatch):
    state = collect_command_center_state(refresh=False)
    if state["summary"].get("flywheel_open", 0) > 0:
        assert isinstance(state.get("workflow_phases"), list)
        assert len(state["workflow_phases"]) >= 1


def test_liaison_allowlist():
    ok, _ = liaison_cmd_is_allowlisted("liaison start-pattern hermes-led-slice --task-id t1")
    assert ok
    ok_ro, _ = liaison_cmd_is_allowlisted("liaison status")
    assert ok_ro == liaison_cmd_is_readonly("liaison status")
    bad, _ = liaison_cmd_is_allowlisted("hermes -s foo")
    assert not bad
    bad_launch, launch_reason = liaison_cmd_is_allowlisted("liaison look && hermes")
    assert not bad_launch
    assert "terminal" in launch_reason.lower() or "agent" in launch_reason.lower()
    ok_val, _ = liaison_cmd_is_allowlisted("liaison validate --profile python", project="sigma")
    assert ok_val
    bad_val, reason_val = liaison_cmd_is_allowlisted("liaison validate --profile bogus", project="sigma")
    assert not bad_val
    assert "profile" in reason_val.lower()


def test_workflow_next_action_when_ready(tmp_path):
    task_dir = tmp_path / "task-close"
    task_dir.mkdir()
    (task_dir / "BRIEF.md").write_text("# brief\n", encoding="utf-8")
    (task_dir / "CONTEXT.md").write_text("# ctx\n", encoding="utf-8")
    outbox = task_dir / "outbox"
    outbox.mkdir()
    (outbox / "report.md").write_text("# r\n", encoding="utf-8")
    approved = task_dir / "approved"
    approved.mkdir()
    (approved / "report.md").write_text("# r\n", encoding="utf-8")
    (task_dir / "GATE_REPORT.md").write_text("- PASS: ok\n", encoding="utf-8")
    enriched = enrich_task_with_reporter_steps({"task_id": "task-close", "path": str(task_dir)})
    action = build_workflow_next_action(enriched)
    assert action is not None
    assert action["action"] == "close-task"
    assert "close-task" in action["liaison_cmd"]


if __name__ == "__main__":
    test_collect_state_has_hub_agents()
    test_engineering_metrics_keys()
    test_handoff_chains_nonempty()
    test_enrich_hub_agents_status()
    test_project_agent_patterns_in_state()
    test_liaison_allowlist()
    print("ok")
