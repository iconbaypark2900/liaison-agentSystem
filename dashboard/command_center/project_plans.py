"""Portfolio operating plans — registry defaults + repo memory artifact."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from liaison_paths import AGENT_SYSTEM_DIR

PLAN_FILENAME = "PROJECT_OPERATING_PLAN.md"
TEMPLATE_PATH = AGENT_SYSTEM_DIR / "templates" / PLAN_FILENAME

_PROFILE_WORKFLOW = {
    "python": "python-cli",
    "backend": "python-cli",
    "frontend": "reporter-mode",
    "ai-app": "ai-app",
    "rag": "rag-system",
    "quantum": "quantum-ising",
    "sigma": "sigma-integration",
    "none": "reporter-mode",
}


def _bridge():
    from dashboard.command_center.data import _bridge as data_bridge

    return data_bridge()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "yes", "1")
    return bool(val)


def _parse_project_plans_yaml() -> dict[str, dict[str, Any]]:
    """Parse registry/project_plans.yaml (project_plans section)."""
    path = AGENT_SYSTEM_DIR / "registry" / "project_plans.yaml"
    if not path.exists():
        return {}
    plans: dict[str, dict[str, Any]] = {}
    current_key: str | None = None
    in_plans = False
    active_list: str | None = None
    list_fields = frozenset(
        {"research_gate_commands", "engineering_gate_commands", "backlog"}
    )
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "project_plans:":
            in_plans = True
            continue
        if not in_plans or not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_key = stripped[:-1]
            plans[current_key] = {}
            active_list = None
            continue
        if not current_key:
            continue
        if re.match(r"^\s+-\s", line):
            item = stripped.lstrip("- ").strip('"')
            field = active_list or "backlog"
            plans[current_key].setdefault(field, [])
            if isinstance(plans[current_key][field], list):
                plans[current_key][field].append(item)
            continue
        if line.startswith("    ") and ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"')
            if key in list_fields:
                plans[current_key][key] = []
                active_list = key
            else:
                active_list = None
                plans[current_key][key] = val
    return plans


def _normalize_plan(raw: dict[str, Any], registry_key: str) -> dict[str, Any]:
    pattern = raw.get("pattern") or None
    if pattern == "null" or pattern == "":
        pattern = None
    return {
        "registry_key": registry_key,
        "tier": raw.get("tier", "A"),
        "intent": raw.get("intent", ""),
        "maturity_target": raw.get("maturity_target", "unassessed"),
        "workflow": raw.get("workflow", "reporter-mode"),
        "workflow_source": raw.get("workflow_source", ""),
        "pattern": pattern,
        "validation_profile": raw.get("validation_profile", "none"),
        "external_guide": raw.get("external_guide", ""),
        "research_gate": {
            "summary": raw.get("research_gate_summary", ""),
            "commands": list(raw.get("research_gate_commands") or []),
        },
        "engineering_gate": {
            "summary": raw.get("engineering_gate_summary", ""),
            "commands": list(raw.get("engineering_gate_commands") or []),
            "blocked": bool(raw.get("engineering_gate_blocked", False)),
        },
        "backlog": list(raw.get("backlog") or []),
        "reporter_auto_advance": _parse_bool(raw.get("reporter_auto_advance", False)),
    }


def _tier_c_default(registry_key: str) -> dict[str, Any]:
    return _normalize_plan(
        {
            "tier": "C",
            "intent": "Intake and assess only — no default pattern until default_profile is set",
            "maturity_target": "unassessed",
            "workflow": "reporter-mode",
            "workflow_source": "registry/workflows.yaml",
            "pattern": None,
            "validation_profile": "none",
            "engineering_gate_blocked": True,
            "research_gate_summary": (
                "Register project memory, run assess-project, and pass project-intake before engineering."
            ),
            "research_gate_commands": [
                f"liaison project-intake --project {registry_key} --show",
                "liaison assess-project --show",
            ],
            "engineering_gate_summary": (
                "Deferred: set default_profile in registry/repos.yaml and pick a pattern from hub_skills."
            ),
            "engineering_gate_commands": [],
            "backlog": [
                "liaison register-project <path> (if not registered)",
                "liaison assess-project --show",
                f"liaison project-intake --project {registry_key} --write",
            ],
        },
        registry_key,
    )


def _tier_b_fallback(registry_key: str, default_profile: str) -> dict[str, Any]:
    workflow = _PROFILE_WORKFLOW.get(default_profile, "reporter-mode")
    wf_source = (
        "workflows/sigma-integration.yaml"
        if workflow == "sigma-integration"
        else "config/skill_resolution.yaml"
        if workflow in ("python-cli", "rag-system", "ml-research", "ai-app")
        else "registry/workflows.yaml"
    )
    return _normalize_plan(
        {
            "tier": "B",
            "intent": f"Registered project ({default_profile} profile) — research intake then Hermes-led engineering",
            "maturity_target": "prototype",
            "workflow": workflow,
            "workflow_source": wf_source,
            "pattern": "hermes-led-slice",
            "validation_profile": default_profile,
            "research_gate_summary": "Project intake and assessment before start-pattern or init",
            "research_gate_commands": [
                f"liaison project-intake --project {registry_key} --show",
                "liaison assess-project --show",
            ],
            "engineering_gate_summary": f"Build slices with validate --profile {default_profile}",
            "engineering_gate_commands": [
                f"liaison start-pattern hermes-led-slice --task-id {registry_key}-slice-1",
                f"liaison validate --profile {default_profile}",
            ],
            "backlog": [
                "Complete intake blockers from project-intake",
                "Classify phase when assessment recommends maturity",
            ],
        },
        registry_key,
    )


def load_project_plan(registry_key: str) -> dict[str, Any] | None:
    """Load normalized plan for a registry repo key (registry + tier fallbacks)."""
    if not registry_key:
        return None
    plans = _parse_project_plans_yaml()
    if registry_key in plans:
        return _normalize_plan(plans[registry_key], registry_key)
    sf = _bridge()
    repos = sf.parse_registry_map("repos.yaml", "repos")
    fields = repos.get(registry_key)
    if not fields:
        return None
    profile = (fields.get("default_profile") or "none").strip()
    if profile == "none":
        return _tier_c_default(registry_key)
    return _tier_b_fallback(registry_key, profile)


def merge_plan_with_intake(plan: dict[str, Any], intake: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay intake readiness onto plan gates (optional)."""
    if not intake:
        return dict(plan)
    merged = dict(plan)
    eng = dict(merged.get("engineering_gate") or {})
    research = dict(merged.get("research_gate") or {})
    ready = bool(intake.get("ready_to_build"))
    lane = intake.get("recommended_lane", "research")
    if not ready:
        eng["blocked"] = True
        eng["intake_note"] = f"Engineering blocked until intake ready (lane: {lane})"
        research["intake_note"] = (
            f"{len(intake.get('blockers') or [])} blocker(s) — resolve research gate first"
        )
    else:
        eng["blocked"] = bool(eng.get("blocked")) and eng.get("blocked")
        eng["intake_note"] = "Intake ready — engineering gate may proceed"
    merged["engineering_gate"] = eng
    merged["research_gate"] = research
    merged["intake"] = {
        "intake_ready": intake.get("intake_ready"),
        "ready_to_build": ready,
        "recommended_lane": lane,
    }
    return merged


