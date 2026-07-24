"""
liaison interactive REPL — works like Claude Code.

Usage:
    liaison          # drop into chat in $PWD
    liaison chat     # same

Features:
  - Multi-turn conversation with persistent history
  - $PWD project context auto-detected at startup
  - Free text → ReflexionAgent (MCP tools, Reflexion, DSPy)
  - /code <task>    → CodingAgent writes files, runs tests, commits
  - /next           → AI-suggested best next step
  - /kanban         → show spark-flow task board
  - /eval <claim>   → score a claim against the project state
  - /compact        → summarise history to save context
  - /clear          → wipe history
  - /help           → commands
  - /quit           → exit
"""

from __future__ import annotations

import json
import os
import readline  # noqa: F401 — side-effect: enables arrow keys / history
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import dspy

# ── rich terminal output ──────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.text import Text
    _RICH = True
except ImportError:
    _RICH = False

_console = Console(highlight=False) if _RICH else None

def _print(msg: str, style: str = "") -> None:
    if _RICH and _console:
        if style:
            _console.print(msg, style=style)
        else:
            _console.print(Markdown(msg))
    else:
        print(msg)

def _rule(title: str = "") -> None:
    if _RICH and _console:
        _console.print(Rule(title, style="dim"))
    else:
        print(f"── {title} " + "─" * max(0, 60 - len(title)))

def _panel(content: str, title: str = "", style: str = "cyan") -> None:
    if _RICH and _console:
        _console.print(Panel(content, title=title, border_style=style))
    else:
        print(f"┌─ {title} ─┐\n{content}\n└────────────┘")


# ── project context ───────────────────────────────────────────────────────────

@dataclass
class ProjectContext:
    path: Path
    name: str
    git_log: str = ""
    todo: str = ""
    readme_excerpt: str = ""
    open_tasks: list[str] = field(default_factory=list)
    test_cmd: str = ""

    @classmethod
    def from_cwd(cls) -> "ProjectContext":
        cwd = Path.cwd()
        name = cwd.name

        # git log
        git_log = ""
        try:
            git_log = subprocess.check_output(
                ["git", "log", "--oneline", "-8"],
                cwd=str(cwd), stderr=subprocess.DEVNULL, text=True
            ).strip()
        except Exception:
            pass

        # TODO.md / TASKS.md / AGENTS.md
        todo = ""
        for candidate in ["TODO.md", "TASKS.md", "AGENTS.md", "PROJECT_SPEC.md"]:
            p = cwd / candidate
            if p.exists():
                todo = p.read_text(errors="replace")[:1200]
                break

        # README excerpt
        readme_excerpt = ""
        for candidate in ["README.md", "README.rst", "readme.md"]:
            p = cwd / candidate
            if p.exists():
                readme_excerpt = p.read_text(errors="replace")[:600]
                break

        # open spark-flow tasks
        open_tasks: list[str] = []
        sf = cwd / ".spark-flow" / "tasks"
        if sf.exists():
            for td in sorted(sf.iterdir()):
                if not td.is_dir():
                    continue
                st = _read_state_txt(td)
                if st:
                    phase = st.get("CURRENT_PHASE", "plan")
                    if phase not in ("complete", "closed"):
                        desc = st.get("DESCRIPTION", "?")[:60]
                        open_tasks.append(f"{td.name}: {desc} [{phase}]")
                else:
                    state_f = td / "state.json"
                    if state_f.exists():
                        try:
                            s = json.loads(state_f.read_text())
                            if s.get("status") not in ("closed", "done"):
                                open_tasks.append(
                                    f"{td.name}: {s.get('title', '?')} [{s.get('status','?')}]"
                                )
                        except Exception:
                            pass

        # detect test command
        test_cmd = ""
        if (cwd / "pytest.ini").exists() or (cwd / "pyproject.toml").exists():
            test_cmd = "pytest -q"
        elif (cwd / "package.json").exists():
            test_cmd = "npm test"
        elif (cwd / "Makefile").exists():
            test_cmd = "make test"

        return cls(
            path=cwd, name=name, git_log=git_log, todo=todo,
            readme_excerpt=readme_excerpt, open_tasks=open_tasks, test_cmd=test_cmd,
        )

    def as_context_block(self) -> str:
        parts = [f"## Project: {self.name} ({self.path})"]
        if self.readme_excerpt:
            parts.append(f"\n### README\n{self.readme_excerpt}")
        if self.todo:
            parts.append(f"\n### TODO / Tasks\n{self.todo[:800]}")
        if self.git_log:
            parts.append(f"\n### Recent commits\n```\n{self.git_log}\n```")
        if self.open_tasks:
            parts.append("\n### Open spark-flow tasks\n" + "\n".join(f"- {t}" for t in self.open_tasks))
        if self.test_cmd:
            parts.append(f"\n### Test command: `{self.test_cmd}`")
        return "\n".join(parts)


