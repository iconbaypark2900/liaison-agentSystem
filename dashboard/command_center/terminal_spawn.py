"""Shared tmux/wezterm spawn helpers for venture queue and execution bridge."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from liaison_paths import AGENT_SYSTEM_DIR


def resolve_bridge_mode() -> str:
    raw = os.environ.get("TERMINAL_BRIDGE", "").strip().lower()
    if raw in ("copy", "tmux", "wezterm"):
        return raw
    if shutil.which("tmux"):
        return "tmux"
    return "copy"


def wrap_launch_with_complete(
    launch: str,
    agent: str,
    project_key: str,
    task_id: str,
) -> str:
    liaison_bin = AGENT_SYSTEM_DIR / "bin" / "liaison"
    bin_str = str(liaison_bin) if liaison_bin.exists() else "liaison"
    complete = (
        f"{bin_str} observe-session complete --agent {agent} --exit-code $EXIT_CODE "
        f"--project {project_key} --task-id {task_id}"
    )
    return f"{launch}; EXIT_CODE=$?; {complete}; exit $EXIT_CODE"


def _capture_tmux_pane_pid(title: str) -> int | None:
    listed = subprocess.run(
        ["tmux", "list-panes", "-a", "-F", "#{window_name}\t#{pane_pid}", "-t", title],
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode == 0 and listed.stdout.strip():
        for line in listed.stdout.strip().split("\n"):
            name, _, pid_str = line.partition("\t")
            if name == title:
                try:
                    return int(pid_str)
                except ValueError:
                    pass
    fallback = subprocess.run(
        ["tmux", "list-panes", "-F", "#{pane_pid}", "-t", title],
        capture_output=True,
        text=True,
        check=False,
    )
    if fallback.returncode == 0 and fallback.stdout.strip():
        try:
            return int(fallback.stdout.strip().split("\n")[0])
        except ValueError:
            return None
    return None


def spawn_tmux_window(title: str, effective_launch: str) -> tuple[bool, int | None, str]:
    created = subprocess.run(
        ["tmux", "new-window", "-P", "-F", "#{pane_pid}", "-n", title, "bash", "-lc", effective_launch],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode != 0:
        err = (created.stderr or created.stdout or "tmux new-window failed").strip()
        return False, None, err
    try:
        pid = int(created.stdout.strip())
        return True, pid, ""
    except ValueError:
        return True, _capture_tmux_pane_pid(title), ""


def spawn_wezterm(title: str, effective_launch: str) -> tuple[bool, int | None, str]:
    if not shutil.which("wezterm"):
        return False, None, "wezterm not found"
    proc = subprocess.Popen(
        ["wezterm", "start", "--", "bash", "-lc", effective_launch],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True, proc.pid, ""


def spawn_venture_session(
    *,
    item: dict[str, Any],
    launch: str,
    spawn_cmd: str,
) -> dict[str, Any]:
    """Spawn executor in tmux/wezterm when bridge mode allows; register session."""
    from dashboard.command_center.project_plans import resolve_project_key_and_path
    from dashboard.command_center.terminal_sessions import register_session

    mode = resolve_bridge_mode()
    agent = item.get("agent", "hermes")
    project_key = item.get("project_key", "")
    task_id = item.get("task_id", "")
    pattern_id = item.get("pattern_id", "") or ""
    title = agent

    if mode == "copy":
        return {
            "spawned": False,
            "mode": "copy",
            "message": "TERMINAL_BRIDGE=copy — use copy block or set TERMINAL_BRIDGE=tmux",
            "launch": launch,
            "spawn_cmd": spawn_cmd,
        }

    if mode == "tmux" and not shutil.which("tmux"):
        mode = "copy"
        return {
            "spawned": False,
            "mode": "copy",
            "message": "tmux not found — falling back to copy",
            "launch": launch,
        }

    effective_launch = spawn_cmd
    if not effective_launch:
        effective_launch = wrap_launch_with_complete(launch, agent, project_key, task_id)

    _, repo_path = resolve_project_key_and_path(project_key)
    pane_pid: int | None = None
    err = ""

    if mode == "tmux":
        ok, pane_pid, err = spawn_tmux_window(title, effective_launch)
        if not ok:
            return {"spawned": False, "mode": mode, "message": err, "launch": launch}
    elif mode == "wezterm":
        ok, pane_pid, err = spawn_wezterm(title, effective_launch)
        if not ok:
            return {"spawned": False, "mode": mode, "message": err, "launch": launch}
    else:
        return {"spawned": False, "mode": "copy", "message": f"unsupported bridge: {mode}"}

    session = register_session(
        agent_name=agent,
        launch=effective_launch,
        pid=pane_pid,
        pane_title=title,
        project_key=project_key,
        repo_path=repo_path or "",
        task_id=task_id,
        pattern_id=pattern_id,
    )
    return {
        "spawned": True,
        "mode": mode,
        "launch": effective_launch,
        "pane_pid": pane_pid,
        "session": session,
        "wrapped": True,
    }


def terminal_bridge_summary() -> dict[str, Any]:
    mode = resolve_bridge_mode()
    return {
        "mode": mode,
        "spawn_allowed": mode in ("tmux", "wezterm"),
        "tmux_available": shutil.which("tmux") is not None,
        "wezterm_available": shutil.which("wezterm") is not None,
    }
