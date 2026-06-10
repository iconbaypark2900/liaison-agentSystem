#!/usr/bin/env python3
"""Tests for portfolio project operating plans."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.project_plans import (  # noqa: E402
    build_project_plan_card,
    load_project_plan,
    merge_plan_with_intake,
    write_project_operating_plan,
)


def test_load_sigma_plan():
    plan = load_project_plan("sigma")
    assert plan is not None
    assert plan["workflow"] == "sigma-integration"
    assert plan["pattern"] == "hermes-led-slice"
    assert plan["validation_profile"] == "sigma"
    assert plan["reporter_auto_advance"] is False
    assert len(plan["backlog"]) >= 1


def test_clinical_suite_reporter_auto_advance():
    plan = load_project_plan("clinical_suite")
    assert plan is not None
    assert plan["reporter_auto_advance"] is True


def test_tier_c_fallback():
    plan = load_project_plan("materialScience")
    assert plan is not None
    assert plan["tier"] == "C"
    assert plan["pattern"] is None
    assert plan["engineering_gate"]["blocked"] is True


def test_merge_plan_with_intake():
    plan = load_project_plan("sigma")
    intake = {
        "intake_ready": False,
        "ready_to_build": False,
        "recommended_lane": "research",
        "blockers": [{"id": "project_brief"}],
    }
    merged = merge_plan_with_intake(plan, intake)
    assert merged["engineering_gate"]["blocked"] is True
    assert "intake" in merged


def test_build_card_and_write(tmp_path):
    memory = tmp_path / ".spark-flow" / "memory"
    memory.mkdir(parents=True)
    plan = load_project_plan("clinical_suite")
    card = build_project_plan_card("clinical_suite", str(tmp_path), plan, None, [])
    assert card["has_registry_plan"] is True
    assert card["workflow"] == "reporter-mode"
    assert card["reporter_auto_advance"] is True
    target = write_project_operating_plan(
        str(tmp_path),
        plan,
        project_key="clinical_suite",
        intake=None,
    )
    assert target.exists()
    card2 = build_project_plan_card("clinical_suite", str(tmp_path), plan, None, [])
    assert card2["has_on_disk_plan"] is True


def test_research_plan_pattern():
    plan = load_project_plan("research")
    assert plan["workflow"] == "ml-research"
    assert plan["pattern"] == "research-to-calibration"


if __name__ == "__main__":
    import tempfile

    test_load_sigma_plan()
    test_clinical_suite_reporter_auto_advance()
    test_tier_c_fallback()
    test_merge_plan_with_intake()
    with tempfile.TemporaryDirectory() as tmp:
        test_build_card_and_write(Path(tmp))
    test_research_plan_pattern()
    print("ok")
