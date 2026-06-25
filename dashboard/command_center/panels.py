"""Phase 11 dashboard panel data helpers.

Builds compact, UI-friendly views for:
- TasksPanel     — task queue overview across all projects
- ApprovalsPanel — pending approvals (handoffs and execution requests)
- ValidationPanel — validation profile coverage and run status
- RoutingPanel   — model route and capability routing
- ContextBundlesPanel — context bundle inventory
- LogsPanel      — recent JSONL run log tail
- BudgetsPanel   — model/route budget limits and usage

All helpers are pure (read-only) and derive from registries and the
existing command-center state. They do not introduce new I/O paths.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from liaison_paths import AGENT_SYSTEM_DIR


EXECUTION_APPROVAL_KEYWORDS = (
    "validation",
    "approval",
    "deploy",
    "release",
    "promote",
    "production",
    "merge",
    "submit",
    "allocate",
)


def _safe_read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def _safe_read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def build_tasks_panel(
    *, state: Mapping[str, Any] | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Build the TasksPanel summary: counts per state, recent task list, by-project."""
    state = state or {}
    tasks = state.get("tasks", []) or []
    open_tasks = state.get("open_tasks", []) or []
    kanban = state.get("kanban", {}) or {}

    bucket_counts = {
        "todo": len(kanban.get("todo", []) or []),
        "in_progress": len(kanban.get("in_progress", []) or []),
        "review": len(kanban.get("review", []) or []),
        "done": len(kanban.get("done", []) or []),
    }

    by_project: Counter[str] = Counter()
    by_priority: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        repo = task.get("repo", {}) or {}
        if isinstance(repo, dict):
            proj = str(repo.get("name") or repo.get("path") or "unknown")
        else:
            proj = str(repo or "unknown")
        by_project[proj] += 1
        priority = str(task.get("priority", "medium")).lower()
        by_priority[priority] += 1
        task_type = str(task.get("type", "unknown"))
        by_type[task_type] += 1

    recent: list[dict[str, Any]] = []
    for task in tasks[:25]:
        if not isinstance(task, Mapping):
            continue
        recent.append({
            "task_id": str(task.get("task_id") or task.get("id") or ""),
            "title": str(task.get("title") or task.get("task_id") or ""),
            "priority": str(task.get("priority", "medium")).lower(),
            "status": str(task.get("status", "backlog")),
            "type": str(task.get("type", "unknown")),
            "repo": (task.get("repo") or {}).get("name", "") if isinstance(task.get("repo"), dict) else "",
        })

    return {
        "total": len(tasks),
        "open": len(open_tasks),
        "closed": sum(1 for t in tasks if isinstance(t, Mapping) and t.get("closed")),
        "buckets": bucket_counts,
        "by_project": dict(by_project.most_common(10)),
        "by_priority": dict(by_priority),
        "by_type": dict(by_type.most_common(10)),
        "recent": recent,
    }


