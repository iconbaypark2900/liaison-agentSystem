"""Rich project portfolio detail for dashboard, TUI, and rolodex."""

from __future__ import annotations

from typing import Any

from dashboard.command_center.project_plans import load_project_plan


def _pattern_fit(project_key: str, plan: dict | None, pattern: dict) -> tuple[int, str]:
    """Score 0–100 and reason why pattern matches focused project."""
    if not plan:
        return 0, "No operating plan — run plan-project after intake"
    pid = plan.get("pattern")
    pat_id = pattern.get("id", "")
    if pid and pid == pat_id:
        return 100, f"Registry default pattern: {pat_id}"
    agents = set(pattern.get("agents") or [])
    specialists = set(pattern.get("specialists") or [])
    when = (pattern.get("when") or "").lower()
    intent = (plan.get("intent") or "").lower()
    score = 40
    reasons = []
    if "research" in intent and "research" in pat_id:
        score += 25
        reasons.append("research intent")
    if "calibrat" in intent and "calibration" in pat_id:
        score += 25
        reasons.append("calibration scope")
    if "flywheel" in intent and "flywheel" in pat_id:
        score += 30
        reasons.append("flywheel improvement")
    if plan.get("workflow") and plan["workflow"] in when:
        score += 15
        reasons.append(f"workflow {plan['workflow']}")
    if specialists & {"ml_intern", "qca", "unsloth_studio"}:
        score += 10
        reasons.append("specialists in pattern")
    return min(score, 95), "; ".join(reasons) or "General hub pattern"


def build_hub_workflows_for_project(state: dict) -> list[dict[str, Any]]:
    """Ranked multi-agent patterns for the focused registry project."""
    project = state.get("selected_project")
    if not project:
        return []
    plan = state.get("project_plan") or load_project_plan(project)
    patterns = state.get("project_agent_patterns") or []
    rows: list[dict[str, Any]] = []
    for pattern in patterns:
        agents = list(pattern.get("agents") or [])
        specialists = list(pattern.get("specialists") or [])
        chain = agents + [s for s in specialists if s not in agents]
        score, reason = _pattern_fit(project, plan, pattern)
        rows.append(
            {
                "id": pattern.get("id", "?"),
                "label": pattern.get("label", pattern.get("id", "?")),
                "when": pattern.get("when", ""),
                "agents": chain,
                "steps": list(pattern.get("steps") or []),
                "fit_score": score,
                "fit_reason": reason,
                "recommended": score >= 70,
                "liaison_cmd": f"liaison start-pattern {pattern.get('id')} --task-id {project}-slice-1",
            }
        )
    return sorted(rows, key=lambda r: (-r["fit_score"], r["label"]))