def _on_disk_plan_path(repo_path: str) -> Path | None:
    if not repo_path:
        return None
    memory = Path(repo_path).expanduser() / ".spark-flow" / "memory"
    target = memory / PLAN_FILENAME
    return target if target.exists() else None


def build_project_plan_card(
    project_key: str,
    repo_path: str,
    plan_registry: dict[str, Any] | None,
    focus: dict[str, Any] | None,
    open_tasks: list[dict] | None,
) -> dict[str, Any]:
    """JSON card for command-center when a project is focused."""
    open_tasks = open_tasks or []
    plan = plan_registry or load_project_plan(project_key)
    if not plan:
        return {
            "project": project_key,
            "path": repo_path,
            "has_registry_plan": False,
            "has_on_disk_plan": False,
        }
    on_disk = _on_disk_plan_path(repo_path)
    return {
        "project": project_key,
        "path": repo_path,
        "generated_at": _now(),
        "has_registry_plan": True,
        "has_on_disk_plan": on_disk is not None,
        "on_disk_path": str(on_disk) if on_disk else None,
        "tier": plan.get("tier"),
        "intent": plan.get("intent"),
        "maturity_target": plan.get("maturity_target"),
        "workflow": plan.get("workflow"),
        "workflow_source": plan.get("workflow_source"),
        "pattern": plan.get("pattern"),
        "validation_profile": plan.get("validation_profile"),
        "external_guide": plan.get("external_guide"),
        "research_gate": plan.get("research_gate"),
        "engineering_gate": plan.get("engineering_gate"),
        "backlog": plan.get("backlog", []),
        "intake": plan.get("intake"),
        "focus_phase": (focus or {}).get("phase"),
        "focus_lifecycle": (focus or {}).get("lifecycle"),
        "open_task_count": len(open_tasks),
        "reporter_auto_advance": bool(plan.get("reporter_auto_advance")),
        "liaison_cmd_write": f"liaison plan-project --project {project_key} --write",
    }


