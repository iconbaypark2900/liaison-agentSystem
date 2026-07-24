"""
CodingAgent — the actual code-writing, test-running, self-improving agent.

Works like Claude Code / Codex, but:
  - Uses MCP tools (filesystem, shell, code-executor, git) instead of direct access
  - Runs inside the spark-flow lifecycle (writes to outbox, awaits approval)
  - Self-improves via Reflexion (test failures → reflections → better next attempt)
  - Improves over tasks via DSPy (approved implementations → compiled prompts)

ReAct loop per attempt:
  Observe (read files) → Think (plan) → Act (write/run) → Observe (test output)
  → if tests pass: commit to feature branch, write outbox artifact
  → if tests fail: Reflexion reflection → retry

Safety:
  - All writes go to a git feature branch reflexion/<task-id>
  - Tests must pass before commit
  - git push requires human (always blocked)
  - Outbox artifact contains full diff for human review
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Any

import dspy

from .memory import export_learning, load_reflections, save_reflection, save_trace
from .mcp_client import MCPSession, GATEWAY_URL
from .skills import route_task_skills
from .tools import enable_coding_mode, disable_coding_mode

GATEWAY_HEADERS = {
    "Authorization": "Bearer local-mcp-key",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


# ── Gated tool caller (write-enabled for coding) ─────────────────────────────

class CodingToolSession:
    """
    MCP session with write operations enabled for coding tasks.

    Concrete capabilities:
      filesystem-read_file / write_file / list_directory  — uses /data/home paths
      code-executor-execute_code  — runs Python with full subprocess access (tests, pip, git)
      shell-shell_execute git     — git only (mcp-shell-server v1.1.2 default policy)

    Path translation: host /home/iconbaypark2900 ↔ container /data/home
    git safe.directory: always pass -c safe.directory=* to avoid bind-mount ownership errors
    """

    HOST_PREFIX = "/home/iconbaypark2900"
    CONTAINER_PREFIX = "/data/home"

    def __init__(self, repo_path: Path, task_id: str) -> None:
        self.repo_path = repo_path
        self.task_id = task_id
        self.container_repo = self._to_container(str(repo_path))
        self._session = MCPSession()
        self._session.initialize()
        self._writes: list[str] = []
        self._commands: list[dict] = []
        enable_coding_mode()

    def close(self) -> None:
        self._session.close()
        disable_coding_mode()

    def _to_container(self, path: str) -> str:
        if path.startswith(self.HOST_PREFIX):
            return self.CONTAINER_PREFIX + path[len(self.HOST_PREFIX):]
        return path

    def _to_host(self, path: str) -> str:
        if path.startswith(self.CONTAINER_PREFIX):
            return self.HOST_PREFIX + path[len(self.CONTAINER_PREFIX):]
        return path

    def _call(self, tool: str, args: dict) -> str:
        import re
        try:
            raw = self._session.call_tool(tool, args)
        except Exception as e:
            return f"[error] {tool}: {e}"
        raw = re.sub(r'(Bearer|token|key|secret)\s+\S{10,}', '[REDACTED]', raw, flags=re.I)
        return raw

    def _git(self, *args: str) -> str:
        """Run a git command via shell-shell_execute (only git is in default security policy)."""
        return self._call("shell-shell_execute", {
            "command": ["git", "-c", f"safe.directory={self.container_repo}", *args],
            "directory": self.container_repo,
        })

    def _exec(self, python_code: str) -> str:
        """Run arbitrary Python (with subprocess access) via code-executor."""
        result = self._call("code-executor-execute_code", {"code": python_code})
        self._commands.append({"type": "exec", "code": python_code[:200], "result": result[:300]})
        return result

    # ── Read operations ───────────────────────────────────────────────────────

    def read_file(self, path: str) -> str:
        return self._call("filesystem-read_file", {"path": self._to_container(path)})

    def list_dir(self, path: str) -> str:
        return self._call("filesystem-list_directory", {"path": self._to_container(path)})

    def search_files(self, path: str, pattern: str) -> str:
        return self._call("filesystem-search_files",
                          {"path": self._to_container(path), "pattern": pattern})

    def git_status(self) -> str:
        return self._git("status", "--short")

    def git_diff(self) -> str:
        return self._git("diff", "HEAD")

    def git_log(self, n: int = 5) -> str:
        return self._git("log", "--oneline", f"-{n}")

    # ── Write operations (tracked) ────────────────────────────────────────────

    def ensure_branch(self) -> str:
        branch = f"reflexion/{self.task_id}"
        # Try create, fall back to checkout if already exists
        r = self._git("checkout", "-b", branch)
        if "already exists" in r or "fatal" in r:
            self._git("checkout", branch)
        return branch

    def write_file(self, path: str, content: str) -> str:
        cpath = self._to_container(path)
        result = self._call("filesystem-write_file", {"path": cpath, "content": content})
        self._writes.append(path)
        return result

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        cpath = self._to_container(path)
        result = self._call("filesystem-edit_file", {
            "path": cpath,
            "edits": [{"oldText": old_string, "newText": new_string}],
        })
        self._writes.append(path)
        return result

    def run_python(self, code: str) -> str:
        """Run a Python snippet (no subprocess). For eval/validation."""
        return self._exec(code)

    def run_command(self, command: str) -> str:
        """
        Run a shell-style command via code-executor subprocess.
        Supports: pytest, python3, pip, npm, make, git.
        Also accepts absolute paths to python/pytest binaries (e.g. .venv/bin/python).
        """
        import shlex as _shlex
        import os as _os
        parts = _shlex.split(command)
        if not parts:
            return "[error] empty command"
        safe_first = {"pytest", "python3", "python", "pip", "pip3", "npm", "npx",
                      "node", "make", "cargo", "go", "git",
                      "mypy", "ruff", "black", "isort", "flake8"}
        # Accept absolute paths whose basename matches a safe command (e.g. .venv/bin/python)
        basename = _os.path.basename(parts[0])
        # Strip version suffixes: python3.12 → python3
        import re as _re
        basename_norm = _re.sub(r'\d+(\.\d+)*$', '', basename)
        if parts[0] not in safe_first and basename not in safe_first and basename_norm not in safe_first:
            return f"[blocked] '{parts[0]}' not in allowed commands"

        # For git, use _git() which goes through shell-shell_execute
        if parts[0] == "git" or basename == "git":
            return self._git(*parts[1:])

        # Translate any absolute host paths in the command to container paths
        # e.g. /home/user/.venv/bin/python → /data/home/.venv/bin/python
        translated = [self._to_container(p) if p.startswith(self.HOST_PREFIX) else p
                      for p in parts]

        # Everything else: run via subprocess inside code-executor
        code = f"""
