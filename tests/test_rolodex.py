#!/usr/bin/env python3
"""Rolodex builder tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.data import collect_command_center_state  # noqa: E402
from dashboard.command_center.rolodex import CATEGORIES, build_rolodex  # noqa: E402


def test_rolodex_four_categories():
    state = collect_command_center_state(refresh=False)
    rolodex = state["rolodex"]
    for cat in CATEGORIES:
        assert cat in rolodex
        assert isinstance(rolodex[cat], list)


def test_rolodex_subagents_include_hub():
    state = collect_command_center_state(refresh=False)
    ids = {e["id"] for e in state["rolodex"]["subagents"]}
    assert "agent:hermes" in ids
    assert "agent:qca" in ids
    assert any(i.startswith("chain:") for i in ids)


def test_rolodex_commands_populated():
    state = collect_command_center_state(refresh=False)
    names = {e["title"] for e in state["rolodex"]["commands"]}
    assert "init" in names
    assert "command-center" in names


def test_rolodex_skills_from_all_hub_members():
    state = collect_command_center_state(refresh=False)
    owners = {e["meta"].get("owner") for e in state["rolodex"]["skills"]}
    assert "hermes" in owners
    assert "liaison" in owners
    assert "qca" in owners
    assert len(state["rolodex"]["skills"]) >= 20


def test_rolodex_project_patterns():
    state = collect_command_center_state(refresh=False)
    repo_cards = [e for e in state["rolodex"]["projects"] if e["id"].startswith("repo:")]
    registry = state.get("projects_registry") or []
    assert len(registry) >= 1
    assert len(repo_cards) >= len(registry)
    titles = {e["title"] for e in state["rolodex"]["projects"]}
    assert any("Hermes" in t for t in titles) or len(repo_cards) >= 1


def test_rolodex_entries_have_actions():
    state = collect_command_center_state(refresh=False)
    for cat in ("commands", "tools"):
        sample = state["rolodex"][cat][:3]
        for entry in sample:
            assert entry.get("actions"), f"{cat} entry missing actions: {entry['id']}"


def test_projects_registry_matches_repos():
    state = collect_command_center_state(refresh=False)
    registry = state.get("projects_registry") or []
    from dashboard.command_center.data import _bridge

    repos = _bridge().parse_registry_map("repos.yaml", "repos")
    assert len(registry) >= len(repos)
    reg_keys = {r["key"] for r in registry}
    for key in repos:
        assert key in reg_keys


def test_ops_signoff_shape():
    state = collect_command_center_state(refresh=False)
    signoff = state.get("ops_signoff")
    assert signoff is not None
    for key in (
        "pending_handoffs",
        "pending_handoff_count",
        "gate_failures",
        "flywheel_open",
        "debrief_age",
        "debrief_stale",
        "flywheel_phases",
        "flywheel_copy_cmds",
        "checklist",
        "copy_hints",
        "ready_for_signoff",
    ):
        assert key in signoff
    assert len(signoff["checklist"]) >= 4
    assert signoff["copy_hints"][0].get("liaison_cmd")


def test_overview_actions_populated():
    state = collect_command_center_state(refresh=False)
    actions = state.get("overview_actions") or []
    assert len(actions) >= 2
    assert any(a["id"] == "action:sync" for a in actions)


def test_metrics_rows_populated():
    state = collect_command_center_state(refresh=False)
    rows = state["metrics_rows"]
    assert len(rows) >= 8
    ids = {r["id"] for r in rows}
    assert "metric:open_tasks" in ids
    assert any(r.get("liaison_cmd") for r in rows)


def test_handoffs_include_paths_when_present():
    state = collect_command_center_state(refresh=False)
    for handoff in state["handoffs"]:
        if handoff.get("path"):
            assert Path(handoff["path"]).suffix == ".md"


def test_debriefs_include_paths():
    state = collect_command_center_state(refresh=False)
    for debrief in state["debriefs"]:
        assert "path" in debrief
        assert debrief["path"]


def test_liaison_cmd_classifiers():
    from dashboard.command_center.data import liaison_cmd_is_destructive, liaison_cmd_is_readonly

    assert liaison_cmd_is_readonly("liaison status")
    assert liaison_cmd_is_readonly("liaison debrief --show")
    assert not liaison_cmd_is_readonly("liaison approve-artifact foo.md")
    assert liaison_cmd_is_destructive("liaison approve-artifact foo.md")
    assert liaison_cmd_is_destructive("liaison close-task --summary done")


if __name__ == "__main__":
    test_rolodex_four_categories()
    test_rolodex_subagents_include_hub()
    test_rolodex_commands_populated()
    print("ok")