def build_project_detail(state: dict, registry_key: str | None = None) -> dict[str, Any] | None:
    """Full portfolio card: goals, agents, skills, production path, research."""
    key = registry_key or state.get("selected_project")
    if not key:
        return None
    from dashboard.command_center.project_plans import build_projects_registry

    reg = next((r for r in build_projects_registry(state) if r["key"] == key), None)
    plan = load_project_plan(key)
    if state.get("selected_project") == key:
        plan_state = state.get("project_plan") or plan
        intake = state.get("project_intake")
    else:
        plan_state = plan
        intake = None

    focus = state.get("focus") if state.get("selected_project") == key else None
    if not focus and reg:
        from dashboard.command_center.data import build_focus

        focus = build_focus(key)

    patterns = build_hub_workflows_for_project(
        {**state, "selected_project": key, "project_plan": plan_state}
    )
    primary = next((p for p in patterns if p.get("recommended")), patterns[0] if patterns else None)

    agents: list[str] = []
    specialists: list[str] = []
    if primary:
        agents = [a for a in primary.get("agents", []) if a in ("hermes", "liaison", "data_flywheel")]
        specialists = [a for a in primary.get("agents", []) if a not in agents]

    if plan_state and plan_state.get("pattern"):
        pat = next((p for p in patterns if p["id"] == plan_state["pattern"]), None)
        if pat:
            agents = list(pat.get("agents") or [])[:4]
            specialists = [a for a in pat.get("agents", []) if a not in ("hermes", "liaison")]

    if focus:
        for name in focus.get("recommended_agents") or []:
            if name not in agents and name not in specialists:
                if name in ("hermes", "liaison", "data_flywheel"):
                    agents.append(name)
                else:
                    specialists.append(name)

    production: list[dict[str, str]] = []
    if reg:
        production.append(
            {
                "id": "brief",
                "label": "Project brief on disk",
                "done": reg.get("has_brief", False),
                "detail": "PROJECT_BRIEF.md in .spark-flow/memory",
            }
        )
        production.append(
            {
                "id": "phase",
                "label": "Phase classified",
                "done": reg.get("has_phase", False),
                "detail": f"Current {reg.get('lifecycle')}/{reg.get('phase')}",
            }
        )
        production.append(
            {
                "id": "plan",
                "label": "Operating plan",
                "done": reg.get("has_on_disk_plan") or reg.get("has_registry_plan"),
                "detail": f"Tier {reg.get('plan_tier') or '—'} registry plan",
            }
        )
    if intake:
        production.append(
            {
                "id": "intake",
                "label": "Intake ready to build",
                "done": bool(intake.get("ready_to_build")),
                "detail": intake.get("recommended_lane", "—"),
            }
        )
        production.append(
            {
                "id": "validate",
                "label": "Validation profile wired",
                "done": bool(plan_state and plan_state.get("validation_profile") not in (None, "none", "")),
                "detail": (plan_state or {}).get("validation_profile", "none"),
            }
        )

    research_cmds: list[str] = []
    research_summary = ""
    if plan_state:
        research_summary = (plan_state.get("research_gate") or {}).get("summary", "")
        research_cmds = list((plan_state.get("research_gate") or {}).get("commands") or [])
    external = (plan_state or {}).get("external_guide", "") if plan_state else ""
    if external:
        research_cmds.append(f"# External guide: {external}")

    skills: list[str] = []
    catalog = state.get("hub_skills_catalog") or {}
    for owner in ("hermes", "liaison", "qca", "ml_intern", "unsloth_studio"):
        for entry in catalog.get(owner, [])[:3]:
            title = entry.get("title", "")
            if title and title not in skills:
                skills.append(f"{owner}: {title}")
    rolodex_skills = state.get("rolodex", {}).get("skills", [])
    for entry in rolodex_skills:
        if entry.get("recommended"):
            skills.append(f"★ {entry.get('title', '')}")

    return {
        "key": key,
        "label": (reg or {}).get("label", key),
        "path": (reg or {}).get("path", ""),
        "intent": (plan_state or {}).get("intent", "Run intake and plan-project to set intent."),
        "maturity_target": (plan_state or {}).get("maturity_target", "—"),
        "workflow": (plan_state or {}).get("workflow", "—"),
        "pattern": (plan_state or {}).get("pattern"),
        "validation_profile": (plan_state or {}).get("validation_profile", "none"),
        "tier": (plan_state or {}).get("tier", reg.get("plan_tier") if reg else "—"),
        "agents": agents or ["hermes"],
        "specialists": specialists,
        "agent_chain": " → ".join((agents + specialists)[:6]) or "hermes",
        "skills": skills[:14],
        "production_checklist": production,
        "research_summary": research_summary,
        "research_commands": research_cmds[:8],
        "backlog": list((plan_state or {}).get("backlog") or [])[:8],
        "recommended_patterns": [p for p in patterns if p.get("recommended")][:3],
        "all_patterns": patterns[:8],
        "liaison_cmds": {
            "intake": f"liaison project-intake --project {key} --show",
            "plan": f"liaison plan-project --project {key} --write",
            "focus": f"liaison command-center --project {key}",
            "assess": "liaison assess-project --show",
        },
    }


def build_projects_portfolio_detail(state: dict) -> list[dict[str, Any]]:
    """Lightweight intake/plan/corpus strip for every registered project (single collect pass)."""
    from collections import defaultdict

    from dashboard.command_center.build_corpus import count_corpus_traces_lightweight
    from dashboard.command_center.data import repo_registry_key
    from dashboard.command_center.project_intake import build_project_intake
    from dashboard.command_center.project_plans import build_projects_registry, load_project_plan

    sf = state.get("_bridge")
    if sf is None:
        from dashboard.command_center.data import _bridge

        sf = _bridge()
    repos_map = sf.parse_registry_map("repos.yaml", "repos")
    open_by_key: dict[str, list] = defaultdict(list)
    for task in state.get("open_tasks") or []:
        key = repo_registry_key(task.get("repo", ""), repos_map)
        if key:
            open_by_key[key].append(task)

    rows: list[dict[str, Any]] = []
    for reg in build_projects_registry(state):
        key = reg["key"]
        path = (reg.get("path") or "").strip()
        intake = build_project_intake(key, path, open_by_key.get(key, [])) if path else None
        plan = load_project_plan(key)
        corpus = count_corpus_traces_lightweight(path) if path else {}
        rows.append(
            {
                "project_key": key,
                "intake_ready": bool(intake and intake.get("intake_ready")),
                "ready_to_build": bool(intake and intake.get("ready_to_build")),
                "has_plan": bool(reg.get("has_registry_plan") or reg.get("has_on_disk_plan")),
                "plan_workflow": (plan or {}).get("workflow") if plan else None,
                "corpus_trace_count": corpus.get("corpus_trace_count", 0),
                "build_steps_recorded": corpus.get("build_steps_recorded", 0),
                "intake_blockers": (intake or {}).get("summary", {}).get("intake_blockers", 0),
            }
        )
    return rows