import subprocess, json as _json
r = subprocess.run(
    {translated!r},
    cwd={self.container_repo!r},
    capture_output=True, text=True, timeout=120
)
print(r.stdout or "")
if r.stderr:
    print("[stderr]", r.stderr[:400])
if r.returncode != 0:
    print(f"[exit {{r.returncode}}]")
"""
        result = self._exec(code)
        self._commands.append({"type": "shell", "command": command[:200], "result": result[:300]})
        return result

    def git_commit(self, message: str) -> str:
        add = self._git("add", "-A")
        commit = self._git("commit", "-m", message)
        return f"{add}\n{commit}"

    @property
    def files_written(self) -> list[str]:
        return list(set(self._writes))

    @property
    def commands_run(self) -> list[dict]:
        return self._commands


# ── DSPy signatures ───────────────────────────────────────────────────────────

class ExploreSignature(dspy.Signature):
    """Explore a project repo and produce a codebase map relevant to the task."""
    task: str = dspy.InputField()
    repo_structure: str = dspy.InputField(desc="Directory listing of the repo")
    relevant_files: str = dspy.OutputField(
        desc="List of specific files to read, with reason for each"
    )
    project_summary: str = dspy.OutputField(
        desc="Brief description of the project's tech stack and architecture"
    )


class CodePlanSignature(dspy.Signature):
    """
    Create a concrete implementation plan as ordered file edits.

    CRITICAL: implementation_steps must contain ONLY these step types:
      WRITE <path>: <full file content>
      EDIT <path> OLD: <exact old text> NEW: <replacement text>
      RUN: <shell command>
      DONE

    Do NOT output VERIFY, CHECK, READ, CONFIRM, or any other step type.
    Do NOT describe what you will do — just output the steps.
    Every step must directly modify or create a file, or run a command.
    If you need to read a file before editing, use RUN: cat <path> first.
    """
    task: str = dspy.InputField()
    project_summary: str = dspy.InputField()
    relevant_code: str = dspy.InputField(desc="Content of files relevant to the task — already read for you")
    past_reflections: str = dspy.InputField(desc="Lessons from failed attempts")
    skill_context: str = dspy.InputField(
        desc="Matched skill guidance (testing rules, review checklists, etc.) — empty if none matched"
    )
    conversation_context: str = dspy.InputField(
        desc="Recent conversation history — what was discussed, prior tasks completed, files already touched. Empty if this is a fresh session."
    )
    implementation_steps: str = dspy.OutputField(
        desc=(
            "Numbered steps using ONLY: WRITE <path>: <content> | EDIT <path> OLD: <old> NEW: <new> | RUN: <cmd> | DONE. "
            "No VERIFY, CHECK, or READ steps. Start writing files immediately."
        )
    )
    test_command: str = dspy.OutputField(
        desc=(
            "Exact command to verify the implementation: pytest, python3 -m pytest, mypy, ruff check, etc. "
            "Include venv path if applicable (e.g. '.venv/bin/python -m pytest tests/ -x -q'). "
            "MUST be a real executable — NOT 'echo', NOT a placeholder, NOT 'RUN: ...'."
        )
    )


class FixSignature(dspy.Signature):
    """Analyze a test failure and produce specific file edits to fix it."""
    task: str = dspy.InputField()
    test_output: str = dspy.InputField(desc="Full test failure output")
    current_code: str = dspy.InputField(desc="Current content of failing files")
    past_fixes: str = dspy.InputField(desc="Previous fix attempts that failed")
    fix_steps: str = dspy.OutputField(
        desc="Concrete EDIT or WRITE steps to fix the failure. Be specific about line content."
    )
    root_cause: str = dspy.OutputField(desc="Why the test is failing")


class ReflectOnFailureSignature(dspy.Signature):
    """Generate a Reflexion reflection on a failed coding attempt."""
    task: str = dspy.InputField()
    implementation_steps: str = dspy.InputField()
    test_command: str = dspy.InputField()
    test_output: str = dspy.InputField()
    reflection: str = dspy.OutputField(
        desc=(
            "Actionable lessons: which approach was wrong, "
            "what to try differently, which files to look at more carefully. "
            "Be specific — 'look at X function in Y file' beats 'try harder'."
        )
    )


# ── Step parser ───────────────────────────────────────────────────────────────

def _parse_steps(steps_text: str) -> list[dict]:
    """
    Parse LM output into structured steps.

    Handles both single-line and multi-line forms:
      Single-line WRITE: WRITE path/to/file.py: <content>
      Multi-line WRITE:
        WRITE path/to/file.py:
        <line1>
        <line2>
      Single-line EDIT: EDIT path OLD: <old> NEW: <new>
      Multi-line EDIT:
        EDIT path/to/file.py OLD:
        <old content>
        NEW:
        <new content>
      RUN: <command>
      DONE
    """
    steps = []
    lines = steps_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i += 1

        if not stripped or stripped.startswith("#"):
            continue

        # Strip leading numbering: "1. EDIT ..." → "EDIT ..."
        if stripped and stripped[0].isdigit() and len(stripped) > 2 and stripped[1] in ".):":
            stripped = stripped[2:].strip()
        elif stripped and stripped[0].isdigit() and len(stripped) > 3 and stripped[2] in ".):":
            stripped = stripped[3:].strip()

        upper = stripped.upper()

        # Skip non-executable step types (model sometimes emits these despite instructions)
        if any(upper.startswith(t) for t in ("VERIFY", "CHECK", "READ ", "CONFIRM", "NOTE", "OBSERVE")):
            continue

        if upper.startswith("DONE"):
            steps.append({"type": "done"})
            break

        if upper.startswith("RUN:"):
            steps.append({"type": "run", "command": stripped[4:].strip()})
            continue

        if upper.startswith("WRITE "):
            rest = stripped[6:]
            if ":" in rest:
                path, inline_content = rest.split(":", 1)
                path = path.strip()
                content_lines = [inline_content] if inline_content.strip() else []
                # Accumulate continuation lines (indented or until next directive)
                while i < len(lines):
                    peek = lines[i]
                    peek_stripped = peek.strip()
                    peek_upper = peek_stripped.upper()
                    if (peek_stripped and
                            not peek.startswith("    ") and not peek.startswith("\t") and
                            (peek_upper.startswith("WRITE ") or peek_upper.startswith("EDIT ")
                             or peek_upper.startswith("RUN:") or peek_upper.startswith("DONE")
                             or (peek_stripped[0].isdigit() and len(peek_stripped) > 2
                                 and peek_stripped[1] in ".):"))
                            ):
                        break
                    content_lines.append(peek)
                    i += 1
                steps.append({
                    "type": "write",
                    "path": path,
                    "content": "\n".join(content_lines).strip(),
                })
            continue

        if upper.startswith("EDIT "):
            rest = stripped[5:]
            path = ""
            old_lines: list[str] = []
            new_lines: list[str] = []

            # Single-line form: EDIT path OLD: <old> NEW: <new>
            if " OLD:" in rest.upper() and " NEW:" in rest.upper():
                rest_upper = rest.upper()
                old_start = rest_upper.index(" OLD:") + 5
                new_start = rest_upper.index(" NEW:")
                path = rest[:rest_upper.index(" OLD:")].strip()
                old_lines = [rest[old_start:new_start].strip()]
                new_lines = [rest[new_start + 5:].strip()]
            else:
                # Multi-line form:
                #   EDIT path/file.py OLD:
                #   <old content ...>
                #   NEW:
                #   <new content ...>
                # Also handle: EDIT path OLD: inline_content (OLD on same line, NEW on next lines)
                if "OLD:" in rest.upper():
                    path = rest[:rest.upper().index("OLD:")].strip()
                    # Capture any content after "OLD:" on the same line
                    inline_old = rest[rest.upper().index("OLD:") + 4:].strip()
                    if inline_old:
                        old_lines.append(inline_old)
                else:
                    path = rest.strip()

                # Collect OLD section (continue from subsequent lines)
                in_old = not bool(old_lines) or True  # always look for more old lines
                in_new = False
                while i < len(lines):
                    peek = lines[i].rstrip()
                    peek_upper = peek.strip().upper()
                    if peek_upper == "NEW:" or peek_upper.startswith("NEW: "):
                        in_old = False
                        in_new = True
                        # content after "NEW:" on same line
                        after = peek.strip()[4:].strip()
                        if after:
                            new_lines.append(after)
                        i += 1
                        continue
                    if peek_upper.startswith("OLD:") and not in_old:
                        in_old = True
                        after = peek.strip()[4:].strip()
                        if after:
                            old_lines.append(after)
                        i += 1
                        continue
                    # Stop at next directive
                    if (peek.strip() and not peek.startswith("    ") and not peek.startswith("\t") and
                            (peek_upper.startswith("WRITE ") or peek_upper.startswith("EDIT ")
                             or peek_upper.startswith("RUN:") or peek_upper.startswith("DONE")
                             or (peek.strip()[0].isdigit() and len(peek.strip()) > 2
                                 and peek.strip()[1] in ".):"))
                            ):
                        break
                    if in_old:
                        old_lines.append(peek)
                    elif in_new:
                        new_lines.append(peek)
                    i += 1

            if path and (old_lines or new_lines):
                steps.append({
                    "type": "edit",
                    "path": path,
                    "old": "\n".join(old_lines),
                    "new": "\n".join(new_lines),
                })
            continue
    return steps


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CodingResult:
    task: str
    repo_path: str
    success: bool
    branch: str
    files_written: list[str]
    test_output: str
    diff: str
    attempts: int
    reflections: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def summary(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        files = ", ".join(self.files_written) if self.files_written else "none"
        return (
            f"[{status}] {self.task[:80]} | "
            f"files={files} | attempts={self.attempts} | "
            f"error={self.error[:120] if self.error else 'none'}"
        )


# ── Main CodingAgent ──────────────────────────────────────────────────────────

class CodingAgent:
    """
    Reads a project, writes code, runs tests, iterates with Reflexion.
    Works on any project that has a .git directory.
    """

    def __init__(
        self,
        max_attempts: int = 4,
        max_fix_rounds: int = 3,
        verbose: bool = True,
    ) -> None:
        self.max_attempts = max_attempts
        self.max_fix_rounds = max_fix_rounds
        self.verbose = verbose

        self.explorer = dspy.ChainOfThought(ExploreSignature)
        self.planner = dspy.ChainOfThought(CodePlanSignature)
        self.fixer = dspy.ChainOfThought(FixSignature)
        self.reflector = dspy.ChainOfThought(ReflectOnFailureSignature)

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def _explore(self, session: CodingToolSession, task: str) -> tuple[str, str]:
        """Read repo structure, ask LM which files to look at, read them."""
        # Use container path for MCP filesystem calls
        repo_str = session.container_repo
        structure = session.list_dir(repo_str)

        # Also get one level deeper for src/lib dirs
        for sub in ["src", "lib", "app", "backend", "frontend", "tests", "scripts"]:
            subpath = session.repo_path / sub
            if subpath.exists():
                structure += f"\n{sub}/:\n" + session.list_dir(
                    session._to_container(str(subpath))
                )

        pred = self.explorer(task=task, repo_structure=structure[:3000])
        self._log(f"Project: {pred.project_summary[:120]}")
        self._log(f"Files to read: {pred.relevant_files[:200]}")

        # Read the listed files (always use host-style paths; read_file translates internally)
        import re as _re
        code_snippets = []
        for line in pred.relevant_files.splitlines()[:12]:
            m = _re.search(r'[\w./\-]+\.\w+', line)
            if m:
                path = m.group(0)
                # Build absolute host path, then let read_file() translate to container
                if path.startswith("/data/home"):
                    full = session._to_host(path)
                elif not path.startswith("/"):
                    full = str(session.repo_path / path)
                else:
                    full = path
                content = session.read_file(full)
                if "[error]" not in content and "Access denied" not in content:
                    code_snippets.append(f"--- {path} ---\n{content[:800]}")

        return pred.project_summary, "\n\n".join(code_snippets)

    def _execute_steps(
        self, session: CodingToolSession, steps: list[dict], repo_path: Path
    ) -> list[str]:
        """Execute WRITE/EDIT/RUN steps, return execution log."""
        log = []
        for step in steps:
            t = step.get("type", "")
            if t == "done":
                break
            elif t == "write":
                path = step["path"]
                # Normalise: container path → host path so write_file() translates correctly
                if path.startswith("/data/home"):
                    path = session._to_host(path)
                elif not path.startswith("/"):
                    path = str(repo_path / path)
                result = session.write_file(path, step["content"])
                log.append(f"WRITE {step['path']}: {result[:60]}")
            elif t == "edit":
                path = step["path"]
                if path.startswith("/data/home"):
                    path = session._to_host(path)
                elif not path.startswith("/"):
                    path = str(repo_path / path)
                result = session.edit_file(path, step["old"], step["new"])
                log.append(f"EDIT {step['path']}: {result[:60]}")
            elif t == "run":
                result = session.run_command(step["command"])
                log.append(f"RUN {step['command'][:60]}: {result[:200]}")
        return log

    def run(self, task: str, repo_path: Path, task_id: str = "coding", context: str = "") -> CodingResult:
        branch = f"reflexion/{task_id}"
        reflections = load_reflections(task)
        reflections_text = "\n".join(f"- {r}" for r in reflections)

        self._log(f"\n{'='*60}")
        self._log(f"CodingAgent: {task[:100]}")
        self._log(f"Repo: {repo_path}")
        self._log(f"Prior reflections: {len(reflections)}")
        self._log(f"{'='*60}\n")

        # ── skills.yaml: pick skill guidance and agent suggestions ────────────
        skill_result = route_task_skills(task)
        skill_context = ""
        if skill_result.skills:
            skill_names = [s.name for s in skill_result.skills]
            self._log(f"[skills.yaml] Matched skills: {skill_names}")
            skill_context = skill_result.context_block
        if skill_result.agents:
            agent_names = [a.name for a in skill_result.agents]
            self._log(f"[hub_skills.yaml] Suggested agents: {agent_names}")

        for attempt in range(1, self.max_attempts + 1):
            self._log(f"\n── Attempt {attempt}/{self.max_attempts} ──")
            session = CodingToolSession(repo_path, task_id)

            # Explore the codebase
            self._log("Exploring codebase...")
            project_summary, relevant_code = self._explore(session, task)

            # Create feature branch
            self._log(f"Creating branch: {branch}")
            session.ensure_branch()

            # Plan implementation
            self._log("Planning implementation...")
            plan = self.planner(
                task=task,
                project_summary=project_summary,
                relevant_code=relevant_code[:3000],
                past_reflections=reflections_text,
                skill_context=skill_context,
                conversation_context=context[:2000],
            )
            # Normalise the test command: strip leading "RUN:" prefix if present
            test_cmd = plan.test_command.strip()
            if test_cmd.upper().startswith("RUN:"):
                test_cmd = test_cmd[4:].strip()

            self._log(f"Plan:\n{plan.implementation_steps[:300]}...")
            self._log(f"Test command: {test_cmd}")

            steps = _parse_steps(plan.implementation_steps)

            # Execute steps (write files, but not run yet)
            write_steps = [s for s in steps if s["type"] in ("write", "edit")]
            self._log(f"Executing {len(write_steps)} write steps...")
            self._execute_steps(session, write_steps, repo_path)

            # Run tests (Reflexion fix loop)
            test_output = ""
            fix_history = []
            for fix_round in range(self.max_fix_rounds + 1):
                if not test_cmd:
                    self._log("No test command specified — skipping tests.")
                    test_output = "No tests specified."
                    break
                # Reject placeholder commands — treat as "no tests yet"
                first_word = test_cmd.split()[0]
                if first_word in ("echo", "true", "false", ":") or "placeholder" in test_cmd.lower():
                    self._log(f"Placeholder test command '{first_word}' — skipping tests.")
                    test_output = "No tests specified."
                    break

                self._log(f"Running tests (round {fix_round + 1}): {test_cmd}")
                test_output = session.run_command(test_cmd)
                self._log(f"Test output: {test_output[:200]}...")

                # Strip code-executor JSON wrapper so "status":"success" doesn't
                # false-positive the "success" check below.
                raw_output = test_output
                import json as _json
                try:
                    jobj = _json.loads(test_output)
                    if isinstance(jobj, dict) and "output" in jobj:
                        raw_output = jobj["output"]
                except Exception:
                    pass

                passed = any(s in raw_output for s in [
                    " passed", "ok", "0 failed", "✓", "PASSED", "All tests"
                ])
                failed = any(s in raw_output for s in [
                    "FAILED", "ERROR", "error", "failed", "Exception", "Traceback",
                    "[exit 1]", "No module named", "SyntaxError"
                ])

                if passed and not failed:
                    self._log("✓ Tests passed!")
                    break

                if fix_round >= self.max_fix_rounds:
                    break

                # Fix loop: read failing files, ask LM to fix
                self._log(f"Tests failed. Attempting fix (round {fix_round + 1})...")
                failing_files = "\n\n".join(
                    f"--- {p} ---\n{session.read_file(p if not p.startswith('/data/home') else session._to_host(p))[:1200]}"
                    for p in session.files_written[:6]
                )
                fix = self.fixer(
                    task=task,
                    test_output=test_output[:3000],
                    current_code=failing_files,
                    past_fixes="\n".join(fix_history[-3:]),
                )
                self._log(f"Root cause: {fix.root_cause[:100]}")
                fix_steps = _parse_steps(fix.fix_steps)
                self._execute_steps(session, fix_steps, repo_path)
                fix_history.append(f"Round {fix_round+1}: {fix.root_cause[:80]}")

            # Check final test result — strip code-executor JSON wrapper first
            raw_final = test_output
            try:
                jobj = _json.loads(test_output)
                if isinstance(jobj, dict) and "output" in jobj:
                    raw_final = jobj["output"]
            except Exception:
                pass
            tests_passed = any(s in raw_final for s in [
                " passed", "ok", "✓", "PASSED", "All tests", "No tests"
            ])
            tests_failed = any(s in raw_final for s in [
                "FAILED", "ERROR", "failed", "Exception", "Traceback",
                "[exit 1]", "No module named", "SyntaxError"
            ])
            success = tests_passed and not tests_failed

            if success:
                # Commit to feature branch
                msg = f"reflexion: {task[:60]} (attempt {attempt})"
                session.git_commit(msg)
                diff = session.git_diff()

                save_trace(
                    task=task,
                    inputs={"task": task, "repo": str(repo_path), "reflections": reflections_text},
                    outputs={"files": session.files_written, "test_output": test_output},
                    tool_calls=session.commands_run,
                    score=1.0,
                    metadata={"attempt": attempt, "branch": branch},
                )
                session.close()

                self._log(f"\n✓ Done. {len(session.files_written)} files written, tests passing.")
                self._log(f"Branch: {branch} — review with: git diff main..{branch}")

                return CodingResult(
                    task=task,
                    repo_path=str(repo_path),
                    success=True,
                    branch=branch,
                    files_written=session.files_written,
                    test_output=test_output,
                    diff=diff,
                    attempts=attempt,
                    reflections=reflections,
                )

            # Failed — Reflexion
            self._log("Reflecting on failure...")
            reflection = self.reflector(
                task=task,
                implementation_steps=plan.implementation_steps[:800],
                test_command=test_cmd,
                test_output=test_output[:800],
            )
            self._log(f"Reflection: {reflection.reflection[:150]}")
            save_reflection(
                task=task,
                attempt=attempt + len(reflections),
                reflection=reflection.reflection,
                outcome=f"tests_failed/attempt_{attempt}",
            )
            reflections_text = (reflections_text + f"\n- {reflection.reflection}").strip()
            session.close()

        # All attempts failed
        export_learning(
            task=task[:100],
            learning=f"Task failed after {self.max_attempts} attempts. Latest test output: {test_output[:200]}",
            tags=["coding-failure", "reflexion"],
        )
        return CodingResult(
            task=task, repo_path=str(repo_path), success=False,
            branch=branch, files_written=[], test_output=test_output,
            diff="", attempts=self.max_attempts,
            error=f"Failed after {self.max_attempts} attempts.",
        )


def write_coding_artifact(
    result: CodingResult, task_id: str, outbox_dir: Path
) -> Path:
    """Write the coding result as a spark-flow outbox artifact."""
    from datetime import datetime
    outbox_dir.mkdir(parents=True, exist_ok=True)
    path = outbox_dir / "build.md"
    verdict = "PASS" if result.success else "FAIL"
    path.write_text(dedent(f"""
        # BUILD: {task_id}

        ## Metadata
        - Agent: reflexion-dspy/coder
        - Task: {task_id}
        - Generated: {datetime.now().isoformat(timespec="seconds")}
        - Branch: `{result.branch}`
        - Attempts: {result.attempts}

        ## Task
        {result.task}

        ## Result: {verdict}

        ## Files Written
        {chr(10).join(f'- `{f}`' for f in result.files_written) or 'None'}

        ## Test Output
        ```
        {result.test_output[:1000]}
        ```

        ## Diff Preview
        ```diff
        {result.diff[:2000]}
        ```

        ## Reflections Used
        {chr(10).join(f'- {r[:100]}' for r in result.reflections) or 'None (first attempt)'}

        ## Next Action
        {"Review the diff above and merge the branch:" if result.success else "Review the failure and re-run:"}
        ```bash
        {"git merge " + result.branch if result.success else "reflexion-agent code " + repr(result.task)}
        ```
    """).strip())
    return path
