"""Discover skills and capabilities from each local-agents hub member."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from liaison_paths import AGENT_SYSTEM_DIR, LIAISON_DOCS_DIR

DOCS_HUB = LIAISON_DOCS_DIR.parent

_TABLE_ROW = re.compile(r"^\│\s*([^│]+?)\s*│\s*([^│]*?)\s*│")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07")


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text).strip()


def _subprocess_env() -> dict[str, str]:
    """Disable terminal color so Rich table output parses cleanly."""
    return {**os.environ, "NO_COLOR": "1", "TERM": "dumb"}


def _expand(path: str) -> Path:
    return Path(path.replace("~/", str(Path.home()) + "/"))


def _read_skill_frontmatter(skill_md: Path) -> dict[str, str]:
    if not skill_md.exists():
        return {}
    text = skill_md.read_text(errors="replace")
    if not text.startswith("---"):
        return {"name": skill_md.parent.name, "description": text[:400]}
    end = text.find("---", 3)
    if end < 0:
        return {"name": skill_md.parent.name}
    block = text[3:end]
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    meta.setdefault("name", skill_md.parent.name)
    body = text[end + 3 :].strip()
    if body:
        meta["body_excerpt"] = _skill_body_excerpt(body)
    return meta


def _skill_body_excerpt(body: str, max_chars: int = 400) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return re.sub(r"\s+", " ", stripped)[:max_chars]
    return re.sub(r"\s+", " ", body.strip())[:max_chars]


def _find_hermes_skill_md(name: str) -> Path | None:
    """Resolve Hermes skill SKILL.md (flat or category/nested layouts)."""
    roots = (
        Path.home() / ".hermes/skills",
        Path.home() / ".hermes/hermes-agent/skills",
    )
    for root in roots:
        if not root.exists():
            continue
        direct = root / name / "SKILL.md"
        if direct.is_file():
            return direct
        matches = sorted(root.glob(f"**/{name}/SKILL.md"))
        if matches:
            return matches[0]
    return None


def skill_capability_text(
    skill_md: Path | None,
    *,
    title: str = "",
    category: str = "",
    owner: str = "hermes",
    max_chars: int = 520,
) -> str:
    """Best-effort capability paragraph from SKILL.md frontmatter or body."""
    if skill_md and skill_md.is_file():
        meta = _read_skill_frontmatter(skill_md)
        desc = (meta.get("description") or "").strip()
        if desc:
            return desc[:max_chars]
        body = (meta.get("body_excerpt") or "").strip()
        if body:
            return body[:max_chars]
    if owner == "hermes":
        return f"Hermes skill in the {category or 'general'} category."
    if title and owner:
        return f"When you need the {title} playbook from {owner}"
    return ""


def is_generic_capability_text(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    if re.match(r"^Hermes skill in the .+ category\.$", stripped, re.I):
        return True
    if re.match(r"^When you need the .+ playbook from .+$", stripped, re.I):
        return True
    return False


def _scan_skill_dirs(root: Path, owner: str, kind: str = "skill") -> list[dict]:
    rows = []
    if not root.exists():
        return rows
    for skill_md in sorted(root.glob("**/SKILL.md")):
        meta = _read_skill_frontmatter(skill_md)
        name = meta.get("name", skill_md.parent.name)
        capability = skill_capability_text(skill_md, title=name, owner=owner)
        summary = capability[:320]
        rows.append(
            {
                "id": f"{owner}:{name}",
                "title": name,
                "subtitle": f"{owner} · {kind}",
                "summary": summary,
                "what": capability,
                "when_to_use": meta.get("category") or f"When you need the {name} playbook from {owner}",
                "launch": _launch_for_owner(owner, name),
                "path": str(skill_md),
                "meta": {"owner": owner, "kind": kind, "category": meta.get("category", "")},
            }
        )
    return rows


def _launch_for_owner(owner: str, skill_name: str) -> str:
    launches = {
        "liaison": f"liaison registry skills  # {skill_name}",
        "hermes": f"hermes -s {skill_name}",
        "qca": "qca serve  # knowledge skill auto-loaded",
        "ml_intern": f"ml-intern  # capability: {skill_name}",
        "unsloth_studio": "unsloth studio",
    }
    return launches.get(owner, "")


def _parse_hub_skills_yaml() -> dict:
    path = AGENT_SYSTEM_DIR / "registry" / "hub_skills.yaml"
    if not path.exists():
        return {"hub_members": {}, "project_agent_patterns": []}
    members: dict = {}
    patterns: list = []
    current_member: str | None = None
    in_patterns = False
    in_capabilities = False
    current_pattern: dict | None = None
    in_steps = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "project_agent_patterns:":
            in_patterns = True
            current_member = None
            in_steps = False
            continue
        if stripped == "hub_members:":
            in_patterns = False
            continue
        if in_patterns:
            if line.startswith("  - id:"):
                if current_pattern:
                    patterns.append(current_pattern)
                current_pattern = {"id": stripped.split(":", 1)[1].strip()}
                in_steps = False
            elif current_pattern and line.startswith("      - "):
                current_pattern.setdefault("steps", []).append(stripped.lstrip("- ").strip('"'))
                in_steps = True
            elif current_pattern and stripped == "steps:":
                current_pattern["steps"] = []
                in_steps = True
            elif current_pattern and ":" in stripped and not in_steps:
                key, val = stripped.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"')
                in_steps = False
                if key in ("agents", "specialists"):
                    current_pattern[key] = [
                        x.strip() for x in val.replace("[", "").replace("]", "").split(",") if x.strip()
                    ]
                else:
                    current_pattern[key] = val
        elif not in_patterns and line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_member = stripped[:-1]
            members[current_member] = {"capabilities": []}
            in_capabilities = False
        elif current_member and stripped == "capabilities:":
            in_capabilities = True
        elif current_member and in_capabilities and stripped.startswith("- {"):
            members[current_member]["capabilities"].append(_parse_inline(stripped))
        elif current_member and not in_capabilities and ":" in stripped:
            key, val = stripped.split(":", 1)
            members[current_member][key.strip()] = val.strip().strip('"')
    if current_pattern:
        patterns.append(current_pattern)
    return {"hub_members": members, "project_agent_patterns": patterns}


def _parse_inline(line: str) -> dict[str, str]:
    body = line.strip().lstrip("- ").strip("{} ")
    out: dict[str, str] = {}
    for part in body.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def list_hermes_skills() -> list[dict]:
    rows = []
    try:
        out = subprocess.check_output(
            ["hermes", "skills", "list", "--enabled-only"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=20,
            env=_subprocess_env(),
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return rows
    for line in out.splitlines():
        m = _TABLE_ROW.match(line.strip())
        if not m:
            continue
        name, category = _strip_ansi(m.group(1)), _strip_ansi(m.group(2))
        if name.lower() == "name":
            continue
        skill_path = _find_hermes_skill_md(name)
        capability = skill_capability_text(skill_path, title=name, category=category, owner="hermes")
        summary = capability[:320]
        rows.append(
            {
                "id": f"hermes:{name}",
                "title": name,
                "subtitle": f"hermes · {category or 'skill'}",
                "summary": summary,
                "what": capability,
                "when_to_use": category or "general",
                "launch": f"hermes -s {name}",
                "path": str(skill_path or Path.home() / ".hermes/skills" / name),
                "meta": {"owner": "hermes", "kind": "hermes_skill", "category": category},
            }
        )
    return rows


def _guide_summary(md: Path) -> str:
    text = md.read_text(errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return re.sub(r"\s+", " ", stripped)[:320]
    return f"Operator guide for bundled Hermes skills ({md.stem})."


def list_hermes_operator_guides() -> list[dict]:
    guides_dir = DOCS_HUB / "hermes/guides/skills"
    rows = []
    if not guides_dir.exists():
        return rows
    for md in sorted(guides_dir.glob("*.md")):
        if md.name == "README.md":
            continue
        title = md.stem.replace("-", " ")
        summary = _guide_summary(md)
        rows.append(
            {
                "id": f"hermes-guide:{md.stem}",
                "title": title,
                "subtitle": "hermes · operator guide",
                "summary": summary,
                "what": summary,
                "when_to_use": "When running a curated Hermes skill bundle for this domain",
                "launch": f"hermes -s <skills-from-{md.stem}>",
                "path": str(md),
                "meta": {"owner": "hermes", "kind": "operator_guide"},
            }
        )
    return rows


def hub_member_config(agent_name: str) -> dict:
    """Raw hub_members entry from registry/hub_skills.yaml."""
    return _parse_hub_skills_yaml().get("hub_members", {}).get(agent_name, {})


def hub_capabilities_for_agent(agent_name: str) -> list[dict[str, str]]:
    """Capability rows declared for ml_intern, unsloth_studio, etc."""
    caps = hub_member_config(agent_name).get("capabilities", [])
    return [c for c in caps if isinstance(c, dict)]


def hub_patterns_for_agent(agent_name: str) -> list[str]:
    """Handoff pattern hints that include this hub agent."""
    hints: list[str] = []
    for pattern in _parse_hub_skills_yaml().get("project_agent_patterns", []):
        agents = list(pattern.get("agents", []))
        specialists = list(pattern.get("specialists", []))
        involved = set(agents) | set(specialists)
        if agent_name not in involved:
            continue
        label = pattern.get("label", pattern.get("id", "pattern"))
        when = pattern.get("when", "")
        hints.append(f"{label}: {when}" if when else str(label))
    return hints[:5]


def build_hub_skills_catalog() -> dict:
    """All skills/capabilities keyed by hub member."""
    catalog: dict[str, list[dict]] = {
        "liaison": [],
        "hermes": [],
        "qca": [],
        "ml_intern": [],
        "unsloth_studio": [],
    }
    config = _parse_hub_skills_yaml()
    members = config.get("hub_members", {})

    liaison_dir = _expand(members.get("liaison", {}).get("skills_dir", str(AGENT_SYSTEM_DIR / "skills")))
    catalog["liaison"] = _scan_skill_dirs(liaison_dir, "liaison")

    qca_dir = _expand(members.get("qca", {}).get("knowledge_skills_dir", ""))
    catalog["qca"] = _scan_skill_dirs(qca_dir, "qca", kind="knowledge")

    for cap in members.get("ml_intern", {}).get("capabilities", []):
        cid = cap.get("id", "?")
        catalog["ml_intern"].append(
            {
                "id": f"ml_intern:{cid}",
                "title": cid,
                "subtitle": "ml_intern · capability",
                "summary": cap.get("summary", ""),
                "launch": _launch_for_owner("ml_intern", cid),
                "path": str(DOCS_HUB / "ml-intern/guides/capabilities"),
                "meta": {"owner": "ml_intern", "kind": "capability"},
            }
        )
    for cap in members.get("unsloth_studio", {}).get("capabilities", []):
        cid = cap.get("id", "?")
        catalog["unsloth_studio"].append(
            {
                "id": f"unsloth_studio:{cid}",
                "title": cid,
                "subtitle": "unsloth_studio · capability",
                "summary": cap.get("summary", ""),
                "launch": _launch_for_owner("unsloth_studio", cid),
                "path": str(DOCS_HUB / "unsloth-studio/guides/capabilities"),
                "meta": {"owner": "unsloth_studio", "kind": "capability"},
            }
        )

    catalog["hermes"] = list_hermes_skills() + list_hermes_operator_guides()
    return catalog


def build_all_skills_entries(catalog: dict | None = None) -> list[dict]:
    catalog = catalog or build_hub_skills_catalog()
    rows = []
    for owner in ("liaison", "hermes", "qca", "ml_intern", "unsloth_studio"):
        for entry in catalog.get(owner, []):
            rows.append(entry)
    return sorted(rows, key=lambda e: (e["meta"].get("owner", ""), e["title"]))


def build_project_agent_patterns() -> list[dict]:
    """Normalized multi-agent patterns for command-center JSON."""
    patterns = _parse_hub_skills_yaml().get("project_agent_patterns", [])
    rows: list[dict] = []
    for p in patterns:
        agents = list(p.get("agents", []))
        specialists = list(p.get("specialists", []))
        all_agents = agents + [s for s in specialists if s not in agents]
        rows.append(
            {
                "id": p.get("id", "?"),
                "label": p.get("label", p.get("id", "?")),
                "agents": all_agents,
                "when": p.get("when", ""),
                "steps": list(p.get("steps", [])),
            }
        )
    return rows


def build_project_pattern_entries() -> list[dict]:
    patterns = _parse_hub_skills_yaml().get("project_agent_patterns", [])
    rows = []
    for p in patterns:
        agents = list(p.get("agents", []))
        specialists = list(p.get("specialists", []))
        all_agents = agents + [s for s in specialists if s not in agents]
        rows.append(
            {
                "id": f"pattern:{p.get('id', '?')}",
                "title": p.get("label", p.get("id", "?")),
                "subtitle": "project · multi-agent",
                "summary": p.get("when", ""),
                "launch": f"liaison start-pattern {p.get('id', '')}",
                "path": "registry/hub_skills.yaml",
                "meta": {
                    "kind": "project_pattern",
                    "agents": all_agents,
                    "steps": p.get("steps", []),
                },
            }
        )
    return rows
