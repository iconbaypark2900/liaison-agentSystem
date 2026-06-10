"""Lightweight registry of terminal agent sessions (tmux/wezterm spawns)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dashboard.command_center.data import AGENT_SYSTEM_DIR
from dashboard.command_center.workstation import engine_for_agent


def sessions_file() -> Path:
    env = os.environ.get("LIAISON_TERMINAL_SESSIONS", "").strip()
    if env:
        return Path(env).expanduser()
    return AGENT_SYSTEM_DIR / "memory" / "terminal_sessions.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> dict[str, Any]:
    path = sessions_file()
    if not path.exists():
        return {"sessions": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("sessions"), list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"sessions": []}


def _save(data: dict[str, Any]) -> None:
    path = sessions_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def prune_dead_sessions() -> list[dict]:
    data = _load()
    alive = []
    for s in data["sessions"]:
        if s.get("status") == "ended":
            alive.append(s)
            continue
        if _pid_alive(s.get("pid")):
            s["alive"] = True
            alive.append(s)
        elif s.get("pid") is None:
            s["alive"] = s.get("status") != "ended"
            alive.append(s)
    data["sessions"] = alive
    _save(data)
    return alive


def register_session(
    *,
    agent_name: str,
    launch: str,
    pid: int | None = None,
    pane_title: str = "",
    project_key: str = "",
    repo_path: str = "",
    task_id: str = "",
    pattern_id: str = "",
) -> dict:
    data = _load()
    engine = engine_for_agent(agent_name)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "agent_name": agent_name,
        "launch": launch,
        "pid": pid,
        "started_at": _now(),
        "pane_title": pane_title or agent_name,
        "alive": _pid_alive(pid) if pid else True,
        "project_key": project_key or "",
        "repo_path": repo_path or "",
        "task_id": task_id or "",
        "pattern_id": pattern_id or "",
        "engine": engine,
        "status": "running",
        "exit_code": None,
        "outcome": None,
        "ended_at": None,
        "log_excerpt": "",
    }
    data["sessions"] = [
        s for s in data["sessions"]
        if not (s.get("agent_name") == agent_name and s.get("status") == "running")
    ]
    data["sessions"].append(entry)
    _save(data)
    if repo_path and project_key and task_id:
        from dashboard.command_center.execution_bridge import bind_session_to_operator_session

        bind_session_to_operator_session(repo_path, project_key, task_id, pattern_id)
    return entry


def find_session(
    *,
    session_id: str | None = None,
    agent_name: str | None = None,
    task_id: str | None = None,
) -> dict | None:
    for s in prune_dead_sessions():
        if session_id and s.get("id") == session_id:
            return s
        if agent_name and s.get("agent_name") == agent_name and s.get("status") == "running":
            return s
        if task_id and s.get("task_id") == task_id and s.get("status") == "running":
            return s
    return None


def complete_session(
    *,
    session_id: str | None = None,
    agent_name: str | None = None,
    exit_code: int | None = None,
    outcome: str | None = None,
    log_excerpt: str = "",
    log_file: str | Path | None = None,
    log_lines: int = 40,
    project_key: str = "",
    task_id: str = "",
    attach_file: str | Path | None = None,
    attach_text: str | None = None,
    attach_title: str = "",
) -> dict[str, Any]:
    from dashboard.command_center.execution_bridge import (
        attach_report_to_outbox,
        infer_outcome,
        read_log_tail,
        record_executor_outcome,
        truncate_excerpt,
    )

    sess = find_session(session_id=session_id, agent_name=agent_name, task_id=task_id)
    if not sess and project_key and task_id:
        sess = {
            "agent_name": agent_name or "unknown",
            "project_key": project_key,
            "task_id": task_id,
            "repo_path": "",
            "pattern_id": "",
        }
    if not sess:
        raise ValueError("No matching terminal session; pass --session-id, --agent-name, or --project + --task-id")

    pk = project_key or sess.get("project_key") or ""
    tid = task_id or sess.get("task_id") or ""
    repo = sess.get("repo_path") or ""
    if pk and not repo:
        from dashboard.command_center.project_plans import resolve_project_key_and_path

        _, repo = resolve_project_key_and_path(pk)

    resolved_outcome = infer_outcome(exit_code, outcome)
    excerpt = log_excerpt or sess.get("log_excerpt") or ""
    if not excerpt.strip() and log_file:
        excerpt = read_log_tail(log_file, log_lines)
    excerpt = truncate_excerpt(excerpt)

    bridge_result = {}
    attach_result = {}
    if repo and tid:
        bridge_result = record_executor_outcome(
            repo,
            tid,
            agent=sess.get("agent_name") or agent_name or "unknown",
            outcome=resolved_outcome,
            exit_code=exit_code,
            excerpt=excerpt,
            pattern_id=sess.get("pattern_id") or "",
            project_key=pk,
        )
        if attach_file or attach_text:
            attach_result = attach_report_to_outbox(
                repo,
                tid,
                agent=sess.get("agent_name") or agent_name or "unknown",
                file_path=attach_file,
                text=attach_text,
                title=attach_title,
            )

    data = _load()
    for s in data["sessions"]:
        if s.get("id") == sess.get("id") or (
            sess.get("id") is None
            and s.get("agent_name") == (agent_name or sess.get("agent_name"))
            and s.get("status") == "running"
        ):
            s["status"] = "ended"
            s["exit_code"] = exit_code
            s["outcome"] = resolved_outcome
            s["ended_at"] = _now()
            s["log_excerpt"] = excerpt[:500]
            s["alive"] = False
            sess = s
            break
    _save(data)

    return {
        "session": sess,
        "bridge": bridge_result,
        "attach": attach_result,
        "outcome": resolved_outcome,
    }


def list_sessions() -> list[dict]:
    sessions = prune_dead_sessions()
    for s in sessions:
        if s.get("status") != "ended":
            s["alive"] = _pid_alive(s.get("pid")) if s.get("pid") else True
    return sessions


def sessions_for_task(task_id: str) -> list[dict]:
    return [s for s in list_sessions() if s.get("task_id") == task_id and s.get("status") == "running"]
