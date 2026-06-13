"""Executor adapters for Liaison v0.2.0.

This module provides stub adapters for shell, opencode, codex, and claude_code executors.
All executors are disabled by default and do not execute any tasks.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class ExecutorStatus:
    """Normalized executor status for ping/list operations."""

    executor_id: str
    enabled: bool
    available: bool
    execution_allowed: bool
    command: list[str]
    reason: str
    capabilities: list[str]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


EXECUTOR_CONFIG_PATH = Path("config/executors.yaml")


def load_executor_config(root: Path = Path(".")) -> dict[str, Any]:
    """Load executor configuration from YAML."""
    config_path = root / EXECUTOR_CONFIG_PATH
    if not config_path.exists():
        return {"version": "0.2.0", "executors": {}}
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid executor config: {exc}") from exc
    if loaded is None:
        loaded = {}
    return loaded if isinstance(loaded, dict) else {}


def get_executor_config(executor_id: str, root: Path = Path(".")) -> dict[str, Any] | None:
    """Get configuration for a specific executor."""
    config = load_executor_config(root)
    executors = config.get("executors", {})
    return executors.get(executor_id)


def is_executor_available(executor_id: str, config: Mapping[str, Any]) -> bool:
    """Check if executor binary is available in PATH."""
    command = config.get("command")
    if not command:
        return False
    return shutil.which(command) is not None


def get_executor_capabilities(executor_id: str, config: Mapping[str, Any]) -> list[str]:
    """Get executor capabilities based on type."""
    exec_type = config.get("type", executor_id)
    base_caps = ["dry_run", "placeholder"]
    if exec_type == "shell":
        return base_caps + ["validation_commands", "diagnostics"]
    if exec_type == "opencode":
        return base_caps + ["code_generation", "refactoring", "litellm_route"]
    if exec_type == "codex":
        return base_caps + ["code_generation", "refactoring", "debugging", "litellm_route"]
    if exec_type == "claude_code":
        return base_caps + ["code_review", "repo_aware", "refactoring"]
    if exec_type == "external_supervisor":
        return base_caps + ["research_supervision"]
    return base_caps


def build_executor_status(executor_id: str, root: Path = Path(".")) -> ExecutorStatus:
    """Build normalized executor status for ping."""
    config = get_executor_config(executor_id, root)
    if config is None:
        return ExecutorStatus(
            executor_id=executor_id,
            enabled=False,
            available=False,
            execution_allowed=False,
            command=[],
            reason=f"Executor '{executor_id}' not configured",
            capabilities=[],
        )

    enabled = bool(config.get("enabled", False))
    command = [config.get("command", "")] if config.get("command") else []
    available = is_executor_available(executor_id, config)
    execution_allowed = False  # Always false in v0.2.0 placeholder mode

    if not enabled:
        reason = "Executor disabled in config"
    elif not available:
        reason = f"Binary not found in PATH: {command[0] if command else 'unknown'}"
    else:
        reason = "v0.2.0 placeholder mode: execution disabled by default"

    capabilities = get_executor_capabilities(executor_id, config)

    return ExecutorStatus(
        executor_id=executor_id,
        enabled=enabled,
        available=available,
        execution_allowed=execution_allowed,
        command=command,
        reason=reason,
        capabilities=capabilities,
    )


def list_executors(root: Path = Path(".")) -> list[ExecutorStatus]:
    """List all configured executors with their status."""
    config = load_executor_config(root)
    executors = config.get("executors", {})
    return [build_executor_status(eid, root) for eid in sorted(executors.keys())]


def format_executor_status_json(status: ExecutorStatus) -> str:
    """Format executor status as JSON."""
    return json.dumps(status.to_json(), indent=2, sort_keys=True)


def format_executor_status_human(status: ExecutorStatus) -> str:
    """Format executor status for human-readable output."""
    lines = [
        f"Executor: {status.executor_id}",
        f"  Enabled: {status.enabled}",
        f"  Available: {status.available}",
        f"  Execution allowed: {status.execution_allowed}",
        f"  Command: {' '.join(status.command) if status.command else 'N/A'}",
        f"  Reason: {status.reason}",
        f"  Capabilities: {', '.join(status.capabilities) if status.capabilities else 'none'}",
    ]
    return "\n".join(lines)


# CLI command handlers

def cmd_executor_list(args) -> int:
    """Handle `liaison executor list`."""
    statuses = list_executors()

    if args.json:
        payload = {
            "executors": [s.to_json() for s in statuses],
            "count": len(statuses),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("Configured executors:")
    for status in statuses:
        print(f"  {status.executor_id}")
        print(f"    Enabled: {status.enabled}")
        print(f"    Available: {status.available}")
        print(f"    Execution allowed: {status.execution_allowed}")
        print(f"    Command: {' '.join(status.command) if status.command else 'N/A'}")
        print(f"    Reason: {status.reason}")
        print(f"    Capabilities: {', '.join(status.capabilities) if status.capabilities else 'none'}")
        print()
    return 0


def cmd_executor_ping(args) -> int:
    """Handle `liaison executor ping <executor_id>`."""
    status = build_executor_status(args.executor_id)

    if args.json:
        print(format_executor_status_json(status))
        return 0

    print(format_executor_status_human(status))
    return 0


def register_executor_subparser(subparsers) -> None:
    """Register `liaison executor ...` commands."""
    parser = subparsers.add_parser(
        "executor",
        help="Manage executor adapters (list, ping).",
    )
    executor_subparsers = parser.add_subparsers(
        dest="executor_command",
        required=True,
    )

    # List command
    list_parser = executor_subparsers.add_parser(
        "list",
        help="List all configured executors.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    list_parser.set_defaults(func=cmd_executor_list)

    # Ping command
    ping_parser = executor_subparsers.add_parser(
        "ping",
        help="Check executor availability and status.",
    )
    ping_parser.add_argument(
        "executor_id",
        choices=["shell", "opencode", "codex", "claude_code", "ml_intern"],
        help="Executor to ping.",
    )
    ping_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    ping_parser.set_defaults(func=cmd_executor_ping)