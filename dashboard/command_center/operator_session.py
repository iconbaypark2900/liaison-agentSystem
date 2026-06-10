"""Repo-scoped operator session persisted for dashboard / TUI continuity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def session_path_for_repo(repo_path: str) -> Path | None:
    if not repo_path:
        return None
    return Path(repo_path).expanduser() / ".spark-flow" / "memory" / "operator_session.json"


def read_operator_session(repo_path: str) -> dict[str, Any] | None:
    path = session_path_for_repo(repo_path)
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_operator_session(
    repo_path: str,
    *,
    project_key: str,
    task_id: str | None = None,
    pattern_id: str | None = None,
) -> dict[str, Any]:
    path = session_path_for_repo(repo_path)
    if not path:
        return {}
    from datetime import datetime

    payload = {
        "project_key": project_key,
        "task_id": task_id or "",
        "pattern_id": pattern_id or "",
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
