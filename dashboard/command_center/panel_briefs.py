"""Operator-readable briefs for Overview, Workstream, and Ops panels."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from liaison_paths import AGENT_SYSTEM_DIR

TASK_PHASE_COMMANDS = {
    "plan": "liaison start build",
    "build": "liaison start build",
    "patch": "liaison start build",
    "review": "liaison approve",
    "close": "liaison close-task",
    "complete": "liaison close-task",
}


def _liaisonify_command(cmd: str) -> str:
    """Prefer liaison CLI prefix for workflow hints shown in the dashboard."""
    stripped = cmd.strip()
    if stripped.startswith("liaison "):
        return stripped
    if stripped.startswith("spark-flow "):
        return "liaison " + stripped[len("spark-flow ") :]
    return stripped


def load_workflow_phases(workflow_name: str, workflow_source: str | None = None) -> list[dict[str, Any]]:
    """Load ordered workflow phases from YAML (id, label, suggested liaison_commands)."""
    if workflow_source:
        path = Path(workflow_source).expanduser()
        if not path.is_absolute():
            path = AGENT_SYSTEM_DIR / workflow_source
    elif workflow_name:
        path = AGENT_SYSTEM_DIR / "workflows" / f"{workflow_name}.yaml"
    else:
        return []

    if not path.exists():
        return []

    text = path.read_text(errors="replace")
    if not text.strip():
        return []

    # List-style: phases:\n  - id: foo
    if re.search(r"^phases:\s*\n\s*-\s+id:", text, re.M):
        return _parse_workflow_phases_list(text)

    return _parse_workflow_phases_dict(text)


def _parse_workflow_phases_list(text: str) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    list_context: str | None = None
    in_phases = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "phases:":
            in_phases = True
            continue
        if not in_phases:
            continue
        if in_phases and line.startswith("validation_profile:"):
            break
        if line.startswith("  - id:"):
            if current:
                phases.append(current)
            current = {
                "id": stripped.split(":", 1)[1].strip().strip('"\''),
                "label": "",
                "objective": "",
                "artifacts": [],
                "suggested_liaison_commands": [],
            }
            list_context = None
        elif current and line.startswith("    ") and not line.startswith("      "):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"\'')
            if key == "label":
                current["label"] = val
            elif key in ("liaison_commands", "artifacts"):
                list_context = key
        elif current and line.startswith("      - ") and list_context:
            item = stripped.lstrip("- ").strip()
            if list_context == "liaison_commands":
                current["suggested_liaison_commands"].append(_liaisonify_command(item))
            elif list_context == "artifacts":
                current["artifacts"].append(item)

    if current:
        if not current.get("label"):
            current["label"] = current["id"].replace("-", " ").title()
        phases.append(current)
    return phases


def _parse_workflow_phases_dict(text: str) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    current_id: str | None = None
    current: dict[str, Any] = {}
    in_phases = False
    list_context: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "phases:":
            in_phases = True
            continue
        if not in_phases:
            continue
        if in_phases and line.startswith("quality_gates:"):
            break
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            if current_id:
                current["suggested_liaison_commands"] = [
                    _liaisonify_command(c) for c in current.get("_commands", [])
                ]
                current.pop("_commands", None)
                phases.append(current)
            current_id = stripped[:-1]
            current = {
                "id": current_id,
                "label": current_id.replace("_", " ").title(),
                "objective": "",
                "artifacts": [],
                "_commands": [],
            }
            list_context = None
        elif current_id and line.startswith("    ") and not line.startswith("      "):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"\'')
            if key == "objective":
                current["objective"] = val
                if val:
                    current["label"] = val[:72]
            elif key in ("commands", "artifacts"):
                list_context = key
        elif current_id and line.startswith("      - ") and list_context:
            item = stripped.lstrip("- ").strip()
            if list_context == "commands":
                current.setdefault("_commands", []).append(item)
            elif list_context == "artifacts":
                current.setdefault("artifacts", []).append(item)

    if current_id:
        current["suggested_liaison_commands"] = [
            _liaisonify_command(c) for c in current.get("_commands", [])
        ]
        current.pop("_commands", None)
        phases.append(current)

    return phases


def pick_next_workflow_phase(
    phases: list[dict[str, Any]],
    task: dict | None,
) -> dict[str, Any] | None:
    """First workflow phase whose artifacts are not all present on the focused task."""
    if not phases:
        return None
    task_path = Path(task["path"]) if task and task.get("path") else None
    if not task_path or not task_path.is_dir():
        return phases[0]
    for phase in phases:
        artifacts = phase.get("artifacts") or []
        if not artifacts:
            continue
        missing = [a for a in artifacts if not (task_path / a).exists()]
        if missing:
            out = dict(phase)
            out["missing_artifacts"] = missing
            return out
    return None


def _focused_task(state: dict) -> dict | None:
    kb = state.get("kanban") or {}
    for bucket in ("in_progress", "todo", "review"):
        tasks = kb.get(bucket) or []
        if tasks:
            return tasks[0]
    return None


def build_overview_brief(state: dict) -> dict[str, Any]:
    """Structured copy for Overview tab panels (TUI + web)."""
    focus = state.get("focus") or {}
    project = state.get("selected_project")
    summary = state.get("summary") or {}
    kb = state.get("kanban") or {}
    signoff = state.get("ops_signoff") or {}

    if project and focus:
        project_body = (
            f"Focused on {project} — lifecycle {focus.get('lifecycle', '—')} / "
            f"phase {focus.get('phase', '—')}. Validation: {focus.get('validation', '—')}. "
            f"Default profile: {focus.get('default_profile', 'none')}. "
            "Workstream kanban, intake, plan, and hub agents all follow this focus until you press Esc."
        )
        exit_items = focus.get("exit_criteria") or []
        project_bullets = [str(x)[:120] for x in exit_items[:6]]
    else:
        project_body = (
            "No project focus yet. Pick a repo in the Workstream project list (↑↓ Enter) "
            "so intake, operating plan, hub recommendations, and ops signoff align to one codebase."
        )
        project_bullets = [
            f"{row.get('option', '?')[:20]} — score {row.get('score', 0)} "
            f"{row.get('lifecycle', '—')}/{row.get('phase', '—')}"
            for row in (state.get("project_matrix") or [])[:5]
        ]

    open_n = summary.get("filtered_open", summary.get("open_tasks", 0))
    total_n = summary.get("open_tasks", 0)
    work_body = (
        f"{open_n} open task(s) in focus · {total_n} total across repos. "
        "Move cards by advancing reporter steps: init → snapshot → attach specialist → "
        "approve-artifact → validate → close-task."
    )
    work_bullets = []
    for bucket, title in (
        ("todo", "TODO"),
        ("in_progress", "IN PROGRESS"),
        ("review", "REVIEW"),
    ):
        for task in (kb.get(bucket) or [])[:2]:
            work_bullets.append(
                f"[{title}] {task.get('task_id', '?')[:16]} · "
                f"{task.get('current_phase', '?')} — "
                f"{str(task.get('description', ''))[:48]}"
            )

    recommended = [r for r in state.get("agent_rows", []) if r.get("recommended")]
    active = [r for r in state.get("agent_rows", []) if r.get("tasks")]
    hub_body = (
        "Hub agents run in terminal panes; liaison governs tasks and outbox. "
        "Default lane is Hermes; attach ml_intern, qca, or unsloth reports before merge."
    )
    hub_bullets = []
    for row in recommended[:4]:
        resume = row.get("resume") or {}
        line = resume.get("headline") or row.get("role", row["name"])
        hub_bullets.append(f"★ {row['display']}: {line[:72]}")
    for row in active[:3]:
        if row not in recommended:
            hub_bullets.append(f"• {row['display']} — {row['tasks']} task(s)")

    patterns = [
        e for e in state.get("rolodex", {}).get("projects", []) if e.get("recommended")
    ]
    skills = [e for e in state.get("rolodex", {}).get("skills", []) if e.get("recommended")]
    pattern_body = (
        f"Phase-fit patterns: {len(patterns)} · recommended skills: {len(skills)}. "
        "Patterns define multi-agent handoffs (Hermes-led, research-to-calibration, flywheel)."
    )
    pattern_bullets = [f"★ {e.get('title', '?')[:56]}" for e in patterns[:4]]
    pattern_bullets.extend(
        f"skill · {e.get('title', '?')[:40]}" for e in skills[:3]
    )

    ops_body = (
        f"Signoff state: {signoff.get('pending_handoff_count', 0)} pending handoff(s), "
        f"{signoff.get('gate_failures', 0)} gate failure(s), "
        f"{signoff.get('flywheel_open', 0)} flywheel task(s). "
        f"Debrief age: {signoff.get('debrief_age', '—')}. "
        "Use the Ops tab for approve-artifact, validate, and close-task copy targets."
    )
    ops_bullets = [
        f"{'✓' if s.get('done') else '○'} {s.get('label', '')[:64]}"
        for s in (signoff.get("checklist") or [])[:6]
    ]

    return {
        "project": {"title": "Project focus", "body": project_body, "bullets": project_bullets},
        "work": {"title": "Workstream", "body": work_body, "bullets": work_bullets},
        "hub": {"title": "Agent hub", "body": hub_body, "bullets": hub_bullets},
        "patterns": {"title": "Patterns & skills", "body": pattern_body, "bullets": pattern_bullets},
        "ops": {"title": "Ops signoff", "body": ops_body, "bullets": ops_bullets},
        "playbook": _playbook_steps(state),
    }


def _playbook_steps(state: dict) -> list[dict[str, str]]:
    project = state.get("selected_project")
    steps = [
        {
            "id": "sync",
            "label": "Sync state",
            "detail": "Refresh tasks, matrix, intake, and metrics from disk.",
        },
    ]
    if not project:
        steps.append(
            {
                "id": "focus",
                "label": "Focus a project",
                "detail": "Workstream → project list — links every panel.",
            }
        )
        return steps
    intake = state.get("project_intake") or {}
    plan = state.get("project_plan") or {}
    steps.extend(
        [
            {
                "id": "intake",
                "label": "Intake",
                "detail": "Ready to build"
                if intake.get("ready_to_build")
                else f"Blocked — {len(intake.get('blockers') or [])} blocker(s)",
            },
            {
                "id": "plan",
                "label": "Operating plan",
                "detail": (
                    f"{plan.get('workflow', '—')} · "
                    f"{'on disk' if plan.get('has_on_disk_plan') else 'registry'}"
                ),
            },
            {
                "id": "hub",
                "label": "Hub slice",
                "detail": f"Agents: {', '.join((state.get('focus') or {}).get('recommended_agents') or []) or '—'}",
            },
            {
                "id": "ops",
                "label": "Ops signoff",
                "detail": "Clear handoffs and gates before close-task",
            },
        ]
    )
    return steps


def build_workstream_brief(state: dict) -> dict[str, Any]:
    """Workstream tab: project playbook + reporter how-to."""
    project = state.get("selected_project")
    if not project:
        return {
            "title": "Workstream",
            "body": (
                "Select a project in the list below to bind kanban, reporter checklist, "
                "intake/plan strips, and overview focus. Esc clears focus."
            ),
            "reporter_how_to": (
                "Reporter path: liaison init <task> → snapshot → run hub agent → "
                "liaison attach <agent> --file report.md → approve-artifact → "
                "validate --profile <name> → close-task."
            ),
            "sections": [],
        }

    intake = state.get("project_intake") or {}
    plan = state.get("project_plan") or {}
    corpus = state.get("build_corpus_summary") or {}
    task = _focused_task(state)
    sections: list[dict[str, Any]] = []

    sections.append(
        {
            "title": "Intake",
            "body": (
                f"Intake {'passed' if intake.get('intake_ready') else 'incomplete'} · "
                f"build {'ready' if intake.get('ready_to_build') else 'blocked'} · "
                f"lane {intake.get('recommended_lane', '—')}."
            ),
            "bullets": [
                b.get("label", "")[:80] for b in (intake.get("blockers") or [])[:4]
            ],
        }
    )
    if plan:
        eng = plan.get("engineering_gate") or {}
        sections.append(
            {
                "title": "Operating plan",
                "body": (
                    f"Tier {plan.get('tier', '—')} · workflow {plan.get('workflow', '—')} · "
                    f"pattern {plan.get('pattern') or '—'} · profile {plan.get('validation_profile', 'none')}."
                ),
                "bullets": list((eng.get("commands") or [])[:4]),
            }
        )
    if corpus:
        sections.append(
            {
                "title": "Build corpus",
                "body": (
                    f"{corpus.get('build_steps_recorded', 0)} recorded steps · "
                    f"{corpus.get('exported_recipes', 0)} exported recipes."
                ),
                "bullets": [
                    corpus.get("liaison_record", ""),
                    corpus.get("liaison_export", ""),
                ],
            }
        )

    reporter_how_to = (
        "On the focused task: (1) liaison init if no BRIEF.md, (2) liaison snapshot after context changes, "
        "(3) launch hub agent and save report to outbox, (4) liaison attach <agent> --file <report>, "
        "(5) liaison approve-artifact when review passes, (6) liaison validate --profile <profile>, "
        "(7) liaison close-task with summary."
    )
    task_line = ""
    if task:
        steps = task.get("reporter_steps") or {}
        order = ("init", "snapshot", "attach", "approve", "validate", "close")
        marks = []
        for key in order:
            val = steps.get(key, False)
            mark = "✓" if val else ("!" if key == "approve" and steps.get("attach") else "○")
            marks.append(f"{mark} {key}")
        task_line = f"Active task {task.get('task_id', '?')}: {' · '.join(marks)}"

    next_wf = state.get("next_workflow_step")
    if next_wf:
        wf_bullets = list(next_wf.get("suggested_liaison_commands") or [])[:4]
        missing = next_wf.get("missing_artifacts") or []
        wf_body = f"Phase {next_wf.get('id', '?')}: {next_wf.get('label', '')[:80]}"
        if missing:
            wf_body += f" — missing: {', '.join(missing[:3])}"
        sections.append(
            {
                "title": "Next workflow step",
                "body": wf_body,
                "bullets": wf_bullets,
            }
        )

    return {
        "title": f"Workstream · {project}",
        "body": task_line or "No open kanban card for this focus — init a task or pick another project.",
        "reporter_how_to": reporter_how_to,
        "sections": sections,
    }


def enrich_ops_signoff(signoff: dict, state: dict) -> dict:
    """Add narrative summary and how-to lines for ops panel."""
    project = state.get("selected_project")
    ready = signoff.get("ready_for_signoff")
    summary = (
        "All signoff gates clear — you may close the focused slice when validation passes."
        if ready
        else "Action required before closeout: clear pending handoffs, fix gate blockers, "
        "and refresh debrief if stale."
    )
    if project:
        summary += f" Focus project: {project}."
    playbook = [
        "Review pending handoffs in outbox — approve or reject with reason.",
        "Run liaison gate / validate for the task validation profile.",
        "liaison debrief --show when choosing the next slice.",
        "liaison close-task only after checklist items are ✓.",
    ]
    how_to_map = {
        "signoff:handoffs": (
            "Open liaison look, find pending_approval rows, then "
            "liaison approve-artifact <path> or reject-artifact with a reason."
        ),
        "signoff:gates": (
            "Run liaison status on the task; fix GATE_REPORT.md failures; "
            "re-run liaison validate --profile <project profile>."
        ),
        "signoff:flywheel": (
            "For data-flywheel tasks: complete observe/curate/evaluate artifacts "
            "before promotion — see policies/data-flywheel-policy.md."
        ),
        "signoff:debrief": (
            "liaison debrief --show ranks next paths; liaison choose <n> records operator decision."
        ),
        "signoff:intake": (
            "liaison project-intake --project <key> --show; resolve blockers before executor launch."
        ),
        "signoff:validate": (
            "liaison validate --profile from registry/repos.yaml default_profile "
            "(or none to skip)."
        ),
    }
    checklist = []
    for step in signoff.get("checklist") or []:
        item = dict(step)
        item["how_to"] = how_to_map.get(step.get("id", ""), step.get("detail", ""))
        checklist.append(item)
    out = dict(signoff)
    out["summary"] = summary
    out["playbook"] = playbook
    out["checklist"] = checklist
    return out


def format_brief_section(section: dict[str, Any], *, plain_fn) -> list[str]:
    """Render one brief section to Rich lines."""
    lines = [f"[bold]{plain_fn(section.get('title', ''))}[/bold]", f"  {plain_fn(section.get('body', ''))}"]
    for bullet in section.get("bullets") or []:
        if bullet:
            lines.append(f"  • {plain_fn(str(bullet)[:100])}")
    return lines


def format_overview_panel_text(brief: dict[str, Any], key: str, *, plain_fn) -> str:
    section = brief.get(key) or {}
    return "\n".join(format_brief_section(section, plain_fn=plain_fn))


def format_workstream_guide_text(brief: dict[str, Any], *, plain_fn) -> str:
    lines = [f"[bold]{plain_fn(brief.get('title', 'Workstream'))}[/bold]", f"  {plain_fn(brief.get('body', ''))}"]
    if brief.get("reporter_how_to"):
        lines.extend(["", "[bold]Reporter path[/bold]", f"  {plain_fn(brief['reporter_how_to'])[:520]}"])
    for section in brief.get("sections") or []:
        lines.append("")
        lines.extend(format_brief_section(section, plain_fn=plain_fn))
    return "\n".join(lines)


def format_ops_signoff_text(signoff: dict[str, Any], *, plain_fn) -> str:
    lines = [
        "[bold]Ops signoff[/bold]",
        f"  {plain_fn(signoff.get('summary', ''))}",
        "",
        "[bold]Playbook[/bold]",
    ]
    for step in signoff.get("playbook") or []:
        lines.append(f"  • {plain_fn(str(step)[:100])}")
    lines.append("")
    lines.append("[bold]Checklist[/bold]")
    for step in signoff.get("checklist") or []:
        mark = "✓" if step.get("done") else "○"
        lines.append(f"  {mark} {plain_fn(step.get('label', ''))}")
        how = step.get("how_to") or step.get("detail")
        if how:
            lines.append(f"     [dim]{plain_fn(str(how)[:90])}[/dim]")
    pending = signoff.get("pending_handoffs") or []
    if pending:
        lines.extend(["", "[bold]Pending handoffs[/bold]"])
        for row in pending[:5]:
            lines.append(
                f"  • {plain_fn(row.get('task_id', ''))} {plain_fn(row.get('artifact', '')[:32])}"
            )
    hints = signoff.get("copy_hints") or []
    if hints:
        lines.extend(["", "[bold]Copy hints[/bold] [dim](!)[/dim]"])
        for hint in hints[:4]:
            lines.append(f"  • {plain_fn(hint.get('label', ''))}: {plain_fn(hint.get('liaison_cmd', ''))}")
    return "\n".join(lines)
