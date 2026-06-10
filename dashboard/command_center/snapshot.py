"""Non-interactive command center snapshot (--once, CI, no TTY)."""

from __future__ import annotations

from pathlib import Path


def _truncate(text: str, width: int) -> str:
    text = str(text).replace("\n", " ")
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _panel(title: str, lines: list[str], width: int = 118) -> list[str]:
    top = "+" + "-" * (width - 2) + "+"
    heading = f"| {title:<{width - 4}} |"
    body = [f"| {_truncate(line, width - 4):<{width - 4}} |" for line in lines]
    return [top, heading, top, *body, top]


def _pair(left_title: str, left_lines: list[str], right_title: str, right_lines: list[str], width: int = 118) -> None:
    gap = "  "
    left_w = width // 2 - len(gap) // 2
    right_w = width - left_w - len(gap)
    left = _panel(left_title, left_lines, left_w)
    right = _panel(right_title, right_lines, right_w)
    rows = max(len(left), len(right))
    blank_left = " " * left_w
    blank_right = " " * right_w
    for idx in range(rows):
        print((left[idx] if idx < len(left) else blank_left) + gap + (right[idx] if idx < len(right) else blank_right))


def print_command_center_snapshot(state: dict) -> None:
    width = 118
    eng = state["engineering_metrics"]
    rolodex = state.get("rolodex", {})
    print("=" * width)
    print(f"LIAISON COMMAND CENTER | {state['generated_at']}")
    print(
        f"Hub={state['hub_status']} Env={state['env']} Tasks={state['summary']['total_tasks']} "
        f"Open={state['summary']['open_tasks']} Agents={len(state['agent_rows'])}"
    )
    print("Tabs: Overview | Rolodex | Hub | Workstream | Ops  —  Keys: Tab focus, c copy, ! cmd, o open, x run, g rolodex")
    print("=" * width)

    rol_lines = ["CATEGORY   COUNT  SAMPLE"]
    for cat in ("skills", "subagents", "projects", "commands", "tools"):
        entries = rolodex.get(cat, [])
        sample = entries[0]["title"] if entries else "—"
        rol_lines.append(f"{cat:<10} {len(entries):>5}  {_truncate(sample, 50)}")
    catalog = state.get("hub_skills_catalog", {})
    if catalog:
        rol_lines.append("skills by hub: " + ", ".join(f"{k}={len(v)}" for k, v in catalog.items() if v))
    _pair("ROLODEX", rol_lines, "ROLODEX DETAIL (first subagent)", [], width)
    if rolodex.get("subagents"):
        detail = rolodex["subagents"][0]
        print(f"  {detail['title']}: {detail.get('launch', '')}")
    print()

    hub_lines = ["AGENT           ST    REG     TASKS LAUNCH / ROLE"]
    for row in state["agent_rows"]:
        hub_lines.append(
            f"{row['name']:<15} {row['status']:<5} {row['registry_status']:<7} {row['tasks']:>5} "
            f"{_truncate(row['role'], 48)}"
        )

    skill_lines = ["SKILL                    UTIL  TREND"]
    for row in state["skills_panel"]["skills"][:8]:
        skill_lines.append(f"{_truncate(row['skill'], 24):<24} {row['util']:>3}% {row['trend']}")
    rec_lines = ["RECOMMENDATIONS"]
    for rec in state["skills_panel"]["recommendations"][:4]:
        rec_lines.append(f"  [{rec.get('kind', '?')}] {_truncate(rec.get('label', ''), 70)}")
    combo_lines = ["HANDOFF CHAINS"]
    for chain in state["handoff_chains"][:4]:
        combo_lines.append(f"  {' → '.join(chain['agents'])} — {_truncate(chain['when'], 50)}")

    _pair("1. AGENT HUB (all)", hub_lines, "2. SKILLS + RECS + CHAINS", skill_lines + [""] + rec_lines + [""] + combo_lines, width)
    print()

    kanban_lines = []
    for bucket in ("todo", "in_progress", "review", "done"):
        cards = state["kanban"][bucket]
        kanban_lines.append(f"{bucket.upper()} ({len(cards)})")
        for task in cards[:4]:
            kanban_lines.append(
                f"  {task['task_id']:<14} {task.get('current_phase', '?'):<8} "
                f"{_truncate(task.get('description', ''), 40)}"
            )
    matrix_lines = ["RANK PROJECT          SCORE  LIFECYCLE   PHASE"]
    for idx, item in enumerate(state["project_matrix"][:6], 1):
        sel = "*" if state.get("selected_project") == item["option"] else " "
        matrix_lines.append(
            f"{sel}{idx:<3} {_truncate(item['option'], 16):<16} {item['score']:>5}  {_truncate(item.get('lifecycle', '—'), 10):<10} {_truncate(item.get('phase', '—'), 10)}"
        )

    _pair("3. KANBAN", kanban_lines or ["No tasks"], "4. PROJECT MATRIX", matrix_lines, width)
    print()

    hand_lines = ["TASK       REPO        ARTIFACT           STATUS"]
    for h in state["handoffs"][:6]:
        hand_lines.append(
            f"{h['task_id']:<10} {h['repo']:<11} {_truncate(h['artifact'], 18):<18} {h['status']}"
        )
    deb_lines = ["REPO       FILE                 AGE"]
    for d in state["debriefs"][:5]:
        deb_lines.append(f"{d['repo']:<10} {_truncate(d['file'], 20):<20} {d['age']}")

    met_lines = [
        f"open_by_repo: {eng.get('open_by_repo')}",
        f"open_by_phase: {eng.get('open_by_phase')}",
        f"validation: {eng['repos_with_profile']}/{eng['repos_registered']} repos, {eng['validation_profiles_defined']} profiles",
        f"profiles: {', '.join(eng['profiles_in_use']) or 'none'}",
        f"gate_fail={eng['gate_failures']} score_fail={eng['score_failures']}",
        f"handoffs pending={eng['pending_handoffs']} approved={eng['approved_handoffs']}",
        f"memory: learnings={eng['promoted_learnings']} last={eng['last_learning_age']} debrief={eng['last_debrief_age']}",
        f"modes: reporter={eng['reporter_tasks']} executor={eng['executor_tasks']}",
        f"branches: {', '.join(eng['active_branches']) or 'none'}",
    ]
    cross_lines = ["CROSS-POLLINATION"]
    for row in state["cross_pollination"][:5]:
        cross_lines.append(f"  [{row['type']}] {_truncate(row['text'], 75)}")

    _pair("5. HANDOFFS", hand_lines, "6. DEBRIEFS", deb_lines, width)
    print()
    _pair("7. ENGINEERING METRICS", met_lines, "8. CROSS-POLLINATION", cross_lines, width)
    metric_rows = state.get("metrics_rows", [])
    if metric_rows:
        print()
        mlines = ["INTERACTIVE METRICS (Ops tab ListView)"]
        for row in metric_rows[:8]:
            mlines.append(f"  {_truncate(row['label'], 70)}")
        for line in _panel("9. METRICS ROWS", mlines, width):
            print(line)
    print("=" * width)
