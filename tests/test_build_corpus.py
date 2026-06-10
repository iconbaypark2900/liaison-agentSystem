#!/usr/bin/env python3
"""Unit tests for build corpus aggregation and recipe export."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.build_corpus import (  # noqa: E402
    append_build_step,
    collect_project_corpus,
    collect_task_corpus,
    export_agent_recipe,
    format_agent_recipe_markdown,
    parse_pattern_from_brief,
)


def test_parse_pattern_from_brief(tmp_path):
    brief = tmp_path / "BRIEF.md"
    brief.write_text("## Multi-agent pattern\n\n- Pattern: `hermes-led-slice`\n", encoding="utf-8")
    assert parse_pattern_from_brief(brief) == "hermes-led-slice"


def test_collect_task_corpus_with_build_trace(tmp_path):
    task = tmp_path / "slice-1"
    task.mkdir()
    (task / "BRIEF.md").write_text("- Pattern: `governed-slice`\n", encoding="utf-8")
    append_build_step(
        task,
        agent="hermes",
        action="Added auth middleware",
        outcome="pytest pass",
        timestamp="2026-05-31T10:00:00",
    )
    (task / "LEARNINGS.md").write_text(
        "## Learning: 2026-05-31\n\nAlways run validate before close.\n",
        encoding="utf-8",
    )
    approved = task / "approved"
    approved.mkdir()
    (approved / "hermes-report.md").write_text("# ok\n", encoding="utf-8")

    row = collect_task_corpus(task)
    assert row["pattern_id"] == "governed-slice"
    assert row["build_step_count"] == 1
    assert row["build_steps"][0]["agent"] == "hermes"
    assert "hermes-report.md" in row["approved_artifacts"]
    assert row["learnings"]


def test_export_agent_recipe_aggregates_tasks(tmp_path):
    task_a = tmp_path / "a"
    task_a.mkdir()
    append_build_step(
        task_a,
        agent="hermes",
        action="Scaffold module",
        outcome="files created",
        timestamp="2026-05-31T11:00:00",
    )
    task_b = tmp_path / "b"
    task_b.mkdir()
    append_build_step(
        task_b,
        agent="qca",
        action="Review plots",
        outcome="approved",
        timestamp="2026-05-31T12:00:00",
    )

    spark = tmp_path / ".spark-flow" / "tasks"
    spark.mkdir(parents=True)
    # collect_project_corpus expects repo/.spark-flow/tasks — restructure
    repo = tmp_path / "repo"
    repo.mkdir()
    tasks_dir = repo / ".spark-flow" / "tasks"
    tasks_dir.mkdir(parents=True)
    import shutil

    shutil.move(str(task_a), str(tasks_dir / "a"))
    shutil.move(str(task_b), str(tasks_dir / "b"))

    corpus = collect_project_corpus("demo", repo)
    assert corpus["task_count"] == 2
    assert corpus["total_build_steps"] == 2

    recipe = export_agent_recipe(
        "demo",
        repo,
        recipe_id="demo-test",
        project_plan={"pattern": "hermes-led-slice", "workflow": "reporter-mode", "validation_profile": "python"},
    )
    assert recipe["recipe_id"] == "demo-test"
    assert len(recipe["build_steps"]) == 2
    md = format_agent_recipe_markdown(recipe)
    assert "demo-test" in md
    assert "hermes" in md
    assert "python" in md