# ── history persistence ───────────────────────────────────────────────────────

_HISTORY_DIR = Path.home() / ".liaison" / "chat_history"

def _history_path(project_name: str) -> Path:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return _HISTORY_DIR / f"{project_name}.jsonl"

def _load_history(project_name: str, max_turns: int = 20) -> list[dict]:
    p = _history_path(project_name)
    if not p.exists():
        return []
    turns = []
    for line in p.read_text().splitlines():
        try:
            turns.append(json.loads(line))
        except Exception:
            pass
    return turns[-max_turns:]

def _append_history(project_name: str, role: str, content: str) -> None:
    p = _history_path(project_name)
    with p.open("a") as f:
        f.write(json.dumps({"role": role, "content": content, "ts": int(time.time())}) + "\n")

def _clear_history(project_name: str) -> None:
    p = _history_path(project_name)
    if p.exists():
        p.unlink()


# ── STATE.txt helpers (spark-flow's canonical task state format) ──────────────

_AGENT_SYSTEM_DIR = Path(__file__).parent.parent
_NEXT_WORK_JSON = _AGENT_SYSTEM_DIR / "dashboard" / "next_work.json"


def _read_state_txt(td: Path) -> dict[str, str]:
    """Parse STATE.txt (key=value) from a spark-flow task directory."""
    state_f = td / "STATE.txt"
    if not state_f.exists():
        return {}
    result: dict[str, str] = {}
    for line in state_f.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def _write_state_txt(td: Path, state: dict[str, str]) -> None:
    """Write STATE.txt from an ordered dict."""
    state_f = td / "STATE.txt"
    state_f.write_text("\n".join(f"{k}={v}" for k, v in state.items()) + "\n")


def _state_txt_bucket(phase: str) -> str:
    if phase in ("complete", "closed"):
        return "done"
    if phase == "review":
        return "review"
    if phase in ("build", "patch"):
        return "in_progress"
    return "todo"


def _load_next_work() -> str:
    """Read next_work.json (written by `liaison plan-next`) and format top items."""
    try:
        if not _NEXT_WORK_JSON.exists():
            return ""
        data = json.loads(_NEXT_WORK_JSON.read_text())
        items = data.get("items", [])[:5]
        if not items:
            return ""
        lines = ["Priority backlog (from `liaison plan-next`):"]
        for i, item in enumerate(items, 1):
            action = item.get("suggested_action", "?")
            repo = item.get("relative_path", item.get("repo", "?"))
            priority = item.get("priority", "?")
            reasons = ", ".join(item.get("reasons", [])[:2])
            lines.append(f"{i}. [P{priority}] {action} — {repo}")
            if reasons:
                lines.append(f"   Why: {reasons}")
        return "\n".join(lines)
    except Exception:
        return ""


# ── next-step suggester ───────────────────────────────────────────────────────

class _NextStepSig(dspy.Signature):
    """Suggest the single best next action for this project given what was just completed."""
    completed: str = dspy.InputField(desc="What the agent just finished")
    project_state: str = dspy.InputField(desc="Project context: README, TODO, git log, open tasks")
    backlog: str = dspy.InputField(
        desc="Priority backlog from `liaison plan-next` — top items to consider. Empty if not yet generated."
    )
    next_step: str = dspy.OutputField(desc="One concrete next action (imperative sentence, under 120 chars)")
    why: str = dspy.OutputField(desc="One-sentence rationale referencing the backlog if relevant")


