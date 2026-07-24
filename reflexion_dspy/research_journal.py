"""
Research journal for StrategyResearchAgent.

Persists findings across runs so knowledge accumulates — every attempt,
failure mode, and finding is recorded. A future agent for the same research
question picks up where the last one left off.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

JOURNAL_DIR = Path(__file__).parent.parent / "memory" / "research"


def _ensure_dir() -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)


def _slug(text: str) -> str:
    """Short filesystem-safe slug from a research question."""
    import re
    s = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())[:48]
    return s.strip("_")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def journal_path(research_question: str) -> Path:
    _ensure_dir()
    return JOURNAL_DIR / f"{_slug(research_question)}.json"


def load_journal(research_question: str) -> dict:
    path = journal_path(research_question)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "research_question": research_question,
        "started_at": _now(),
        "attempts": [],
        "outcome": "in_progress",
        "final_finding": None,
        "completed_at": None,
    }


def append_attempt(
    research_question: str,
    *,
    attempt: int,
    hypothesis: str,
    strategies: list[str],
    symbols: list[str],
    train_end: str,
    asset_class: str,
    train_stats: dict[str, Any],
    oos_stats: dict[str, Any],
    gate_passed: bool,
    gate_reasons: list[str],
    failure_mode: str = "",
    next_direction: str = "",
    reflection: str = "",
) -> None:
    journal = load_journal(research_question)
    journal["attempts"].append({
        "attempt": attempt,
        "timestamp": _now(),
        "hypothesis": hypothesis,
        "strategies": strategies,
        "symbols": symbols,
        "train_end": train_end,
        "asset_class": asset_class,
        "train_stats": train_stats,
        "oos_stats": oos_stats,
        "gate_passed": gate_passed,
        "gate_reasons": gate_reasons,
        "failure_mode": failure_mode,
        "next_direction": next_direction,
        "reflection": reflection,
    })
    journal["outcome"] = "in_progress"
    _save(research_question, journal)


def close_journal(
    research_question: str,
    outcome: str,
    final_finding: str,
) -> None:
    journal = load_journal(research_question)
    journal["outcome"] = outcome
    journal["final_finding"] = final_finding
    journal["completed_at"] = _now()
    _save(research_question, journal)


def _save(research_question: str, journal: dict) -> None:
    _ensure_dir()
    journal_path(research_question).write_text(json.dumps(journal, indent=2))


def get_all_reflections(research_question: str) -> list[str]:
    """Return all reflection texts from past attempts, chronological."""
    journal = load_journal(research_question)
    return [a["reflection"] for a in journal["attempts"] if a.get("reflection")]


def get_past_attempts_summary(research_question: str) -> str:
    """Human-readable summary of all past attempts for injection into prompts."""
    journal = load_journal(research_question)
    attempts = journal.get("attempts", [])
    if not attempts:
        return "No prior attempts."
    lines = []
    for a in attempts:
        status = "PASSED" if a.get("gate_passed") else "FAILED"
        lines.append(
            f"Attempt {a['attempt']} [{status}]: "
            f"strategies={a.get('strategies')}, symbols={a.get('symbols')}\n"
            f"  Failure mode: {a.get('failure_mode', 'n/a')}\n"
            f"  Reflection: {a.get('reflection', 'n/a')}\n"
            f"  Next direction: {a.get('next_direction', 'n/a')}"
        )
    return "\n".join(lines)
