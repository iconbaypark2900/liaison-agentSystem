"""Textual TUI for Liaison Command Center — rolodex-first layout."""

from __future__ import annotations

import itertools
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflexion_dspy.repl import ChatSession

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from dashboard.command_center.data import (
    AGENT_SYSTEM_DIR,
    COMMAND_CENTER_REFRESH_SEC,
    collect_command_center_state,
    ensure_import_path,
    format_gate_strip_tui,
    liaison_cmd_is_destructive,
    liaison_cmd_is_readonly,
)
from dashboard.command_center.rolodex import CATEGORIES, ROLODEX_CATEGORY_HINTS, format_detail

LIAISON_VERSION = "v0.5.0"
LIAISON_BIN = AGENT_SYSTEM_DIR / "bin" / "liaison"

_ID_INVALID = re.compile(r"[^a-zA-Z0-9_-]")
_ID_GEN = itertools.count(1)


def new_gen() -> str:
    """A fresh per-populate prefix so rebuilt lists never collide with not-yet-removed items."""
    return f"g{next(_ID_GEN)}_"


def safe_id(raw: str, used: set[str] | None = None) -> str:
    """Sanitize a value into a Textual-valid widget id (letters/digits/_/-, no leading digit)."""
    sid = _ID_INVALID.sub("_", str(raw)) or "item"
    if not (sid[0].isalpha() or sid[0] == "_"):
        sid = f"x_{sid}"
    if used is not None:
        base = sid
        counter = 1
        while sid in used:
            sid = f"{base}_{counter}"
            counter += 1
        used.add(sid)
    return sid
ROLODEX_LABELS = {
    "skills": "Skills",
    "subagents": "Subagents",
    "projects": "Projects",
    "commands": "Commands",
    "tools": "Tools",
}


class FocusBar(Static):
    """Persistent bar showing the focused project across all tabs."""

    def show_focus(self, focus: dict | None) -> None:
        if not focus:
            self.update("[dim]Focus: all projects — select a project in Workstream to link every panel (Esc clears).[/dim]")
            return
        crit = focus.get("exit_criteria", [])
        crit_text = f" · exit: {crit[0][:48]}" if crit else ""
        self.update(
            f"[bold]FOCUS[/bold] {focus['project']}  "
            f"[cyan]{focus['lifecycle']}/{focus['phase']}[/cyan]  "
            f"validation={focus['validation']}  "
            f"agents={', '.join(focus['recommended_agents']) or '—'}{crit_text}"
        )


class GateStripBar(Static):
    """Compact gate strip — mirrors web GateStrip from JSON summary."""

    def show_gates(self, state: dict) -> None:
        self.update(format_gate_strip_tui(state))


class RolodexCategoryList(ListView):
    """Left nav: skills | subagents | commands | tools."""


class RolodexItemList(ListView):
    """Middle list: entries for selected category."""


class RolodexDetail(Static):
    can_focus = True

    def show_entry(self, entry: dict | None) -> None:
        self.update(format_detail(entry))


class HubAgentList(ListView):
    """All hub agents from agent_rows."""


class HubDetail(Static):
    can_focus = True

    def show_agent(self, agent: dict | None) -> None:
        from dashboard.command_center.rolodex_resume import format_hub_agent_detail

        if not agent:
            self.update(
                "[dim]Select a hub agent (↑↓ Enter). c copy launch · g rolodex · o open docs · x run[/dim]"
            )
            return
        chains = self.app.state.get("handoff_chains", [])
        self.update(format_hub_agent_detail(agent, handoff_chains=chains))


class OverviewActionsList(ListView):
    def populate(self, rows: list[dict]) -> None:
        self.border_title = "Quick actions"
        self.clear()
        self.id_map: dict[str, str] = {}
        used: set[str] = set()
        prefix = new_gen()
        for row in rows:
            sid = prefix + safe_id(row["id"], used)
            self.id_map[sid] = row["id"]
            self.append(ListItem(Label(row["label"][:68]), id=sid))


class OverviewActionDetail(Static):
    """How-to for selected overview quick action."""

    def show_action(self, row: dict | None) -> None:
        from rich.markup import escape as markup_escape

        if not row:
            self.update("[dim]Select a quick action (↑↓) · ! copy · x run[/dim]")
            return
        plain = markup_escape
        lines = [f"[bold]{plain(row.get('label', ''))}[/bold]", "", f"  {plain(row.get('detail', ''))}"]
        how = (row.get("how_to") or "").strip()
        if how:
            lines.extend(["", "[bold]How to use[/bold]", f"  {plain(how)[:520]}"])
        cmd = row.get("liaison_cmd")
        if cmd and row.get("kind") != "refresh":
            lines.extend(["", "[bold]Command[/bold]", f"  {plain(cmd)}", "[dim]! copy · x run[/dim]"])
        elif row.get("kind") == "refresh":
            lines.append("\n[dim]Press r to sync[/dim]")
        self.update("\n".join(lines))


class OverviewPanel(Static):
    """Small dashboard panel on the overview tab."""


class KanbanColumn(ListView):
    def populate(self, title: str, tasks: list[dict]) -> None:
        self.border_title = title
        self.clear()
        self.id_map: dict[str, str] = {}
        used: set[str] = set()
        prefix = new_gen()
        for task in tasks:
            sid = prefix + safe_id(task["task_id"], used)
            self.id_map[sid] = task["task_id"]
            label = (
                f"{task['task_id'][:14]} · {task.get('current_phase', '?')}\n"
                f"{str(task.get('description', ''))[:40]}"
            )
            self.append(ListItem(Label(label), id=sid))


class HandoffList(ListView):
    def populate(self, handoffs: list[dict], debriefs: list[dict]) -> None:
        self.clear()
        self.id_map: dict[str, dict] = {}
        used: set[str] = set()
        prefix = new_gen()
        for h in handoffs[:12]:
            mark = "⏳" if h["status"] == "pending_approval" else "✓"
            sid = prefix + safe_id(f"handoff_{h['task_id']}_{h['artifact']}", used)
            self.id_map[sid] = {"kind": "handoff", "row": h}
            self.append(ListItem(Label(f"{mark} {h['task_id']} · {h['artifact'][:24]}"), id=sid))
        for d in debriefs[:6]:
            sid = prefix + safe_id(f"debrief_{d['repo']}_{d['file']}", used)
            self.id_map[sid] = {"kind": "debrief", "row": d}
            self.append(ListItem(Label(f"📋 {d['repo']} · {d['file'][:20]} · {d['age']}"), id=sid))