def build_project_portfolio_list(state: dict) -> list[dict[str, Any]]:
    """Lightweight list for matrix sidebar (all registered projects)."""
    from dashboard.command_center.project_plans import build_projects_registry

    rows = []
    for reg in build_projects_registry(state):
        detail = build_project_detail(state, reg["key"])
        if not detail:
            continue
        rows.append(
            {
                "key": reg["key"],
                "label": detail["label"],
                "score": reg["score"],
                "phase": reg["phase"],
                "lifecycle": reg["lifecycle"],
                "intent_short": (detail["intent"] or "")[:100],
                "agent_chain": detail["agent_chain"],
                "pattern": detail.get("pattern"),
                "ready": any(
                    p.get("done") for p in detail.get("production_checklist", []) if p["id"] == "intake"
                ),
            }
        )
    return rows


def format_project_detail_tui(detail: dict[str, Any], *, plain_fn) -> str:
    """Textual markup for workstream / overview project panel."""
    lines = [
        f"[bold]{plain_fn(detail.get('label', detail.get('key', '')))}[/bold]",
        f"  {plain_fn(detail.get('intent', ''))[:400]}",
        "",
        f"[bold]Workflow[/bold]  {plain_fn(detail.get('workflow', '—'))} · "
        f"[bold]Pattern[/bold] {plain_fn(str(detail.get('pattern') or '—'))}",
        f"[bold]Agents[/bold]   {plain_fn(detail.get('agent_chain', '—'))}",
        f"[bold]Profile[/bold]  {plain_fn(detail.get('validation_profile', 'none'))}",
    ]
    lines.append("")
    lines.append("[bold]Production readiness[/bold]")
    for item in detail.get("production_checklist") or []:
        mark = "✓" if item.get("done") else "○"
        lines.append(f"  {mark} {plain_fn(item.get('label', ''))}")
    if detail.get("research_summary"):
        lines.append("")
        lines.append("[bold]Research first[/bold]")
        lines.append(f"  {plain_fn(detail['research_summary'][:320])}")
    if detail.get("research_commands"):
        lines.append("  [dim]Commands:[/dim]")
        for cmd in detail["research_commands"][:4]:
            lines.append(f"    {plain_fn(cmd)}")
    if detail.get("skills"):
        lines.append("")
        lines.append("[bold]Skills to use[/bold]")
        for sk in detail["skills"][:6]:
            lines.append(f"  • {plain_fn(sk)}")
    if detail.get("recommended_patterns"):
        lines.append("")
        lines.append("[bold]Recommended workflows[/bold]")
        for p in detail["recommended_patterns"][:3]:
            lines.append(
                f"  • {plain_fn(p.get('label', ''))}: {plain_fn(' → '.join(p.get('agents', [])))}"
            )
    return "\n".join(lines)


ROLODEX_CATEGORY_INTROS: dict[str, dict[str, str]] = {
    "skills": {
        "title": "Skills",
        "body": (
            "Playbooks and capabilities per hub member (Hermes skills, liaison skills, "
            "ML Intern HF capabilities, QCA knowledge skills). Run with hermes -s <skill> or "
            "via specialist launch lines."
        ),
    },
    "subagents": {
        "title": "Subagents",
        "body": (
            "Hub agents and handoff chains. Executors run in terminal panes; reports return via "
            "liaison attach. Each card includes a resume: profile, capabilities, when to use."
        ),
    },
    "projects": {
        "title": "Projects",
        "body": (
            "Every repo in registry/repos.yaml plus multi-agent patterns. Registered repos show "
            "intent, workflow, validation profile, and production checklist."
        ),
    },
    "commands": {
        "title": "Commands",
        "body": (
            "Liaison CLI verbs grouped by lifecycle: init/snapshot/attach, debrief/memory, "
            "validate/gate, registry, and phase executor. Copy usage lines into pane B."
        ),
    },
    "tools": {
        "title": "Tools",
        "body": (
            "MCP integrations, validation check scripts, hub CLIs (hermes, qca, ml-intern), "
            "and capability routes. Tools are launched in the terminal, not from the browser."
        ),
    },
}
