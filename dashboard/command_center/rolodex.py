"""Build rolodex entries: skills, subagents, commands, tools."""

from __future__ import annotations

import re
from pathlib import Path

from rich.markup import escape as markup_escape

from liaison_paths import AGENT_SYSTEM_DIR, LIAISON_DOCS_DIR

DOCS_HUB = LIAISON_DOCS_DIR.parent
CATEGORIES = ("skills", "subagents", "projects", "commands", "tools")

_INLINE = re.compile(
    r"(\w+):\s*\"([^\"]*)\"|(\w+):\s*([^,}\s][^,}]*)"
)


def _parse_inline_dict(line: str) -> dict[str, str]:
    body = line.strip().lstrip("- ").strip("{} ")
    out: dict[str, str] = {}
    for m in _INLINE.finditer(body):
        if m.group(1):
            out[m.group(1)] = m.group(2)
        elif m.group(3):
            out[m.group(3)] = m.group(4).strip()
    return out


def _parse_rolodex_yaml() -> dict:
    path = AGENT_SYSTEM_DIR / "registry" / "rolodex.yaml"
    if not path.exists():
        return {}
    groups: dict[str, dict] = {}
    tools: list[dict] = []
    current_group: str | None = None
    in_tools = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "command_groups:":
            in_tools = False
            continue
        if stripped == "tools:":
            in_tools = True
            current_group = None
            continue
        if in_tools and stripped.startswith("- {"):
            tools.append(_parse_inline_dict(stripped))
            continue
        if in_tools:
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            if stripped.startswith("label:"):
                if current_group:
                    groups[current_group]["label"] = stripped.split(":", 1)[1].strip().strip('"')
                continue
            current_group = stripped[:-1]
            groups[current_group] = {"label": current_group, "commands": []}
        elif current_group and stripped.startswith("- {"):
            groups[current_group]["commands"].append(_parse_inline_dict(stripped))
    return {"command_groups": list(groups.values()), "tools": tools}


def _skill_path(skill_id: str) -> Path | None:
    for base in (AGENT_SYSTEM_DIR / "skills", DOCS_HUB):
        for candidate in (
            base / skill_id / "SKILL.md",
            base / skill_id.replace("-", "_") / "SKILL.md",
        ):
            if candidate.exists():
                return candidate
    return None


def _with_actions(entry: dict, extra: list[dict] | None = None) -> dict:
    """Attach copyable liaison actions to a rolodex card."""
    actions: list[dict] = list(extra or [])
    launch = entry.get("launch")
    if launch and not any(a.get("liaison_cmd") == launch for a in actions):
        actions.insert(0, {"label": "Copy launch", "liaison_cmd": launch})
    path = entry.get("path")
    if path and Path(str(path)).expanduser().exists():
        actions.append({"label": "Open reference path", "liaison_cmd": f"# path: {path}"})
    if actions:
        entry = dict(entry)
        entry["actions"] = actions
    return entry


def build_skills_entries(state: dict) -> list[dict]:
    from dashboard.command_center.hub_skills import build_all_skills_entries, build_hub_skills_catalog

    catalog = state.get("hub_skills_catalog") or build_hub_skills_catalog()
    skills_in_use = {r["skill"]: r for r in state.get("skills_panel", {}).get("skills", [])}
    rows = build_all_skills_entries(catalog)
    for entry in rows:
        owner = entry["meta"].get("owner", "")
        sid = entry["title"]
        if sid in skills_in_use:
            u = skills_in_use[sid]
            entry["subtitle"] = f"{owner} · in use {u.get('util')}% {u.get('trend', '')}"
            entry["meta"]["util"] = u.get("util")
            entry["meta"]["trend"] = u.get("trend")
            entry["actions"] = [
                {"label": "Copy launch", "liaison_cmd": entry.get("launch", "")},
                {"label": "Registry skills", "liaison_cmd": "liaison registry skills"},
            ]
    return [_with_actions(e) for e in rows]


def build_project_entries(state: dict) -> list[dict]:
    from dashboard.command_center.hub_skills import build_project_pattern_entries
    from dashboard.command_center.project_plans import build_registry_rolodex_entries

    patterns = []
    for entry in build_project_pattern_entries():
        meta = entry.get("meta") or {}
        steps = meta.get("steps") or []
        agents = meta.get("agents") or []
        actions = [
            {"label": "Start pattern", "liaison_cmd": entry.get("launch", "")},
            {"label": "List patterns", "liaison_cmd": "liaison start-pattern --list"},
        ]
        if agents:
            actions.append(
                {
                    "label": f"Attach first agent ({agents[0]})",
                    "liaison_cmd": f"liaison attach {agents[0]} --file <report>",
                }
            )
        patterns.append(_with_actions({**entry, "actions": actions}))
    registry = build_registry_rolodex_entries(state)
    return registry + patterns