def _format_command_list(commands: list[str]) -> str:
    if not commands:
        return "- _(none)_"
    return "\n".join(f"- `{c}`" for c in commands)


def _format_backlog(lines: list[str]) -> str:
    if not lines:
        return "- _(empty)_"
    return "\n".join(f"- {line}" for line in lines)


def format_operating_plan_markdown(
    plan: dict[str, Any],
    *,
    project_key: str,
    repo_path: str,
    intake: dict[str, Any] | None = None,
) -> str:
    template = TEMPLATE_PATH.read_text(errors="replace") if TEMPLATE_PATH.exists() else ""
    if not template:
        template = "# Project operating plan: {{PROJECT_KEY}}\n"
    intake = intake or {}
    subs = {
        "PROJECT_KEY": project_key,
        "GENERATED_AT": _now(),
        "REPO_PATH": repo_path,
        "INTENT": plan.get("intent", "—"),
        "MATURITY_TARGET": plan.get("maturity_target", "unassessed"),
        "WORKFLOW": plan.get("workflow", "reporter-mode"),
        "WORKFLOW_SOURCE": plan.get("workflow_source", "—"),
        "PATTERN": plan.get("pattern") or "_(none — set after profile)_",
        "VALIDATION_PROFILE": plan.get("validation_profile", "none"),
        "EXTERNAL_GUIDE": plan.get("external_guide") or "—",
        "RESEARCH_GATE_SUMMARY": (plan.get("research_gate") or {}).get("summary", "—"),
        "RESEARCH_GATE_COMMANDS": _format_command_list(
            (plan.get("research_gate") or {}).get("commands", [])
        ),
        "ENGINEERING_GATE_SUMMARY": (plan.get("engineering_gate") or {}).get("summary", "—"),
        "ENGINEERING_GATE_COMMANDS": _format_command_list(
            (plan.get("engineering_gate") or {}).get("commands", [])
        ),
        "BACKLOG": _format_backlog(plan.get("backlog", [])),
        "INTAKE_READY": str(intake.get("intake_ready", "—")),
        "READY_TO_BUILD": str(intake.get("ready_to_build", "—")),
        "RECOMMENDED_LANE": intake.get("recommended_lane", "—"),
    }
    out = template
    for key, val in subs.items():
        out = out.replace(f"{{{{{key}}}}}", str(val))
    return out