class ProjectList(ListView):
    def populate(self, matrix: list[dict], selected: str | None) -> None:
        self.clear()
        self.id_map: dict[str, str] = {}
        used: set[str] = set()
        prefix = new_gen()
        for item in matrix:
            sid = prefix + safe_id(item["option"], used)
            self.id_map[sid] = item["option"]
            mark = "▸ " if selected == item["option"] else "  "
            label = (
                f"{mark}{item['option'][:16]}  score={item['score']:3}  "
                f"{item.get('lifecycle', '—')[:10]}/{item.get('phase', '—')[:8]}"
            )
            self.append(ListItem(Label(label), id=sid))


class MetricsList(ListView):
    def populate(self, rows: list[dict]) -> None:
        self.border_title = "Metrics & cross-pollination"
        self.clear()
        self.id_map: dict[str, str] = {}
        used: set[str] = set()
        prefix = new_gen()
        for row in rows:
            sid = prefix + safe_id(row["id"], used)
            self.id_map[sid] = row["id"]
            self.append(ListItem(Label(row["label"][:72]), id=sid))


class OpsDetail(Static):
    can_focus = True

    def show_selection(
        self,
        title: str,
        detail: str,
        *,
        path: str | None = None,
        liaison_cmd: str | None = None,
        output: str | None = None,
    ) -> None:
        lines = [f"[bold]{title}[/bold]", "", detail]
        if path:
            lines.extend(["", f"[bold]Path[/bold]", f"  {path}"])
        if liaison_cmd:
            lines.extend(
                [
                    "",
                    f"[bold]Liaison[/bold]",
                    f"  {liaison_cmd}",
                    "[dim]x or Enter run (read-only) · ! copy · o open path[/dim]",
                ]
            )
        if output:
            lines.extend(["", "[bold]Output[/bold]", output[:4000]])
        self.update("\n".join(lines))


