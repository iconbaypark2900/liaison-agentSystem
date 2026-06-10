"""Command center data layer — registry, tasks, handoffs, engineering metrics."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from liaison_paths import AGENT_SYSTEM_DIR, LIAISON_DOCS_DIR

DOCS_HUB = LIAISON_DOCS_DIR.parent
COMMAND_CENTER_REFRESH_SEC = 30
DEBRIEF_STALE_DAYS_DEFAULT = 7

FLYWHEEL_INIT_COPY_CMDS = [
    "liaison init --workflow data-flywheel",
    'liaison init <task-id> "Flywheel cycle goal"',
]

# Orchestration chains from hub docs (orchestration-and-specialists.md, local-agents README)
HANDOFF_CHAINS = [
    {
        "name": "ML Intern → QCA → Hermes",
        "agents": ["ml_intern", "qca", "hermes"],
        "when": "Benchmark code → VLM plot review → integrate/PR",
    },
    {
        "name": "Unsloth → Hermes deploy",
        "agents": ["unsloth_studio", "hermes"],
        "when": "GPU fine-tune/export → vLLM/Ollama compose and git",
    },
    {
        "name": "Hermes → Liaison task",
        "agents": ["hermes", "liaison"],
        "when": "Exploratory work → governed vertical slice",
    },
    {
        "name": "Liaison plan → build → review → close",
        "agents": ["claude", "opencode", "claude", "opencode"],
        "when": "Phase executor lane for one slice",
    },
    {
        "name": "Hermes → QCA → Hermes",
        "agents": ["hermes", "qca", "hermes"],
        "when": "Ising/calibration routing and integration",
    },
]

PHASE_ROUTE_AGENTS = {
    "plan": "claude",
    "build": "opencode",
    "patch": "codex",
    "review": "claude",
    "close": "opencode",
}

_spark_flow = None


def _bridge():
    global _spark_flow
    if _spark_flow is None:
        from importlib.machinery import SourceFileLoader

        path = AGENT_SYSTEM_DIR / "bin" / "spark-flow"
        _spark_flow = SourceFileLoader("spark_flow_bridge", str(path)).load_module()
    return _spark_flow


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _age_hours(path: Path) -> float | None:
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 3600.0


def _format_age(hours: float | None) -> str:
    if hours is None:
        return "never"
    if hours < 1:
        return f"{int(hours * 60)}m ago"
    if hours < 48:
        return f"{hours:.1f}h ago"
    return f"{hours / 24:.1f}d ago"


def parse_phase_routing() -> dict:
    path = AGENT_SYSTEM_DIR / "registry" / "phase_routing.yaml"
    phases: dict[str, dict[str, str]] = {}
    if not path.exists():
        return phases
    current: str | None = None
    in_project = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "project_phases:":
            in_project = True
            continue
        if stripped.startswith("task_phases:"):
            in_project = False
            continue
        if not in_project:
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current = stripped[:-1]
            phases[current] = {}
        elif current and line.startswith("    ") and ":" in stripped:
            key, val = stripped.split(":", 1)
            phases[current][key.strip()] = val.strip().strip('"\'')
    return phases


def parse_capability_routes() -> list[dict]:
    path = AGENT_SYSTEM_DIR / "config" / "capability_routes.yaml"
    rows = []
    if not path.exists():
        return rows
    current: str | None = None
    fields: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "capabilities:":
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            if current and fields:
                rows.append({"capability": current, **fields})
            current = stripped[:-1]
            fields = {}
        elif current and line.startswith("    ") and ":" in stripped:
            key, val = stripped.split(":", 1)
            fields[key.strip()] = val.strip().strip('"\'')
    if current and fields:
        rows.append({"capability": current, **fields})
    return rows


def parse_validation_profiles() -> dict[str, dict]:
    path = AGENT_SYSTEM_DIR / "config" / "validation_profiles.yaml"
    profiles: dict[str, dict] = {}
    current: str | None = None
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "profiles:":
            continue
        if stripped == "command_center:":
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            if stripped == "command_center:":
                continue
            current = stripped[:-1]
            profiles[current] = {}
        elif current and line.startswith("    ") and ":" in stripped:
            key, val = stripped.split(":", 1)
            profiles[current][key.strip()] = val.strip().strip('"\'')
    return profiles


def parse_command_center_config() -> dict:
    """Command-center knobs from validation_profiles.yaml (command_center: block)."""
    path = AGENT_SYSTEM_DIR / "config" / "validation_profiles.yaml"
    cfg = {"debrief_stale_days": DEBRIEF_STALE_DAYS_DEFAULT}
    if not path.exists():
        return cfg
    in_block = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "command_center:":
            in_block = True
            continue
        if in_block:
            if not line.startswith("  ") or line.startswith("    "):
                if stripped and not stripped.startswith("#"):
                    break
                continue
            if ":" not in stripped:
                continue
            key, val = stripped.split(":", 1)
            if key.strip() == "debrief_stale_days":
                try:
                    cfg["debrief_stale_days"] = int(val.strip())
                except ValueError:
                    pass
    return cfg


def _freshest_debrief_hours() -> float | None:
    """Hours since the newest debrief markdown across registered repos."""
    best: float | None = None
    for repo in _bridge().parse_registered_repos():
        debrief_dir = repo / ".spark-flow" / "memory" / "debriefs"
        if not debrief_dir.exists():
            continue
        for path in debrief_dir.glob("*.md"):
            hours = _age_hours(path)
            if hours is not None and (best is None or hours < best):
                best = hours
    return best


def build_debrief_staleness() -> dict:
    cc = parse_command_center_config()
    stale_days = int(cc.get("debrief_stale_days") or DEBRIEF_STALE_DAYS_DEFAULT)
    hours = _freshest_debrief_hours()
    if hours is None:
        return {
            "last_debrief_age": "no debrief",
            "debrief_age_days": None,
            "debrief_stale": True,
            "debrief_stale_days": stale_days,
        }
    days = hours / 24.0
    return {
        "last_debrief_age": _format_age(hours),
        "debrief_age_days": round(days, 2),
        "debrief_stale": days > stale_days,
        "debrief_stale_days": stale_days,
    }


def enrich_hub_agents(raw: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Merge registry fields with hub doc paths."""
    enriched = {}
    for name, fields in raw.items():
        entry = dict(fields)
        entry.setdefault("status", "ready")
        if "hub_docs" not in entry:
            hub = DOCS_HUB / name.replace("_", "-")
            if hub.exists():
                entry["hub_docs"] = str(hub)
        enriched[name] = entry
    return enriched


def scan_handoffs(tasks: list[dict]) -> list[dict]:
    rows = []
    for task in tasks:
        if task.get("closed"):
            continue
        task_path = Path(task["path"])
        outbox = task_path / "outbox"
        approved = task_path / "approved"
        out_files = sorted(outbox.glob("*.md")) if outbox.exists() else []
        app_files = {p.name for p in approved.glob("*.md")} if approved.exists() else set()
        pending = [p for p in out_files if p.name not in app_files]
        for path in pending[:3]:
            rows.append(
                {
                    "task_id": task["task_id"],
                    "repo": Path(task["repo"]).name,
                    "artifact": path.name,
                    "status": "pending_approval",
                    "phase": task.get("current_phase", "?"),
                    "path": str(path),
                }
            )
        for path in sorted(approved.glob("*.md"))[:2] if approved.exists() else []:
            rows.append(
                {
                    "task_id": task["task_id"],
                    "repo": Path(task["repo"]).name,
                    "artifact": path.name,
                    "status": "approved",
                    "phase": task.get("current_phase", "?"),
                    "path": str(path),
                }
            )
    return rows[:20]


REPORTER_STEP_KEYS = ("init", "snapshot", "attach", "approve", "validate", "close")


def build_workflow_next_action(task: dict | None) -> dict[str, str] | None:
    """When reporter steps are done except close, suggest close-task (copy-only hint)."""
    if not task:
        return None
    steps = task.get("reporter_steps") or {}
    if not steps:
        return None
    if steps.get("close"):
        return None
    for key in REPORTER_STEP_KEYS:
        if key == "close":
            continue
        if not steps.get(key):
            return None
    task_id = task.get("task_id") or ""
    if not task_id:
        return None
    cmd = f'liaison close-task --summary "Slice ready to close"'
    return {
        "action": "close-task",
        "liaison_cmd": cmd,
        "hint": "All reporter steps complete except close — run close-task when ready.",
        "task_id": task_id,
    }