_next_step_predictor: dspy.Predict | None = None

def _suggest_next(completed: str, project: ProjectContext) -> tuple[str, str]:
    global _next_step_predictor
    if _next_step_predictor is None:
        _next_step_predictor = dspy.Predict(_NextStepSig)
    try:
        pred = _next_step_predictor(
            completed=completed,
            project_state=project.as_context_block()[:2000],
            backlog=_load_next_work(),
        )
        return pred.next_step.strip(), pred.why.strip()
    except Exception as e:
        return "", f"(next-step suggestion failed: {e})"


# ── eval scorer ──────────────────────────────────────────────────────────────

class _EvalSig(dspy.Signature):
    """Score a claim about the project on a 0-5 scale."""
    claim: str = dspy.InputField()
    project_state: str = dspy.InputField()
    score: str = dspy.OutputField(desc="Integer 0-5")
    verdict: str = dspy.OutputField(desc="pass / fail / partial")
    reasoning: str = dspy.OutputField(desc="One sentence explaining the score")


def _eval_claim(claim: str, project: ProjectContext) -> str:
    try:
        pred = dspy.Predict(_EvalSig)(
            claim=claim,
            project_state=project.as_context_block()[:2000],
        )
        return f"Score: {pred.score}/5  Verdict: {pred.verdict}\n{pred.reasoning}"
    except Exception as e:
        return f"Eval failed: {e}"


# ── kanban display ────────────────────────────────────────────────────────────

def _show_kanban(project: ProjectContext) -> None:
    sf = project.path / ".spark-flow" / "tasks"
    if not sf.exists():
        _print("No spark-flow tasks found in this project.", style="yellow")
        _print("Run `liaison init <task-name>` to create one.", style="dim")
        return

    buckets: dict[str, list[str]] = {"todo": [], "in_progress": [], "review": [], "done": []}
    for td in sorted(sf.iterdir()):
        if not td.is_dir():
            continue
        st = _read_state_txt(td)
        if st:
            phase = st.get("CURRENT_PHASE", "plan")
            desc = st.get("DESCRIPTION", td.name)[:48]
            task_id = st.get("TASK_ID", td.name)
            label = f"[{task_id}] {desc}"
            buckets[_state_txt_bucket(phase)].append(label)
        else:
            state_f = td / "state.json"
            if state_f.exists():
                try:
                    s = json.loads(state_f.read_text())
                    status = s.get("status", "todo")
                    title = s.get("title", td.name)[:48]
                    label = f"[{td.name}] {title}"
                    bucket = "done" if status in ("closed", "done") else \
                             "review" if "review" in status else \
                             "in_progress" if status in ("in_progress", "build", "test", "patch") else "todo"
                    buckets[bucket].append(label)
                except Exception:
                    pass

    lines = []
    for col, items in buckets.items():
        header = {"todo": "📋 TODO", "in_progress": "⚙️  IN PROGRESS",
                  "review": "👀 REVIEW", "done": "✅ DONE"}[col]
        lines.append(f"\n**{header}**")
        if items:
            for item in items:
                lines.append(f"  · {item}")
        else:
            lines.append("  (empty)")

    _panel("\n".join(lines), title=f"Kanban — {project.name}", style="blue")


# ── compact history ───────────────────────────────────────────────────────────

class _CompactSig(dspy.Signature):
    """Summarise a conversation history into a compact context block."""
    history: str = dspy.InputField()
    summary: str = dspy.OutputField(desc="Bullet-point summary of decisions and completed actions, under 300 words")


def _compact_history(history: list[dict]) -> str:
    if not history:
        return ""
    text = "\n".join(
        f"{h['role'].upper()}: {h['content'][:300]}" for h in history
    )
    try:
        pred = dspy.Predict(_CompactSig)(history=text)
        return pred.summary
    except Exception:
        return text[:800]


# ── main ChatSession ──────────────────────────────────────────────────────────

