"""Build structured rolodex resumes (CV-style detail) for TUI and web."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from liaison_paths import AGENT_SYSTEM_DIR

_PROFILES_PATH = AGENT_SYSTEM_DIR / "registry" / "rolodex_profiles.yaml"
_TOOL_HEADING = re.compile(r"^Tool\s+\d+:\s*", re.I)
_SKIP_SECTIONS = frozenset(
    {
        "setup",
        "usage",
        "tips",
        "recommended fonts",
        "dependencies",
        "license",
    }
)
def _parse_profiles_yaml() -> dict[str, dict[str, Any]]:
    if not _PROFILES_PATH.exists():
        return {}
    profiles: dict[str, dict[str, Any]] = {}
    current_id: str | None = None
    in_profiles = False
    for line in _PROFILES_PATH.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "profiles:":
            in_profiles = True
            continue
        if not in_profiles:
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_id = stripped[:-1].strip('"').strip("'")
            profiles[current_id] = {}
            continue
        if current_id and line.startswith("    ") and ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == "capabilities":
                profiles[current_id]["capabilities"] = []
                continue
            profiles[current_id][key] = val
        elif current_id and line.startswith("      - "):
            caps = profiles[current_id].setdefault("capabilities", [])
            if isinstance(caps, list):
                caps.append(stripped.lstrip("- ").strip('"'))
    return profiles


def _merge_resume(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in override.items():
        if key == "capabilities" and isinstance(val, list):
            existing = list(out.get("capabilities") or [])
            for item in val:
                if item and item not in existing:
                    existing.append(str(item))
            out["capabilities"] = existing[:12]
        elif val:
            out[key] = val
    return out


def _normalize_resume(raw: dict[str, Any]) -> dict[str, Any]:
    caps = raw.get("capabilities") or []
    if isinstance(caps, str):
        caps = [caps]
    clean_caps = []
    for c in caps:
        s = re.sub(r"\s+", " ", str(c).strip())
        if s and s not in clean_caps and len(s) > 2:
            clean_caps.append(s[:160])
    resume: dict[str, Any] = {
        "headline": (raw.get("headline") or "").strip()[:120],
        "summary": (raw.get("summary") or "").strip()[:720],
        "capabilities": clean_caps[:12],
        "best_for": (raw.get("best_for") or "").strip()[:400],
        "when_to_use": (raw.get("when_to_use") or "").strip()[:400],
        "outputs": (raw.get("outputs") or "").strip()[:320],
        "limits": (raw.get("limits") or "").strip()[:320],
    }
    if not resume["summary"] and resume["headline"]:
        resume["summary"] = resume["headline"]
    return resume


def _extract_skill_sections(body: str) -> tuple[list[str], str]:
    """Section titles and bullet capabilities from SKILL.md body."""
    capabilities: list[str] = []
    intro_parts: list[str] = []
    in_intro = True
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue
        if stripped.startswith("## "):
            in_intro = False
            title = stripped[3:].strip()
            key = title.split("(")[0].strip().lower()
            if any(key.startswith(s) for s in _SKIP_SECTIONS):
                continue
            cap = _TOOL_HEADING.sub("", title).strip()
            if cap and cap not in capabilities:
                capabilities.append(cap[:160])
            continue
        if in_intro and stripped and not stripped.startswith("```"):
            intro_parts.append(stripped)
        if stripped.startswith(("- ", "* ")):
            bullet = stripped[2:].strip()
            if bullet.startswith("`") or bullet.startswith("|"):
                continue
            if len(bullet) > 8 and bullet not in capabilities:
                capabilities.append(bullet[:160])
    intro = re.sub(r"\s+", " ", " ".join(intro_parts))[:400]
    return capabilities, intro


def resume_from_skill_md(path: Path | None, *, category: str = "") -> dict[str, Any]:
    from dashboard.command_center.hub_skills import _read_skill_frontmatter, is_generic_capability_text

    raw: dict[str, Any] = {"capabilities": []}
    if not path or not path.is_file():
        return _normalize_resume(raw)
    meta = _read_skill_frontmatter(path)
    desc = (meta.get("description") or "").strip()
    body = path.read_text(errors="replace")
    if body.startswith("---"):
        end = body.find("---", 3)
        body = body[end + 3 :] if end >= 0 else body
    section_caps, intro = _extract_skill_sections(body)
    if desc and not is_generic_capability_text(desc):
        raw["summary"] = desc
        raw["headline"] = desc.split(".")[0][:120] if "." in desc else desc[:120]
    elif intro:
        raw["summary"] = intro
        raw["headline"] = intro.split(".")[0][:120]
    raw["capabilities"] = section_caps
    if category:
        cat_label = category.replace("_", " ").replace("-", " ")
        name = raw.get("headline") or path.parent.name
        raw["when_to_use"] = (
            f"Hermes {cat_label} skill — use when the slice needs {name}."
        )
    tags = meta.get("tags") or ""
    if "tags:" in str(meta):
        pass
    raw["best_for"] = (
        f"Terminal-friendly text art and banners; complements docs and CLI output."
        if "ascii" in path.parent.name.lower() or "art" in path.parent.name.lower()
        else ""
    )
    raw["outputs"] = "Skill-guided CLI commands and plain-text artifacts."
    raw["limits"] = "Not a substitute for governed closeout or production UI design."
    return _normalize_resume(raw)


def resume_from_hub_agent(entry: dict) -> dict[str, Any]:
    from dashboard.command_center.hub_skills import (
        hub_capabilities_for_agent,
        hub_member_config,
        hub_patterns_for_agent,
    )

    meta = entry.get("meta") or {}
    agent_name = str(meta.get("agent_name") or entry.get("id", "").replace("agent:", "")).strip()
    title = entry.get("title", "Agent")
    role = (entry.get("summary") or "").strip()
    contract = str(meta.get("output_contract") or "").strip()
    launch = (entry.get("launch") or "").strip()
    launch_note = str(meta.get("launch_note") or "").strip()
    caps: list[str] = []
    for item in meta.get("capabilities") or hub_capabilities_for_agent(agent_name):
        if isinstance(item, dict):
            summary = (item.get("summary") or item.get("id", "")).strip()
            cid = item.get("id", "")
            if summary and cid:
                caps.append(f"{summary} ({cid})")
            elif summary:
                caps.append(summary)
        else:
            caps.append(str(item))
    member = hub_member_config(agent_name)
    if member.get("skills_cli"):
        caps.append(f"Skills CLI: {member['skills_cli']}")
    if member.get("builtin_note"):
        caps.append(str(member["builtin_note"]))
    if member.get("guide"):
        caps.append(f"Capability guide: {member['guide']}")
    patterns = hub_patterns_for_agent(agent_name)
    summary_parts = []
    if role:
        summary_parts.append(role)
    if launch:
        summary_parts.append(f"Launch: {launch}")
    summary_parts.append(
        "Typical flow: run the agent, produce a report, then "
        f"`liaison attach {agent_name or 'agent'} --file <report>.md` for Hermes or liaison to integrate."
    )
    best_for = role
    if patterns:
        best_for = f"{role} Patterns: {'; '.join(patterns[:2])}"[:400]
    when_parts = list(patterns[:3])
    if launch_note:
        when_parts.insert(0, launch_note)
    if not when_parts:
        when_parts.append(f"When {title} owns the next slice in a hub handoff chain.")
    tasks = meta.get("tasks")
    limits = ""
    if launch_note and "exceptional" in launch_note.lower():
        limits = launch_note
    elif agent_name in ("ml_intern", "qca", "unsloth_studio"):
        limits = "Specialist lane — does not replace Hermes for git merge, closeout, or default build ownership."
    return _normalize_resume(
        {
            "headline": title,
            "summary": " ".join(summary_parts)[:720],
            "capabilities": caps,
            "best_for": best_for[:400] if best_for else "",
            "when_to_use": " ".join(when_parts)[:400],
            "outputs": contract or "Reports via liaison attach / outbox.",
            "limits": limits,
        }
    )


def build_hub_agent_resume(agent: dict) -> dict[str, Any]:
    """Structured resume for Hub panel JSON and rolodex subagent cards."""
    name = agent.get("name", "")
    entry = {
        "id": f"agent:{name}",
        "title": agent.get("display", name),
        "summary": agent.get("role", ""),
        "launch": agent.get("launch", ""),
        "path": agent.get("hub_docs") or agent.get("handoff_guide", ""),
        "meta": {
            "kind": "hub_agent",
            "agent_name": name,
            "output_contract": agent.get("output_contract", ""),
            "launch_note": agent.get("launch_note", ""),
            "tasks": agent.get("tasks", 0),
            "hub_docs": agent.get("hub_docs", ""),
        },
    }
    return build_rolodex_resume(entry)


def format_hub_agent_detail(
    agent: dict | None,
    *,
    handoff_chains: list[dict] | None = None,
) -> str:
    """Rich Textual markup for Hub tab right pane."""
    from rich.markup import escape as markup_escape

    if not agent:
        return "[dim]Select a hub agent (↑↓ Enter). c copy launch · g rolodex · o open docs · x run[/dim]"

    def plain(value: str | None) -> str:
        return markup_escape(value or "")

    resume = agent.get("resume") or build_hub_agent_resume(agent)
    rec = "  ★ recommended for focused phase" if agent.get("recommended") else ""
    lines = [
        f"[bold]{plain(agent.get('display'))}[/bold] ({plain(agent.get('name'))}){rec}",
        f"[cyan]{plain(agent.get('status'))} · registry {plain(agent.get('registry_status'))} · "
        f"{agent.get('tasks', 0)} open tasks[/cyan]",
    ]
    for section_title, content in resume_plain_lines(resume):
        lines.append("")
        lines.append(f"[bold]{section_title}[/bold]")
        if isinstance(content, list):
            for item in content:
                lines.append(f"  • {plain(str(item))}")
        else:
            lines.append(f"  {plain(str(content))}")
    chain_hints: list[str] = []
    agent_name = agent.get("name", "")
    for chain in handoff_chains or []:
        agents = chain.get("agents", [])
        if agent_name in agents:
            chain_hints.append(chain.get("name", " → ".join(agents)))
    if chain_hints:
        lines.append("\n[bold]Handoff chains[/bold]")
        for hint in chain_hints[:3]:
            lines.append(f"  • {plain(hint)}")
    if agent.get("handoff_guide") and agent["handoff_guide"] != "—":
        lines.append(f"\n[bold]Handoff guide[/bold]\n  {plain(agent['handoff_guide'])}")
    if agent.get("hub_docs") and agent["hub_docs"] != "—":
        lines.append(f"\n[bold]Hub docs[/bold]\n  {plain(agent['hub_docs'])}")
    lines.append("\n[dim]Press g to open Subagents rolodex entry[/dim]")
    return "\n".join(lines)


def resume_from_capability_meta(entry: dict) -> dict[str, Any]:
    meta = entry.get("meta") or {}
    caps_meta = meta.get("capabilities") or []
    caps: list[str] = []
    if isinstance(caps_meta, list):
        for item in caps_meta:
            if isinstance(item, dict):
                summary = item.get("summary") or item.get("id", "")
                if summary:
                    caps.append(str(summary))
            else:
                caps.append(str(item))
    use_for = str(meta.get("use_for") or entry.get("when_to_use") or "").strip()
    return _normalize_resume(
        {
            "headline": entry.get("title", ""),
            "summary": (entry.get("summary") or entry.get("what") or "").strip(),
            "capabilities": caps,
            "best_for": use_for,
            "when_to_use": use_for or (entry.get("when_to_use") or ""),
            "outputs": str(meta.get("output_contract") or ""),
        }
    )


def resume_from_generic(entry: dict) -> dict[str, Any]:
    meta = entry.get("meta") or {}
    kind = meta.get("kind", "entry")
    title = entry.get("title", "Item")
    summary = (entry.get("summary") or entry.get("what") or "").strip()
    caps: list[str] = []
    for step in meta.get("steps") or []:
        caps.append(str(step))
    agents = meta.get("agents")
    if agents:
        caps.append(f"Agent chain: {' → '.join(agents)}")
    when = meta.get("when") or entry.get("when_to_use") or ""
    if meta.get("kind") == "registered_repo":
        when = (
            f"Registered repo — lifecycle {meta.get('lifecycle', '?')}, "
            f"phase {meta.get('phase', '?')}, profile {meta.get('default_profile', '?')}."
        )
    return _normalize_resume(
        {
            "headline": title,
            "summary": summary or f"{title} ({kind.replace('_', ' ')}) in the liaison command center.",
            "capabilities": caps,
            "when_to_use": str(when) if when else "",
            "outputs": str(meta.get("output_contract") or ""),
        }
    )


def resume_from_registered_project(
    entry: dict, *, portfolio_state: dict | None = None
) -> dict[str, Any]:
    """Portfolio-style resume for rolodex project/repo cards."""
    meta = entry.get("meta") or {}
    key = meta.get("registry_key") or entry.get("id", "").replace("repo:", "")
    if key:
        from dashboard.command_center.project_portfolio import build_project_detail

        detail = build_project_detail(portfolio_state or {"selected_project": key}, key)
        if detail:
            caps = [
                f"Workflow: {detail.get('workflow', '—')}",
                f"Pattern: {detail.get('pattern') or '—'}",
                f"Agents: {detail.get('agent_chain', '—')}",
                f"Profile: {detail.get('validation_profile', 'none')}",
            ]
            caps.extend(detail.get("skills", [])[:6])
            return _normalize_resume(
                {
                    "headline": detail.get("label", key),
                    "summary": detail.get("intent", entry.get("summary", "")),
                    "capabilities": caps,
                    "best_for": f"Maturity target: {detail.get('maturity_target', '—')}",
                    "when_to_use": detail.get("research_summary") or entry.get("when_to_use", ""),
                    "outputs": f"Production path via validate --profile {detail.get('validation_profile')}",
                    "limits": "Engineering blocked until intake/plan gates pass when tier C.",
                }
            )
    return resume_from_generic(entry)


def build_rolodex_resume(entry: dict) -> dict[str, Any]:
    """Structured CV for a rolodex card."""
    from dashboard.command_center.hub_skills import (
        _find_hermes_skill_md,
        is_generic_capability_text,
        skill_capability_text,
    )

    meta = entry.get("meta") or {}
    kind = meta.get("kind", "")
    owner = meta.get("owner", "")
    entry_id = entry.get("id", "")

    if meta.get("kind") == "registered_repo":
        resume = resume_from_registered_project(entry)
    elif kind == "hub_agent":
        resume = resume_from_hub_agent(entry)
    elif kind in ("hermes_skill", "skill") or owner == "hermes":
        path = entry.get("path")
        skill_path = Path(str(path)) if path else None
        if not skill_path or not skill_path.is_file():
            found = _find_hermes_skill_md(entry.get("title", ""))
            skill_path = found
        category = str(meta.get("category") or "")
        if kind == "skill" and owner != "hermes":
            from dashboard.command_center.hub_skills import _read_skill_frontmatter

            resume = resume_from_skill_md(skill_path, category=category)
            if owner:
                resume["when_to_use"] = resume.get("when_to_use") or (
                    f"When you need the {entry.get('title')} playbook from {owner}."
                )
        else:
            resume = resume_from_skill_md(skill_path, category=category)
    elif meta.get("capabilities"):
        resume = resume_from_capability_meta(entry)
    else:
        resume = resume_from_generic(entry)

    summary = (entry.get("what") or entry.get("summary") or "").strip()
    if summary and not is_generic_capability_text(summary):
        if not resume.get("summary") or is_generic_capability_text(resume.get("summary", "")):
            resume["summary"] = summary
        elif summary not in resume["summary"]:
            resume["summary"] = f"{summary} {resume['summary']}"[:720]
    elif skill_path := (
        Path(str(entry["path"])) if entry.get("path") else _find_hermes_skill_md(entry.get("title", ""))
    ):
        if skill_path and skill_path.is_file():
            extra = skill_capability_text(skill_path, title=entry.get("title", ""), owner=owner)
            if extra and not is_generic_capability_text(extra):
                resume["summary"] = extra

    profiles = _parse_profiles_yaml()
    override = profiles.get(entry_id) or profiles.get(entry.get("title", ""))
    if override:
        resume = _merge_resume(resume, override)

    return _normalize_resume(resume)


def resume_plain_lines(resume: dict[str, Any]) -> list[tuple[str, str | list[str]]]:
    """Sections for TUI rendering: (title, content str or bullet list)."""
    sections: list[tuple[str, str | list[str]]] = []
    if resume.get("headline") and resume.get("headline") != resume.get("summary", "")[:120]:
        sections.append(("Headline", resume["headline"]))
    if resume.get("summary"):
        sections.append(("Profile", resume["summary"]))
    caps = resume.get("capabilities") or []
    if caps:
        sections.append(("Capabilities", caps))
    if resume.get("best_for"):
        sections.append(("Best for", resume["best_for"]))
    if resume.get("when_to_use"):
        sections.append(("When to use", resume["when_to_use"]))
    if resume.get("outputs"):
        sections.append(("Outputs", resume["outputs"]))
    if resume.get("limits"):
        sections.append(("Limits", resume["limits"]))
    return sections
