#!/usr/bin/env python3
"""Panel brief builders for Overview, Workstream, and Ops."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.panel_briefs import (  # noqa: E402
    build_overview_brief,
    build_workstream_brief,
    enrich_ops_signoff,
    load_workflow_phases,
)
from dashboard.command_center.data import (  # noqa: E402
    build_ops_signoff,
    build_overview_actions,
    executor_launch_ready,
)


def _minimal_state(**kwargs):
    base = {
        "selected_project": None,
        "summary": {"open_tasks": 2, "filtered_open": 1, "blockers": 0, "ready_to_build": False},
        "kanban": {"todo": [], "in_progress": [], "review": [], "done": []},
        "agent_rows": [
            {
                "name": "ml_intern",
                "display": "ML Intern",
                "role": "HF research",
                "recommended": True,
                "tasks": 0,
                "resume": {"headline": "ML research specialist"},
            }
        ],
        "rolodex": {"projects": [], "skills": []},
        "ops_signoff": {"pending_handoff_count": 0, "gate_failures": 0, "flywheel_open": 0, "checklist": []},
        "project_matrix": [{"option": "demo", "score": 10, "lifecycle": "active", "phase": "build"}],
    }
    base.update(kwargs)
    return base


def test_overview_brief_has_paragraphs():
    brief = build_overview_brief(_minimal_state())
    assert len(brief["project"]["body"]) > 40
    assert brief["hub"]["title"] == "Agent hub"
    assert any("ml_intern" in b.lower() or "ML" in b for b in brief["hub"]["bullets"])


def test_workstream_brief_reporter_how_to():
    state = _minimal_state(
        selected_project="sigma",
        project_intake={"intake_ready": True, "ready_to_build": True, "recommended_lane": "engineering"},
        project_plan={"tier": "A", "workflow": "sigma-integration", "has_on_disk_plan": True, "engineering_gate": {"commands": ["liaison validate --profile sigma"]}},
    )
    brief = build_workstream_brief(state)
    assert "liaison attach" in brief["reporter_how_to"]
    assert brief["sections"][0]["title"] == "Intake"


def test_ops_signoff_enriched_how_to():
    state = _minimal_state(selected_project="sigma")
    raw = build_ops_signoff(state)
    enriched = enrich_ops_signoff(raw, state)
    assert enriched.get("summary")
    assert enriched.get("playbook")
    assert enriched["checklist"][0].get("how_to")


def test_overview_actions_how_to():
    state = _minimal_state(selected_project="sigma", focus={"phase": "build", "recommended_agents": ["hermes"]})
    actions = build_overview_actions(state)
    sync = next(a for a in actions if a["id"] == "action:sync")
    assert len(sync.get("how_to", "")) > 20


def test_load_workflow_phases_data_flywheel():
    phases = load_workflow_phases("data-flywheel")
    assert len(phases) >= 3
    assert phases[0].get("id")
    assert isinstance(phases[0].get("suggested_liaison_commands"), list)


def test_load_workflow_phases_sigma_list():
    phases = load_workflow_phases("sigma-integration", "workflows/sigma-integration.yaml")
    assert len(phases) >= 2
    assert phases[0]["id"] == "archive-inspect"
    assert phases[0]["suggested_liaison_commands"]


def test_executor_launch_soft_gate():
    assert executor_launch_ready(
        intake={"ready_to_build_strict": False, "ready_to_build_soft": True},
        focus={"default_profile": "sigma"},
        project_plan=None,
    )
    assert not executor_launch_ready(
        intake={"ready_to_build_strict": False, "ready_to_build_soft": False},
        focus={"default_profile": "none"},
        project_plan={"tier": "C"},
    )


if __name__ == "__main__":
    test_overview_brief_has_paragraphs()
    test_workstream_brief_reporter_how_to()
    test_ops_signoff_enriched_how_to()
    test_overview_actions_how_to()
    test_load_workflow_phases_data_flywheel()
    test_load_workflow_phases_sigma_list()
    test_executor_launch_soft_gate()
    print("ok")
