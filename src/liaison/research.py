"""ML-Intern sandbox execution module for Liaison v0.2.0.

Implements Phase 9: sandbox-only ML-Intern execution with no publishing
or private-data upload.

Safety enforcement:
- ml_intern executor must be enabled and available
- sandbox_only must be true in research_workers.yaml
- forbidden actions are checked before execution
- outputs go to ml_research/outbox or task outbox only
- all runs logged to logs/ml_intern_runs.jsonl
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from liaison.executors import run_executor


RESEARCH_WORKERS_PATH = Path("config/research_workers.yaml")
RESEARCH_LOG_PATH = Path("logs/ml_intern_runs.jsonl")


class ResearchExecutionError(RuntimeError):
    """Raised when a research execution gate fails."""


@dataclass(frozen=True)
class ResearchRunResult:
    worker_name: str
    status: str  # success, blocked, failed, sandbox_violation
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    output_path: str | None
    log_path: str
    sandbox_enforced: bool
    forbidden_checked: list[str]
    reason: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_research_workers(root: Path = Path(".")) -> dict[str, Any]:
    return _safe_load_yaml(root / RESEARCH_WORKERS_PATH)


def resolve_research_worker(worker_name: str, root: Path = Path(".")) -> dict[str, Any]:
    workers = load_research_workers(root)
    config = workers.get("research_workers", {}).get(worker_name)
    if config is None:
        return {}
    return dict(config)


def check_sandbox_safety(
    worker_name: str, root: Path = Path(".")
) -> tuple[bool, str, list[str]]:
    """Verify all sandbox safety constraints for a research worker."""
    config = resolve_research_worker(worker_name, root)
    if not config:
        return False, f"Unknown research worker: {worker_name}", []

    if not config.get("sandbox_only", False):
        return False, f"Worker '{worker_name}' does not enforce sandbox_only", []

    forbidden = config.get("forbidden", [])
    checked = list(forbidden)

    env_publish = os.environ.get("ML_INTERN_ALLOW_PUBLISH", "").lower()
    if "publish_without_approval" in forbidden and env_publish in ("1", "true", "yes"):
        return False, "publish_without_approval is forbidden but ML_INTERN_ALLOW_PUBLISH is set", checked

    env_upload = os.environ.get("ML_INTERN_ALLOW_PRIVATE_UPLOAD", "").lower()
    if "upload_private_data" in forbidden and env_upload in ("1", "true", "yes"):
        return False, "upload_private_data is forbidden but ML_INTERN_ALLOW_PRIVATE_UPLOAD is set", checked

    return True, "Sandbox safety checks passed", checked


def check_executor_available(worker_name: str, root: Path = Path(".")) -> tuple[bool, str]:
    """Check if the ml_intern executor is enabled and available."""
    config_path = root / "config" / "executors.yaml"
    if not config_path.exists():
        return False, "executors.yaml not found"
    config = _safe_load_yaml(config_path)
    executors = config.get("executors", {})
    ml_config = executors.get("ml_intern")
    if ml_config is None:
        return False, "ml_intern executor not configured"
    if not ml_config.get("enabled", False):
        return False, "ml_intern executor is disabled in config"
    import shutil
    command = ml_config.get("command", "ml-intern")
    if not shutil.which(command):
        return False, f"ml_intern binary not found in PATH: {command}"
    return True, "Executor available"


def run_research_worker(
    worker_name: str,
    args: list[str] | None = None,
    *,
    root: Path = Path("."),
    outbox_dir: Path | None = None,
    timeout: int = 300,
) -> ResearchRunResult:
    """Execute a research worker in sandbox mode.

    Gates (all must pass):
    1. Worker must be configured in research_workers.yaml
    2. sandbox_only must be true
    3. Forbidden actions must not be triggered by environment
    4. ml_intern executor must be enabled and available

    If any gate fails, returns ResearchRunResult with status='blocked'.
    """
    log_path = root / RESEARCH_LOG_PATH

    sandbox_ok, sandbox_reason, forbidden_checked = check_sandbox_safety(worker_name, root)
    if not sandbox_ok:
        result = ResearchRunResult(
            worker_name=worker_name,
            status="blocked",
            exit_code=1,
            stdout="",
            stderr=sandbox_reason,
            duration_sec=0.0,
            output_path=None,
            log_path=str(log_path),
            sandbox_enforced=True,
            forbidden_checked=forbidden_checked,
            reason=sandbox_reason,
        )
        _write_log(log_path, result)
        return result

    executor_ok, executor_reason = check_executor_available(worker_name, root)
    if not executor_ok:
        result = ResearchRunResult(
            worker_name=worker_name,
            status="blocked",
            exit_code=1,
            stdout="",
            stderr=executor_reason,
            duration_sec=0.0,
            output_path=None,
            log_path=str(log_path),
            sandbox_enforced=True,
            forbidden_checked=forbidden_checked,
            reason=executor_reason,
        )
        _write_log(log_path, result)
        return result

    try:
        exec_result = run_executor("ml_intern", args or [], root=root, timeout=timeout)
    except RuntimeError as exc:
        result = ResearchRunResult(
            worker_name=worker_name,
            status="failed",
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            duration_sec=0.0,
            output_path=None,
            log_path=str(log_path),
            sandbox_enforced=True,
            forbidden_checked=forbidden_checked,
            reason=str(exc),
        )
        _write_log(log_path, result)
        return result

    out_dir = outbox_dir or (root / "ml_research" / "outbox")
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"research.{worker_name}.md"
    output_content = (
        f"# Research Worker Output: {worker_name}\n\n"
        f"## Exit Code\n{exec_result.exit_code}\n\n"
        f"## Stdout\n```\n{exec_result.stdout}\n```\n\n"
        f"## Stderr\n```\n{exec_result.stderr}\n```\n\n"
        f"## Duration\n{exec_result.duration_sec}s\n\n"
        f"## Sandbox\n- sandbox_enforced: true\n- forbidden_checked: {forbidden_checked}\n"
    )
    output_path.write_text(output_content, encoding="utf-8")

    status = "success" if exec_result.exit_code == 0 else "failed"
    result = ResearchRunResult(
        worker_name=worker_name,
        status=status,
        exit_code=exec_result.exit_code,
        stdout=exec_result.stdout[:4000],
        stderr=exec_result.stderr[:4000],
        duration_sec=exec_result.duration_sec,
        output_path=str(output_path),
        log_path=str(log_path),
        sandbox_enforced=True,
        forbidden_checked=forbidden_checked,
        reason="Research worker completed in sandbox mode",
    )
    _write_log(log_path, result)
    return result


def _write_log(log_path: Path, result: ResearchRunResult) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        **result.to_json(),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def cmd_research_run(args) -> int:
    """Handle `liaison research run <worker> [--real]`."""
    root = Path(getattr(args, "root", "."))
    if getattr(args, "stub", False):
        result = ResearchRunResult(
            worker_name=args.worker_name,
            status="stub",
            exit_code=0,
            stdout="Stub output — no real execution.",
            stderr="",
            duration_sec=0.0,
            output_path=None,
            log_path=str(root / RESEARCH_LOG_PATH),
            sandbox_enforced=False,
            forbidden_checked=[],
            reason="Stub mode requested",
        )
        if getattr(args, "json", False):
            print(json.dumps(result.to_json(), indent=2, sort_keys=True))
        else:
            print(f"Worker:  {result.worker_name}")
            print(f"Status:  {result.status}")
            print(f"Reason:  {result.reason}")
        return 0

    result = run_research_worker(args.worker_name, root=root, timeout=getattr(args, "timeout", 300))
    if getattr(args, "json", False):
        print(json.dumps(result.to_json(), indent=2, sort_keys=True))
    else:
        print(f"Worker:    {result.worker_name}")
        print(f"Status:    {result.status}")
        print(f"Exit code: {result.exit_code}")
        print(f"Duration:  {result.duration_sec}s")
        print(f"Sandbox:   {result.sandbox_enforced}")
        print(f"Output:    {result.output_path or 'N/A'}")
        print(f"Reason:    {result.reason}")
    return 0 if result.status == "success" else 1


def cmd_research_validate(args) -> int:
    """Handle `liaison research validate <worker>`."""
    root = Path(getattr(args, "root", "."))
    sandbox_ok, sandbox_reason, forbidden = check_sandbox_safety(args.worker_name, root)
    executor_ok, executor_reason = check_executor_available(args.worker_name, root)
    payload = {
        "worker": args.worker_name,
        "sandbox_ok": sandbox_ok,
        "sandbox_reason": sandbox_reason,
        "executor_ok": executor_ok,
        "executor_reason": executor_reason,
        "forbidden_checked": forbidden,
        "can_run": sandbox_ok and executor_ok,
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Worker:   {args.worker_name}")
        print(f"Sandbox:  {sandbox_ok} ({sandbox_reason})")
        print(f"Executor: {executor_ok} ({executor_reason})")
        print(f"Can run:  {payload['can_run']}")
    return 0 if payload["can_run"] else 1


def register_research_subparser(subparsers) -> None:
    """Register `liaison research ...` commands."""
    parser = subparsers.add_parser(
        "research",
        help="ML-Intern sandbox execution (Phase 9).",
    )
    research_subparsers = parser.add_subparsers(dest="research_command", required=True)

    validate_parser = research_subparsers.add_parser(
        "validate",
        help="Validate sandbox safety and executor availability.",
    )
    validate_parser.add_argument("worker_name", help="Research worker name (e.g. ml_intern).")
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.set_defaults(func=cmd_research_validate)

    run_parser = research_subparsers.add_parser(
        "run",
        help="Run a research worker in sandbox mode.",
    )
    run_parser.add_argument("worker_name", help="Research worker name.")
    run_parser.add_argument("--stub", action="store_true", help="Write stub output without execution.")
    run_parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds.")
    run_parser.add_argument("--json", action="store_true")
    run_parser.set_defaults(func=cmd_research_run)


__all__: Sequence[str] = (
    "ResearchExecutionError",
    "ResearchRunResult",
    "check_executor_available",
    "check_sandbox_safety",
    "cmd_research_run",
    "cmd_research_validate",
    "load_research_workers",
    "register_research_subparser",
    "resolve_research_worker",
    "run_research_worker",
)