def build_subagent_entries(state: dict) -> list[dict]:
    rows = []
    from dashboard.command_center.hub_skills import hub_capabilities_for_agent

    for agent in state.get("agent_rows", []):
        name = agent["name"]
        rows.append(
            _with_actions(
                {
                    "id": f"agent:{name}",
                    "title": agent["display"],
                    "subtitle": f"{agent['status']} · {agent['registry_status']}",
                    "summary": agent["role"],
                    "launch": agent["launch"],
                    "path": agent.get("hub_docs") or agent.get("handoff_guide", ""),
                    "resume": agent.get("resume"),
                    "meta": {
                        "kind": "hub_agent",
                        "agent_name": name,
                        "tasks": agent["tasks"],
                        "output_contract": agent["output_contract"],
                        "launch_note": agent.get("launch_note", ""),
                        "hub_docs": agent.get("hub_docs", ""),
                        "capabilities": hub_capabilities_for_agent(name),
                    },
                },
                [
                    {
                        "label": f"Launch {agent['display']} for the next slice",
                        "liaison_cmd": agent["launch"],
                    },
                    {
                        "label": f"Attach a report for {name}",
                        "liaison_cmd": f"liaison attach {name} --file <report>",
                    },
                    {"label": "List hub agents in registry", "liaison_cmd": "liaison registry agents"},
                ],
            )
        )
    rw_path = AGENT_SYSTEM_DIR / "config" / "research_workers.yaml"
    if rw_path.exists():
        current = None
        fields: dict = {}
        use_list: list[str] = []
        in_use_for = False
        for line in rw_path.read_text(errors="replace").splitlines():
            stripped = line.strip()
            if stripped == "research_workers:":
                continue
            if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
                if current and fields:
                    if use_list:
                        fields["use_for"] = ", ".join(use_list)
                    rows.append(_research_worker_row(current, fields))
                current = stripped[:-1]
                fields = {}
                use_list = []
                in_use_for = False
            elif current and stripped == "use_for:":
                in_use_for = True
            elif in_use_for and line.startswith("      - "):
                use_list.append(stripped.lstrip("- "))
            elif current and line.startswith("    ") and ":" in stripped and not in_use_for:
                key, val = stripped.split(":", 1)
                fields[key.strip()] = val.strip().strip('"')
            elif current and line.startswith("    ") and not stripped.startswith("-") and in_use_for and not line.startswith("      "):
                in_use_for = False
        if current and fields:
            if use_list:
                fields["use_for"] = ", ".join(use_list)
            rows.append(_research_worker_row(current, fields))

    for idx, chain in enumerate(state.get("handoff_chains", [])):
        agents = chain.get("agents", [])
        rows.append(
            _with_actions(
                {
                    "id": f"chain:{idx}",
                    "title": chain.get("name", " → ".join(agents)),
                    "subtitle": "handoff chain",
                    "summary": chain.get("when", ""),
                    "launch": f"liaison attach {agents[0]} --file <report>" if agents else "liaison look",
                    "path": "liaison/guides/workflows/specialist-handoffs.md",
                    "meta": {"kind": "combination", "agents": agents, "steps": chain.get("steps", [])},
                },
                [
                    {
                        "label": "Copy handoff play",
                        "liaison_cmd": " → ".join(agents) if agents else chain.get("name", ""),
                    },
                    {
                        "label": "Attach first agent",
                        "liaison_cmd": f"liaison attach {agents[0]} --file <report>" if agents else "liaison look",
                    },
                ],
            )
        )
    return rows


def _research_worker_row(name: str, fields: dict[str, str]) -> dict:
    tool = fields.get("tool", name)
    status = fields.get("status", "?")
    use = fields.get("use_for", "")
    if isinstance(use, str):
        use_text = use
    else:
        use_text = ", ".join(use) if use else ""
    return {
        "id": f"worker:{name}",
        "title": name.replace("_", " "),
        "subtitle": f"research_worker · {status}",
        "summary": use_text[:120] or fields.get("provider", ""),
        "launch": f"liaison request-research {name} \"<request>\"",
        "path": str(AGENT_SYSTEM_DIR / "config" / "research_workers.yaml"),
        "meta": {"kind": "research_worker", "tool": tool, **fields},
    }