def probe_reporter_steps(task_path: Path) -> dict[str, bool]:
    """Filesystem signals for reporter checklist (init → close)."""
    td = Path(task_path)
    state_file = td / "STATE.txt"
    phase = "unknown"
    if state_file.exists():
        for line in state_file.read_text(errors="replace").splitlines():
            if line.startswith("CURRENT_PHASE:"):
                phase = line.split(":", 1)[1].strip()
                break
    outbox = td / "outbox"
    approved = td / "approved"
    out_files = sorted(outbox.glob("*.md")) if outbox.exists() else []
    app_names = {p.name for p in approved.glob("*.md")} if approved.exists() else set()
    pending_outbox = [p for p in out_files if p.name not in app_names]
    gate_ok = False
    gate_file = td / "GATE_REPORT.md"
    if gate_file.exists():
        gate_ok = "- FAIL:" not in gate_file.read_text(errors="replace")
    return {
        "init": (td / "BRIEF.md").exists(),
        "snapshot": (td / "CONTEXT.md").exists()
        or (td / "context" / "reporter.manifest.json").exists(),
        "attach": len(out_files) > 0,
        "approve": len(app_names) > 0 and len(pending_outbox) == 0,
        "validate": gate_ok,
        "close": (td / "CLOSEOUT.md").exists() or phase == "complete",
    }


def enrich_task_with_reporter_steps(task: dict) -> dict:
    enriched = dict(task)
    path = task.get("path")
    if path:
        enriched["reporter_steps"] = probe_reporter_steps(Path(path))
        from dashboard.command_center.execution_bridge import latest_executor_outcome
        from dashboard.command_center.terminal_sessions import sessions_for_task

        task_path = Path(path)
        enriched["last_executor_outcome"] = latest_executor_outcome(task_path)
        bound = sessions_for_task(task.get("task_id", ""))
        enriched["bound_agent"] = bound[0].get("agent_name") if bound else None
    else:
        enriched["reporter_steps"] = {
            k: False for k in ("init", "snapshot", "attach", "approve", "validate", "close")
        }
        enriched["last_executor_outcome"] = None
        enriched["bound_agent"] = None
    return enriched


REPORTER_STEP_STATE_FILE = "reporter_step_state.json"


def reporter_step_state_path(task_path: Path) -> Path:
    return Path(task_path) / REPORTER_STEP_STATE_FILE


def default_reporter_step_state() -> dict:
    return {
        "current_step_id": "init",
        "completed_steps": [],
        "updated_at": _now(),
    }


def load_reporter_step_state_file(task_path: Path) -> dict:
    path = reporter_step_state_path(task_path)
    if not path.exists():
        return default_reporter_step_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_reporter_step_state()
    current = str(raw.get("current_step_id") or "init")
    if current not in REPORTER_STEP_KEYS:
        current = "init"
    completed = [s for s in (raw.get("completed_steps") or []) if s in REPORTER_STEP_KEYS]
    return {
        "current_step_id": current,
        "completed_steps": list(dict.fromkeys(completed)),
        "updated_at": raw.get("updated_at") or _now(),
    }