class CommandCenterApp(App):
    """Rolodex + hub + workstream + ops — focusable panels."""

    TITLE = "Liaison Command Center"
    CSS = """
    Screen { layout: vertical; }
    #focusbar { height: 1; padding: 0 1; background: $boost; }
    #gate-strip { height: 2; padding: 0 1; background: $surface; }
    #body { height: 1fr; }
    TabbedContent { height: 100%; }
    TabPane { padding: 0 1; }
    #overview-root { height: 1fr; }
    #overview-cols { height: 1fr; layout: vertical; }
    #overview-cols.layout-medium { layout: horizontal; }
    #overview-cols.layout-wide { layout: horizontal; }
    #overview-col-actions { layout: vertical; min-height: 6; }
    #overview-col-brief { layout: vertical; overflow-y: auto; min-height: 6; }
    #overview-col-signoff { layout: vertical; overflow-y: auto; min-height: 6; }
    #overview-cols.layout-medium #overview-col-actions { width: 40%; }
    #overview-cols.layout-medium #overview-col-brief { width: 60%; }
    #overview-cols.layout-medium #overview-col-signoff { width: 100%; height: auto; }
    #overview-cols.layout-wide #overview-col-actions { width: 32%; }
    #overview-cols.layout-wide #overview-col-brief { width: 36%; }
    #overview-cols.layout-wide #overview-col-signoff { width: 32%; }
    #overview-project, #overview-work, #overview-hub, #overview-patterns,
    #overview-ops, #overview-bridge { border: solid $accent; padding: 0 1; overflow-y: auto; min-height: 5; }
    #overview-actions { height: 1fr; min-height: 6; border: solid $accent; }
    #overview-action-detail { height: auto; max-height: 12; min-height: 5; border: solid $primary; padding: 0 1; overflow-y: auto; }
    #workstream-guide { height: auto; max-height: 18; min-height: 8; border: solid $primary; padding: 0 1; overflow-y: auto; }
    #project-report { height: auto; max-height: 8; min-height: 3; border: solid $accent; padding: 0 1; overflow-y: auto; }
    #rolodex-row { height: 1fr; min-height: 14; }
    #rolodex-cats { width: 20; min-width: 16; border: solid $accent; height: 100%; }
    #rolodex-items { width: 38%; min-width: 34; border: solid $accent; height: 100%; }
    #rolodex-detail { width: 1fr; border: solid $accent; padding: 0 1; height: 100%; }
    RolodexDetail { height: 100%; overflow-y: auto; }
    #hub-row { height: 1fr; min-height: 12; }
    #hub-agents { width: 42%; min-width: 36; border: solid $accent; height: 100%; }
    #hub-detail { width: 1fr; border: solid $accent; padding: 0 1; height: 100%; }
    HubDetail { height: 100%; overflow-y: auto; }
    #workstream-row { height: 1fr; min-height: 10; }
    #kanban-row { height: 1fr; layout: horizontal; }
    KanbanColumn { width: 1fr; min-width: 16; border: solid $primary; height: 100%; }
    #projects { height: 9; min-height: 7; border: solid $accent; }
    #ops-row { height: 1fr; min-height: 10; layout: horizontal; }
    #handoffs { width: 42%; border: solid $accent; height: 100%; }
    #ops-right { width: 1fr; height: 100%; }
    #metrics { height: 55%; border: solid $accent; }
    #ops-detail { height: 45%; border: solid $accent; padding: 0 1; overflow-y: auto; }
    ListView { height: 100%; }
    ListView > ListItem { padding: 0 1; }
    ListView:focus ListItem.--highlight { background: $accent 40%; }
    #agent-tab { height: 100%; }
    #agent-log { height: 1fr; border: solid $accent; padding: 0 1; overflow-y: auto; }
    #agent-status { height: 1; padding: 0 1; background: $boost; color: $text-muted; }
    #agent-input-row { height: 3; }
    #agent-input { width: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "copy_launch", "Copy launch"),
        Binding("o", "open_path", "Open path"),
        Binding("x", "execute_liaison", "Run liaison"),
        Binding("enter", "execute_liaison", "Run liaison", show=False),
        Binding("!", "copy_command", "Copy cmd"),
        Binding("g", "goto_subagent", "Rolodex agent"),
        Binding("1", "digit_1", "Skills", show=False),
        Binding("2", "digit_2", "Subagents", show=False),
        Binding("3", "digit_3", "Projects", show=False),
        Binding("4", "digit_4", "Commands", show=False),
        Binding("5", "digit_5", "Tools", show=False),
        Binding("6", "digit_6", "Action 6", show=False),
        Binding("7", "digit_7", "Action 7", show=False),
        Binding("8", "digit_8", "Action 8", show=False),
        Binding("9", "digit_9", "Action 9", show=False),
        Binding("h", "filter_hermes_skills", "Hermes skills", show=False),
        Binding("escape", "clear_project", "All projects"),
        Binding("a", "goto_agent", "Agent", show=True),
    ]

    def __init__(self, initial_state: dict, refresh_on_start: bool = False) -> None:
        super().__init__()
        self.state = initial_state
        self.selected_project: str | None = None
        self.rolodex_category = initial_state.get("rolodex_category", "skills")
        self._skills_owner_filter: str | None = None
        self._selected_rolodex_id: str | None = None
        self._selected_rolodex_action_idx: int = 0
        self._selected_hub_name: str | None = None
        self._selected_metric_id: str | None = None
        self._selected_overview_action_id: str | None = None
        self._rolodex_item_map: dict[str, str] = {}
        self._hub_item_map: dict[str, str] = {}
        self._category_map: dict[str, str] = {}
        self._selected_ops: dict | None = None
        self._refresh_on_start = refresh_on_start
        self._last_refresh = time.time()
        self._cmd_output = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield FocusBar(id="focusbar")
        yield GateStripBar(id="gate-strip")
        with Container(id="body"):
            with TabbedContent(initial="overview"):
                with TabPane("Overview", id="overview"):
                    with Vertical(id="overview-root"):
                        with Horizontal(id="overview-cols"):
                            with Vertical(id="overview-col-actions"):
                                yield OverviewActionsList(id="overview-actions")
                                yield OverviewActionDetail(id="overview-action-detail")
                            with Vertical(id="overview-col-brief"):
                                yield OverviewPanel(id="overview-project")
                                yield OverviewPanel(id="overview-work")
                                yield OverviewPanel(id="overview-hub")
                                yield OverviewPanel(id="overview-patterns")
                            with Vertical(id="overview-col-signoff"):
                                yield OverviewPanel(id="overview-ops")
                                yield OverviewPanel(id="overview-bridge")
                with TabPane("Rolodex", id="rolodex"):
                    with Horizontal(id="rolodex-row"):
                        yield RolodexCategoryList(id="rolodex-cats")
                        yield RolodexItemList(id="rolodex-items")
                        yield RolodexDetail(id="rolodex-detail")
                with TabPane("Hub", id="hub"):
                    with Horizontal(id="hub-row"):
                        yield HubAgentList(id="hub-agents")
                        yield HubDetail(id="hub-detail")
                with TabPane("Workstream", id="workstream"):
                    with Vertical(id="workstream-row"):
                        yield Static(id="workstream-guide")
                        yield Static(id="reporter-checklist", classes="reporter-checklist")
                        yield Static(id="project-report")
                        with Horizontal(id="kanban-row"):
                            yield KanbanColumn(id="kanban-todo")
                            yield KanbanColumn(id="kanban-progress")
                            yield KanbanColumn(id="kanban-review")
                            yield KanbanColumn(id="kanban-done")
                        yield ProjectList(id="projects")
                with TabPane("Ops", id="ops"):
                    with Horizontal(id="ops-row"):
                        yield HandoffList(id="handoffs")
                        with Vertical(id="ops-right"):
                            yield MetricsList(id="metrics")
                            yield OpsDetail(id="ops-detail")
                with TabPane("Agent", id="agent"):
                    with Vertical(id="agent-tab"):
                        yield RichLog(id="agent-log", highlight=True, markup=True, wrap=True)
                        yield Static("", id="agent-status")
                        with Horizontal(id="agent-input-row"):
                            yield Input(
                                id="agent-input",
                                placeholder=(
                                    "liaison agent-code sigma 'Add Kelly criterion'  |  "
                                    "agent-run 'Search arxiv for VQE'  |  "
                                    "or type a task directly"
                                ),
                            )
        yield Footer()

    def on_mount(self) -> None:
        self._populate_categories()
        self._populate_rolodex_items()
        self._render_overview()
        self._render_hub()
        self._render_workstream()
        self._render_ops()
        self._render_focusbar()
        self._render_gate_strip()
        if self._refresh_on_start:
            self.action_refresh()
        else:
            self._update_subtitle()
        self.set_interval(1.0, self._tick)
        self._update_overview_layout()
        self.query_one(RolodexCategoryList).focus()

    def on_resize(self, event) -> None:  # noqa: ANN001
        self._update_overview_layout()

    def _update_overview_layout(self) -> None:
        try:
            cols = self.query_one("#overview-cols")
        except Exception:  # noqa: BLE001
            return
        width = self.size.width
        cols.remove_class("layout-wide", "layout-medium", "layout-narrow")
        if width >= 120:
            cols.add_class("layout-wide")
        elif width >= 80:
            cols.add_class("layout-medium")
        else:
            cols.add_class("layout-narrow")

    def _render_focusbar(self) -> None:
        self.query_one(FocusBar).show_focus(self.state.get("focus"))

    def _render_gate_strip(self) -> None:
        self.query_one(GateStripBar).show_gates(self.state)

    def _render_all_panels(self) -> None:
        self._populate_categories()
        self._populate_rolodex_items(select_first=False)
        self._render_overview()
        self._render_hub()
        self._render_workstream()
        self._render_ops()
        self._render_focusbar()
        self._render_gate_strip()
        self._update_subtitle()

    def _render_overview(self) -> None:
        from rich.markup import escape as markup_escape

        from dashboard.command_center.panel_briefs import format_overview_panel_text

        plain = markup_escape
        brief = self.state.get("overview_brief") or {}
        self.query_one("#overview-project", OverviewPanel).update(
            format_overview_panel_text(brief, "project", plain_fn=plain)
        )
        self.query_one("#overview-work", OverviewPanel).update(
            format_overview_panel_text(brief, "work", plain_fn=plain)
        )
        self.query_one("#overview-hub", OverviewPanel).update(
            format_overview_panel_text(brief, "hub", plain_fn=plain)
        )
        self.query_one("#overview-patterns", OverviewPanel).update(
            format_overview_panel_text(brief, "patterns", plain_fn=plain)
        )
        self.query_one("#overview-ops", OverviewPanel).update(
            format_overview_panel_text(brief, "ops", plain_fn=plain)
        )
        from dashboard.command_center.workstation import format_execution_bridge_tui

        self.query_one("#overview-bridge", OverviewPanel).update(
            format_execution_bridge_tui(self.state, plain_fn=plain)
        )
        actions = self.state.get("overview_actions") or []
        self.query_one(OverviewActionsList).populate(actions)
        if actions and not self._selected_overview_action_id:
            self._selected_overview_action_id = actions[0]["id"]
        row = self._overview_action_by_id(self._selected_overview_action_id)
        self.query_one(OverviewActionDetail).show_action(row)
        self._update_overview_layout()

    def _copyable_rolodex_actions(self, entry: dict | None) -> list[dict]:
        if not entry:
            return []
        return [
            a
            for a in entry.get("actions") or []
            if a.get("liaison_cmd") and not str(a["liaison_cmd"]).startswith("#")
        ]

    def _rolodex_action_digit(self, digit: int) -> bool:
        """When rolodex tab is active, 1-9 copies numbered actions[] entry."""
        try:
            tabs = self.query_one(TabbedContent)
        except Exception:  # noqa: BLE001
            return False
        if tabs.active != "rolodex":
            return False
        ctx = self._focused_context()
        if ctx == "rolodex" and getattr(self.focused, "id", None) == "rolodex-cats":
            return False
        entry = self._entry_by_id(self._selected_rolodex_id)
        actions = self._copyable_rolodex_actions(entry)
        idx = digit - 1
        if idx >= len(actions):
            self.notify(f"No action {digit} for this entry", title="Rolodex", timeout=3)
            return True
        self._selected_rolodex_action_idx = idx
        cmd = actions[idx]["liaison_cmd"]
        label = actions[idx].get("label", "Action")
        self.copy_to_clipboard(cmd)
        self.notify(f"Copied [{digit}] {label[:40]}:\n{cmd[:72]}", title="Rolodex action", timeout=5)
        return True

    def action_digit_1(self) -> None:
        if not self._rolodex_action_digit(1):
            self.action_category_skills()

    def action_digit_2(self) -> None:
        if not self._rolodex_action_digit(2):
            self.action_category_subagents()

    def action_digit_3(self) -> None:
        if not self._rolodex_action_digit(3):
            self.action_category_projects()

    def action_digit_4(self) -> None:
        if not self._rolodex_action_digit(4):
            self.action_category_commands()

    def action_digit_5(self) -> None:
        if not self._rolodex_action_digit(5):
            self.action_category_tools()

    def action_digit_6(self) -> None:
        self._rolodex_action_digit(6)

    def action_digit_7(self) -> None:
        self._rolodex_action_digit(7)

    def action_digit_8(self) -> None:
        self._rolodex_action_digit(8)

    def action_digit_9(self) -> None:
        self._rolodex_action_digit(9)

    def _tick(self) -> None:
        if time.time() - self._last_refresh >= COMMAND_CENTER_REFRESH_SEC:
            self.action_refresh()

    def _overview_action_by_id(self, action_id: str | None) -> dict | None:
        if not action_id:
            return None
        for row in self.state.get("overview_actions") or []:
            if row["id"] == action_id:
                return row
        return None

    def _metric_by_id(self, metric_id: str | None) -> dict | None:
        if not metric_id:
            return None
        for row in self.state.get("metrics_rows", []):
            if row["id"] == metric_id:
                return row
        return None

    def _agent_by_name(self, name: str | None) -> dict | None:
        if not name:
            return None
        for row in self.state["agent_rows"]:
            if row["name"] == name:
                return row
        return None

    def _task_by_id(self, task_id: str | None) -> dict | None:
        if not task_id:
            return None
        for task in self.state["tasks"]:
            if task["task_id"] == task_id:
                return task
        return None

    def _focused_context(self) -> str:
        focused = self.focused
        if focused is None:
            return "none"
        node_id = getattr(focused, "id", None) or ""
        if node_id == "hub-agents":
            return "hub"
        if node_id == "handoffs":
            return "handoffs"
        if node_id == "metrics":
            return "metrics"
        if node_id == "overview-actions":
            return "overview_actions"
        if node_id in ("rolodex-items", "rolodex-detail", "rolodex-cats"):
            return "rolodex"
        if isinstance(focused, KanbanColumn):
            return "kanban"
        return node_id or "other"

    def _current_liaison_cmd(self) -> str | None:
        ctx = self._focused_context()
        if ctx == "hub":
            agent = self._agent_by_name(self._selected_hub_name)
            launch = (agent or {}).get("launch", "")
            return launch if launch and launch != "—" else None
        if ctx == "overview_actions":
            row = self._overview_action_by_id(self._selected_overview_action_id)
            if row and row.get("kind") == "refresh":
                return None
            cmd = (row or {}).get("liaison_cmd")
            return cmd if cmd and not cmd.startswith("#") else None
        if ctx == "rolodex":
            entry = self._entry_by_id(self._selected_rolodex_id)
            actions = self._copyable_rolodex_actions(entry)
            if actions:
                idx = min(self._selected_rolodex_action_idx, len(actions) - 1)
                return actions[idx]["liaison_cmd"]
            launch = (entry or {}).get("launch", "")
            return launch if launch else None
        if ctx == "metrics":
            row = self._metric_by_id(self._selected_metric_id)
            return (row or {}).get("liaison_cmd")
        if ctx == "handoffs" and self._selected_ops:
            kind = self._selected_ops.get("kind")
            if kind == "handoff":
                row = self._selected_ops["row"]
                if row["status"] == "pending_approval":
                    path = row.get("path", "<file>")
                    return f"liaison approve-artifact {path}"
                return "liaison look"
            if kind == "debrief":
                return "liaison debrief --show"
        if ctx == "kanban" and self._selected_ops:
            return "liaison status"
        return None

    def _current_path(self) -> str | None:
        ctx = self._focused_context()
        if ctx == "hub":
            agent = self._agent_by_name(self._selected_hub_name)
            docs = (agent or {}).get("hub_docs", "")
            if docs and docs != "—" and Path(docs).exists():
                return docs
            guide = (agent or {}).get("handoff_guide", "")
            if guide and guide != "—" and Path(guide).exists():
                return guide
            return None
        if ctx == "rolodex":
            entry = self._entry_by_id(self._selected_rolodex_id)
            path = (entry or {}).get("path", "")
            if path and Path(path).expanduser().exists():
                return str(Path(path).expanduser())
            return None
        if ctx == "metrics":
            row = self._metric_by_id(self._selected_metric_id)
            path = (row or {}).get("path")
            if path and Path(path).exists():
                return path
            return None
        if ctx == "handoffs" and self._selected_ops:
            row = self._selected_ops.get("row", {})
            path = row.get("path")
            if path and Path(path).exists():
                return path
            return None
        if ctx == "kanban" and self._selected_ops:
            task = self._selected_ops.get("task")
            if task:
                return task.get("path")
        return None

    def _show_ops_detail(self, title: str, detail: str, **kwargs) -> None:
        self.query_one(OpsDetail).show_selection(
            title, detail, output=self._cmd_output or None, **kwargs
        )

    def _populate_categories(self) -> None:
        cats = self.query_one(RolodexCategoryList)
        cats.clear()
        self._category_map = {}
        prefix = new_gen()
        for key in CATEGORIES:
            sid = prefix + key
            self._category_map[sid] = key
            count = len(self.state["rolodex"].get(key, []))
            hint = ROLODEX_CATEGORY_HINTS.get(key, "")
            label = f"{ROLODEX_LABELS[key]} ({count})"
            if hint:
                label = f"{label}\n[dim]{hint}[/dim]"
            cats.append(ListItem(Label(label), id=sid))

    def _populate_rolodex_items(self, select_first: bool = True) -> None:
        items = self.query_one(RolodexItemList)
        items.clear()
        entries = list(self.state["rolodex"].get(self.rolodex_category, []))
        if self.rolodex_category == "skills" and self._skills_owner_filter:
            entries = [
                e for e in entries if e.get("meta", {}).get("owner") == self._skills_owner_filter
            ]
        self._rolodex_item_map = {}
        used: set[str] = set()
        prefix = new_gen()
        for entry in entries:
            sid = prefix + safe_id(entry["id"], used)
            self._rolodex_item_map[sid] = entry["id"]
            star = "★ " if entry.get("recommended") else ""
            items.append(
                ListItem(
                    Label(f"{star}{entry['title'][:28]}\n{entry.get('subtitle', '')[:32]}"),
                    id=sid,
                )
            )
        detail = self.query_one(RolodexDetail)
        if entries and select_first:
            items.index = 0
            self._selected_rolodex_id = entries[0]["id"]
            self._selected_rolodex_action_idx = 0
            detail.show_entry(entries[0])
        else:
            self._selected_rolodex_id = None
            self._selected_rolodex_action_idx = 0
            detail.show_entry(None)

    def _entry_by_id(self, entry_id: str | None) -> dict | None:
        if not entry_id:
            return None
        for entry in self.state["rolodex"].get(self.rolodex_category, []):
            if entry["id"] == entry_id:
                return entry
        return None

    def _render_hub(self) -> None:
        agents = self.query_one(HubAgentList)
        agents.border_title = f"Hub agents ({len(self.state['agent_rows'])})"
        agents.clear()
        self._hub_item_map = {}
        used: set[str] = set()
        prefix = new_gen()
        groups = self.state.get("hub_agent_groups") or []
        if not groups:
            groups = [{"id": "all", "label": "All", "agents": self.state["agent_rows"]}]
        for group in groups:
            header = f"── {group.get('label', group.get('id', ''))} ──"
            hid = prefix + safe_id(f"hdr-{group.get('id', '')}", used)
            agents.append(ListItem(Label(header), id=hid, disabled=True))
            for row in group.get("agents", []):
                sid = prefix + safe_id(row["name"], used)
                self._hub_item_map[sid] = row["name"]
                star = "★ " if row.get("recommended") else "  "
                display = (row.get("display") or row["name"])[:13]
                label = (
                    f"{star}{display:<13} {row['status']:<6} "
                    f"t={row['tasks']} {(row.get('role') or '')[:22]}"
                )
                agents.append(ListItem(Label(label), id=sid))
        detail = self.query_one(HubDetail)
        if self.state["agent_rows"]:
            if self._selected_hub_name:
                agent = self._agent_by_name(self._selected_hub_name)
                detail.show_agent(agent)
            else:
                self._selected_hub_name = self.state["agent_rows"][0]["name"]
                agents.index = 0
                detail.show_agent(self.state["agent_rows"][0])
        else:
            self._selected_hub_name = None
            detail.show_agent(None)

    def _render_project_report(self) -> None:
        from rich.markup import escape as markup_escape

        from dashboard.command_center.panel_briefs import format_workstream_guide_text
        from dashboard.command_center.project_portfolio import format_project_detail_tui

        guide = self.query_one("#workstream-guide", Static)
        detail = self.state.get("project_detail")
        if detail:
            body = format_project_detail_tui(detail, plain_fn=markup_escape)
            brief = self.state.get("workstream_brief") or {}
            if brief.get("reporter_how_to"):
                body += f"\n\n[bold]Reporter path[/bold]\n  {markup_escape(brief['reporter_how_to'][:480])}"
            guide.update(body)
        else:
            brief = self.state.get("workstream_brief") or {}
            guide.update(format_workstream_guide_text(brief, plain_fn=markup_escape))

        panel = self.query_one("#project-report", Static)
        if not self.selected_project:
            panel.update("")
            return
        lines = [f"[bold]Quick status · {self.selected_project}[/bold]"]
        for section in brief.get("sections") or []:
            lines.append(f"  {section.get('title', '')}: {str(section.get('body', ''))[:72]}")
        lines.append("[dim]Overview tab · quick actions · !/x on command[/dim]")
        panel.update("\n".join(lines))

    def _render_reporter_checklist(self) -> None:
        panel = self.query_one("#reporter-checklist", Static)
        if not self.selected_project:
            panel.update("")
            return
        open_tasks = [
            t
            for bucket in ("todo", "in_progress", "review")
            for t in self.state["kanban"].get(bucket, [])
        ]
        if not open_tasks:
            panel.update("[dim]No open tasks for focused project[/]")
            return
        task = open_tasks[0]
        steps = task.get("reporter_steps") or {}
        order = ("init", "snapshot", "attach", "approve", "validate", "close")
        glyphs = {True: "✓", False: "○"}

        def mark(key: str) -> str:
            val = steps.get(key, False)
            if key == "approve" and not val and steps.get("attach"):
                return "!"
            return glyphs.get(bool(val), "○")

        lines = [f"[bold]Reporter[/] · {task.get('task_id', '?')}"]
        for key in order:
            lines.append(f"  {mark(key)} {key}")
        panel.update("\n".join(lines))

    def _render_workstream(self) -> None:
        self._render_reporter_checklist()
        self._render_project_report()
        kb = self.state["kanban"]
        self.query_one("#kanban-todo", KanbanColumn).populate(
            f"TODO ({len(kb['todo'])})", kb["todo"]
        )
        self.query_one("#kanban-progress", KanbanColumn).populate(
            f"IN PROGRESS ({len(kb['in_progress'])})", kb["in_progress"]
        )
        self.query_one("#kanban-review", KanbanColumn).populate(
            f"REVIEW ({len(kb['review'])})", kb["review"]
        )
        self.query_one("#kanban-done", KanbanColumn).populate(
            f"DONE ({len(kb['done'])})", kb["done"]
        )
        self.query_one(ProjectList).populate(
            self.state["project_matrix"], self.selected_project
        )

    def _render_ops(self) -> None:
        self.query_one(HandoffList).border_title = "Handoffs & debriefs (signoff first)"
        self.query_one(HandoffList).populate(
            self.state["handoffs"], self.state["debriefs"]
        )
        self.query_one(MetricsList).populate(self.state.get("metrics_rows", []))
        if self._selected_metric_id:
            row = self._metric_by_id(self._selected_metric_id)
            if row:
                self._show_ops_detail(row["label"], row["detail"], path=row.get("path"), liaison_cmd=row.get("liaison_cmd"))
            else:
                self._show_signoff_detail()
        elif self._selected_ops:
            self._update_ops_from_selection(self._selected_ops)
        else:
            self._show_signoff_detail()

    def _show_signoff_detail(self) -> None:
        from rich.markup import escape as markup_escape

        from dashboard.command_center.panel_briefs import format_ops_signoff_text

        signoff = self.state.get("ops_signoff") or {}
        ready = signoff.get("ready_for_signoff")
        title = "Ready for signoff" if ready else "Ops signoff — action required"
        self._show_ops_detail(
            title,
            format_ops_signoff_text(signoff, plain_fn=markup_escape),
            liaison_cmd="liaison look",
        )

    def _update_subtitle(self) -> None:
        sel = f" · project={self.selected_project}" if self.selected_project else ""
        rc = ROLODEX_LABELS.get(self.rolodex_category, self.rolodex_category)
        self.sub_title = (
            f"{LIAISON_VERSION} · {len(self.state['agent_rows'])} hub agents · "
            f"{self.state['summary']['open_tasks']} open · rolodex={rc}{sel} · "
            "Tab focus · o open · x run · ! copy"
        )

    def _set_category(self, category: str) -> None:
        if category not in CATEGORIES:
            return
        self.rolodex_category = category
        if category != "skills":
            self._skills_owner_filter = None
        self._populate_rolodex_items()
        cats = self.query_one(RolodexCategoryList)
        for idx, key in enumerate(CATEGORIES):
            if key == category:
                cats.index = idx
                break
        self._update_subtitle()

    def _update_ops_from_selection(self, selection: dict) -> None:
        kind = selection.get("kind")
        if kind == "handoff":
            row = selection["row"]
            cmd = (
                f"liaison approve-artifact {row.get('path', '<file>')}"
                if row["status"] == "pending_approval"
                else "liaison look"
            )
            self._show_ops_detail(
                f"Handoff {row['task_id']}",
                f"Repo {row['repo']} · {row['artifact']} · {row['status']} · phase {row['phase']}",
                path=row.get("path"),
                liaison_cmd=cmd,
            )
        elif kind == "debrief":
            row = selection["row"]
            self._show_ops_detail(
                f"Debrief {row['repo']}",
                f"{row['file']} · {row['age']}",
                path=row.get("path"),
                liaison_cmd="liaison debrief --show",
            )
        elif kind == "kanban":
            task = selection["task"]
            self._show_ops_detail(
                f"Task {task['task_id']}",
                str(task.get("description", ""))[:200],
                path=task.get("path"),
                liaison_cmd="liaison status",
            )

    def action_category_skills(self) -> None:
        self._skills_owner_filter = None
        self._set_category("skills")

    def action_category_subagents(self) -> None:
        self._skills_owner_filter = None
        self._set_category("subagents")

    def action_category_commands(self) -> None:
        self._skills_owner_filter = None
        self._set_category("commands")

    def action_category_projects(self) -> None:
        self._skills_owner_filter = None
        self._set_category("projects")

    def action_category_tools(self) -> None:
        self._skills_owner_filter = None
        self._set_category("tools")

    def action_filter_hermes_skills(self) -> None:
        self._set_category("skills")
        self._skills_owner_filter = "hermes"
        self._populate_rolodex_items()
        self._update_subtitle()

    def action_clear_project(self) -> None:
        if not self.selected_project:
            return
        self.selected_project = None
        self.state = collect_command_center_state(
            refresh=False, selected_project=None, rolodex_category=self.rolodex_category
        )
        self._render_all_panels()
        self.notify("Focus cleared — showing all projects", title="Focus", timeout=3)

    def action_copy_launch(self) -> None:
        ctx = self._focused_context()
        if ctx == "hub":
            agent = self._agent_by_name(self._selected_hub_name)
            launch = (agent or {}).get("launch", "")
            if launch and launch != "—":
                self.copy_to_clipboard(launch)
                self.notify(f"Copied: {launch[:72]}", title="Hub launch", timeout=4)
            else:
                self.notify("No launch line for this agent", title="Hub")
            return
        entry = self._entry_by_id(self._selected_rolodex_id)
        launch = (entry or {}).get("launch", "")
        if launch:
            self.copy_to_clipboard(launch)
            self.notify(f"Copied: {launch[:72]}", title="Launch", timeout=4)
        else:
            self.notify("No launch line for this entry", title="Rolodex")

    def action_copy_command(self) -> None:
        cmd = self._current_liaison_cmd()
        if not cmd:
            self.notify("No liaison command for this selection", title="Copy")
            return
        self.copy_to_clipboard(cmd)
        self.notify(f"Copied: {cmd[:72]}", title="Liaison cmd", timeout=4)

    def action_open_path(self) -> None:
        path_str = self._current_path()
        if not path_str:
            self.notify("No path for this selection", title="Open")
            return
        path = Path(path_str)
        if not path.exists():
            self.copy_to_clipboard(path_str)
            self.notify(f"Path missing — copied to clipboard:\n{path_str}", title="Open", timeout=8)
            return
        opened = False
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            try:
                subprocess.run(
                    ["xdg-open", str(path)],
                    check=False,
                    timeout=5,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                opened = True
                self.notify(f"Opened {path_str}", title="Open", timeout=4)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                opened = False
        if not opened:
            self.copy_to_clipboard(path_str)
            self.notify(f"Headless — copied path:\n{path_str}", title="Open", timeout=8)

    def action_execute_liaison(self) -> None:
        cmd = self._current_liaison_cmd()
        if not cmd:
            self.notify("No liaison command for this selection", title="Run")
            return
        if liaison_cmd_is_destructive(cmd):
            self.notify(
                f"Destructive — copy with ! and run manually:\n{cmd[:120]}",
                title="Not auto-run",
                timeout=10,
            )
            return
        if not liaison_cmd_is_readonly(cmd):
            self.notify(
                f"Not allowlisted — copy with !:\n{cmd[:120]}",
                title="Read-only only",
                timeout=10,
            )
            return
        self._run_liaison_cmd(cmd)

    def action_goto_subagent(self) -> None:
        if self._focused_context() != "hub" or not self._selected_hub_name:
            self.notify("Focus a hub agent first", title="Rolodex")
            return
        agent_id = f"agent:{self._selected_hub_name}"
        self._set_category("subagents")
        tabs = self.query_one(TabbedContent)
        tabs.active = "rolodex"
        items = self.query_one(RolodexItemList)
        entries = self.state["rolodex"].get("subagents", [])
        for idx, entry in enumerate(entries):
            if entry["id"] == agent_id:
                items.index = idx
                self._selected_rolodex_id = agent_id
                self.query_one(RolodexDetail).show_entry(entry)
                self.query_one(RolodexItemList).focus()
                self.notify(f"Rolodex → {self._selected_hub_name}", title="Subagents", timeout=3)
                return
        self.notify(f"No rolodex entry for {self._selected_hub_name}", title="Subagents")

    @work(thread=True)
    def _run_liaison_cmd(self, cmd: str) -> None:
        try:
            parts = shlex.split(cmd)
            if parts and parts[0] == "liaison":
                executable = str(LIAISON_BIN) if LIAISON_BIN.exists() else parts[0]
                argv = [executable, *parts[1:]]
            else:
                argv = parts
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(AGENT_SYSTEM_DIR),
            )
            output = (result.stdout or "") + (result.stderr or "")
            if not output.strip():
                output = f"(exit {result.returncode}, no output)"
            self.call_from_thread(self._apply_cmd_output, cmd, output.strip())
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(self._apply_cmd_output, cmd, f"Error: {exc}")

    def _apply_cmd_output(self, cmd: str, output: str) -> None:
        self._cmd_output = output
        self.notify(f"Ran: {cmd[:60]}", title="Liaison", timeout=3)
        ctx = self._focused_context()
        if ctx == "metrics":
            row = self._metric_by_id(self._selected_metric_id)
            if row:
                self._show_ops_detail(
                    row["label"], row["detail"], path=row.get("path"), liaison_cmd=row.get("liaison_cmd")
                )
        elif self._selected_ops:
            self._update_ops_from_selection(self._selected_ops)

    # ── Agent tab ─────────────────────────────────────────────────────────────

    def action_goto_agent(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = "agent"
        self.query_one("#agent-input", Input).focus()

    # ── ChatSession singleton (shared across all Agent tab interactions) ──────

    _chat_session: "ChatSession | None" = None  # type: ignore[name-defined]

    def _get_chat_session(self) -> "ChatSession":  # type: ignore[name-defined]
        if self._chat_session is None:
            import sys as _sys
            _agent_root = str(Path(__file__).parent.parent.parent)
            if _agent_root not in _sys.path:
                _sys.path.insert(0, _agent_root)
            from reflexion_dspy.repl import ChatSession
            # Verbose=False for TUI — we capture stdout instead
            self._chat_session = ChatSession(verbose=True)
        return self._chat_session

    @on(Input.Submitted, "#agent-input")
    def agent_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()
        self._agent_dispatch(text)

    def _agent_dispatch(self, text: str) -> None:
        """Route input to ChatSession (slash commands or free text)."""
        log = self.query_one("#agent-log", RichLog)
        log.write(f"[bold cyan]you ▶[/bold cyan] {text}")
        self.query_one("#agent-status", Static).update(f"Running…")
        self._run_chat_turn(text)

    @work(thread=True)
    def _run_chat_turn(self, text: str) -> None:
        """Execute one ChatSession turn, capturing output to the TUI log."""
        import io, sys as _sys, threading

        # Animated spinner so the user knows the agent is running
        _stop_spinner = threading.Event()
        _spinner_frames = "⣾⣽⣻⢿⡿⣟⣯⣷"

        def _spin() -> None:
            i = 0
            while not _stop_spinner.is_set():
                frame = _spinner_frames[i % len(_spinner_frames)]
                self.call_from_thread(self._agent_set_status, f"{frame} thinking…")
                i += 1
                _stop_spinner.wait(0.12)

        _spinner_thread = threading.Thread(target=_spin, daemon=True)
        _spinner_thread.start()

        # Redirect stdout so verbose agent logs appear in the TUI log
        old_stdout = _sys.stdout
        captured = io.StringIO()
        _sys.stdout = captured

        try:
            session = self._get_chat_session()
            session._handle(text)
        except SystemExit:
            # /quit typed in TUI — don't actually exit, just note it
            self.call_from_thread(self._agent_log_line, "[yellow]Use Ctrl+Q or q to quit the TUI.[/yellow]")
        except Exception as exc:
            self.call_from_thread(self._agent_log_line, f"[red]Error: {exc}[/red]")
        finally:
            _stop_spinner.set()
            _sys.stdout = old_stdout

        output = captured.getvalue()
        for line in output.splitlines():
            stripped = line.strip()
            if stripped:
                self.call_from_thread(self._agent_log_line, stripped)

        # Refresh kanban after any agent run that may have advanced tasks
        self.call_from_thread(self._refresh_kanban_from_thread)
        self.call_from_thread(self._agent_set_status, "Ready")

    def _refresh_kanban_from_thread(self) -> None:
        """Re-populate kanban columns from disk state (called after agent run)."""
        try:
            from dashboard.command_center.data import collect_command_center_state
            fresh = collect_command_center_state(refresh=True)
            kb = fresh.get("kanban", {})
            from dashboard.command_center.app import KanbanColumn
            for bucket, col_id in [
                ("todo", "#kanban-todo"),
                ("in_progress", "#kanban-progress"),
                ("review", "#kanban-review"),
                ("done", "#kanban-done"),
            ]:
                col = self.query_one(col_id, KanbanColumn)
                col.populate(bucket.replace("_", " ").title(), kb.get(bucket, []))
        except Exception:
            pass  # non-fatal — kanban refreshes on next poll anyway

    @work(thread=True)
    def _stream_agent_cmd(self, cmd: str) -> None:
        """Legacy: run a raw liaison CLI command and stream output. Kept for backward compat."""
        executable = str(LIAISON_BIN) if LIAISON_BIN.exists() else "liaison"
        parts = shlex.split(cmd)
        if parts and parts[0] == "liaison":
            argv = [executable, *parts[1:]]
        else:
            argv = parts

        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(Path.cwd()),
            )
            for line in proc.stdout:  # type: ignore[union-attr]
                stripped = line.rstrip("\n")
                if stripped:
                    self.call_from_thread(self._agent_log_line, stripped)
            proc.wait()
            rc = proc.returncode
            summary = f"[green]✓ done (exit {rc})[/green]" if rc == 0 else f"[red]✗ exit {rc}[/red]"
            self.call_from_thread(self._agent_log_line, summary)
            self.call_from_thread(self._agent_set_status, "Ready")
        except Exception as exc:
            self.call_from_thread(self._agent_log_line, f"[red]Error: {exc}[/red]")
            self.call_from_thread(self._agent_set_status, "Error")

    def _agent_log_line(self, line: str) -> None:
        self.query_one("#agent-log", RichLog).write(line)

    def _agent_set_status(self, text: str) -> None:
        self.query_one("#agent-status", Static).update(text)

    @on(ListView.Selected, "#rolodex-cats")
    def category_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            category = self._category_map.get(event.item.id)
            if category:
                self._set_category(category)

    @on(ListView.Selected, "#rolodex-items")
    def rolodex_item_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            raw = self._rolodex_item_map.get(event.item.id)
            self._selected_rolodex_id = raw
            self._selected_rolodex_action_idx = 0
            entry = self._entry_by_id(raw)
            if entry:
                self.query_one(RolodexDetail).show_entry(entry)

    @on(ListView.Selected, "#hub-agents")
    def hub_agent_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            name = self._hub_item_map.get(event.item.id)
            if not name:
                return
            self._selected_hub_name = name
            agent = self._agent_by_name(name)
            self.query_one(HubDetail).show_agent(agent)
            launch = (agent or {}).get("launch", "")
            if launch and launch != "—":
                self.notify(
                    f"{name}: {launch[:80]}\nc copy · g rolodex · o docs · x run",
                    title="Hub agent",
                    timeout=6,
                )

    @on(ListView.Selected, "#projects")
    def project_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            self.selected_project = getattr(event.control, "id_map", {}).get(event.item.id, event.item.id)
            self.state = collect_command_center_state(
                refresh=False,
                selected_project=self.selected_project,
                rolodex_category=self.rolodex_category,
            )
            self._render_all_panels()
            focus = self.state.get("focus") or {}
            self.notify(
                f"Focus: {self.selected_project} ({focus.get('lifecycle','?')}/{focus.get('phase','?')}) — "
                "Hub, Skills, Patterns, Kanban, Ops linked. Esc clears.",
                title="Project focus",
                timeout=6,
            )

    @on(ListView.Selected, "#handoffs")
    def handoff_selected(self, event: ListView.Selected) -> None:
        if not event.item or not event.item.id:
            return
        mapped = getattr(event.control, "id_map", {}).get(event.item.id)
        if not mapped:
            return
        row = mapped["row"]
        if mapped["kind"] == "handoff":
            self._selected_ops = {"kind": "handoff", "row": row}
            self._update_ops_from_selection(self._selected_ops)
            path_hint = f"\n{row['path']}" if row.get("path") else ""
            self.notify(
                f"Task {row['task_id']} · {row['artifact']}{path_hint}",
                title="Handoff",
                timeout=8,
            )
        else:
            self._selected_ops = {"kind": "debrief", "row": row}
            self._update_ops_from_selection(self._selected_ops)
            self.notify(
                f"{row['path']}\nliaison debrief --show",
                title="Debrief",
                timeout=8,
            )

    @on(ListView.Selected, "#overview-actions")
    def overview_action_selected(self, event: ListView.Selected) -> None:
        if not event.item or not event.item.id:
            return
        action_id = getattr(event.control, "id_map", {}).get(event.item.id)
        self._selected_overview_action_id = action_id
        row = self._overview_action_by_id(action_id)
        self.query_one(OverviewActionDetail).show_action(row)
        if not row:
            return
        if row.get("kind") == "refresh":
            self.notify("Press r to sync liaison state", title=row["label"], timeout=4)
            return

    @on(ListView.Selected, "#metrics")
    def metric_selected(self, event: ListView.Selected) -> None:
        if not event.item or not event.item.id:
            return
        self._selected_metric_id = getattr(event.control, "id_map", {}).get(event.item.id)
        row = self._metric_by_id(self._selected_metric_id)
        if not row:
            return
        self._show_ops_detail(
            row["label"], row["detail"], path=row.get("path"), liaison_cmd=row.get("liaison_cmd")
        )
        if row.get("liaison_cmd"):
            self.notify(row["liaison_cmd"], title="Metric hint", timeout=6)

    @on(ListView.Selected)
    def kanban_task_selected(self, event: ListView.Selected) -> None:
        widget = event.control
        if not isinstance(widget, KanbanColumn) or not event.item or not event.item.id:
            return
        task_id = getattr(widget, "id_map", {}).get(event.item.id)
        task = self._task_by_id(task_id)
        if not task:
            return
        self._selected_ops = {"kind": "kanban", "task": task}
        self._update_ops_from_selection(self._selected_ops)
        self.notify(
            f"Task {task['task_id']}\n{task.get('path', '')}\nliaison status",
            title="Kanban",
            timeout=8,
        )

    @work(thread=True)
    def action_refresh(self) -> None:
        state = collect_command_center_state(
            refresh=True,
            selected_project=self.selected_project,
            rolodex_category=self.rolodex_category,
        )
        self.call_from_thread(self._apply_refresh, state)

    def _apply_refresh(self, state: dict) -> None:
        self.state = state
        self._last_refresh = time.time()
        sel_id = self._selected_rolodex_id
        self._populate_categories()
        self._populate_rolodex_items(select_first=False)
        if sel_id:
            items = self.query_one(RolodexItemList)
            entries = state["rolodex"].get(self.rolodex_category, [])
            for idx, entry in enumerate(entries):
                if entry["id"] == sel_id:
                    items.index = idx
                    self.query_one(RolodexDetail).show_entry(entry)
                    break
        self._render_hub()
        self._render_workstream()
        self._render_ops()
        self._render_focusbar()
        self._render_gate_strip()
        self._update_subtitle()


def run_command_center_app(state: dict, refresh: bool = False) -> None:
    ensure_import_path()
    try:
        CommandCenterApp(state, refresh_on_start=refresh).run()
    except Exception as exc:  # noqa: BLE001
        from dashboard.command_center.snapshot import print_command_center_snapshot

        print(f"Interactive TUI unavailable ({exc}); printing snapshot.")
        print_command_center_snapshot(state)