def build_command_entries() -> list[dict]:
    rows = []
    data = _parse_rolodex_yaml()
    for group in data.get("command_groups", []):
        label = group.get("label", "commands")
        for cmd in group.get("commands", []):
            name = cmd.get("name", "?")
            summary = cmd.get("summary", "")
            rows.append(
                {
                    "id": f"cmd:{name}",
                    "title": name,
                    "subtitle": label,
                    "summary": summary,
                    "what": summary,
                    "when_to_use": f"CLI group «{label}» — copy usage into liaison pane.",
                    "launch": cmd.get("usage", f"liaison {name}"),
                    "path": "docs/command_reference.md",
                    "meta": {"group": label, "kind": "liaison_command"},
                }
            )
    return [
        _with_actions(
            row,
            [{"label": f"Run liaison {row.get('title', 'command')}", "liaison_cmd": row.get("launch", "")}],
        )
        for row in rows
    ]


def build_tool_entries() -> list[dict]:
    rows = []
    for tool in _parse_rolodex_yaml().get("tools", []):
        tid = tool.get("id", "?")
        summary = tool.get("summary", "")
        rows.append(
            {
                "id": f"tool:{tid}",
                "title": tid,
                "subtitle": tool.get("kind", "tool"),
                "summary": summary,
                "what": summary,
                "when_to_use": f"Launch in terminal — {summary[:120]}",
                "launch": tool.get("launch", ""),
                "path": tool.get("path", ""),
                "meta": {**tool, "kind": "tool"},
            }
        )
    caps_path = AGENT_SYSTEM_DIR / "config" / "capability_routes.yaml"
    if caps_path.exists():
        current = None
        for line in caps_path.read_text(errors="replace").splitlines():
            stripped = line.strip()
            if stripped == "capabilities:":
                continue
            if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
                current = stripped[:-1]
            elif current and "description:" in stripped:
                desc = stripped.split(":", 1)[1].strip().strip('"')
                rows.append(
                    {
                        "id": f"cap:{current}",
                        "title": current,
                        "subtitle": "capability route",
                        "summary": desc[:120],
                        "launch": f"liaison route \"{current}\"",
                        "path": str(caps_path),
                        "meta": {"kind": "capability"},
                    }
                )
                current = None
    return [
        _with_actions(
            row,
            [{"label": f"Open {row.get('title', 'tool')}", "liaison_cmd": row.get("launch", "")}],
        )
        for row in rows
    ]


def _enrich_rolodex_entry_with_state(state: dict, entry: dict) -> dict:
    """Enrich card; portfolio resume for registered repos."""
    from dashboard.command_center.rolodex_resume import resume_from_registered_project

    out = enrich_rolodex_entry(entry)
    meta = out.get("meta") or {}
    if meta.get("kind") == "registered_repo":
        key = meta.get("registry_key") or out.get("id", "").replace("repo:", "")
        pr = resume_from_registered_project(out, portfolio_state={**state, "selected_project": key})
        out["resume"] = pr
        out["what"] = (pr.get("summary") or out.get("what", ""))[:520]
    return out


def build_rolodex(state: dict) -> dict[str, list[dict]]:
    """Category → list of rolodex cards."""
    raw = {
        "skills": build_skills_entries(state),
        "subagents": build_subagent_entries(state),
        "projects": build_project_entries(state),
        "commands": build_command_entries(),
        "tools": build_tool_entries(),
    }
    return {
        key: [_enrich_rolodex_entry_with_state(state, e) for e in entries]
        for key, entries in raw.items()
    }


ROLODEX_CATEGORY_HINTS = {
    "skills": "Capabilities and playbooks",
    "subagents": "Hub agents, workers, and handoff chains",
    "projects": "Registered repos and multi-agent patterns",
    "commands": "Liaison CLI verbs and workflows",
    "tools": "MCP tools, routes, and integrations",
}


def _skill_doc_excerpt(path: str | Path | None, max_chars: int = 400) -> str:
    if not path:
        return ""
    p = Path(str(path))
    if not p.is_file():
        return ""
    from dashboard.command_center.hub_skills import _read_skill_frontmatter

    meta = _read_skill_frontmatter(p)
    desc = (meta.get("description") or "").strip()
    if desc:
        return desc[:max_chars]
    body = (meta.get("body_excerpt") or "").strip()
    return body[:max_chars]


