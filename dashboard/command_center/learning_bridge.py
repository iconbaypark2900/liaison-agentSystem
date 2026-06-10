"""Hermes hints bridge — append promoted learnings into repo memory (operator-visible)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from liaison_paths import AGENT_SYSTEM_DIR


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _learning_matches_project(text: str, project_key: str, path: Path) -> bool:
    key = project_key.lower()
    if key in path.stem.lower():
        return True
    tags_match = re.search(r"- Tags:\s*(.+)", text)
    if tags_match:
        tags = {t.strip().lower() for t in tags_match.group(1).split(",")}
        if key in tags:
            return True
    if f"Source repo:" in text and key in text.lower():
        return True
    return False


def find_promoted_learnings(project_key: str, *, limit: int = 12) -> list[Path]:
    memory_dir = AGENT_SYSTEM_DIR / "memory"
    if not memory_dir.exists():
        return []
    matched: list[tuple[float, Path]] = []
    for path in memory_dir.glob("*.learning.md"):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if _learning_matches_project(text, project_key, path):
            matched.append((path.stat().st_mtime, path))
    matched.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in matched[:limit]]


def export_learning_bridge(
    project_key: str,
    *,
    repo_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Append latest promoted learnings digest to repo `.spark-flow/memory/hermes_hints.md`."""
    from dashboard.command_center.project_plans import resolve_project_key_and_path

    _, resolved_repo = resolve_project_key_and_path(project_key)
    repo = Path(repo_path or resolved_repo or "")
    if not repo.is_dir():
        return {"ok": False, "error": f"unknown or missing repo for project: {project_key}"}

    learnings = find_promoted_learnings(project_key)
    if not learnings:
        return {
            "ok": True,
            "project": project_key,
            "repo": str(repo),
            "appended": 0,
            "message": "No promoted learnings matched this project",
        }

    dest_dir = repo / ".spark-flow" / "memory"
    dest = dest_dir / "hermes_hints.md"
    sections: list[str] = [
        f"\n## Learning bridge digest · {project_key} · {_now()}\n",
        f"Source: liaison memory/*.learning.md ({len(learnings)} file(s))\n",
    ]
    for path in learnings:
        text = path.read_text(errors="replace").strip()
        sections.append(f"### From `{path.name}`\n\n{text}\n")

    block = "\n".join(sections)
    if dry_run:
        return {
            "ok": True,
            "project": project_key,
            "repo": str(repo),
            "destination": str(dest),
            "appended": len(learnings),
            "dry_run": True,
            "preview_chars": len(block),
        }

    dest_dir.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        existing = dest.read_text(errors="replace")
        dest.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
    else:
        header = (
            f"# Hermes hints (learning bridge)\n\n"
            f"Append-only digest from Liaison promoted learnings. "
            f"Do not edit skill files directly — review here first.\n"
        )
        dest.write_text(header + block, encoding="utf-8")

    return {
        "ok": True,
        "project": project_key,
        "repo": str(repo),
        "destination": str(dest),
        "appended": len(learnings),
        "files": [p.name for p in learnings],
    }