SLASH_HELP = """
**Available commands**

| Command | Description |
|---|---|
| /code <task> | CodingAgent: write files, run tests, commit, iterate |
| /next | Suggest the best next action for this project |
| /kanban | Show spark-flow task board |
| /eval <claim> | Score a claim about the project (0-5) |
| /compact | Summarise conversation history to save context |
| /clear | Wipe conversation history |
| /refresh | Re-scan project context ($PWD) |
| /history | Show recent conversation turns |
| /help | This message |
| /quit | Exit |

Free text (no slash) is sent to the research + tool-use agent.
"""


class ChatSession:
    """
    Interactive multi-turn liaison session.
    Maintains project context, conversation history, and routes to the right agent.
    """

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.project = ProjectContext.from_cwd()
        self.history: list[dict] = _load_history(self.project.name)
        self._agent: Any = None   # ReflexionAgent (lazy)
        self._coder: Any = None   # CodingAgent (lazy)
        self._lm_ready = False

    # ── lazy LM init ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        """Extract #hashtags from task text (used to select NVIDIA NIM models)."""
        import re as _re
        return _re.findall(r'#\w+', text)

    def _ensure_lm(self, task: str = "", use_for: str = "implementation") -> None:
        tags = self._extract_tags(task)
        if self._lm_ready and not tags:
            return
        from reflexion_dspy.config import configure_dspy
        configure_dspy(use_for=use_for, task_tags=tags)
        self._lm_ready = True

    def _get_agent(self) -> Any:
        if self._agent is None:
            self._ensure_lm()
            from reflexion_dspy.agent import ReflexionAgent
            from reflexion_dspy.tools import MCPToolRegistry
            registry = MCPToolRegistry()
            registry.connect()
            self._agent = ReflexionAgent(tool_registry=registry, verbose=self.verbose)
        return self._agent

    def _get_coder(self) -> Any:
        if self._coder is None:
            self._ensure_lm()
            from reflexion_dspy.coder import CodingAgent
            self._coder = CodingAgent(verbose=self.verbose)
        return self._coder

    # ── context for agent calls ───────────────────────────────────────────────

    def _build_context(self) -> str:
        parts: list[str] = []

        # Project snapshot
        parts.append(self.project.as_context_block())

        # Recent conversation (last 6 turns)
        recent = self.history[-6:]
        if recent:
            parts.append("\n## Conversation so far")
            for h in recent:
                role = "You" if h["role"] == "user" else "Agent"
                parts.append(f"\n**{role}:** {h['content'][:400]}")

        return "\n".join(parts)

    # ── routing ───────────────────────────────────────────────────────────────

    def _handle(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        if text.startswith("/"):
            parts = text[1:].split(None, 1)
            cmd = parts[0].lower()
            rest = parts[1].strip() if len(parts) > 1 else ""
            self._slash(cmd, rest)
        else:
            self._free_text(text)

    def _slash(self, cmd: str, rest: str) -> None:
        if cmd in ("quit", "exit", "q"):
            _rule("Goodbye")
            sys.exit(0)
        elif cmd == "help":
            _print(SLASH_HELP)
        elif cmd == "clear":
            self.history.clear()
            _clear_history(self.project.name)
            _print("History cleared.", style="green")
        elif cmd == "refresh":
            self.project = ProjectContext.from_cwd()
            _print(f"Project context refreshed: **{self.project.name}**", style="green")
        elif cmd == "history":
            if not self.history:
                _print("No history yet.", style="dim")
            else:
                for h in self.history[-10:]:
                    role = "You" if h["role"] == "user" else "Agent"
                    _print(f"**{role}:** {h['content'][:200]}", style="cyan" if role == "You" else "white")
        elif cmd == "compact":
            _print("Compacting history…", style="dim")
            self._ensure_lm()
            summary = _compact_history(self.history)
            self.history = [{"role": "assistant", "content": f"[compact] {summary}"}]
            _clear_history(self.project.name)
            _append_history(self.project.name, "assistant", f"[compact] {summary}")
            _print("History compacted.", style="green")
        elif cmd == "kanban":
            _show_kanban(self.project)
        elif cmd == "next":
            self._cmd_next()
        elif cmd == "eval":
            if not rest:
                _print("Usage: /eval <claim>", style="yellow")
                return
            self._ensure_lm()
            _print("Evaluating…", style="dim")
            result = _eval_claim(rest, self.project)
            _panel(result, title="Eval result", style="magenta")
        elif cmd == "code":
            if not rest:
                _print("Usage: /code <task description>", style="yellow")
                return
            self._cmd_code(rest)
        else:
            _print(f"Unknown command `/{cmd}`. Type `/help` for commands.", style="yellow")

    def _cmd_next(self) -> None:
        self._ensure_lm()
        last_completed = next(
            (h["content"][:120] for h in reversed(self.history) if h["role"] == "assistant"),
            "no previous task"
        )
        _print("Thinking about next step…", style="dim")
        step, why = _suggest_next(last_completed, self.project)
        if step:
            _panel(f"**→ {step}**\n\n_{why}_", title="Suggested next step", style="green")
        else:
            _print(why, style="yellow")

    def _cmd_code(self, task: str) -> None:
        # Auto-compact before a code task if history is getting long
        if len(self.history) >= 20:
            _print("[dim]Auto-compacting conversation history before coding…[/dim]")
            self._ensure_lm()
            summary = _compact_history(self.history)
            self.history = [{"role": "assistant", "content": f"[compact] {summary}"}]
            _clear_history(self.project.name)
            _append_history(self.project.name, "assistant", f"[compact] {summary}")

        _rule(f"CodingAgent → {self.project.name}")
        _print(f"**Task:** {task}", style="cyan")
        _print(f"**Repo:** `{self.project.path}`\n", style="dim")

        # Re-configure LM with task hashtags (may switch to NVIDIA NIM)
        self._ensure_lm(task=task, use_for="implementation")
        coder = self._get_coder()
        import hashlib
        task_id = hashlib.md5(f"{task}{time.time()}".encode()).hexdigest()[:8]

        # Build conversation context for the coder from recent history
        context_lines = []
        for turn in self.history[-8:]:
            role = "user" if turn["role"] == "user" else "assistant"
            context_lines.append(f"{role}: {turn['content'][:200]}")
        conversation_context = "\n".join(context_lines)

        try:
            result = coder.run(
                task=task,
                repo_path=self.project.path,
                task_id=task_id,
                context=conversation_context,
            )
        except Exception as e:
            _print(f"CodingAgent error: {e}", style="red")
            return

        # Record in history
        summary = result.summary
        self.history.append({"role": "user", "content": f"/code {task}"})
        self.history.append({"role": "assistant", "content": summary})
        _append_history(self.project.name, "user", f"/code {task}")
        _append_history(self.project.name, "assistant", summary)

        # Show result
        status_style = "green" if result.success else "red"
        status_icon = "✓" if result.success else "✗"
        _rule()
        _print(f"{status_icon} **{'Success' if result.success else 'Failed'}**", style=status_style)
        if result.files_written:
            _print(f"Files: {', '.join(Path(f).name for f in result.files_written)}", style="dim")
        _print(f"Branch: `{result.branch}`  |  Attempts: {result.attempts}", style="dim")
        if result.error:
            _print(f"Error: {result.error[:200]}", style="red")

        # Advance kanban if applicable
        self._maybe_advance_kanban(task, result)

        # Suggest next step
        if result.success:
            step, why = _suggest_next(f"Completed: {task}", self.project)
            if step:
                _rule()
                _print(f"**Next suggestion:** {step}", style="green")
                _print(f"_{why}_", style="dim")

    def _free_text(self, text: str) -> None:
        _rule("Agent")
        agent = self._get_agent()
        context = self._build_context()

        # Record user turn
        self.history.append({"role": "user", "content": text})
        _append_history(self.project.name, "user", text)

        try:
            result = agent.forward(task=text, context=context)
            answer = result.final_answer if hasattr(result, "final_answer") else str(result)
        except Exception as e:
            answer = f"Error: {e}"

        # Record assistant turn
        self.history.append({"role": "assistant", "content": answer})
        _append_history(self.project.name, "assistant", answer)

        _rule()
        _print(answer)

        # Suggest next if the task looks like something completed
        action_words = ("fix", "add", "build", "create", "implement", "write", "update", "refactor")
        if any(text.lower().startswith(w) for w in action_words):
            self._ensure_lm()
            step, why = _suggest_next(text, self.project)
            if step:
                _print(f"\n**→ Next:** {step}", style="green dim")

    # ── kanban bridge ─────────────────────────────────────────────────────────

    def _maybe_advance_kanban(self, task: str, result: Any) -> None:
        """Advance the matching spark-flow card to 'review' on CodingAgent success."""
        if not result.success:
            return
        sf = self.project.path / ".spark-flow" / "tasks"
        if not sf.exists():
            return
        task_lower = task.lower()
        task_words = [w for w in task_lower.split() if len(w) > 4]

        from datetime import datetime as _dt
        now_iso = _dt.now().isoformat(timespec="seconds")

        for td in sf.iterdir():
            if not td.is_dir():
                continue
            st = _read_state_txt(td)
            if st:
                phase = st.get("CURRENT_PHASE", "")
                if phase in ("complete", "closed", "review"):
                    continue
                task_id = st.get("TASK_ID", td.name)
                desc = st.get("DESCRIPTION", "").lower()
                # Match: task_id explicitly mentioned, OR 2+ meaningful words in description
                id_match = task_id.lower() in task_lower
                word_matches = sum(1 for w in task_words if w in desc)
                if id_match or word_matches >= 2:
                    st["CURRENT_PHASE"] = "review"
                    st["UPDATED_AT"] = now_iso
                    _write_state_txt(td, st)
                    _print(f"\nKanban: moved **{task_id}** → review  (branch: {result.branch})", style="cyan")
            else:
                # Fall back to state.json for non-STATE.txt tasks
                state_f = td / "state.json"
                if not state_f.exists():
                    continue
                try:
                    s = json.loads(state_f.read_text())
                    if s.get("status") in ("closed", "done", "review"):
                        continue
                    title = s.get("title", "").lower()
                    word_matches = sum(1 for w in task_words if w in title)
                    if word_matches >= 2:
                        s["status"] = "review"
                        s["advanced_by"] = "liaison-chat"
                        s["branch"] = result.branch
                        state_f.write_text(json.dumps(s, indent=2))
                        _print(f"\nKanban: moved **{td.name}** → review", style="cyan")
                except Exception:
                    pass

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        # Banner
        _rule()
        if _RICH and _console:
            _console.print(
                f"[bold cyan]liaison[/bold cyan] [dim]—[/dim] [bold]{self.project.name}[/bold]  "
                f"[dim]{self.project.path}[/dim]"
            )
        else:
            print(f"liaison — {self.project.name}  ({self.project.path})")

        hints = []
        if self.history:
            hints.append(f"{len(self.history)} turns in history")
        if self.project.open_tasks:
            hints.append(f"{len(self.project.open_tasks)} open task(s)")
        if hints:
            _print("  ".join(hints), style="dim")
        _print("Type `/help` for commands, `/quit` to exit.\n", style="dim")

        while True:
            try:
                if _RICH and _console:
                    prompt_text = Text()
                    prompt_text.append("liaison", style="bold cyan")
                    prompt_text.append(f"({self.project.name})", style="dim")
                    prompt_text.append(" > ", style="bold")
                    text = _console.input(str(prompt_text))
                else:
                    text = input(f"liaison({self.project.name}) > ")
            except (EOFError, KeyboardInterrupt):
                print()
                _rule("Goodbye")
                break

            self._handle(text)


# ── entry point ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import argparse
    p = argparse.ArgumentParser(prog="liaison chat", description="Interactive liaison REPL")
    p.add_argument("--quiet", action="store_true", help="Suppress verbose agent logs")
    args = p.parse_args(argv)
    session = ChatSession(verbose=not args.quiet)
    session.run()


if __name__ == "__main__":
    main()
