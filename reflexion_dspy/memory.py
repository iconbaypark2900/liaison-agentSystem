"""
Episodic memory for Reflexion.

Stores:
  - Reflections from failed attempts  (.reflection.md)
  - Successful traces for DSPy optimization  (.trace.jsonl)

Follows the liaison-agentSystem convention of writing to memory/.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

MEMORY_DIR = Path(__file__).parent.parent / "memory"
REFLECTION_DIR = MEMORY_DIR / "reflexion"
TRACE_DIR = MEMORY_DIR / "traces"


def _ensure_dirs() -> None:
    REFLECTION_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)


def _task_key(task: str) -> str:
    return hashlib.md5(task.strip().lower().encode()).hexdigest()[:10]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Reflections ──────────────────────────────────────────────────────────────

def save_reflection(task: str, attempt: int, reflection: str, outcome: str) -> Path:
    _ensure_dirs()
    key = _task_key(task)
    ts = int(time.time())
    path = REFLECTION_DIR / f"{key}_attempt{attempt}_{ts}.reflection.md"
    content = f"""# Reflection — Attempt {attempt}
Date: {_now()}
Outcome: {outcome}

## Task
{task}

## Reflection
{reflection}
"""
    path.write_text(content)
    return path


def load_reflections(task: str, max_reflections: int = 5) -> list[str]:
    """Load recent reflections for a task to inject into next attempt."""
    _ensure_dirs()
    key = _task_key(task)
    files = sorted(REFLECTION_DIR.glob(f"{key}_*.reflection.md"), reverse=True)
    reflections = []
    for f in files[:max_reflections]:
        text = f.read_text()
        m = re.search(r"## Reflection\n(.+)", text, re.DOTALL)
        if m:
            reflections.append(m.group(1).strip())
    return list(reversed(reflections))  # chronological order


def count_reflections(task: str) -> int:
    _ensure_dirs()
    key = _task_key(task)
    return len(list(REFLECTION_DIR.glob(f"{key}_*.reflection.md")))


# ── Traces ───────────────────────────────────────────────────────────────────

def save_trace(
    task: str,
    inputs: dict,
    outputs: dict,
    tool_calls: list[dict],
    score: float,
    metadata: dict | None = None,
) -> Path:
    _ensure_dirs()
    key = _task_key(task)
    path = TRACE_DIR / f"{key}.trace.jsonl"
    record = {
        "ts": _now(),
        "task_key": key,
        "task": task,
        "inputs": inputs,
        "outputs": outputs,
        "tool_calls": tool_calls,
        "score": score,
        "metadata": metadata or {},
    }
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return path


def load_traces(task: str, min_score: float = 0.7) -> list[dict]:
    _ensure_dirs()
    key = _task_key(task)
    path = TRACE_DIR / f"{key}.trace.jsonl"
    if not path.exists():
        return []
    traces = []
    for line in path.read_text().splitlines():
        try:
            record = json.loads(line)
            if record.get("score", 0) >= min_score:
                traces.append(record)
        except json.JSONDecodeError:
            pass
    return traces


def load_all_traces(min_score: float = 0.5) -> list[dict]:
    _ensure_dirs()
    all_traces = []
    for path in TRACE_DIR.glob("*.trace.jsonl"):
        for line in path.read_text().splitlines():
            try:
                record = json.loads(line)
                if record.get("score", 0) >= min_score:
                    all_traces.append(record)
            except json.JSONDecodeError:
                pass
    return sorted(all_traces, key=lambda x: x.get("ts", ""))


# ── Learning export (liaison-agentSystem compatible) ─────────────────────────

def export_learning(task: str, learning: str, tags: list[str] | None = None) -> Path:
    """Write a .learning.md file compatible with liaison learning_bridge.py."""
    _ensure_dirs()
    key = _task_key(task)
    ts = int(time.time())
    path = MEMORY_DIR / f"{key}_{ts}.learning.md"
    tag_str = ", ".join(tags or ["reflexion", "dspy", "self-improving"])
    content = f"""# Learning — {_now()}
- Tags: {tag_str}
- Source repo: reflexion-dspy

## Task context
{task[:200]}

## Learning
{learning}
"""
    path.write_text(content)
    return path