def build_approvals_panel(
    *, state: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Build the ApprovalsPanel summary: pending handoffs and execution requests."""
    state = state or {}
    handoffs = state.get("handoffs", []) or []
    pending_handoffs = [
        h for h in handoffs
        if isinstance(h, Mapping) and h.get("status") == "pending_approval"
    ]
    approved = [
        h for h in handoffs
        if isinstance(h, Mapping) and h.get("status") == "approved"
    ]
    rejected = [
        h for h in handoffs
        if isinstance(h, Mapping) and h.get("status") == "rejected"
    ]

    rows: list[dict[str, Any]] = []
    for h in (pending_handoffs + approved + rejected)[:50]:
        if not isinstance(h, Mapping):
            continue
        rows.append({
            "task_id": str(h.get("task_id") or h.get("id") or ""),
            "from_agent": str(h.get("from_agent") or h.get("from") or ""),
            "to_agent": str(h.get("to_agent") or h.get("to") or ""),
            "status": str(h.get("status", "pending_approval")),
            "summary": str(h.get("summary") or h.get("detail") or ""),
            "phase": str(h.get("phase", "")),
            "repo": str(h.get("repo") or ""),
        })

    return {
        "total": len(handoffs),
        "pending": len(pending_handoffs),
        "approved": len(approved),
        "rejected": len(rejected),
        "rows": rows,
    }


def build_validation_panel(
    *, state: Mapping[str, Any] | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Build the ValidationPanel summary: validation profile coverage and run status."""
    state = state or {}
    profiles = _safe_read_yaml((root or AGENT_SYSTEM_DIR) / "config" / "validation_profiles.yaml")
    project_plans = _safe_read_yaml((root or AGENT_SYSTEM_DIR) / "registry" / "project_plans.yaml")

    profile_names: list[str] = []
    if isinstance(profiles, dict):
        raw = profiles.get("profiles", {})
        if isinstance(raw, dict):
            profile_names = sorted(raw.keys())
        elif isinstance(raw, list):
            profile_names = [str(p) for p in raw]

    profile_usage: Counter[str] = Counter()
    profile_check_scripts: dict[str, str] = {}
    if isinstance(profiles, dict):
        raw = profiles.get("profiles", {})
        if isinstance(raw, dict):
            for name, cfg in raw.items():
                if isinstance(cfg, dict) and cfg.get("checks_script"):
                    profile_check_scripts[str(name)] = str(cfg["checks_script"])

    if isinstance(project_plans, dict):
        plans = project_plans.get("projects", project_plans.get("plans", {}))
        if isinstance(plans, dict):
            for plan in plans.values():
                if isinstance(plan, Mapping):
                    p = str(plan.get("validation_profile", "") or "").strip()
                    if p and p != "none":
                        profile_usage[p] += 1

    run_dirs_root = (root or AGENT_SYSTEM_DIR) / ".liaison" / "runs"
    recent_runs: list[dict[str, Any]] = []
    if run_dirs_root.exists():
        run_dirs = sorted(
            [p for p in run_dirs_root.iterdir() if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        for rd in run_dirs[:10]:
            gate_path = rd / "promotion_gate.json"
            if not gate_path.exists():
                continue
            try:
                gate = json.loads(gate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(gate, dict):
                continue
            recent_runs.append({
                "run_id": rd.name,
                "task_id": str(gate.get("task_id", "")),
                "project": str(gate.get("project", "")),
                "status": str(gate.get("status", "unknown")),
                "validation_passed": bool(gate.get("validation_passed", False)),
                "security_passed": bool(gate.get("security_passed", False)),
            })

    return {
        "profiles_defined": profile_names,
        "profile_count": len(profile_names),
        "profile_usage": dict(profile_usage),
        "profile_check_scripts": profile_check_scripts,
        "recent_runs": recent_runs,
    }


def build_routing_panel(
    *, state: Mapping[str, Any] | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Build the RoutingPanel summary: model routes, executors, and capabilities."""
    state = state or {}
    routes = _safe_read_yaml((root or AGENT_SYSTEM_DIR) / "config" / "model_routes.yaml")
    executors = _safe_read_yaml((root or AGENT_SYSTEM_DIR) / "config" / "executors.yaml")
    phase_routing = _safe_read_yaml((root or AGENT_SYSTEM_DIR) / "registry" / "phase_routing.yaml")

    model_routes: list[dict[str, Any]] = []
    if isinstance(routes, dict):
        raw = routes.get("routes", routes)
        if isinstance(raw, dict):
            for name, cfg in raw.items():
                if not isinstance(cfg, Mapping):
                    continue
                model_routes.append({
                    "name": str(name),
                    "provider": str(cfg.get("provider", "")),
                    "model": str(cfg.get("model", "")),
                    "capabilities": list(cfg.get("capabilities", []) or []),
                })
        elif isinstance(raw, list):
            for cfg in raw:
                if isinstance(cfg, Mapping):
                    model_routes.append({
                        "name": str(cfg.get("name", "")),
                        "provider": str(cfg.get("provider", "")),
                        "model": str(cfg.get("model", "")),
                        "capabilities": list(cfg.get("capabilities", []) or []),
                    })

    executor_routes: list[dict[str, Any]] = []
    if isinstance(executors, dict):
        raw = executors.get("executors", {})
        if isinstance(raw, dict):
            for name, cfg in raw.items():
                if not isinstance(cfg, Mapping):
                    continue
                executor_routes.append({
                    "name": str(name),
                    "type": str(cfg.get("type", name)),
                    "enabled": bool(cfg.get("enabled", False)),
                    "command": str(cfg.get("command", "")),
                    "allow_execution": bool(cfg.get("allow_execution", False)),
                })

    phases: list[dict[str, Any]] = []
    if isinstance(phase_routing, dict):
        raw = phase_routing.get("phases", phase_routing)
        if isinstance(raw, dict):
            for name, cfg in raw.items():
                if not isinstance(cfg, Mapping):
                    continue
                phases.append({
                    "name": str(name),
                    "preferred_agent": str(cfg.get("preferred_agent", "")),
                    "fallback_agent": str(cfg.get("fallback_agent", "")),
                    "validation": str(cfg.get("validation", "optional")),
                })

    return {
        "model_routes": model_routes,
        "executor_routes": executor_routes,
        "phases": phases,
    }


def build_context_bundles_panel(
    *, state: Mapping[str, Any] | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Build the ContextBundlesPanel summary: context bundle inventory and recent items."""
    state = state or {}
    bundles_root = (root or AGENT_SYSTEM_DIR) / ".liaison" / "context_bundles"
    bundles: list[dict[str, Any]] = []
    if bundles_root.exists():
        for entry in sorted(bundles_root.iterdir(), reverse=True)[:20]:
            if entry.is_dir():
                bundles.append({"name": entry.name, "kind": "directory", "path": str(entry)})
            elif entry.is_file():
                bundles.append({"name": entry.name, "kind": "file", "path": str(entry)})
    project_intake = state.get("project_intake", {}) or {}
    if isinstance(project_intake, Mapping):
        bundle_id = project_intake.get("bundle_id") or project_intake.get("id")
        if bundle_id:
            bundles.insert(0, {
                "name": str(bundle_id),
                "kind": "active",
                "path": project_intake.get("bundle_path", ""),
            })
    return {"count": len(bundles), "bundles": bundles}


def build_logs_panel(
    *, state: Mapping[str, Any] | None = None, root: Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Build the LogsPanel summary: tail of recent run logs (JSONL artifacts)."""
    state = state or {}
    root = root or AGENT_SYSTEM_DIR
    runs_root = root / ".liaison" / "runs"
    log_files = ("stdout.log", "stderr.log", "validation.log", "security.log", "model_calls.jsonl")
    rows: list[dict[str, Any]] = []
    if runs_root.exists():
        run_dirs = sorted(
            [p for p in runs_root.iterdir() if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        for rd in run_dirs[:limit]:
            for lf in log_files:
                p = rd / lf
                if not p.exists():
                    continue
                try:
                    stat = p.stat()
                except OSError:
                    continue
                try:
                    tail_text = p.read_text(encoding="utf-8", errors="ignore")[-4000:]
                except OSError:
                    tail_text = ""
                rows.append({
                    "run_id": rd.name,
                    "log": lf,
                    "size": stat.st_size,
                    "tail": tail_text,
                })
    return {"count": len(rows), "rows": rows}


def build_budgets_panel(
    *, state: Mapping[str, Any] | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Build the BudgetsPanel summary: model/route budget limits and recent usage."""
    state = state or {}
    root = root or AGENT_SYSTEM_DIR
    budgets = _safe_read_yaml(root / "config" / "budgets.yaml")
    limits = _safe_read_yaml(root / "config" / "budget_limits.yaml")
    rows: list[dict[str, Any]] = []
    for source, key in ((budgets, "budgets"), (limits, "limits")):
        if not isinstance(source, dict):
            continue
        raw = source.get(key, source)
        if isinstance(raw, dict):
            for name, cfg in raw.items():
                if not isinstance(cfg, Mapping):
                    continue
                rows.append({
                    "name": str(name),
                    "source": str(key),
                    "per_run": cfg.get("per_run") or cfg.get("limit"),
                    "per_day": cfg.get("per_day") or cfg.get("daily_limit"),
                    "currency": str(cfg.get("currency", "usd")),
                })
    runs_root = root / ".liaison" / "runs"
    recent_spend: list[dict[str, Any]] = []
    if runs_root.exists():
        for rd in sorted(
            [p for p in runs_root.iterdir() if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )[:10]:
            meta = rd / "run_metadata.json"
            if not meta.exists():
                continue
            try:
                payload = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, Mapping):
                tool_exec = payload.get("tool_execution", {}) or {}
                recent_spend.append({
                    "run_id": rd.name,
                    "task_id": str(payload.get("task_id", "")),
                    "shell_commands_executed": bool(tool_exec.get("shell_commands_run", False)),
                    "models_called": bool(tool_exec.get("model_calls_made", False)),
                    "executors_called": bool(tool_exec.get("executor_invoked", False)),
                })
    return {
        "limits_count": len(rows),
        "limits": rows,
        "recent_runs": recent_spend,
    }


def build_all_panels(
    *, state: Mapping[str, Any] | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Build all Phase 11 panel data blocks at once."""
    return {
        "tasks": build_tasks_panel(state=state, root=root),
        "approvals": build_approvals_panel(state=state),
        "validation": build_validation_panel(state=state, root=root),
        "routing": build_routing_panel(state=state, root=root),
        "context_bundles": build_context_bundles_panel(state=state, root=root),
        "logs": build_logs_panel(state=state, root=root),
        "budgets": build_budgets_panel(state=state, root=root),
    }
