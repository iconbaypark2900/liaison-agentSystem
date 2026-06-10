"""Build corpus — aggregate task traces into exportable agent recipes."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from liaison_paths import AGENT_SYSTEM_DIR

BUILD_TRACE_NAME = "BUILD_TRACE.md"
BUILD_TRACE_TEMPLATE = AGENT_SYSTEM_DIR / "templates" / BUILD_TRACE_NAME
AGENT_RECIPE_TEMPLATE = AGENT_SYSTEM_DIR / "templates" / "AGENT_RECIPE.md"
RECIPES_DIR = AGENT_SYSTEM_DIR / "registry" / "recipes"
RECIPES_INDEX = AGENT_SYSTEM_DIR / "registry" / "agent_recipes.yaml"

_PATTERN_RE = re.compile(r"Pattern:\s*`([^`]+)`")
_LEARNING_RE = re.compile(r"^## Learning:", re.MULTILINE)
_BUILD_STEP_RE = re.compile(r"^## Build step:", re.MULTILINE)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_text(path: Path, limit: int | None = None) -> str:
    if not path.exists():
        return ""
    text = path.read_text(errors="replace")
    if limit and len(text) > limit:
        return text[:limit] + "\n…"
    return text


def parse_pattern_from_brief(brief_path: Path) -> str | None:
    text = _read_text(brief_path)
    match = _PATTERN_RE.search(text)
    return match.group(1) if match else None


def extract_build_steps(build_trace_path: Path) -> list[dict[str, str]]:
    if not build_trace_path.exists():
        return []
    text = build_trace_path.read_text(errors="replace")
    chunks = _BUILD_STEP_RE.split(text)
    steps: list[dict[str, str]] = []
    for chunk in chunks[1:]:
        lines = chunk.strip().splitlines()
        header = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:]).strip()
        agent = action = outcome = notes = ""
        for line in lines[1:]:
            low = line.strip().lower()
            if low.startswith("- agent:"):
                agent = line.split(":", 1)[1].strip().strip("`")
            elif low.startswith("- action:"):
                action = line.split(":", 1)[1].strip()
            elif low.startswith("- outcome:"):
                outcome = line.split(":", 1)[1].strip()
            elif low.startswith("- notes:"):
                notes = line.split(":", 1)[1].strip()
        steps.append(
            {
                "header": header,
                "agent": agent,
                "action": action,
                "outcome": outcome,
                "notes": notes,
                "raw": body[:500],
            }
        )
    return steps


def extract_learning_snippets(learnings_path: Path, limit: int = 8) -> list[str]:
    if not learnings_path.exists():
        return []
    text = learnings_path.read_text(errors="replace")
    parts = _LEARNING_RE.split(text)
    snippets: list[str] = []
    for part in parts[1:]:
        snippet = part.strip()
        if snippet and not snippet.startswith("<"):
            first_line = snippet.splitlines()[0][:80] if snippet.splitlines() else ""
            snippets.append(first_line or snippet[:120])
        if len(snippets) >= limit:
            break
    return snippets


def summarize_events(events_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not events_path.exists():
        return counts
    for line in events_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        cmd = row.get("command") or row.get("event") or "unknown"
        counts[cmd] = counts.get(cmd, 0) + 1
    return counts


def collect_task_corpus(task_path: Path) -> dict[str, Any]:
    """Filesystem corpus for one .spark-flow/tasks/<id> directory."""
    task_id = task_path.name
    approved_dir = task_path / "approved"
    approved = (
        sorted(p.name for p in approved_dir.glob("*.md"))
        if approved_dir.exists()
        else []
    )
    build_trace = task_path / BUILD_TRACE_NAME
    closeout = task_path / "CLOSEOUT.md"
    closeout_text = _read_text(closeout, limit=800)
    closed = "has not been closed" not in closeout_text.lower() if closeout_text else False
    events = summarize_events(task_path / "events.jsonl")
    executor_ends = events.get("observe-session", 0) + events.get("executor_session_end", 0)
    return {
        "task_id": task_id,
        "path": str(task_path),
        "pattern_id": parse_pattern_from_brief(task_path / "BRIEF.md"),
        "has_build_trace": build_trace.exists(),
        "build_step_count": len(extract_build_steps(build_trace)),
        "build_steps": extract_build_steps(build_trace),
        "approved_artifacts": approved,
        "learnings": extract_learning_snippets(task_path / "LEARNINGS.md"),
        "event_counts": events,
        "executor_session_ends": executor_ends,
        "failure_evaluations": _count_failure_evaluations(task_path / "EVALUATIONS.md"),
        "has_closeout": closeout.exists() and closed,
        "closeout_excerpt": closeout_text.splitlines()[:6] if closeout_text else [],
    }


def _count_failure_evaluations(eval_path: Path) -> int:
    text = _read_text(eval_path, limit=20000)
    if not text:
        return 0
    return text.lower().count("status: fail")


def iter_project_task_dirs(repo_path: str | Path) -> list[Path]:
    tasks_dir = Path(repo_path).expanduser() / ".spark-flow" / "tasks"
    if not tasks_dir.exists():
        return []
    return sorted(p for p in tasks_dir.iterdir() if p.is_dir())


def count_corpus_traces_lightweight(repo_path: str | Path) -> dict[str, int]:
    """Fast corpus counts for portfolio matrix (no step parsing)."""
    repo = Path(repo_path).expanduser()
    tasks_dir = repo / ".spark-flow" / "tasks"
    if not tasks_dir.is_dir():
        return {"corpus_trace_count": 0, "build_steps_recorded": 0, "task_slices_indexed": 0}
    trace_count = 0
    step_count = 0
    task_count = 0
    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir():
            continue
        task_count += 1
        trace = task_dir / BUILD_TRACE_NAME
        if not trace.exists():
            continue
        trace_count += 1
        try:
            step_count += trace.read_text(errors="replace").count("## Build step:")
        except OSError:
            continue
    return {
        "corpus_trace_count": trace_count,
        "build_steps_recorded": step_count,
        "task_slices_indexed": task_count,
    }


def collect_project_corpus(
    project_key: str,
    repo_path: str | Path,
    *,
    task_ids: list[str] | None = None,
) -> dict[str, Any]:
    repo = Path(repo_path).expanduser()
    tasks_raw = iter_project_task_dirs(repo)
    if task_ids:
        allowed = set(task_ids)
        tasks_raw = [p for p in tasks_raw if p.name in allowed]
    task_rows = [collect_task_corpus(p) for p in tasks_raw]
    patterns = {t["pattern_id"] for t in task_rows if t.get("pattern_id")}
    return {
        "project_key": project_key,
        "repo_path": str(repo),
        "task_count": len(task_rows),
        "tasks": task_rows,
        "pattern_ids": sorted(patterns),
        "total_build_steps": sum(t.get("build_step_count", 0) for t in task_rows),
        "total_approved": sum(len(t.get("approved_artifacts") or []) for t in task_rows),
        "closed_tasks": sum(1 for t in task_rows if t.get("has_closeout")),
    }


def _load_hub_pattern(pattern_id: str | None) -> dict[str, Any] | None:
    if not pattern_id:
        return None
    path = AGENT_SYSTEM_DIR / "registry" / "hub_skills.yaml"
    if not path.exists():
        return None
    patterns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_section = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "project_agent_patterns:":
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("  - id:"):
            if current:
                patterns.append(current)
            current = {"id": stripped.split(":", 1)[1].strip()}
            continue
        if current and line.startswith("    ") and ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"')
            if key in ("agents", "specialists"):
                current.setdefault(key, [])
                if val.startswith("["):
                    inner = val.strip("[]")
                    current[key] = [x.strip() for x in inner.split(",") if x.strip()]
            else:
                current[key] = val
    if current:
        patterns.append(current)
    return next((p for p in patterns if p.get("id") == pattern_id), None)


def _agent_chain_from_pattern(pattern: dict[str, Any] | None) -> list[str]:
    if not pattern:
        return []
    chain = list(pattern.get("agents") or [])
    for spec in pattern.get("specialists") or []:
        if spec not in chain:
            chain.append(spec)
    return chain


def build_corpus_summary(
    project_key: str,
    repo_path: str,
    open_tasks: list[dict] | None = None,
    *,
    project_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact summary for command-center JSON when a project is focused."""
    corpus = collect_project_corpus(project_key, repo_path)
    plan_pattern = (project_plan or {}).get("pattern")
    plan_workflow = (project_plan or {}).get("workflow")
    primary_pattern = plan_pattern or (corpus["pattern_ids"][0] if corpus["pattern_ids"] else None)
    recipe_files = list(RECIPES_DIR.glob("*.md")) if RECIPES_DIR.exists() else []
    project_recipes = [
        p.name
        for p in recipe_files
        if project_key.replace("_", "-") in p.name or project_key in p.name
    ]
    open_with_trace = 0
    for task in open_tasks or []:
        path = task.get("path")
        if path and (Path(path) / BUILD_TRACE_NAME).exists():
            open_with_trace += 1
    executor_ends = sum(t.get("executor_session_ends", 0) for t in corpus["tasks"])
    failures = sum(t.get("failure_evaluations", 0) for t in corpus["tasks"])
    return {
        "project": project_key,
        "repo_path": repo_path,
        "task_slices_indexed": corpus["task_count"],
        "build_steps_recorded": corpus["total_build_steps"],
        "approved_artifacts_total": corpus["total_approved"],
        "closed_slices": corpus["closed_tasks"],
        "pattern_ids_observed": corpus["pattern_ids"],
        "recommended_pattern": primary_pattern,
        "workflow": plan_workflow,
        "open_tasks_with_build_trace": open_with_trace,
        "executor_session_ends": executor_ends,
        "failure_evaluations": failures,
        "exported_recipes": len(project_recipes),
        "recipe_paths": [str(RECIPES_DIR / n) for n in project_recipes[:5]],
        "liaison_record": f"liaison record-build --agent hermes --action \"<step>\" --outcome \"<result>\"",
        "liaison_export": f"liaison export-agent-recipe --from-project {project_key} --write",
        "liaison_observe_session": (
            f"liaison observe-session complete --agent hermes --exit-code 0 "
            f"--project {project_key} --task-id <task-id>"
        ),
    }