def _friendly_primary_action(entry: dict) -> dict | None:
    """One operator-facing action (label + underlying command)."""
    meta = entry.get("meta") or {}
    kind = meta.get("kind", "")
    owner = meta.get("owner", "")
    title = entry.get("title", "this item")
    launch = entry.get("launch") or ""
    if kind == "hermes_skill" or owner == "hermes":
        return {"label": f"Run «{title}» in Hermes", "liaison_cmd": launch or f"hermes -s {title}"}
    if kind == "operator_guide":
        return {"label": f"Open Hermes guide for {title}", "liaison_cmd": launch}
    if owner == "liaison" and launch:
        return {"label": f"Use Liaison skill «{title}»", "liaison_cmd": launch}
    if kind == "hub_agent":
        return {"label": f"Launch {title} for the next slice", "liaison_cmd": launch}
    if kind == "research_worker":
        return {"label": f"Request research from {title}", "liaison_cmd": launch}
    if kind == "combination":
        return {"label": "Copy handoff chain play", "liaison_cmd": launch}
    if kind == "project_pattern":
        return {"label": f"Start pattern «{title}»", "liaison_cmd": launch}
    if kind == "registered_repo":
        return {"label": f"Focus project {title}", "liaison_cmd": launch or "liaison look"}
    if entry.get("id", "").startswith("cmd:"):
        return {"label": f"Run liaison {title}", "liaison_cmd": launch}
    if launch:
        return {"label": f"Run {title}", "liaison_cmd": launch}
    return None


def _derive_what(entry: dict) -> str:
    from dashboard.command_center.hub_skills import is_generic_capability_text

    explicit = (entry.get("what") or "").strip()
    if explicit and not is_generic_capability_text(explicit):
        return explicit
    parts: list[str] = []
    summary = (entry.get("summary") or "").strip()
    if summary and not is_generic_capability_text(summary):
        parts.append(summary)
    meta = entry.get("meta") or {}
    if meta.get("output_contract") and meta.get("kind") == "hub_agent":
        parts.append(f"Delivers: {meta['output_contract']}.")
    excerpt = _skill_doc_excerpt(entry.get("path"))
    if excerpt and excerpt not in " ".join(parts):
        parts.append(excerpt)
    if not parts:
        kind = meta.get("kind", "entry")
        parts.append(f"{entry.get('title', 'Item')} — {kind.replace('_', ' ')} in the liaison hub.")
    text = " ".join(parts)
    return text[:520] if len(text) > 520 else text


def _derive_when_to_use(entry: dict) -> str:
    explicit = (entry.get("when_to_use") or "").strip()
    if explicit:
        return explicit
    meta = entry.get("meta") or {}
    hints: list[str] = []
    subtitle = entry.get("subtitle") or ""
    if subtitle:
        hints.append(subtitle)
    use_for = meta.get("use_for")
    if use_for:
        hints.append(str(use_for))
    when = meta.get("when") or entry.get("summary", "")
    if when and when not in hints:
        hints.append(str(when))
    group = meta.get("group")
    if group:
        hints.append(f"Command group: {group}")
    category = meta.get("category")
    if category:
        hints.append(f"Category: {category}")
    if meta.get("kind") == "registered_repo":
        hints.append(
            f"Lifecycle {meta.get('lifecycle', '?')} · phase {meta.get('phase', '?')}"
        )
    if meta.get("agents"):
        hints.append(f"Agent chain: {' → '.join(meta['agents'])}")
    if not hints:
        return "When this capability fits your current project phase or handoff."
    return " · ".join(hints)[:400]


def _derive_next_steps(entry: dict) -> list[dict]:
    stored = entry.get("next_steps")
    if stored:
        return list(stored)
    steps: list[dict] = []
    primary = _friendly_primary_action(entry)
    if primary:
        steps.append(primary)
    for act in entry.get("actions") or []:
        cmd = act.get("liaison_cmd", "")
        if not cmd or cmd.startswith("#"):
            continue
        label = act.get("label", "Action")
        if primary and cmd == primary.get("liaison_cmd") and label.lower().startswith("copy"):
            continue
        if any(s.get("liaison_cmd") == cmd for s in steps):
            continue
        friendly = label
        if label.lower() == "copy launch":
            friendly = primary["label"] if primary else "Copy run command"
        steps.append({"label": friendly, "liaison_cmd": cmd})
    meta = entry.get("meta") or {}
    for step in meta.get("steps") or []:
        steps.append({"label": str(step), "liaison_cmd": ""})
    return steps[:8]


