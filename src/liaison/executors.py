"""Executor adapters for Liaison v0.2.0.

This module provides stub adapters for shell, opencode, codex, and claude_code executors.
All executors are disabled by default and do not execute any tasks.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class ExecutorResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    executor_id: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


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
    execution_allowed = bool(config.get("allow_execution", False))

    if not enabled:
        reason = "Executor disabled in config"
    elif not available:
        reason = f"Binary not found in PATH: {command[0] if command else 'unknown'}"
    elif not execution_allowed:
        reason = "Execution not allowed in config (allow_execution: false)"
    else:
        reason = "Ready"

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


def run_executor(
    executor_id: str,
    args: list[str] | None = None,
    *,
    root: Path = Path("."),
    timeout: int | None = None,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> ExecutorResult:
    """Run a command via the specified executor.

    Args:
        executor_id: Executor identifier (e.g. 'shell', 'opencode').
        args: Arguments to pass to the executor binary.
        root: Project root for config lookup.
        timeout: Maximum execution time in seconds (default: no timeout).
        cwd: Working directory for the subprocess.
        env: Environment variables (merged with current env).

    Returns:
        ExecutorResult with exit code, output streams, and duration.

    Raises:
        RuntimeError: If executor is not available or execution not allowed.
    """
    config = get_executor_config(executor_id, root)
    if config is None:
        raise RuntimeError(f"Executor '{executor_id}' not configured")

    status = build_executor_status(executor_id, root)
    if not status.enabled:
        raise RuntimeError(f"Executor '{executor_id}' is disabled")
    if not status.available:
        raise RuntimeError(
            f"Executor '{executor_id}' binary not found: "
            f"{' '.join(status.command) if status.command else 'unknown'}"
        )
    if not status.execution_allowed:
        raise RuntimeError(f"Executor '{executor_id}' execution not allowed by config")

    cmd = list(status.command)
    if args:
        cmd.extend(args)

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            env=run_env,
            timeout=timeout,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = -1
        stdout = exc.stdout.decode("utf-8") if exc.stdout else ""
        stderr = (exc.stderr.decode("utf-8") if exc.stderr else "") + f"\nTIMEOUT after {timeout}s"
    except FileNotFoundError:
        raise RuntimeError(f"Executor binary not found: {cmd[0]}")
    except OSError as exc:
        raise RuntimeError(f"Failed to run executor '{executor_id}': {exc}") from exc
    finally:
        duration = time.monotonic() - started

    return ExecutorResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_sec=round(duration, 3),
        executor_id=executor_id,
    )


def cmd_executor_run(args) -> int:
    """Handle `liaison executor run <executor_id> [-- <args>...]`."""
    try:
        result = run_executor(
            args.executor_id,
            args.command_args,
            timeout=args.timeout,
            cwd=args.cwd,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_json(), indent=2, sort_keys=True))
    else:
        print(f"Executor:  {result.executor_id}")
        print(f"Exit code: {result.exit_code}")
        print(f"Duration:  {result.duration_sec}s")
        if result.stdout:
            print("--- stdout ---")
            print(result.stdout.rstrip())
        if result.stderr:
            print("--- stderr ---")
            print(result.stderr.rstrip())
        if not result.stdout and not result.stderr:
            print("(no output)")

    return 0


def register_executor_subparser(subparsers) -> None:
    """Register `liaison executor ...` commands."""
    parser = subparsers.add_parser(
        "executor",
        help="Manage executor adapters (list, ping, run).",
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

    # Run command
    run_parser = executor_subparsers.add_parser(
        "run",
        help="Run a command via an executor.",
    )
    run_parser.add_argument(
        "executor_id",
        choices=["shell", "opencode", "codex", "claude_code", "ml_intern"],
        help="Executor to run.",
    )
    run_parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the executor (prefix with -- to disambiguate).",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Maximum execution time in seconds.",
    )
    run_parser.add_argument(
        "--cwd",
        type=str,
        default=None,
        help="Working directory for the subprocess.",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    run_parser.set_defaults(func=cmd_executor_run)