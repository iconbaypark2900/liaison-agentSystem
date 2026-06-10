"""Deterministic project intake readiness — knowledge + hygiene before build."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

BRIEF_PLACEHOLDER = "Describe what this project is trying to become"
STATE_PLACEHOLDER = "No debrief has been recorded yet"
UNASSESSED_PHASE = "unassessed"
LIFECYCLE_REGISTERED = "registered"

CHECK_ORDER = (
    "registry_path",
    "project_brief",
    "task_hygiene",
    "current_state",
    "lifecycle",
    "assessment",
    "phase_classified",
    "runnable",
    "decisions_or_scope",
)


def _bridge():
    from dashboard.command_center.data import _bridge as data_bridge

    return data_bridge()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="replace")


def _brief_has_substance(text: str) -> bool:
    if not text.strip():
        return False
    if BRIEF_PLACEHOLDER.lower() in text.lower():
        purpose = ""
        in_purpose = False
        for line in text.splitlines():
            if re.match(r"^##\s+Purpose\s*$", line, re.I):
                in_purpose = True
                continue
            if in_purpose and line.startswith("##"):
                break
            if in_purpose:
                purpose += line + "\n"
        if not purpose.strip() or BRIEF_PLACEHOLDER.lower() in purpose.lower():
            return False
    return len(text.strip()) > 80


def _current_state_substantive(text: str) -> bool:
    if not text.strip():
        return False
    if STATE_PLACEHOLDER in text and len(text.strip()) < 120:
        return False
    return True


def _decisions_substantive(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return len(lines) >= 1


def _non_goals_substantive(brief: str) -> bool:
    match = re.search(r"^##\s+Non-goals\s*$", brief, re.I | re.M)
    if not match:
        return False
    rest = brief[match.end() :]
    chunk = rest.split("##")[0].strip()
    return len(chunk) > 20 and "list" not in chunk.lower()[:30]


def _open_tasks_missing_brief(open_tasks: list[dict]) -> list[str]:
    missing = []
    for task in open_tasks:
        if task.get("closed"):
            continue
        path = task.get("path")
        if not path:
            continue
        brief = Path(path) / "BRIEF.md"
        if not brief.exists():
            missing.append(task.get("task_id") or str(path))
    return missing


def _run_checks(
    project_key: str,
    repo_path: str,
    open_tasks: list[dict],
) -> list[dict]:
    root = Path(repo_path).expanduser() if repo_path else None
    memory = root / ".spark-flow" / "memory" if root else None
    sf = _bridge()

    phase_state = sf.read_repo_phase_state(repo_path) if repo_path else {"phase": "—", "lifecycle": "—"}
    phase = (phase_state.get("phase") or "—").lower()
    lifecycle = (phase_state.get("lifecycle") or "—").lower()

    brief_path = memory / "project_brief.md" if memory else None
    state_path = memory / "current_state.md" if memory else None
    assess_path = memory / "ASSESSMENT.md" if memory else None
    decisions_path = memory / "decisions.md" if memory else None

    brief_text = _read_text(brief_path) if brief_path else ""
    state_text = _read_text(state_path) if state_path else ""
    decisions_text = _read_text(decisions_path) if decisions_path else ""

    commands = sf.detect_project_commands(root) if root and root.is_dir() else {}
    has_build_test = bool(
        commands.get("build") or commands.get("test") or commands.get("validate")
    )
    missing_briefs = _open_tasks_missing_brief(open_tasks)

    checks: list[dict] = []

    def add(
        cid: str,
        severity: str,
        passed: bool,
        label: str,
        detail: str,
        liaison_cmd: str | None = None,
        path: str | None = None,
    ) -> None:
        checks.append(
            {
                "id": cid,
                "severity": severity,
                "pass": passed,
                "label": label,
                "detail": detail,
                "liaison_cmd": liaison_cmd,
                "path": str(path) if path else None,
            }
        )

    add(
        "registry_path",
        "critical",
        bool(root and root.is_dir()),
        "Registry path exists",
        f"Resolved path: {repo_path or '—'}",
        "liaison register-project <path>",
        str(root) if root else None,
    )
    add(
        "project_brief",
        "critical",
        bool(brief_path and brief_path.exists() and _brief_has_substance(brief_text)),
        "Project brief filled",
        "Purpose and scope documented in project_brief.md",
        "liaison memory-init && edit .spark-flow/memory/project_brief.md",
        str(brief_path) if brief_path else None,
    )
    add(
        "task_hygiene",
        "critical",
        len(missing_briefs) == 0,
        "Open tasks have BRIEF",
        "All open tasks need BRIEF.md"
        if missing_briefs
        else "No open tasks missing BRIEF",
        "liaison index-tasks --show",
        None,
    )
    add(
        "current_state",
        "warn",
        bool(state_path and state_path.exists() and _current_state_substantive(state_text)),
        "Current state updated",
        "Run debrief or edit current_state.md with real architecture/status",
        "liaison debrief",
        str(state_path) if state_path else None,
    )
    add(
        "lifecycle",
        "warn",
        lifecycle not in ("", "—", LIFECYCLE_REGISTERED),
        "Lifecycle beyond registered",
        f"Lifecycle: {lifecycle}",
        "liaison assess-project",
        str(memory / "project_phase.json") if memory else None,
    )
    add(
        "assessment",
        "warn",
        bool(assess_path and assess_path.exists()),
        "Assessment on disk",
        "ASSESSMENT.md records maturity evidence",
        "liaison assess-project --show",
        str(assess_path) if assess_path else None,
    )
    add(
        "phase_classified",
        "warn",
        phase not in ("", "—", UNASSESSED_PHASE),
        "Project phase classified",
        f"Phase: {phase}",
        "liaison project-phase classify --from-assessment --yes",
        str(memory / "PROJECT_PHASE.md") if memory else None,
    )
    runnable_ok = has_build_test or phase == "prototype"
    add(
        "runnable",
        "warn",
        runnable_ok,
        "Runnable or prototype",
        "Build/test/validate detected"
        if has_build_test
        else "Prototype phase allows scaffold-first path",
        "liaison discover-projects --show",
        str(root) if root else None,
    )
    scope_ok = _decisions_substantive(decisions_text) or _non_goals_substantive(brief_text)
    add(
        "decisions_or_scope",
        "warn",
        scope_ok,
        "Scope or decisions recorded",
        "Non-goals in brief or entries in decisions.md",
        None,
        str(decisions_path) if decisions_path else None,
    )

    if missing_briefs and checks:
        for c in checks:
            if c["id"] == "task_hygiene":
                c["detail"] = f"Missing BRIEF: {', '.join(missing_briefs[:5])}"

    return checks


def _checks_to_blockers(checks: list[dict]) -> list[dict]:
    blockers = []
    for c in checks:
        if c["pass"]:
            continue
        blockers.append(
            {
                "id": c["id"],
                "severity": c["severity"],
                "label": c["label"],
                "detail": c["detail"],
                "liaison_cmd": c.get("liaison_cmd"),
                "path": c.get("path"),
            }
        )
    order = {"critical": 0, "warn": 1}
    blockers.sort(key=lambda b: (order.get(b["severity"], 9), b["id"]))
    return blockers


def _recommended_lane(checks: list[dict], intake_ready: bool, ready_to_build: bool) -> str:
    if ready_to_build:
        return "execute"
    if not intake_ready:
        failed = {c["id"] for c in checks if not c["pass"]}
        if "project_brief" in failed or "registry_path" in failed:
            return "research"
        if "task_hygiene" in failed:
            return "scaffold"
        return "research"
    failed_warn = {c["id"] for c in checks if not c["pass"] and c["severity"] == "warn"}
    if failed_warn & {"phase_classified", "lifecycle", "assessment"}:
        return "classify"
    if failed_warn & {"current_state", "decisions_or_scope", "runnable"}:
        return "research"
    return "scaffold"


def build_project_intake(
    project_key: str,
    repo_path: str,
    open_tasks: list[dict] | None = None,
) -> dict[str, Any]:
    """Score intake readiness for a registered project (read-only)."""
    open_tasks = open_tasks or []
    checks = _run_checks(project_key, repo_path, open_tasks)
    critical_fail = [c for c in checks if c["severity"] == "critical" and not c["pass"]]
    warn_fail = [c for c in checks if c["severity"] == "warn" and not c["pass"]]
    intake_ready = len(critical_fail) == 0
    brief_ok = any(c["id"] == "project_brief" and c["pass"] for c in checks)
    ready_to_build_strict = intake_ready and len(warn_fail) == 0
    ready_to_build_soft = intake_ready and brief_ok
    ready_to_build = ready_to_build_strict
    blockers = _checks_to_blockers(checks)
    return {
        "project": project_key,
        "path": repo_path,
        "generated_at": _now(),
        "intake_ready": intake_ready,
        "ready_to_build": ready_to_build,
        "ready_to_build_strict": ready_to_build_strict,
        "ready_to_build_soft": ready_to_build_soft,
        "recommended_lane": _recommended_lane(checks, intake_ready, ready_to_build_strict),
        "checks": checks,
        "blockers": blockers,
        "summary": {
            "critical_fail": len(critical_fail),
            "warn_fail": len(warn_fail),
            "intake_blockers": len([b for b in blockers if b["severity"] == "critical"]),
        },
    }


def format_intake_report(intake: dict[str, Any]) -> str:
    lines = [
        "# Project intake report",
        "",
        f"- Project: `{intake.get('project', '—')}`",
        f"- Path: `{intake.get('path', '—')}`",
        f"- Generated: {intake.get('generated_at', '—')}",
        f"- Intake ready: {intake.get('intake_ready')}",
        f"- Ready to build (strict): {intake.get('ready_to_build_strict', intake.get('ready_to_build'))}",
        f"- Ready to build (soft): {intake.get('ready_to_build_soft', False)}",
        f"- Recommended lane: {intake.get('recommended_lane')}",
        "",
        "## Checks",
        "",
    ]
    for c in intake.get("checks", []):
        mark = "pass" if c.get("pass") else "FAIL"
        lines.append(f"- [{mark}] **{c.get('label')}** ({c.get('severity')}): {c.get('detail')}")
        if c.get("liaison_cmd") and not c.get("pass"):
            lines.append(f"  - Fix: `{c['liaison_cmd']}`")
    if intake.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        for b in intake["blockers"]:
            lines.append(f"- **{b.get('label')}**: {b.get('detail')}")
    lines.append("")
    return "\n".join(lines)


def open_tasks_for_repo(repo_path: str) -> list[dict]:
    """List open tasks under a repo for intake hygiene checks."""
    tasks_dir = Path(repo_path).expanduser() / ".spark-flow" / "tasks"
    if not tasks_dir.exists():
        return []
    rows = []
    for task_path in sorted(tasks_dir.iterdir()):
        if not task_path.is_dir():
            continue
        state_file = task_path / "STATE.txt"
        phase = "unknown"
        if state_file.exists():
            for line in state_file.read_text(errors="replace").splitlines():
                if line.startswith("CURRENT_PHASE:"):
                    phase = line.split(":", 1)[1].strip()
                    break
        if phase == "complete":
            continue
        rows.append(
            {
                "task_id": task_path.name,
                "path": str(task_path),
                "closed": False,
                "current_phase": phase,
            }
        )
    return rows


def resolve_project_key_and_path(
    project_key: str | None,
    cwd: Path | None = None,
) -> tuple[str, str]:
    """Resolve registry key and repo path from --project or cwd."""
    sf = _bridge()
    repos = sf.parse_registry_map("repos.yaml", "repos")
    cwd = cwd or Path.cwd()
    if project_key:
        fields = repos.get(project_key)
        if fields:
            return project_key, fields.get("path", "")
        for name, data in repos.items():
            if name == project_key or project_key in (data.get("path", ""),):
                return name, data.get("path", "")
        return project_key, ""
    resolved = cwd.resolve()
    for name, data in repos.items():
        try:
            if Path(data.get("path", "")).expanduser().resolve() == resolved:
                return name, data.get("path", "")
        except OSError:
            continue
    return resolved.name, str(resolved)


def write_intake_report(repo_path: str, intake: dict[str, Any]) -> Path:
    memory = Path(repo_path).expanduser() / ".spark-flow" / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    target = memory / "INTAKE_REPORT.md"
    target.write_text(format_intake_report(intake) + "\n", encoding="utf-8")
    return target