def write_project_operating_plan(
    repo_path: str,
    plan: dict[str, Any],
    *,
    project_key: str,
    intake: dict[str, Any] | None = None,
) -> Path:
    memory = Path(repo_path).expanduser() / ".spark-flow" / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    target = memory / PLAN_FILENAME
    target.write_text(
        format_operating_plan_markdown(
            plan,
            project_key=project_key,
            repo_path=repo_path,
            intake=intake,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def resolve_project_key_and_path(project_key: str | None, cwd: Path | None = None) -> tuple[str, str]:
    from dashboard.command_center.project_intake import resolve_project_key_and_path as _resolve

    return _resolve(project_key, cwd=cwd)


def open_tasks_for_repo(repo_path: str) -> list[dict]:
    from dashboard.command_center.project_intake import open_tasks_for_repo as _open

    return _open(repo_path)


def _repo_memory_path(repo_path: str) -> Path | None:
    if not repo_path:
        return None
    memory = Path(repo_path).expanduser() / ".spark-flow" / "memory"
    return memory if memory.is_dir() else None


def build_projects_registry(state: dict | None = None) -> list[dict[str, Any]]:
    """All registered repos with intake/plan status for command-center JSON."""
    sf = _bridge()
    repos = sf.parse_registry_map("repos.yaml", "repos")
    matrix_by_key: dict[str, dict] = {}
    if state:
        for row in state.get("project_matrix", []):
            matrix_by_key[row["option"]] = row

    entries: list[dict[str, Any]] = []
    for key, fields in sorted(repos.items()):
        path = (fields.get("path") or "").strip()
        plan = load_project_plan(key)
        on_disk = _on_disk_plan_path(path) if path else None
        memory = _repo_memory_path(path)
        matrix_row = matrix_by_key.get(key, {})
        has_brief = bool(memory and (memory / "PROJECT_BRIEF.md").exists())
        has_phase = bool(memory and (memory / "project_phase.json").exists())
        entries.append(
            {
                "key": key,
                "path": path,
                "label": fields.get("label", key),
                "default_profile": fields.get("default_profile", "none"),
                "phase": matrix_row.get("phase", "—"),
                "lifecycle": matrix_row.get("lifecycle", "—"),
                "score": matrix_row.get("score", 0),
                "has_registry_plan": plan is not None,
                "has_on_disk_plan": on_disk is not None,
                "plan_tier": plan.get("tier") if plan else None,
                "has_brief": has_brief,
                "has_phase": has_phase,
                "liaison_cmd_intake": f"liaison project-intake --project {key} --show",
                "liaison_cmd_plan": f"liaison plan-project --project {key} --write",
                "liaison_cmd_focus": f"liaison command-center --project {key}",
            }
        )
    return entries


def build_registry_rolodex_entries(state: dict | None = None) -> list[dict[str, Any]]:
    """Rolodex project cards for every registered repo."""
    rows: list[dict[str, Any]] = []
    for reg in build_projects_registry(state):
        key = reg["key"]
        subtitle = f"repo · {reg['lifecycle']}/{reg['phase']} · profile {reg['default_profile']}"
        plan_bits = []
        if reg["has_on_disk_plan"]:
            plan_bits.append("plan on disk")
        elif reg["has_registry_plan"]:
            plan_bits.append(f"tier {reg.get('plan_tier', '?')} plan")
        else:
            plan_bits.append("no plan")
        if reg["has_brief"]:
            plan_bits.append("brief")
        summary = f"Score {reg['score']} · " + ", ".join(plan_bits)
        actions = [
            {"label": "Run intake", "liaison_cmd": reg["liaison_cmd_intake"]},
            {"label": "Write plan", "liaison_cmd": reg["liaison_cmd_plan"]},
            {"label": "Focus command center", "liaison_cmd": reg["liaison_cmd_focus"]},
        ]
        if reg["path"]:
            actions.append(
                {
                    "label": "Open repo",
                    "liaison_cmd": f"cd {reg['path']} && liaison look",
                }
            )
        rows.append(
            {
                "id": f"repo:{key}",
                "title": reg.get("label") or key,
                "subtitle": subtitle,
                "summary": summary,
                "launch": reg["liaison_cmd_intake"],
                "path": reg["path"] or f"registry/repos.yaml#{key}",
                "actions": actions,
                "meta": {
                    "kind": "registered_repo",
                    "registry_key": key,
                    "default_profile": reg["default_profile"],
                    "has_registry_plan": reg["has_registry_plan"],
                    "has_on_disk_plan": reg["has_on_disk_plan"],
                    "has_brief": reg["has_brief"],
                    "phase": reg["phase"],
                    "lifecycle": reg["lifecycle"],
                    "score": reg["score"],
                },
            }
        )
    return rows