def export_agent_recipe(
    project_key: str,
    repo_path: str | Path,
    *,
    recipe_id: str | None = None,
    task_ids: list[str] | None = None,
    project_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    corpus = collect_project_corpus(project_key, repo_path, task_ids=task_ids)
    plan = project_plan or {}
    pattern_id = plan.get("pattern") or (
        corpus["pattern_ids"][0] if corpus["pattern_ids"] else "hermes-led-slice"
    )
    hub_pattern = _load_hub_pattern(pattern_id)
    chain = _agent_chain_from_pattern(hub_pattern)
    all_steps: list[dict[str, str]] = []
    all_learnings: list[str] = []
    all_approved: list[str] = []
    failure_patterns: list[str] = []
    for task in corpus["tasks"]:
        all_steps.extend(task.get("build_steps") or [])
        all_learnings.extend(task.get("learnings") or [])
        all_approved.extend(task.get("approved_artifacts") or [])
        if task.get("failure_evaluations"):
            failure_patterns.append(
                f"{task['task_id']}: {task['failure_evaluations']} failed evaluation(s)"
            )

    rid = recipe_id or f"{project_key}-{pattern_id}-{datetime.now().strftime('%Y%m%d')}"
    launch_lines = []
    if hub_pattern:
        launch_lines.append(hub_pattern.get("when", ""))
        for step in hub_pattern.get("steps") or []:
            launch_lines.append(f"- {step}")
    else:
        launch_lines.append("Hermes-led slice with liaison attach / approve / validate.")

    return {
        "recipe_id": rid,
        "project_key": project_key,
        "repo_path": str(Path(repo_path).expanduser()),
        "pattern_id": pattern_id,
        "workflow": plan.get("workflow") or "reporter-mode",
        "validation_profile": plan.get("validation_profile") or "",
        "exported_at": _now(),
        "task_ids": [t["task_id"] for t in corpus["tasks"]],
        "agent_chain": chain,
        "launch_recipe_lines": launch_lines,
        "build_steps": all_steps,
        "learnings": list(dict.fromkeys(all_learnings))[:20],
        "approved_artifacts": list(dict.fromkeys(all_approved))[:30],
        "failure_patterns": failure_patterns,
        "corpus_stats": {
            "tasks": corpus["task_count"],
            "build_steps": len(all_steps),
            "closed": corpus["closed_tasks"],
            "executor_session_ends": sum(t.get("executor_session_ends", 0) for t in corpus["tasks"]),
        },
    }


def format_agent_recipe_markdown(recipe: dict[str, Any]) -> str:
    template = _read_text(AGENT_RECIPE_TEMPLATE)
    if not template:
        template = "# Agent recipe: {{RECIPE_ID}}\n"

    def bullet_lines(items: list[str], empty: str = "- _(none)_") -> str:
        if not items:
            return empty
        return "\n".join(f"- {item}" for item in items)

    steps_md = []
    for step in recipe.get("build_steps") or []:
        agent = step.get("agent") or "?"
        action = step.get("action") or step.get("header") or "step"
        outcome = step.get("outcome") or ""
        line = f"**{agent}** — {action}"
        if outcome:
            line += f" → {outcome}"
        steps_md.append(line)

    replacements = {
        "{{RECIPE_ID}}": recipe.get("recipe_id", ""),
        "{{PROJECT_KEY}}": recipe.get("project_key", ""),
        "{{REPO_PATH}}": recipe.get("repo_path", ""),
        "{{PATTERN_ID}}": recipe.get("pattern_id", ""),
        "{{WORKFLOW}}": recipe.get("workflow", ""),
        "{{EXPORTED_AT}}": recipe.get("exported_at", ""),
        "{{TASK_IDS}}": ", ".join(recipe.get("task_ids") or []) or "—",
        "{{LAUNCH_RECIPE}}": bullet_lines(recipe.get("launch_recipe_lines") or []),
        "{{AGENT_CHAIN}}": " → ".join(recipe.get("agent_chain") or []) or "hermes",
        "{{BUILD_STEPS}}": bullet_lines(steps_md) if steps_md else "- Record steps with `liaison record-build` during slices.",
        "{{APPROVED_ARTIFACTS}}": bullet_lines(recipe.get("approved_artifacts") or []),
        "{{LEARNINGS}}": bullet_lines(recipe.get("learnings") or []),
        "{{VALIDATION}}": f"Profile: `{recipe.get('validation_profile') or 'project default'}`",
        "{{OPERATOR_NOTES}}": (
            f"Aggregated {recipe.get('corpus_stats', {}).get('tasks', 0)} task(s), "
            f"{recipe.get('corpus_stats', {}).get('build_steps', 0)} build step(s)."
        ),
        "{{FAILURE_PATTERNS}}": bullet_lines(recipe.get("failure_patterns") or []),
    }
    out = template
    for key, val in replacements.items():
        out = out.replace(key, val)
    return out


def append_recipe_index(recipe_id: str, project_key: str, pattern_id: str, rel_path: str) -> None:
    """Append a minimal index entry to registry/agent_recipes.yaml."""
    path = RECIPES_INDEX
    lines = path.read_text(errors="replace").splitlines() if path.exists() else ["version: 1", "recipes: []"]
    if lines and lines[-1].strip() == "recipes: []":
        lines[-1] = "recipes:"
    entry = (
        f"  - id: {recipe_id}\n"
        f"    project: {project_key}\n"
        f"    pattern: {pattern_id}\n"
        f"    path: {rel_path}\n"
        f"    exported_at: \"{_now()}\"\n"
    )
    lines.append(entry.rstrip())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_agent_recipe_file(recipe: dict[str, Any]) -> Path:
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    rid = recipe["recipe_id"]
    target = RECIPES_DIR / f"{rid}.md"
    target.write_text(format_agent_recipe_markdown(recipe), encoding="utf-8")
    rel = f"registry/recipes/{rid}.md"
    append_recipe_index(rid, recipe["project_key"], recipe.get("pattern_id", ""), rel)
    return target


def ensure_build_trace(task_dir: Path, task_id: str) -> Path:
    target = task_dir / BUILD_TRACE_NAME
    if target.exists():
        return target
    body = _read_text(BUILD_TRACE_TEMPLATE)
    if not body:
        body = f"# BUILD TRACE: {task_id}\n\n## Build steps\n\n"
    body = body.replace("<task-id>", task_id)
    target.write_text(body, encoding="utf-8")
    return target


def append_build_step(
    task_dir: Path,
    *,
    agent: str,
    action: str,
    outcome: str,
    notes: str = "",
    timestamp: str | None = None,
) -> Path:
    task_id = task_dir.name
    trace = ensure_build_trace(task_dir, task_id)
    ts = timestamp or _now()
    block = [
        f"\n## Build step: {ts}\n",
        f"- Agent: `{agent}`",
        f"- Action: {action}",
        f"- Outcome: {outcome}",
    ]
    if notes:
        block.append(f"- Notes: {notes}")
    block.append("")
    with trace.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(block))
    return trace
