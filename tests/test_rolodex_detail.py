#!/usr/bin/env python3
"""Rolodex detail panel and category label tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.rolodex import (  # noqa: E402
    ROLODEX_CATEGORY_HINTS,
    enrich_rolodex_entry,
    format_detail,
)
from dashboard.command_center.rolodex_resume import (  # noqa: E402
    build_hub_agent_resume,
    build_rolodex_resume,
    format_hub_agent_detail,
    resume_from_skill_md,
)
from dashboard.command_center.hub_skills import (  # noqa: E402
    _find_hermes_skill_md,
    is_generic_capability_text,
    skill_capability_text,
)


def _sample_skill_entry() -> dict:
    return {
        "id": "hermes:data-science",
        "title": "data-science",
        "subtitle": "hermes · analytics",
        "summary": "Analyze datasets, build features, and document findings for ML workflows.",
        "when_to_use": "Analytics and ML exploration slices on tabular or notebook workflows.",
        "launch": "hermes -s data-science",
        "path": str(Path.home() / ".hermes/skills/data-science/SKILL.md"),
        "meta": {"owner": "hermes", "kind": "hermes_skill", "category": "analytics"},
        "actions": [{"label": "Copy launch", "liaison_cmd": "hermes -s data-science"}],
    }


def test_format_detail_has_what_section():
    text = format_detail(enrich_rolodex_entry(_sample_skill_entry()))
    assert "Profile" in text or "What" in text
    assert "When to use" in text
    assert "Next steps" in text
    assert "data-science" in text
    assert "Run «data-science» in Hermes" in text
    assert "[he" not in text


def test_category_label_no_rich_markup_leak():
    """Skills count suffix must not use bracketed owner:count (Rich parses as tags)."""
    count = 110
    label = f"Skills ({count})"
    hint = ROLODEX_CATEGORY_HINTS["skills"]
    full = f"{label}\n[dim]{hint}[/dim]"
    assert "[he" not in full
    assert "hermes:50" not in full
    bad_legacy = f"Skills ({count}) [hermes:50, liaison:10]"
    assert "[he" in bad_legacy


def test_enrich_skill_next_step_friendly():
    entry = enrich_rolodex_entry(_sample_skill_entry())
    assert entry["what"]
    assert entry["when_to_use"]
    assert entry["next_steps"][0]["label"].startswith("Run «data-science»")


def test_is_generic_capability_text():
    assert is_generic_capability_text("Hermes skill in the creative category.")
    assert is_generic_capability_text("When you need the ascii-art playbook from hermes")
    assert not is_generic_capability_text("ASCII art: pyfiglet, cowsay, boxes, image-to-ascii.")


def test_derive_what_replaces_generic_boilerplate():
    with tempfile.TemporaryDirectory() as tmp:
        skill_md = Path(tmp) / "ascii-art" / "SKILL.md"
        skill_md.parent.mkdir()
        skill_md.write_text(
            "---\nname: ascii-art\ndescription: "
            '"ASCII art: pyfiglet, cowsay, boxes, image-to-ascii."\n---\n\n# ASCII Art Skill\n'
        )
        entry = {
            "id": "hermes:ascii-art",
            "title": "ascii-art",
            "subtitle": "hermes · creative",
            "summary": "Hermes skill in the creative category.",
            "what": "Hermes skill in the creative category.",
            "path": str(skill_md),
            "meta": {"owner": "hermes", "kind": "hermes_skill", "category": "creative"},
        }
        enriched = enrich_rolodex_entry(entry)
        assert "pyfiglet" in enriched["what"]
        assert "Hermes skill in the creative category" not in enriched["what"]


def test_skill_capability_from_frontmatter():
    with tempfile.TemporaryDirectory() as tmp:
        skill_md = Path(tmp) / "demo" / "SKILL.md"
        skill_md.parent.mkdir()
        skill_md.write_text("---\ndescription: Does useful demo work.\n---\n\nBody ignored when desc set.\n")
        assert skill_capability_text(skill_md) == "Does useful demo work."


def test_enrich_ascii_art_resume():
    with tempfile.TemporaryDirectory() as tmp:
        skill_md = Path(tmp) / "creative" / "ascii-art" / "SKILL.md"
        skill_md.parent.mkdir(parents=True)
        skill_md.write_text(
            "---\nname: ascii-art\ndescription: "
            '"ASCII art: pyfiglet, cowsay, boxes, image-to-ascii."\n---\n\n'
            "Intro paragraph about ASCII tools.\n\n"
            "## Tool 1: Text Banners (pyfiglet — local)\n\n"
            "- Render large banners\n"
        )
        entry = {
            "id": "hermes:ascii-art",
            "title": "ascii-art",
            "subtitle": "hermes · creative",
            "summary": "Hermes skill in the creative category.",
            "what": "Hermes skill in the creative category.",
            "when_to_use": "creative",
            "path": str(skill_md),
            "meta": {"owner": "hermes", "kind": "hermes_skill", "category": "creative"},
        }
        enriched = enrich_rolodex_entry(entry)
        resume = enriched.get("resume") or {}
        assert "pyfiglet" in enriched["what"].lower()
        assert enriched["when_to_use"] != "creative"
        assert len(resume.get("capabilities") or []) >= 1
        text = format_detail(enriched)
        assert "Capabilities" in text or "Profile" in text
        assert "pyfiglet" in text.lower()


def test_profile_override_merges():
    entry = {
        "id": "hermes:ascii-art",
        "title": "ascii-art",
        "summary": "short",
        "path": "/nonexistent/SKILL.md",
        "meta": {"owner": "hermes", "kind": "hermes_skill", "category": "creative"},
    }
    resume = build_rolodex_resume(entry)
    assert "Demos" in (resume.get("best_for") or "") or "pyfiglet" in str(resume.get("capabilities"))


def test_resume_from_skill_md_sections():
    with tempfile.TemporaryDirectory() as tmp:
        skill_md = Path(tmp) / "demo" / "SKILL.md"
        skill_md.parent.mkdir()
        skill_md.write_text(
            "---\ndescription: Demo skill.\n---\n\n"
            "## Tool 1: Widgets (local)\n\n- Widget A\n- Widget B\n"
        )
        resume = resume_from_skill_md(skill_md, category="test")
        assert "Demo skill" in resume["summary"]
        assert any("Widget" in c for c in resume["capabilities"])


def test_ml_intern_hub_resume():
    agent = {
        "name": "ml_intern",
        "display": "ML Intern",
        "status": "Idle",
        "registry_status": "active",
        "role": "paper-to-code, Hugging Face datasets/models/jobs, research loops",
        "output_contract": "research_report",
        "launch": "cd ~/apps/ml-intern && ml-intern",
        "handoff_guide": "liaison/guides/workflows/specialist-handoffs.md",
        "hub_docs": "~/spark/docs/local-agents/ml-intern",
        "tasks": 0,
    }
    resume = build_hub_agent_resume(agent)
    assert "Hugging Face" in resume["summary"] or "Hub" in resume["summary"]
    assert len(resume.get("capabilities") or []) >= 4
    assert "liaison attach" in resume["summary"].lower()
    text = format_hub_agent_detail({**agent, "resume": resume})
    assert "Capabilities" in text
    assert "hf-datasets" in text.lower() or "Hugging Face datasets" in text


def test_hub_agent_rolodex_subagent_enriched():
    agent = {
        "name": "ml_intern",
        "display": "ML Intern",
        "status": "Idle",
        "registry_status": "active",
        "role": "paper-to-code, Hugging Face datasets/models/jobs, research loops",
        "output_contract": "research_report",
        "launch": "cd ~/apps/ml-intern && ml-intern",
        "tasks": 0,
        "resume": build_hub_agent_resume(
            {
                "name": "ml_intern",
                "display": "ML Intern",
                "role": "paper-to-code, Hugging Face datasets/models/jobs, research loops",
                "output_contract": "research_report",
                "launch": "cd ~/apps/ml-intern && ml-intern",
                "tasks": 0,
            }
        ),
    }
    entry = {
        "id": "agent:ml_intern",
        "title": "ML Intern",
        "summary": agent["role"],
        "meta": {
            "kind": "hub_agent",
            "agent_name": "ml_intern",
            "output_contract": "research_report",
            "capabilities": [],
        },
    }
    enriched = enrich_rolodex_entry(entry)
    assert "research_report" in (enriched.get("resume") or {}).get("outputs", "")
    assert len(enriched.get("resume", {}).get("capabilities") or []) >= 4


def test_find_hermes_skill_md_nested():
    path = _find_hermes_skill_md("ascii-art")
    if path is None:
        return
    assert path.name == "SKILL.md"
    assert path.parent.name == "ascii-art"
    text = skill_capability_text(path, category="creative", owner="hermes")
    assert "pyfiglet" in text.lower() or "ascii" in text.lower()
    assert not is_generic_capability_text(text)


if __name__ == "__main__":
    test_format_detail_has_what_section()
    test_category_label_no_rich_markup_leak()
    test_enrich_skill_next_step_friendly()
    test_is_generic_capability_text()
    test_derive_what_replaces_generic_boilerplate()
    test_skill_capability_from_frontmatter()
    test_enrich_ascii_art_resume()
    test_ml_intern_hub_resume()
    test_hub_agent_rolodex_subagent_enriched()
    test_profile_override_merges()
    test_resume_from_skill_md_sections()
    test_find_hermes_skill_md_nested()
    print("ok")
