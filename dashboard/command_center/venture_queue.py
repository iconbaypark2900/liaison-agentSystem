"""Lightweight venture queue for execution bridge."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from liaison_paths import AGENT_SYSTEM_DIR

from dashboard.command_center.workstation import can_start_engine, engine_for_agent, load_workstation_profile


def queue_file() -> Path:
    env = os.environ.get("LIAISON_VENTURE_QUEUE", "").strip()
    if env:
        return Path(env).expanduser()
    return AGENT_SYSTEM_DIR / "memory" / "venture_queue.json"


def _load() -> dict[str, Any]:
    path = queue_file()
    if not path.exists():
        return {"items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"items": []}


def _save(data: dict[str, Any]) -> None:
    path = queue_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def list_items(status: str | None = None) -> list[dict[str, Any]]:
    items = _load()["items"]
    if status:
        return [i for i in items if i.get("status") == status]
    return list(items)


def add_item(
    *,
    project_key: str,
    task_id: str,
    agent: str = "hermes",
    pattern_id: str = "",
    engine: str = "",
    priority: int = 50,
) -> dict[str, Any]:
    data = _load()
    entry = {
        "id": uuid.uuid4().hex[:10],
        "project_key": project_key,
        "task_id": task_id,
        "pattern_id": pattern_id or "",
        "agent": agent,
        "engine": engine or engine_for_agent(agent),
        "priority": priority,
        "status": "pending",
        "created_at": _now(),
    }
    data["items"].append(entry)
    _save(data)
    return entry


def update_item(item_id: str, **fields: Any) -> dict[str, Any] | None:
    data = _load()
    for item in data["items"]:
        if item.get("id") == item_id:
            item.update(fields)
            _save(data)
            return item
    return None


def cancel_item(item_id: str) -> dict[str, Any] | None:
    return update_item(item_id, status="cancelled")


def mark_running(item_id: str) -> dict[str, Any] | None:
    return update_item(item_id, status="running", started_at=_now())


def mark_done(item_id: str) -> dict[str, Any] | None:
    return update_item(item_id, status="done", finished_at=_now())


def build_queue_summary(sessions: list[dict]) -> dict[str, Any]:
    pending = list_items("pending")
    running = list_items("running")
    profile = load_workstation_profile()
    return {
        "pending_count": len(pending),
        "running_count": len(running),
        "total_items": len(_load()["items"]),
        "max_active_ventures": profile.get("defaults", {}).get("max_active_ventures", 3),
    }


def pick_next(
    sessions: list[dict],
    *,
    spawn: bool = False,
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """Return (item, hint_message, launch_hints). Optionally spawn tmux/wezterm session."""
    pending = sorted(list_items("pending"), key=lambda i: (-int(i.get("priority", 0)), i.get("created_at", "")))
    hints: dict[str, Any] = {}
    for item in pending:
        agent = item.get("agent", "hermes")
        ok, reason = can_start_engine(agent, sessions)
        if not ok:
            continue
        sf = _bridge()
        launch = ""
        try:
            agents = sf.parse_registry_map("agents.yaml", "agents")
            launch = (agents.get(agent) or {}).get("launch", "") or agent
        except Exception:
            launch = agent
        hints = {
            "launch": launch,
            "register_cmd": (
                f"liaison terminal-session register --agent-name {agent} "
                f"--project {item.get('project_key')} --task-id {item.get('task_id')} "
                f"--launch '<launch>'"
            ),
            "complete_cmd": (
                f"liaison observe-session complete --agent {agent} --exit-code 0 "
                f"--project {item.get('project_key')} --task-id {item.get('task_id')}"
            ),
            "spawn_cmd": (
                f"bash -lc '{launch}; EXIT_CODE=$?; "
                f"liaison observe-session complete --agent {agent} --exit-code $EXIT_CODE "
                f"--project {item.get('project_key')} --task-id {item.get('task_id')}'; "
                f"exit $EXIT_CODE'"
            ),
        }
        copy_block = "\n".join(
            [
                f"# Venture queue next · {item.get('project_key')}/{item.get('task_id')}",
                f"liaison venture-queue mark-running {item.get('id')}",
                hints["spawn_cmd"],
                hints["complete_cmd"],
            ]
        )
        hints["copy_block"] = copy_block
        if spawn:
            from dashboard.command_center.terminal_spawn import spawn_venture_session

            mark_running(item["id"])
            item = update_item(item["id"], status="running") or item
            hints["spawn_result"] = spawn_venture_session(
                item=item,
                launch=launch,
                spawn_cmd=hints["spawn_cmd"],
            )
        return item, "", hints
    if pending:
        ok0, reason0 = can_start_engine(pending[0].get("agent", "hermes"), sessions)
        return None, reason0 or "No engine slot available", {}
    return None, "Queue empty", {}


def _bridge():
    from dashboard.command_center.data import _bridge as data_bridge

    return data_bridge()
