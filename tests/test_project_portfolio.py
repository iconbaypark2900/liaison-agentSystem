#!/usr/bin/env python3
"""Project portfolio detail builders."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.project_portfolio import (  # noqa: E402
    build_hub_workflows_for_project,
    build_project_detail,
)


def test_sigma_project_detail_has_agents_and_research():
    from dashboard.command_center.data import collect_command_center_state

    state = collect_command_center_state(selected_project="sigma", refresh=False)
    detail = state.get("project_detail")
    assert detail is not None
    assert "sigma" in detail.get("intent", "").lower() or detail.get("workflow") == "sigma-integration"
    assert detail.get("agent_chain")
    assert len(detail.get("production_checklist", [])) >= 3
    assert detail.get("research_commands")


def test_hub_workflows_ranked():
    from dashboard.command_center.data import collect_command_center_state

    state = collect_command_center_state(selected_project="sigma", refresh=False)
    wfs = state.get("hub_workflows") or []
    assert len(wfs) >= 1
    assert any(w.get("fit_score", 0) >= 70 for w in wfs)


if __name__ == "__main__":
    test_sigma_project_detail_has_agents_and_research()
    test_hub_workflows_ranked()
    print("ok")
