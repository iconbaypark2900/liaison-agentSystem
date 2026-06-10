"""Workstation capacity profile for execution bridge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from liaison_paths import AGENT_SYSTEM_DIR

_DEFAULT_PROFILE: dict[str, Any] = {
    "defaults": {"max_active_ventures": 3, "default_engine": "hermes", "log_excerpt_max_chars": 4000},
    "engines": {
        "hermes": {"max_concurrent": 1, "requires_gpu": False, "agents": ["hermes"]},
        "qca": {"max_concurrent": 1, "requires_gpu": False, "agents": ["qca"]},
        "ml_intern": {"max_concurrent": 1, "requires_gpu": True, "agents": ["ml_intern"]},
        "unsloth_studio": {"max_concurrent": 1, "requires_gpu": True, "agents": ["unsloth_studio"]},
    },
}

_AGENT_ENGINE: dict[str, str] = {
    "hermes": "hermes",
    "qca": "qca",
    "ml_intern": "ml_intern",
    "ml-intern": "ml_intern",
    "unsloth_studio": "unsloth_studio",
    "unsloth": "unsloth_studio",
    "data_flywheel": "hermes",
    "liaison": "hermes",
}


def load_workstation_profile() -> dict[str, Any]:
    path = AGENT_SYSTEM_DIR / "registry" / "workstation_profile.yaml"
    if not path.exists():
        return dict(_DEFAULT_PROFILE)
    engines: dict[str, dict[str, Any]] = {}
    defaults: dict[str, Any] = dict(_DEFAULT_PROFILE["defaults"])
    current_engine: str | None = None
    in_engines = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "defaults:":
            in_engines = False
            continue
        if stripped == "engines:":
            in_engines = True
            continue
        if not in_engines and ":" in stripped:
            key, val = stripped.split(":", 1)
            key, val = key.strip(), val.strip()
            if key == "max_active_ventures":
                defaults[key] = int(val)
            elif key == "log_excerpt_max_chars":
                defaults[key] = int(val)
            else:
                defaults[key] = val.strip('"')
            continue
        if in_engines and line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_engine = stripped[:-1]
            engines[current_engine] = {"agents": []}
            continue
        if in_engines and current_engine and line.startswith("    "):
            key, val = stripped.split(":", 1)
            key, val = key.strip(), val.strip()
            if key == "agents":
                inner = val.strip("[]")
                engines[current_engine]["agents"] = [
                    a.strip().strip('"') for a in inner.split(",") if a.strip()
                ]
            elif key == "max_concurrent":
                engines[current_engine][key] = int(val)
            elif key == "requires_gpu":
                engines[current_engine][key] = val.lower() in ("true", "yes", "1")
    if not engines:
        return dict(_DEFAULT_PROFILE)
    return {"defaults": defaults, "engines": engines}


def engine_for_agent(agent_name: str) -> str:
    name = (agent_name or "").strip().lower().replace("-", "_")
    if name in _AGENT_ENGINE:
        return _AGENT_ENGINE[name]
    profile = load_workstation_profile()
    for engine_id, spec in profile.get("engines", {}).items():
        agents = [a.lower().replace("-", "_") for a in spec.get("agents") or []]
        if name in agents:
            return engine_id
    return profile.get("defaults", {}).get("default_engine", "hermes")


def count_active_sessions(sessions: list[dict]) -> dict[str, Any]:
    """Count running sessions by engine and venture totals."""
    profile = load_workstation_profile()
    engines = profile.get("engines") or {}
    by_engine: dict[str, int] = {eid: 0 for eid in engines}
    running_ventures = 0
    for sess in sessions:
        if sess.get("status") == "ended":
            continue
        alive = sess.get("alive", True)
        if sess.get("pid") is not None and not alive:
            continue
        running_ventures += 1
        eid = sess.get("engine") or engine_for_agent(sess.get("agent_name", ""))
        by_engine[eid] = by_engine.get(eid, 0) + 1
    slots: list[dict[str, Any]] = []
    for eid, spec in engines.items():
        max_c = int(spec.get("max_concurrent", 1))
        used = by_engine.get(eid, 0)
        slots.append(
            {
                "engine": eid,
                "used": used,
                "max": max_c,
                "free": max(0, max_c - used),
                "requires_gpu": bool(spec.get("requires_gpu")),
            }
        )
    max_ventures = int(profile.get("defaults", {}).get("max_active_ventures", 3))
    return {
        "running_ventures": running_ventures,
        "max_active_ventures": max_ventures,
        "ventures_free": max(0, max_ventures - running_ventures),
        "engine_slots": slots,
    }


def can_start_engine(agent_name: str, sessions: list[dict]) -> tuple[bool, str]:
    profile = load_workstation_profile()
    eid = engine_for_agent(agent_name)
    engines = profile.get("engines") or {}
    spec = engines.get(eid)
    if not spec:
        return True, ""
    usage = count_active_sessions(sessions)
    slot = next((s for s in usage["engine_slots"] if s["engine"] == eid), None)
    if slot and slot["used"] >= slot["max"]:
        return False, f"Engine '{eid}' at capacity ({slot['used']}/{slot['max']})"
    if usage["running_ventures"] >= usage["max_active_ventures"]:
        return (
            False,
            f"Max active ventures ({usage['max_active_ventures']}) reached",
        )
    return True, ""


def build_workstation_usage(sessions: list[dict]) -> dict[str, Any]:
    usage = count_active_sessions(sessions)
    profile = load_workstation_profile()
    return {
        **usage,
        "profile_defaults": profile.get("defaults", {}),
    }


def format_execution_bridge_tui(state: dict, *, plain_fn) -> str:
    """TUI strip for overview — capacity, sessions, queue."""
    usage = state.get("workstation_usage") or {}
    qsum = state.get("venture_queue_summary") or {}
    sessions = [
        s
        for s in state.get("terminal_sessions") or []
        if s.get("status") != "ended" and s.get("alive") is not False
    ]
    lines = ["[bold]Execution bridge[/bold]"]
    if usage:
        lines.append(
            f"Ventures {usage.get('running_ventures', 0)}/{usage.get('max_active_ventures', 3)} · "
            f"queue pending {qsum.get('pending_count', 0)}"
        )
        for slot in usage.get("engine_slots") or []:
            lines.append(f"  {slot['engine']}: {slot['used']}/{slot['max']}")
    for s in sessions[:4]:
        lines.append(
            f"  live {plain_fn(s.get('agent_name', '?'))} "
            f"{plain_fn(s.get('project_key') or '')} {plain_fn(s.get('task_id') or '')}"
        )
    if not sessions:
        lines.append("  [dim]No live executor sessions[/dim]")
    lines.append("[dim]End pane A: liaison observe-session complete ...[/dim]")
    return "\n".join(lines)