def save_reporter_step_state_file(task_path: Path, state: dict) -> None:
    """Persist reporter step state; skip write when content unchanged (idempotent)."""
    normalized = {
        "current_step_id": state["current_step_id"],
        "completed_steps": list(state.get("completed_steps") or []),
        "updated_at": _now(),
    }
    path = reporter_step_state_path(task_path)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if (
                existing.get("current_step_id") == normalized["current_step_id"]
                and existing.get("completed_steps") == normalized["completed_steps"]
            ):
                return
        except (OSError, json.JSONDecodeError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")


def next_reporter_step_id(step_id: str) -> str | None:
    try:
        idx = REPORTER_STEP_KEYS.index(step_id)
    except ValueError:
        return None
    if idx + 1 >= len(REPORTER_STEP_KEYS):
        return None
    return REPORTER_STEP_KEYS[idx + 1]


def reporter_step_is_complete(step_id: str, probe: dict, completed: list[str]) -> bool:
    return step_id in completed or bool(probe.get(step_id))


def merge_reporter_step_state(task_path: Path) -> dict:
    """Merge disk state file with filesystem probe signals."""
    probe = probe_reporter_steps(task_path)
    raw = load_reporter_step_state_file(task_path)
    completed = list(dict.fromkeys(raw.get("completed_steps") or []))
    for step in REPORTER_STEP_KEYS:
        if probe.get(step) and step not in completed:
            completed.append(step)
    current = raw.get("current_step_id") or "init"
    allowed_next: list[str] = []
    if reporter_step_is_complete(current, probe, completed):
        nxt = next_reporter_step_id(current)
        if nxt:
            allowed_next.append(nxt)
    return {
        "current_step_id": current,
        "completed_steps": completed,
        "allowed_next": allowed_next,
        "updated_at": raw.get("updated_at"),
        "task_id": task_path.name,
    }


def build_reporter_step_state_for_task(task: dict | None) -> dict | None:
    if not task:
        return None
    path = task.get("path")
    if not path:
        return None
    return merge_reporter_step_state(Path(path))


def reporter_step_show(task_path: Path) -> dict:
    merged = merge_reporter_step_state(task_path)
    print(f"Task: {task_path.name}")
    print(f"Current step: {merged['current_step_id']}")
    print(f"Completed: {', '.join(merged['completed_steps']) or '(none)'}")
    if merged["allowed_next"]:
        print(f"Allowed next: {', '.join(merged['allowed_next'])}")
    else:
        print("Allowed next: (complete current step first, or at final step)")
    probe = probe_reporter_steps(task_path)
    print("Probe (filesystem):")
    for key in REPORTER_STEP_KEYS:
        mark = "✓" if probe.get(key) else "○"
        print(f"  {mark} {key}")
    return merged


def reporter_step_set(
    task_path: Path,
    step_id: str,
    *,
    mark_complete: bool = False,
) -> dict:
    step_id = step_id.lower()
    if step_id not in REPORTER_STEP_KEYS:
        raise ValueError(f"Unknown step '{step_id}'. Known: {', '.join(REPORTER_STEP_KEYS)}")
    state = load_reporter_step_state_file(task_path)
    probe = probe_reporter_steps(task_path)
    completed = list(dict.fromkeys(state.get("completed_steps") or []))
    for step in REPORTER_STEP_KEYS:
        if probe.get(step) and step not in completed:
            completed.append(step)
    state["current_step_id"] = step_id
    if mark_complete and step_id not in completed:
        completed.append(step_id)
    state["completed_steps"] = completed
    save_reporter_step_state_file(task_path, state)
    return merge_reporter_step_state(task_path)


def reporter_step_advance(task_path: Path, *, force: bool = False) -> dict:
    state = load_reporter_step_state_file(task_path)
    probe = probe_reporter_steps(task_path)
    completed = list(dict.fromkeys(state.get("completed_steps") or []))
    for step in REPORTER_STEP_KEYS:
        if probe.get(step) and step not in completed:
            completed.append(step)
    current = state.get("current_step_id") or "init"
    if not reporter_step_is_complete(current, probe, completed) and not force:
        raise ValueError(
            f"Step '{current}' is not complete. Run reporter-step set --complete {current} "
            f"or satisfy filesystem probes, or pass --force."
        )
    if current not in completed:
        completed.append(current)
    nxt = next_reporter_step_id(current)
    if not nxt:
        state["completed_steps"] = completed
        save_reporter_step_state_file(task_path, state)
        return merge_reporter_step_state(task_path)
    state["current_step_id"] = nxt
    state["completed_steps"] = completed
    save_reporter_step_state_file(task_path, state)
    return merge_reporter_step_state(task_path)


def count_flywheel_open_tasks(tasks: list[dict]) -> int:
    n = 0
    for task in tasks:
        if task.get("closed"):
            continue
        tid = (task.get("task_id") or "").lower()
        desc = (task.get("description") or "").lower()
        if "flywheel" in tid or "data-flywheel" in desc or "data_flywheel" in desc:
            n += 1
    return n


def resolve_workload_id(focus_path: str | None) -> str | None:
    """L5 flywheel workload tag from env or focused repo PROJECT_PHASE.md."""
    for key in ("LIAISON_WORKLOAD_ID", "FLYWHEEL_WORKLOAD_ID"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    if not focus_path:
        return None
    phase_md = Path(focus_path).expanduser() / ".spark-flow" / "memory" / "PROJECT_PHASE.md"
    if not phase_md.exists():
        return None
    for line in phase_md.read_text(errors="replace").splitlines():
        match = re.match(r"^\s*workload_id\s*:\s*(.+)$", line, re.I)
        if not match:
            continue
        raw = match.group(1).strip()
        if raw.startswith("<!--"):
            inner = re.sub(r"<!--\s*|\s*-->", "", raw).strip()
            if "(" in inner:
                inner = inner.split("(", 1)[0].strip()
            if not inner or inner.lower() in {"project-workload-v1", "—"}:
                continue
            return inner
        if not raw or raw.lower().startswith("project-workload-v1"):
            continue
        return raw.split()[0]
    return None


def build_suggested_workflow_commands(next_workflow_step: dict | None) -> list[str]:
    """Copy-only liaison commands for the active workflow phase (not auto-exec)."""
    if not next_workflow_step:
        return []
    return list(next_workflow_step.get("suggested_liaison_commands") or [])[:8]


def format_gate_strip_tui(state: dict) -> str:
    """Compact 1–2 line gate strip mirroring web GateStrip signals."""
    summary = state.get("summary") or {}
    focus = state.get("focus")
    parts: list[str] = []
    if focus:
        parts.append(f"phase {focus.get('lifecycle', '—')}/{focus.get('phase', '—')}")
    else:
        parts.append("phase —")
    blockers = int(summary.get("blockers") or 0)
    gate_fail = int((state.get("engineering_metrics") or {}).get("gate_failures") or 0)
    if blockers or gate_fail:
        val = "fail"
    elif focus and focus.get("validation") == "required":
        val = "warn"
    else:
        val = "pass"
    parts.append(f"validate {val}")
    parts.append(f"blocked {blockers}")
    if state.get("selected_project") and state.get("project_intake"):
        ready = summary.get("intake_ready")
        parts.append(f"intake {'ready' if ready else 'blocked'}")
        if ready:
            if summary.get("ready_to_build_strict"):
                parts.append("build strict")
            elif summary.get("ready_to_build_soft"):
                parts.append("build soft")
            else:
                parts.append("build pending")
    flywheel = int(summary.get("flywheel_open") or 0)
    if flywheel:
        parts.append(f"flywheel {flywheel}")
    workload = summary.get("workload_id")
    if workload:
        parts.append(f"workload {workload[:28]}")
    usage = state.get("workstation_usage") or {}
    if usage:
        parts.append(
            f"slots {usage.get('running_ventures', 0)}/{usage.get('max_active_ventures', 3)}"
        )
    pending = int((state.get("venture_queue_summary") or {}).get("pending_count") or 0)
    if pending:
        parts.append(f"queue {pending}")
    if summary.get("executor_session_stale"):
        parts.append(f"stale {summary.get('executor_session_stale_count', 1)}")
    live = [
        s
        for s in state.get("terminal_sessions") or []
        if s.get("alive") is not False and s.get("status") != "ended"
    ]
    for session in live[:2]:
        parts.append(f"{session.get('agent_name', '?')} live")
    eng = state.get("engineering_metrics") or {}
    debrief = eng.get("last_debrief_age") or "—"
    if eng.get("debrief_stale"):
        debrief = f"{debrief} [red]STALE[/red]"
    line2 = (
        f"{state.get('env', 'LOCAL')} · {state.get('user', 'operator')} · debrief {debrief}"
    )
    return f"[bold]GATES[/bold] {' · '.join(parts)}\n[dim]{line2}[/dim]"


def resolve_active_task_id(
    requested: str | None,
    open_tasks: list[dict],
) -> str | None:
    if not open_tasks:
        return None
    if requested:
        for task in open_tasks:
            if task.get("task_id") == requested:
                return requested
    return open_tasks[0].get("task_id")


def scan_debriefs() -> list[dict]:
    rows = []
    for repo in _bridge().parse_registered_repos():
        mem = repo / ".spark-flow" / "memory"
        debrief_dir = mem / "debriefs"
        if debrief_dir.exists():
            for path in sorted(debrief_dir.glob("*.md"), reverse=True)[:2]:
                rows.append(
                    {
                        "repo": repo.name,
                        "file": path.name,
                        "age": _format_age(_age_hours(path)),
                        "path": str(path),
                    }
                )
        cs = mem / "current_state.md"
        if cs.exists():
            rows.append(
                {
                    "repo": repo.name,
                    "file": "current_state.md",
                    "age": _format_age(_age_hours(cs)),
                    "path": str(cs),
                }
            )
    return rows[:12]


def count_task_modes(tasks: list[dict]) -> dict[str, int]:
    reporter = 0
    executor = 0
    for task in tasks:
        if task.get("closed"):
            continue
        task_path = Path(task["path"])
        if (task_path / "context" / "reporter.manifest.json").exists():
            reporter += 1
        elif any((task_path / phase).exists() for phase in ("plan", "build", "patch", "review", "close")):
            executor += 1
        else:
            reporter += 1
    return {"reporter": reporter, "executor": executor}


def active_git_branches() -> list[str]:
    branches = []
    sf = _bridge()
    for repo in sf.parse_registered_repos():
        if not (repo / ".git").exists():
            continue
        try:
            out = subprocess.check_output(
                ["git", "-C", str(repo), "branch", "--show-current"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).strip()
            if out:
                branches.append(f"{repo.name}:{out}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return branches[:12]


def build_engineering_metrics(state: dict) -> dict:
    tasks = state["tasks"]
    open_tasks = state["open_tasks"]
    profiles = parse_validation_profiles()
    repos = state["registered_projects"]

    by_repo: Counter[str] = Counter()
    by_phase: Counter[str] = Counter()
    for task in open_tasks:
        by_repo[Path(task["repo"]).name] += 1
        by_phase[task.get("current_phase", "unknown")] += 1

    gate_fail = sum(1 for t in open_tasks if t.get("gate_status") == "fail")
    score_fail = sum(1 for t in open_tasks if t.get("score_status") == "fail")
    handoffs = scan_handoffs(tasks)
    pending_handoffs = sum(1 for h in handoffs if h["status"] == "pending_approval")

    repos_with_profile = sum(
        1 for _, f in repos.items() if f.get("default_profile") and f.get("default_profile") != "none"
    )
    profile_names = set(f.get("default_profile", "") for f in repos.values() if f.get("default_profile"))

    memory_dir = AGENT_SYSTEM_DIR / "memory"
    learnings = list(memory_dir.glob("*.learning.md")) if memory_dir.exists() else []
    last_learning = max(learnings, key=lambda p: p.stat().st_mtime) if learnings else None

    debrief_meta = build_debrief_staleness()
    debrief_rows = scan_debriefs()

    modes = count_task_modes(tasks)
    branches = active_git_branches()

    return {
        "open_by_repo": dict(by_repo.most_common(8)),
        "open_by_phase": dict(by_phase.most_common()),
        "validation_profiles_defined": len(profiles),
        "repos_with_profile": repos_with_profile,
        "repos_registered": len(repos),
        "profiles_in_use": sorted(p for p in profile_names if p),
        "gate_failures": gate_fail,
        "score_failures": score_fail,
        "pending_handoffs": pending_handoffs,
        "approved_handoffs": sum(1 for h in handoffs if h["status"] == "approved"),
        "promoted_learnings": len(learnings),
        "last_learning_age": _format_age(_age_hours(last_learning)) if last_learning else "none",
        "last_debrief_age": debrief_meta["last_debrief_age"],
        "debrief_age_days": debrief_meta["debrief_age_days"],
        "debrief_stale": debrief_meta["debrief_stale"],
        "debrief_stale_days": debrief_meta["debrief_stale_days"],
        "reporter_tasks": modes["reporter"],
        "executor_tasks": modes["executor"],
        "active_branches": branches,
        "capability_routes": len(parse_capability_routes()),
    }


def phase_recommendations(state: dict) -> list[dict]:
    recs = []
    routing = parse_phase_routing()
    open_count = len(state["open_tasks"])
    default_phase = "prototype"
    if routing:
        default_phase = next(iter(routing.keys()), "prototype")
    for phase_name, fields in routing.items():
        recs.append(
            {
                "kind": "project_phase",
                "label": f"{fields.get('label', phase_name)}: {fields.get('liaison_focus', '')[:60]}",
                "phase": phase_name,
                "validation": fields.get("validation", "?"),
            }
        )
    caps = parse_capability_routes()
    for cap in caps[:4]:
        recs.append(
            {
                "kind": "capability",
                "label": cap.get("description", cap["capability"])[:72],
                "capability": cap["capability"],
            }
        )
    for rec in state.get("recommendations", [])[:3]:
        recs.append({"kind": "debrief", "label": rec.get("label", ""), "agents": rec.get("agents", [])})
    if open_count > 4:
        recs.insert(
            0,
            {
                "kind": "ops",
                "label": f"{open_count} open tasks — run liaison index-tasks --refresh",
            },
        )
    return recs[:10]


READONLY_LIAISON_CMDS = frozenset(
    {
        "liaison status",
        "liaison registry agents",
        "liaison registry repos",
        "liaison debrief --show",
        "liaison look",
        "liaison index-tasks --show",
        "liaison doctor",
        "liaison plan-next --show",
        "liaison memory-report --limit 5",
        "liaison trend-report --show",
    }
)

DESTRUCTIVE_LIAISON_MARKERS = (
    "approve-artifact",
    "reject-artifact",
    "close-task",
    "promote-learning",
    " attach ",
    " init ",
    " choose ",
)


def liaison_cmd_is_readonly(cmd: str) -> bool:
    normalized = " ".join(cmd.strip().split())
    if normalized in READONLY_LIAISON_CMDS:
        return True
    if normalized.startswith("liaison registry "):
        return True
    return False


def liaison_cmd_is_destructive(cmd: str) -> bool:
    lower = f" {cmd.strip().lower()} "
    return any(marker in lower for marker in DESTRUCTIVE_LIAISON_MARKERS)


AGENT_LAUNCH_MARKERS = (
    "hermes ",
    "qca ",
    "ml-intern",
    "unsloth",
    "codex ",
    "opencode ",
    "claude ",
)


AGENT_BINARIES = frozenset(
    {"hermes", "qca", "codex", "claude", "ml-intern", "unsloth", "opencode"}
)


def liaison_cmd_contains_agent_launch(cmd: str) -> bool:
    lower = cmd.strip().lower()
    for segment in re.split(r"[;&|]+", lower):
        seg = segment.strip()
        if not seg:
            continue
        if any(marker in seg for marker in AGENT_LAUNCH_MARKERS):
            return True
        first = seg.split()[0] if seg.split() else ""
        if first in AGENT_BINARIES:
            return True
    return False


def _repo_cwd_for_project(project: str | None) -> Path | None:
    if not project:
        return None
    focus = build_focus(project)
    path = focus.get("path") if focus else None
    if path:
        return Path(path)
    return None


def _open_task_dirs_for_project(project: str | None) -> list[Path]:
    repo = _repo_cwd_for_project(project)
    if not repo:
        return []
    tasks_dir = repo / ".spark-flow" / "tasks"
    if not tasks_dir.is_dir():
        return []
    open_dirs: list[Path] = []
    for td in sorted(tasks_dir.iterdir()):
        if not td.is_dir():
            continue
        if (td / "CLOSEOUT.md").exists():
            continue
        state = td / "STATE.txt"
        if state.exists():
            text = state.read_text(errors="replace")
            if "CLOSED: true" in text or "CURRENT_PHASE: complete" in text:
                continue
        open_dirs.append(td)
    return open_dirs


def _task_outbox_for_project(project: str | None, task_id: str | None = None) -> Path | None:
    if task_id:
        repo = _repo_cwd_for_project(project)
        if not repo:
            return None
        outbox = repo / ".spark-flow" / "tasks" / task_id / "outbox"
        return outbox if outbox.is_dir() else None
    for td in _open_task_dirs_for_project(project):
        outbox = td / "outbox"
        if outbox.is_dir():
            return outbox
    return None


def liaison_cmd_is_allowlisted(cmd: str, project: str | None = None) -> tuple[bool, str]:
    """Return (allowed, reason). Safe writes: start-pattern scaffold, init with registered project."""
    normalized = " ".join(cmd.strip().split())
    if not normalized:
        return False, "empty command"
    if liaison_cmd_contains_agent_launch(normalized):
        return False, "agent launch lines must run in terminal, not browser"
    if liaison_cmd_is_readonly(normalized):
        return True, ""

    try:
        parts = shlex.split(normalized)
    except ValueError as exc:
        return False, f"invalid command: {exc}"

    if len(parts) < 2 or parts[0] != "liaison":
        return False, "command must start with liaison"

    sub = parts[1]

    if sub == "validate":
        profiles = parse_validation_profiles()
        if "--profile" not in parts:
            return False, "validate requires --profile"
        idx = parts.index("--profile")
        if idx + 1 >= len(parts):
            return False, "validate requires profile name"
        profile = parts[idx + 1]
        if profile != "none" and profile not in profiles:
            return False, f"unknown validation profile: {profile}"
        if not project:
            return False, "validate requires focused ?project="
        if not _repo_cwd_for_project(project):
            return False, f"unknown or unregistered project: {project}"
        return True, ""

    if sub == "approve-artifact":
        if len(parts) < 3:
            return False, "approve-artifact requires artifact path"
        artifact = parts[2]
        if ".." in artifact or artifact.startswith("/"):
            return False, "approve-artifact must be a relative outbox filename"
        if not artifact.endswith(".md"):
            return False, "approve-artifact must target an outbox .md file"
        if not project:
            return False, "approve-artifact requires focused ?project="
        outbox = _task_outbox_for_project(project)
        if not outbox:
            return False, "no open task outbox found for project"
        candidate = (outbox / Path(artifact).name).resolve()
        if not candidate.is_relative_to(outbox.resolve()) or not candidate.exists():
            return False, f"artifact not in current task outbox: {artifact}"
        return True, ""

    if sub == "close-task":
        if not project:
            return False, "close-task requires focused ?project="
        repo = _repo_cwd_for_project(project)
        if not repo:
            return False, f"unknown or unregistered project: {project}"
        ready = False
        for td in _open_task_dirs_for_project(project):
            enriched = enrich_task_with_reporter_steps({"task_id": td.name, "path": str(td)})
            if build_workflow_next_action(enriched):
                ready = True
                break
        if not ready:
            return False, "close-task blocked: reporter steps not ready (all except close required)"
        return True, ""

    if liaison_cmd_is_destructive(normalized):
        return False, "destructive command not allowlisted for browser execution"

    if sub == "start-pattern":
        from dashboard.command_center.hub_skills import build_project_agent_patterns

        if "--list" in parts or (len(parts) == 2 and parts[1] == "start-pattern"):
            return True, ""
        pattern_ids = {p["id"] for p in build_project_agent_patterns()}
        if len(parts) < 3 or parts[2].startswith("-"):
            return False, "start-pattern requires a pattern id"
        if parts[2] not in pattern_ids:
            return False, f"unknown pattern: {parts[2]}"
        return True, ""

    if sub == "init":
        if not project:
            return False, "init requires registered ?project= key"
        focus = build_focus(project)
        if not focus or not focus.get("path"):
            return False, f"unknown or unregistered project: {project}"
        if len(parts) < 4:
            return False, "init requires task_id and description"
        return True, ""

    return False, "command not on browser allowlist"


def run_allowlisted_liaison_cmd(
    cmd: str,
    *,
    project: str | None = None,
    cwd: Path | None = None,
    timeout: int = 120,
) -> dict:
    """Execute an allowlisted liaison command; returns {ok, output, cmd}."""
    allowed, reason = liaison_cmd_is_allowlisted(cmd, project=project)
    if not allowed:
        return {"ok": False, "output": reason, "cmd": cmd}

    normalized = " ".join(cmd.strip().split())
    try:
        parts = shlex.split(normalized)
    except ValueError as exc:
        return {"ok": False, "output": str(exc), "cmd": cmd}

    liaison_bin = AGENT_SYSTEM_DIR / "bin" / "liaison"
    executable = str(liaison_bin) if liaison_bin.exists() else parts[0]
    argv = [executable, *parts[1:]] if parts[0] == "liaison" else parts
    run_cwd = cwd or _repo_cwd_for_project(project) or AGENT_SYSTEM_DIR

    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(run_cwd),
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        if not output:
            output = f"(exit {result.returncode}, no output)"
        return {"ok": result.returncode == 0, "output": output, "cmd": normalized}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"timeout after {timeout}s", "cmd": normalized}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "output": f"Error: {exc}", "cmd": normalized}


def run_reporter_step_advance_browser(
    project: str,
    *,
    task_id: str | None = None,
) -> dict:
    """Browser-safe reporter-step advance (no --force). Requires project plan opt-in."""
    from dashboard.command_center.project_plans import load_project_plan

    cmd_label = "liaison reporter-step advance"
    if not project:
        return {"ok": False, "output": "project is required", "cmd": cmd_label}
    plan = load_project_plan(project)
    if not plan or not plan.get("reporter_auto_advance"):
        return {
            "ok": False,
            "output": "reporter_auto_advance is not enabled in registry/project_plans.yaml",
            "cmd": cmd_label,
        }
    open_dirs = _open_task_dirs_for_project(project)
    if not open_dirs:
        return {"ok": False, "output": "no open tasks for project", "cmd": cmd_label}
    task_path: Path | None = None
    if task_id:
        for td in open_dirs:
            if td.name == task_id:
                task_path = td
                break
        if not task_path:
            return {"ok": False, "output": f"open task not found: {task_id}", "cmd": cmd_label}
    else:
        task_path = open_dirs[0]

    merged_before = merge_reporter_step_state(task_path)
    if not merged_before.get("allowed_next"):
        current = merged_before.get("current_step_id", "init")
        return {
            "ok": False,
            "output": (
                f"Step '{current}' is not complete — finish the current reporter step before advance"
            ),
            "cmd": cmd_label,
        }
    if merged_before.get("current_step_id") == "approve":
        probe = probe_reporter_steps(task_path)
        if probe.get("attach") and not probe.get("approve"):
            return {
                "ok": False,
                "output": "approve step: all outbox artifacts must be approved before advance",
                "cmd": cmd_label,
            }

    try:
        merged = reporter_step_advance(task_path, force=False)
    except ValueError as exc:
        return {"ok": False, "output": str(exc), "cmd": cmd_label}
    lines = [f"Reporter step advanced: current={merged['current_step_id']}"]
    if merged.get("allowed_next"):
        lines.append(f"Allowed next: {', '.join(merged['allowed_next'])}")
    return {"ok": True, "output": "\n".join(lines), "cmd": cmd_label, "state": merged}


def build_metrics_rows(state: dict) -> list[dict]:
    """Interactive Ops metrics + cross-pollination rows for ListView."""
    e = state["engineering_metrics"]
    summary = state["summary"]
    rows: list[dict] = []

    def add(
        row_id: str,
        label: str,
        detail: str,
        *,
        path: str | None = None,
        liaison_cmd: str | None = None,
    ) -> None:
        rows.append(
            {
                "id": row_id,
                "label": label,
                "detail": detail,
                "path": path,
                "liaison_cmd": liaison_cmd,
            }
        )

    add(
        "metric:open_tasks",
        f"Open {summary['open_tasks']} / {summary['total_tasks']} tasks",
        f"Closed {summary['closed_tasks']} · blockers {summary['blockers']}",
        liaison_cmd="liaison index-tasks --show",
    )
    if e.get("open_by_repo"):
        add(
            "metric:by_repo",
            f"By repo: {e['open_by_repo']}",
            "Open tasks grouped by registered project repo.",
            liaison_cmd="liaison look",
        )
    if e.get("open_by_phase"):
        add(
            "metric:by_phase",
            f"By phase: {e['open_by_phase']}",
            "Task phases: plan, build, patch, review, close.",
            liaison_cmd="liaison status",
        )
    add(
        "metric:validation",
        f"Validation {e['repos_with_profile']}/{e['repos_registered']} repos · "
        f"{e['validation_profiles_defined']} profiles",
        f"Profiles in use: {', '.join(e['profiles_in_use']) or 'none'}",
        path=str(AGENT_SYSTEM_DIR / "config" / "validation_profiles.yaml"),
        liaison_cmd="liaison registry repos",
    )
    add(
        "metric:gates",
        f"Gates {e['gate_failures']} fail · Scores {e['score_failures']} fail",
        "Run gate/score checks per task before closeout.",
        liaison_cmd="liaison status",
    )
    add(
        "metric:handoffs",
        f"Handoffs {e['pending_handoffs']} pending · {e['approved_handoffs']} approved",
        "Pending artifacts live under .spark-flow/tasks/<id>/outbox/",
        liaison_cmd="liaison look",
    )
    add(
        "metric:memory",
        f"Memory {e['promoted_learnings']} learnings · {e['last_learning_age']}",
        f"Promoted learnings in {AGENT_SYSTEM_DIR / 'memory'}",
        path=str(AGENT_SYSTEM_DIR / "memory"),
        liaison_cmd="liaison memory-report --limit 5",
    )
    add(
        "metric:debrief",
        f"Debrief {e['last_debrief_age']}",
        "Latest repo memory debrief age across registered projects.",
        liaison_cmd="liaison debrief --show",
    )
    add(
        "metric:modes",
        f"Modes reporter={e['reporter_tasks']} executor={e['executor_tasks']}",
        "Reporter vs executor lane counts for open tasks.",
        liaison_cmd="liaison status",
    )
    branches = ", ".join(e["active_branches"][:4]) or "—"
    add(
        "metric:branches",
        f"Branches: {branches}",
        "Active git branches on registered repos.",
        liaison_cmd="liaison look",
    )
    add(
        "metric:capability_routes",
        f"Capability routes: {e['capability_routes']}",
        "Routes from config/capability_routes.yaml",
        path=str(AGENT_SYSTEM_DIR / "config" / "capability_routes.yaml"),
    )

    for idx, rec in enumerate(state.get("skills_panel", {}).get("recommendations", [])[:4]):
        add(
            f"rec:{idx}",
            f"[{rec.get('kind', '?')}] {str(rec.get('label', ''))[:52]}",
            str(rec.get("label", "")),
            liaison_cmd="liaison plan-next --show" if rec.get("kind") == "ops" else "liaison debrief --show",
        )

    for idx, row in enumerate(state.get("cross_pollination", [])[:8]):
        add(
            f"cross:{idx}",
            f"[{row['type']}] {str(row['text'])[:52]}",
            str(row["text"]),
            liaison_cmd="liaison trend-report --show" if row["type"] == "trend" else None,
        )

    return rows


def _overview_action_how_to(action_id: str, state: dict) -> str:
    project = state.get("selected_project")
    hints = {
        "action:sync": (
            "Pulls fresh JSON from disk (tasks, project matrix, intake, ops signoff). "
            "In the web UI use Sync liaison; in TUI press r."
        ),
        "action:look": (
            "Lists open tasks and pending outbox artifacts across focused repos. "
            "Start here before approve-artifact or close-task."
        ),
        "action:pick-project": (
            "Workstream tab → project list (↑↓ Enter). Focus wires intake, plan, hub, and ops to one registry key."
        ),
        "action:intake": (
            f"Scores readiness for {project or 'project'} — blockers must clear before executor agents launch in terminal."
        ),
        "action:plan": (
            "Writes PROJECT_OPERATING_PLAN.md from registry defaults (workflow, pattern, validation profile, gates)."
        ),
        "action:hub": (
            "Opens hub context for the focused phase — launch Hermes or specialists, then attach reports via liaison."
        ),
        "action:next-fix": "Copy and run the top intake blocker command, then re-run intake until ready_to_build.",
        "action:plan-show": "Prints plan gates and engineering commands without writing files.",
    }
    return hints.get(action_id, "")


def build_overview_actions(state: dict) -> list[dict]:
    """Actionable rows for Overview tab (TUI + web)."""
    project = state.get("selected_project")
    focus = state.get("focus") or {}
    actions: list[dict] = [
        {
            "id": "action:sync",
            "label": "Sync liaison state",
            "detail": "Re-read tasks, matrix, intake, and metrics from disk.",
            "how_to": _overview_action_how_to("action:sync", state),
            "liaison_cmd": "liaison command-center --json",
            "kind": "refresh",
        },
        {
            "id": "action:look",
            "label": "Open task inbox",
            "detail": "Show open tasks and pending handoffs.",
            "how_to": _overview_action_how_to("action:look", state),
            "liaison_cmd": "liaison look",
        },
    ]
    if project:
        actions.extend(
            [
                {
                    "id": "action:intake",
                    "label": f"Run intake · {project}",
                    "detail": "Score project readiness before build executors.",
                    "how_to": _overview_action_how_to("action:intake", state),
                    "liaison_cmd": f"liaison project-intake --project {project} --show",
                },
                {
                    "id": "action:plan",
                    "label": f"Write operating plan · {project}",
                    "detail": "Materialize PROJECT_OPERATING_PLAN.md from registry defaults.",
                    "how_to": _overview_action_how_to("action:plan", state),
                    "liaison_cmd": f"liaison plan-project --project {project} --write",
                },
                {
                    "id": "action:hub",
                    "label": f"Open hub focus · {project}",
                    "detail": f"Phase {focus.get('phase', '—')} · agents {', '.join(focus.get('recommended_agents') or []) or '—'}",
                    "how_to": _overview_action_how_to("action:hub", state),
                    "liaison_cmd": f"liaison command-center --project {project}",
                },
            ]
        )
        intake = state.get("project_intake")
        if intake and not intake.get("ready_to_build"):
            blockers = intake.get("blockers") or []
            if blockers and blockers[0].get("liaison_cmd"):
                actions.append(
                    {
                        "id": "action:next-fix",
                        "label": "Copy next intake fix",
                        "detail": blockers[0].get("label", "Resolve top blocker"),
                        "how_to": _overview_action_how_to("action:next-fix", state),
                        "liaison_cmd": blockers[0]["liaison_cmd"],
                    }
                )
    else:
        actions.append(
            {
                "id": "action:pick-project",
                "label": "Select a project in Workstream",
                "detail": "Focus links intake, plan, hub, and ops panels.",
                "how_to": _overview_action_how_to("action:pick-project", state),
                "liaison_cmd": "liaison registry repos",
            }
        )
    plan = state.get("project_plan")
    if plan and plan.get("liaison_cmd_write"):
        actions.append(
            {
                "id": "action:plan-show",
                "label": "Show operating plan gates",
                "detail": (plan.get("intent") or "")[:120],
                "how_to": _overview_action_how_to("action:plan-show", state),
                "liaison_cmd": plan["liaison_cmd_write"].replace(" --write", " --show"),
                "path": plan.get("on_disk_path"),
            }
        )
    for action in actions:
        if not action.get("how_to"):
            action["how_to"] = _overview_action_how_to(action["id"], state)
    return actions


def build_ops_signoff(state: dict) -> dict:
    """Ops tab signoff bundle — handoffs, blockers, checklist."""
    handoffs = state.get("handoffs", [])
    debriefs = state.get("debriefs", [])
    eng = state.get("engineering_metrics", {})
    summary = state.get("summary", {})
    pending = [h for h in handoffs if h.get("status") == "pending_approval"]
    gate_fail = eng.get("gate_failures", 0)
    flywheel = summary.get("flywheel_open", 0)
    blockers = summary.get("blockers", 0)
    launch_ready = summary.get("executor_launch_ready", summary.get("ready_to_build", False))
    soft_ready = summary.get("ready_to_build_soft", False)
    strict_ready = summary.get("ready_to_build_strict", summary.get("ready_to_build", False))

    intake_label = "Project intake ready to build"
    if state.get("selected_project") and not strict_ready and soft_ready:
        intake_label = "Project intake soft-ready (warnings remain)"
    elif state.get("selected_project") and not launch_ready:
        intake_label = "Project intake blocked for executors"

    checklist: list[dict] = [
        {
            "id": "signoff:handoffs",
            "label": f"Clear {len(pending)} pending handoff(s)",
            "done": len(pending) == 0,
            "liaison_cmd": "liaison look",
            "detail": "Approve or reject artifacts in task outbox.",
        },
        {
            "id": "signoff:gates",
            "label": f"Resolve {blockers} gate blocker(s)",
            "done": blockers == 0,
            "liaison_cmd": "liaison status",
            "detail": f"{gate_fail} gate failures across open tasks.",
        },
        {
            "id": "signoff:flywheel",
            "label": f"Close {flywheel} flywheel task(s)" if flywheel else "Flywheel queue clear",
            "done": flywheel == 0,
            "liaison_cmd": "liaison look",
            "detail": "Data flywheel workflow tasks awaiting closeout.",
        },
        {
            "id": "signoff:debrief",
            "label": (
                f"Debrief stale · {eng.get('last_debrief_age', 'unknown')}"
                if eng.get("debrief_stale")
                else f"Debrief freshness · {eng.get('last_debrief_age', 'unknown')}"
            ),
            "done": not eng.get("debrief_stale")
            and eng.get("last_debrief_age") not in ("no debrief", "never"),
            "liaison_cmd": "liaison debrief --show",
            "detail": (
                f"Debrief older than {eng.get('debrief_stale_days', DEBRIEF_STALE_DAYS_DEFAULT)} days "
                f"({eng.get('debrief_age_days')}d) · {len(debriefs)} debrief(s) in scope."
                if eng.get("debrief_stale")
                else f"{len(debriefs)} debrief(s) in scope."
            ),
        },
        {
            "id": "signoff:intake",
            "label": intake_label,
            "done": bool(launch_ready),
            "liaison_cmd": (
                f"liaison project-intake --project {state.get('selected_project')} --show"
                if state.get("selected_project")
                else "liaison registry repos"
            ),
            "detail": (
                f"{summary.get('intake_blockers', 0)} intake blocker(s)"
                if not launch_ready
                else (
                    "Soft-ready — resolve warn checks when convenient."
                    if soft_ready and not strict_ready
                    else "Intake passed — executors may run in terminal."
                )
            ),
        },
        {
            "id": "signoff:validate",
            "label": "Validate before close",
            "done": blockers == 0 and len(pending) == 0,
            "liaison_cmd": "liaison validate --profile none",
            "detail": "Run validation profile for focused project phase.",
        },
    ]

    copy_hints = [
        {"label": "Approve artifact", "liaison_cmd": "liaison approve-artifact .spark-flow/tasks/<id>/outbox/<file>.md"},
        {"label": "Validate slice", "liaison_cmd": "liaison validate --profile <profile>"},
        {"label": "Close task", "liaison_cmd": "liaison close-task --task-id <id> --summary \"done\""},
        {"label": "Show debrief", "liaison_cmd": "liaison debrief --show"},
    ]

    flywheel_copy_cmds = list(FLYWHEEL_INIT_COPY_CMDS) if flywheel else []

    return {
        "pending_handoffs": pending[:24],
        "pending_handoff_count": len(pending),
        "global_scope": not bool(state.get("selected_project")),
        "gate_failures": gate_fail,
        "flywheel_open": flywheel,
        "debrief_age": eng.get("last_debrief_age", "unknown"),
        "debrief_age_days": eng.get("debrief_age_days"),
        "debrief_stale": bool(eng.get("debrief_stale")),
        "debrief_stale_days": eng.get("debrief_stale_days", DEBRIEF_STALE_DAYS_DEFAULT),
        "debrief_count": len(debriefs),
        "flywheel_phases": [],
        "flywheel_copy_cmds": flywheel_copy_cmds,
        "checklist": checklist,
        "copy_hints": copy_hints,
        "ready_for_signoff": len(pending) == 0 and blockers == 0 and flywheel == 0,
    }


def cross_pollination(state: dict) -> list[dict]:
    rows = []
    trends = state.get("trends", {})
    for item in trends.get("candidate_improvements", [])[:4]:
        rows.append({"type": "trend", "text": item.get("candidate_improvement", "")[:80]})
    for name in state.get("recent_learnings", [])[-3:]:
        rows.append({"type": "learning", "text": name})
    skills = _bridge().parse_registry_map("skills.yaml", "skills")
    owners = Counter(fields.get("owner", "?") for fields in skills.values())
    for owner, count in owners.most_common(4):
        if count > 1:
            rows.append({"type": "shared_skill", "text": f"{owner}: {count} registered skills"})
    return rows[:12]


# Recommended hub agents per *project* phase (distinct from task-phase routing).
PROJECT_PHASE_AGENTS = {
    "prototype": ["hermes"],
    "alpha": ["hermes", "opencode", "codex", "claude"],
    "beta": ["hermes", "qca", "ml_intern", "claude"],
    "mvp": ["hermes", "liaison", "opencode"],
    "unassessed": [],
}


def project_match(task_repo: str, selected: str | None) -> bool:
    if not selected:
        return True
    return selected in task_repo or Path(task_repo).name == selected


def repo_registry_key(task_repo: str, repos: dict[str, dict]) -> str | None:
    """Map task repo path or folder name to registry key."""
    try:
        resolved = str(Path(task_repo).expanduser().resolve())
    except OSError:
        resolved = task_repo
    name = Path(task_repo).name
    for key, fields in repos.items():
        path = fields.get("path", "")
        if not path:
            continue
        try:
            if str(Path(path).expanduser().resolve()) == resolved:
                return key
        except OSError:
            pass
        if key == name or Path(path).name == name or key in task_repo:
            return key
    return None


def enrich_handoffs(handoffs: list[dict], repos: dict[str, dict]) -> list[dict]:
    rows = []
    for h in handoffs:
        row = dict(h)
        row["project_key"] = repo_registry_key(h.get("repo", ""), repos) or h.get("repo", "")
        rows.append(row)
    return rows


def executor_launch_ready(
    *,
    intake: dict | None,
    focus: dict | None,
    project_plan: dict | None,
) -> bool:
    """Whether hub executors may launch — soft gate for profile/tier-A projects."""
    if not intake:
        return True
    strict = bool(intake.get("ready_to_build_strict", intake.get("ready_to_build")))
    soft = bool(intake.get("ready_to_build_soft"))
    profile = (focus or {}).get("default_profile", "none")
    tier = (project_plan or {}).get("tier", "")
    if profile and profile != "none":
        return soft
    if tier == "A":
        return soft
    return strict


def build_agent_hub(state: dict, open_tasks: list[dict] | None = None, recommended_agents: set[str] | None = None) -> list[dict]:
    hub = enrich_hub_agents(state["hub_agents"])
    tasks = open_tasks if open_tasks is not None else state["open_tasks"]
    recommended = recommended_agents or set()
    counts: dict[str, int] = {name: 0 for name in hub}
    for task in tasks:
        phase = task.get("current_phase", "plan")
        agent = PHASE_ROUTE_AGENTS.get(phase, "hermes")
        if agent in counts:
            counts[agent] += 1
        elif "hermes" in counts:
            counts["hermes"] += 1

    rows = []
    for name, fields in sorted(hub.items()):
        status = fields.get("status", "ready")
        task_count = counts.get(name, 0)
        if task_count:
            live_status = "Active"
        else:
            live_status = "Idle" if status == "active" else status.capitalize()
        from dashboard.command_center.hub_groups import AGENT_DISPLAY_NAMES
        from dashboard.command_center.rolodex_resume import build_hub_agent_resume

        display = AGENT_DISPLAY_NAMES.get(name, name.replace("_", " "))
        row = {
            "name": name,
            "display": display,
            "status": live_status,
            "registry_status": status,
            "role": fields.get("role", "—"),
            "output_contract": fields.get("output_contract", "—"),
            "launch": fields.get("launch", "—"),
            "launch_note": fields.get("launch_note", ""),
            "handoff_guide": fields.get("handoff_guide", "—"),
            "hub_docs": fields.get("hub_docs", "—"),
            "tasks": task_count,
            "recommended": name in recommended,
        }
        row["resume"] = build_hub_agent_resume(row)
        rows.append(row)
    return rows


def build_focus(selected_project: str | None) -> dict | None:
    """Resolve the focused project's lifecycle, phase, exit criteria, and recommendations."""
    if not selected_project:
        return None
    sf = _bridge()
    repos = sf.parse_registry_map("repos.yaml", "repos")
    fields = repos.get(selected_project)
    path = ""
    if fields:
        path = fields.get("path", "")
    else:
        for name, data in repos.items():
            if name == selected_project or selected_project in (data.get("path", "")):
                fields = data
                path = data.get("path", "")
                break
    phase_state = sf.read_repo_phase_state(path) if path else {"phase": "—", "lifecycle": "—"}
    phase = phase_state.get("phase", "—")
    routing = sf.parse_phase_routing()
    meta = routing["phases"].get(phase, {})
    recommended_agents = set(PROJECT_PHASE_AGENTS.get(phase, []))
    return {
        "project": selected_project,
        "path": path,
        "default_profile": (fields or {}).get("default_profile", "none"),
        "lifecycle": phase_state.get("lifecycle", "—"),
        "phase": phase,
        "project_phase": phase,
        "label": meta.get("label", phase),
        "validation": meta.get("validation", "optional"),
        "debrief_required": meta.get("debrief_required", "false"),
        "exit_criteria": meta.get("exit_criteria", []),
        "recommended_agents": sorted(recommended_agents),
    }


def build_skills_panel(state: dict) -> dict:
    sf = _bridge()
    skills = sf.parse_skills_in_use()
    return {
        "skills": skills,
        "recommendations": phase_recommendations(state),
        "chains": HANDOFF_CHAINS,
    }


def kanban_bucket(task: dict) -> str:
    if task.get("closed") or task.get("current_phase") == "complete":
        return "done"
    phase = task.get("current_phase", "unknown")
    if phase == "review":
        return "review"
    if phase in {"build", "patch"}:
        return "in_progress"
    return "todo"


def collect_command_center_state(
    refresh: bool = False,
    selected_project: str | None = None,
    active_task_id: str | None = None,
    pattern_id: str | None = None,
    rolodex_category: str | None = None,
    persist_session: bool = False,
) -> dict:
    sf = _bridge()
    base = sf.collect_look_state(refresh)
    base["hub_agents"] = enrich_hub_agents(base["hub_agents"])

    focus = build_focus(selected_project)
    recommended_agents = set(focus["recommended_agents"]) if focus else set()

    filtered_open = [t for t in base["open_tasks"] if project_match(t["repo"], selected_project)]

    kanban_raw = {
        bucket: [
            task
            for task in base["tasks"]
            if kanban_bucket(task) == bucket and project_match(task["repo"], selected_project)
        ]
        for bucket in ("todo", "in_progress", "review", "done")
    }
    kanban = {
        bucket: [enrich_task_with_reporter_steps(t) for t in tasks]
        for bucket, tasks in kanban_raw.items()
    }

    # Project focus scopes the whole board: hub counts, handoffs, debriefs, metrics.
    scoped_tasks = [t for t in base["tasks"] if project_match(t["repo"], selected_project)]
    agent_rows = build_agent_hub(base, open_tasks=filtered_open, recommended_agents=recommended_agents)
    engineering = build_engineering_metrics(base)
    repos_map = sf.parse_registry_map("repos.yaml", "repos")
    handoffs = enrich_handoffs(scan_handoffs(scoped_tasks), repos_map)
    if not selected_project:
        all_handoffs = enrich_handoffs(scan_handoffs(base["tasks"]), repos_map)
        handoffs = sorted(
            all_handoffs,
            key=lambda h: (0 if h.get("status") == "pending_approval" else 1, h.get("task_id", "")),
        )[:24]
    debriefs = [d for d in scan_debriefs() if project_match(d["repo"], selected_project)]
    skills_panel = build_skills_panel(base)
    project_matrix = sf.build_project_matrix(base)
    cross = cross_pollination(base)

    from dashboard.command_center.hub_skills import build_hub_skills_catalog, build_project_agent_patterns
    from dashboard.command_center.rolodex import build_rolodex

    hub_skills_catalog = build_hub_skills_catalog()
    project_agent_patterns = build_project_agent_patterns()
    rolodex_state = {
        **base,
        "agent_rows": agent_rows,
        "skills_panel": skills_panel,
        "handoff_chains": HANDOFF_CHAINS,
        "hub_skills_catalog": hub_skills_catalog,
        "_bridge": sf,
    }
    rolodex = build_rolodex(rolodex_state)

    # Link patterns and skills to the focused project's phase.
    if focus:
        for entry in rolodex.get("projects", []):
            agents = entry.get("meta", {}).get("agents", [])
            entry["recommended"] = bool(recommended_agents.intersection(agents))
        for entry in rolodex.get("skills", []):
            owner = entry.get("meta", {}).get("owner")
            entry["recommended"] = owner in recommended_agents

    total = len(base["tasks"])
    closed = sum(1 for item in base["tasks"] if item["closed"])
    blockers = sum(1 for item in base["open_tasks"] if item.get("gate_status") == "fail")
    resolved_task_id = resolve_active_task_id(active_task_id, filtered_open)
    flywheel_open = count_flywheel_open_tasks(filtered_open)

    operator_session = None
    if focus and focus.get("path"):
        from dashboard.command_center.operator_session import (
            read_operator_session,
            write_operator_session,
        )

        if persist_session and selected_project:
            operator_session = write_operator_session(
                focus["path"],
                project_key=selected_project,
                task_id=resolved_task_id,
                pattern_id=pattern_id,
            )
        else:
            operator_session = read_operator_session(focus["path"])

    from dashboard.command_center.hub_groups import group_agent_rows
    from dashboard.command_center.project_intake import build_project_intake
    from dashboard.command_center.project_plans import build_projects_registry
    from dashboard.command_center.terminal_sessions import list_sessions
    from dashboard.command_center.venture_queue import build_queue_summary, list_items as list_queue_items
    from dashboard.command_center.workstation import build_workstation_usage

    terminal_sessions = list_sessions()
    workstation_usage = build_workstation_usage(terminal_sessions)
    venture_queue_summary = build_queue_summary(terminal_sessions)
    venture_queue = list_queue_items()

    from dashboard.command_center.execution_bridge import detect_stale_executor_sessions

    stale_executor_sessions = detect_stale_executor_sessions(terminal_sessions)

    project_intake = None
    project_plan = None
    if focus and focus.get("path"):
        project_intake = build_project_intake(
            selected_project or focus["project"],
            focus["path"],
            filtered_open,
        )
        from dashboard.command_center.project_plans import (
            build_project_plan_card,
            load_project_plan,
            merge_plan_with_intake,
        )

        registry_key = selected_project or focus["project"]
        plan_registry = load_project_plan(registry_key)
        merged_plan = (
            merge_plan_with_intake(plan_registry, project_intake)
            if plan_registry and project_intake
            else plan_registry
        )
        if merged_plan:
            project_plan = build_project_plan_card(
                registry_key,
                focus["path"],
                merged_plan,
                focus,
                filtered_open,
            )

    build_corpus_summary = None
    if focus and focus.get("path"):
        from dashboard.command_center.build_corpus import build_corpus_summary as _build_corpus_summary

        build_corpus_summary = _build_corpus_summary(
            registry_key or focus["project"],
            focus["path"],
            filtered_open,
            project_plan=project_plan,
        )

    workload_id = resolve_workload_id(focus.get("path") if focus else None)

    summary = {
        "total_tasks": total,
        "open_tasks": len(base["open_tasks"]),
        "closed_tasks": closed,
        "blockers": blockers,
        "filtered_open": len(filtered_open),
        "flywheel_open": flywheel_open,
        "workload_id": workload_id,
        "intake_ready": bool(project_intake and project_intake.get("intake_ready")),
        "ready_to_build": bool(project_intake and project_intake.get("ready_to_build")),
        "ready_to_build_strict": bool(
            project_intake and project_intake.get("ready_to_build_strict", project_intake.get("ready_to_build"))
        ),
        "ready_to_build_soft": bool(project_intake and project_intake.get("ready_to_build_soft")),
        "executor_launch_ready": executor_launch_ready(
            intake=project_intake,
            focus=focus,
            project_plan=project_plan,
        ),
        "intake_blockers": (
            project_intake.get("summary", {}).get("intake_blockers", 0) if project_intake else 0
        ),
        "has_project_plan": bool(
            project_plan
            and (
                project_plan.get("has_registry_plan")
                or project_plan.get("has_on_disk_plan")
            )
        ),
        "executor_session_stale": len(stale_executor_sessions) > 0,
        "executor_session_stale_count": len(stale_executor_sessions),
        "debrief_age_days": engineering.get("debrief_age_days"),
        "debrief_stale": bool(engineering.get("debrief_stale")),
        "debrief_stale_days": engineering.get("debrief_stale_days", DEBRIEF_STALE_DAYS_DEFAULT),
    }
    metrics_rows = build_metrics_rows(
        {
            **base,
            "engineering_metrics": engineering,
            "cross_pollination": cross,
            "skills_panel": skills_panel,
            "summary": summary,
        }
    )
    if focus:
        focus_open = len(filtered_open)
        focus_handoffs = sum(1 for h in handoffs if h["status"] == "pending_approval")
        focus_rows = [
            {
                "id": "focus:phase",
                "label": f"FOCUS {focus['project']}: {focus['lifecycle']}/{focus['phase']}",
                "detail": f"Validation {focus['validation']} · debrief_required {focus['debrief_required']}",
                "path": str(Path(focus["path"]).expanduser() / ".spark-flow" / "memory" / "PROJECT_PHASE.md") if focus["path"] else None,
                "liaison_cmd": "liaison project-phase show",
            },
            {
                "id": "focus:work",
                "label": f"FOCUS work: {focus_open} open tasks · {focus_handoffs} pending handoffs",
                "detail": "Scoped to the selected project. Esc clears focus.",
                "path": None,
                "liaison_cmd": "liaison look",
            },
            {
                "id": "focus:agents",
                "label": f"FOCUS agents: {', '.join(focus['recommended_agents']) or '—'}",
                "detail": f"Recommended hub agents for phase {focus['phase']}.",
                "path": None,
                "liaison_cmd": "liaison registry agents",
            },
        ]
        metrics_rows = focus_rows + metrics_rows

    partial_state = {
        **base,
        "selected_project": selected_project,
        "summary": summary,
        "engineering_metrics": engineering,
        "handoffs": handoffs,
        "debriefs": debriefs,
        "project_intake": project_intake,
        "project_plan": project_plan,
        "focus": focus,
    }
    from dashboard.command_center.panel_briefs import (
        build_overview_brief,
        build_workstream_brief,
        enrich_ops_signoff,
        load_workflow_phases,
        pick_next_workflow_phase,
        _focused_task,
    )

    workflow_phases: list[dict] = []
    next_workflow_step: dict | None = None
    active_task_phase: str | None = None
    if project_plan and project_plan.get("workflow"):
        workflow_phases = load_workflow_phases(
            project_plan.get("workflow", ""),
            project_plan.get("workflow_source"),
        )
    focused_task = None
    if resolved_task_id:
        for bucket_tasks in kanban.values():
            for t in bucket_tasks:
                if t.get("task_id") == resolved_task_id:
                    focused_task = t
                    break
            if focused_task:
                break
    if not focused_task:
        focused_task = _focused_task({"kanban": kanban})
    if focused_task:
        active_task_phase = focused_task.get("current_phase")
    if flywheel_open > 0 and not workflow_phases:
        workflow_phases = load_workflow_phases("data-flywheel")

    if workflow_phases:
        next_workflow_step = pick_next_workflow_phase(workflow_phases, focused_task)

    suggested_workflow_commands = build_suggested_workflow_commands(next_workflow_step)
    reporter_step_state = build_reporter_step_state_for_task(focused_task)

    workflow_next_action = build_workflow_next_action(focused_task)
    from dashboard.command_center.terminal_spawn import terminal_bridge_summary

    terminal_bridge = terminal_bridge_summary()

    ops_signoff = enrich_ops_signoff(build_ops_signoff(partial_state), partial_state)
    if flywheel_open > 0 and workflow_phases:
        ops_signoff["flywheel_phases"] = workflow_phases
    overview_actions = build_overview_actions(
        {**partial_state, "focus": focus, "project_plan": project_plan}
    )
    projects_registry = build_projects_registry(
        {**base, "project_matrix": project_matrix}
    )
    brief_state = {
        **partial_state,
        "focus": focus,
        "project_plan": project_plan,
        "kanban": kanban,
        "agent_rows": agent_rows,
        "rolodex": rolodex,
        "ops_signoff": ops_signoff,
        "build_corpus_summary": build_corpus_summary,
        "project_agent_patterns": project_agent_patterns,
        "workflow_phases": workflow_phases,
        "next_workflow_step": next_workflow_step,
        "suggested_workflow_commands": suggested_workflow_commands,
        "reporter_step_state": reporter_step_state,
        "workflow_next_action": workflow_next_action,
        "active_task_phase": active_task_phase,
        "terminal_bridge": terminal_bridge,
    }
    overview_brief = build_overview_brief(brief_state)
    workstream_brief = build_workstream_brief(brief_state)
    from dashboard.command_center.project_portfolio import (
        ROLODEX_CATEGORY_INTROS,
        build_hub_workflows_for_project,
        build_project_detail,
        build_project_portfolio_list,
        build_projects_portfolio_detail,
    )

    project_detail = build_project_detail(brief_state)
    hub_workflows = build_hub_workflows_for_project(brief_state)

    return {
        **base,
        "selected_project": selected_project,
        "active_task_id": resolved_task_id,
        "pattern_id": (pattern_id or None) or (operator_session or {}).get("pattern_id") or None,
        "operator_session": operator_session,
        "hub_agent_groups": group_agent_rows(agent_rows),
        "terminal_sessions": terminal_sessions,
        "workstation_profile": workstation_usage.get("profile_defaults"),
        "workstation_usage": workstation_usage,
        "venture_queue": venture_queue,
        "venture_queue_summary": venture_queue_summary,
        "stale_executor_sessions": stale_executor_sessions,
        "focus": focus,
        "kanban": kanban,
        "agent_rows": agent_rows,
        "skills_panel": skills_panel,
        "project_matrix": project_matrix,
        "engineering_metrics": engineering,
        "handoffs": handoffs,
        "debriefs": debriefs,
        "cross_pollination": cross,
        "metrics_rows": metrics_rows,
        "handoff_chains": HANDOFF_CHAINS,
        "summary": summary,
        "hub_status": "active" if agent_rows else "empty",
        "env": os.environ.get("LIAISON_ENV", "local").upper(),
        "platform": Path.cwd().name,
        "user": os.environ.get("USER", "operator"),
        "sqlite_loaded": sf.repo_memory_db().exists(),
        "refresh_sec": COMMAND_CENTER_REFRESH_SEC,
        "generated_at": _now(),
        "rolodex": rolodex,
        "rolodex_category": rolodex_category or "skills",
        "hub_skills_catalog": hub_skills_catalog,
        "project_agent_patterns": project_agent_patterns,
        "project_intake": project_intake,
        "project_plan": project_plan,
        "build_corpus_summary": build_corpus_summary,
        "ops_signoff": ops_signoff,
        "overview_actions": overview_actions,
        "overview_brief": overview_brief,
        "workstream_brief": workstream_brief,
        "project_detail": project_detail,
        "project_portfolio": build_project_portfolio_list(brief_state),
        "projects_portfolio_detail": build_projects_portfolio_detail(
            {**base, "project_matrix": project_matrix, "_bridge": sf}
        ),
        "hub_workflows": hub_workflows,
        "rolodex_category_intros": ROLODEX_CATEGORY_INTROS,
        "projects_registry": projects_registry,
        "workflow_phases": workflow_phases,
        "next_workflow_step": next_workflow_step,
        "suggested_workflow_commands": suggested_workflow_commands,
        "reporter_step_state": reporter_step_state,
        "workflow_next_action": workflow_next_action,
        "active_task_phase": active_task_phase,
        "terminal_bridge": terminal_bridge,
    }


def ensure_import_path() -> None:
    root = str(AGENT_SYSTEM_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)