def enrich_rolodex_entry(entry: dict) -> dict:
    """Add human-readable what / when / next_steps and structured resume for TUI and web."""
    from dashboard.command_center.rolodex_resume import build_rolodex_resume

    out = dict(entry)
    resume = build_rolodex_resume(out)
    out["what"] = (resume.get("summary") or "").strip() or _derive_what(out)
    out["when_to_use"] = (resume.get("when_to_use") or "").strip() or _derive_when_to_use(out)
    if out.get("when_to_use") and not resume.get("when_to_use"):
        resume = {**resume, "when_to_use": out["when_to_use"]}
    out["resume"] = resume
    out["next_steps"] = _derive_next_steps(out)
    actions = list(out.get("actions") or [])
    primary = _friendly_primary_action(out)
    if primary and not any(a.get("liaison_cmd") == primary["liaison_cmd"] for a in actions):
        actions.insert(0, primary)
    elif primary and actions:
        actions[0] = {**actions[0], "label": primary["label"]}
    out["actions"] = actions
    return out


def _plain(value: str | None) -> str:
    return markup_escape(value or "")


def format_detail(entry: dict | None) -> str:
    from dashboard.command_center.rolodex_resume import resume_plain_lines

    if not entry:
        return "[dim]Select an item in the list (↑↓ Enter). c copy launch · ! copy action · x run read-only[/dim]"
    entry = enrich_rolodex_entry(entry)
    resume = entry.get("resume") or {}
    lines = [
        f"[bold]{_plain(entry['title'])}[/bold]",
        f"[cyan]{_plain(entry.get('subtitle', ''))}[/cyan]",
    ]
    rendered_resume = False
    for section_title, content in resume_plain_lines(resume):
        rendered_resume = True
        lines.append("")
        lines.append(f"[bold]{section_title}[/bold]")
        if isinstance(content, list):
            for item in content:
                lines.append(f"  • {_plain(str(item))}")
        else:
            lines.append(f"  {_plain(str(content))}")
    if not rendered_resume:
        lines.extend(
            [
                "",
                "[bold]What[/bold]",
                f"  {_plain(entry.get('what') or entry.get('summary', ''))}",
                "",
                "[bold]When to use[/bold]",
                f"  {_plain(entry.get('when_to_use', ''))}",
            ]
        )
    next_steps = entry.get("next_steps") or []
    if next_steps:
        lines.append("")
        lines.append("[bold]Next steps[/bold] [dim](! copy · x run if read-only)[/dim]")
        for idx, step in enumerate(next_steps, 1):
            label = step.get("label", "Step")
            cmd = step.get("liaison_cmd", "")
            if cmd:
                lines.append(f"  {idx}. {_plain(label)}")
                lines.append(f"     [dim]{_plain(cmd)}[/dim]")
            else:
                lines.append(f"  {idx}. {_plain(label)}")
    meta = entry.get("meta") or {}
    if meta.get("kind") == "registered_repo":
        lines.append(
            f"\n[bold]Registry[/bold]\n  phase {meta.get('phase')} · lifecycle {meta.get('lifecycle')} · "
            f"score {meta.get('score')}"
        )
        flags = []
        if meta.get("has_on_disk_plan"):
            flags.append("plan on disk")
        elif meta.get("has_registry_plan"):
            flags.append("registry plan")
        if meta.get("has_brief"):
            flags.append("brief")
        if flags:
            lines.append(f"  {' · '.join(flags)}")
    if meta.get("output_contract") and meta.get("kind") == "hub_agent":
        lines.append(f"\n[bold]Output contract[/bold]\n  {_plain(str(meta['output_contract']))}")
    if meta.get("hub_docs") and meta["hub_docs"] != "—":
        lines.append(f"\n[bold]Hub docs[/bold]\n  {_plain(str(meta['hub_docs']))}")
    if meta.get("util") is not None:
        lines.append(
            f"\n[bold]Utilization[/bold] {meta.get('util')}% {_plain(str(meta.get('trend', '')))}"
        )
    actions = [
        a
        for a in entry.get("actions") or []
        if a.get("liaison_cmd") and not str(a["liaison_cmd"]).startswith("#")
    ]
    if actions:
        lines.append("")
        lines.append("[bold]Actions[/bold] [dim](1-9 copy · ! selected action)[/dim]")
        for idx, act in enumerate(actions[:9], 1):
            lines.append(f"  {idx}. {_plain(act.get('label', 'Action'))}")
            lines.append(f"     [dim]{_plain(act.get('liaison_cmd', ''))}[/dim]")
    lines.append("\n[dim]Technical reference[/dim]")
    if entry.get("path"):
        lines.append(f"  {_plain(entry['path'])}")
    if entry.get("launch"):
        lines.append(f"  {_plain(entry.get('launch'))}")
    return "\n".join(lines)
