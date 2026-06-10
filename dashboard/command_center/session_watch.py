"""Lightweight log tail watcher — completes observe-session on exit or log stability."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def watch_session(
    *,
    log_file: Path,
    agent: str,
    project_key: str = "",
    task_id: str = "",
    marker_file: Path | None = None,
    pid: int | None = None,
    stable_seconds: float = 8.0,
    poll_interval: float = 2.0,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Tail log file; on marker, process exit, or stable log — run observe-session complete."""
    from dashboard.command_center.terminal_sessions import complete_session

    log_file = log_file.expanduser()
    tail_proc: subprocess.Popen | None = None
    if log_file.parent.exists():
        try:
            tail_proc = subprocess.Popen(
                ["tail", "-F", str(log_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            tail_proc = None

    start = time.time()
    exit_code = 0
    reason = "unknown"
    last_size = -1
    last_mtime = 0.0
    stable_since: float | None = None

    try:
        while True:
            if timeout and (time.time() - start) > timeout:
                exit_code = 124
                reason = "timeout"
                break

            if marker_file and marker_file.expanduser().exists():
                marker_text = marker_file.expanduser().read_text(errors="replace").strip()
                if marker_text.isdigit():
                    exit_code = int(marker_text)
                reason = "marker_file"
                break

            if pid and not _pid_alive(pid):
                exit_code = 1
                reason = "pid_exit"
                break

            if log_file.exists():
                stat = log_file.stat()
                if stat.st_size == last_size and stat.st_mtime == last_mtime:
                    if stable_since is None:
                        stable_since = time.time()
                    elif (time.time() - stable_since) >= stable_seconds:
                        exit_code = 0
                        reason = "log_stable"
                        break
                else:
                    last_size = stat.st_size
                    last_mtime = stat.st_mtime
                    stable_since = None

            time.sleep(poll_interval)
    finally:
        if tail_proc and tail_proc.poll() is None:
            tail_proc.send_signal(signal.SIGTERM)
            try:
                tail_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                tail_proc.kill()

    result = complete_session(
        agent_name=agent,
        exit_code=exit_code,
        project_key=project_key,
        task_id=task_id,
        log_file=str(log_file) if log_file.exists() else None,
    )
    return {
        "watch_reason": reason,
        "exit_code": exit_code,
        "log_file": str(log_file),
        **result,
    }
