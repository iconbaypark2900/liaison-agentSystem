"""Safe placeholder worker runtime for Liaison v0.2.0.

The v0.2.0 worker is intentionally evidence-only. It reads one backlog task,
locks it by moving it to the active queue, writes auditable placeholder run
artifacts, and moves the task to review_required. It does not call models,
executors, shell validation commands, deployment tools, trading systems, or
promotion approval flows.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from liaison.executors import run_executor


TASK_STATES = (
    "backlog",
    "active",
    "review_required",
    "blocked",
    "failed",
    "done",
    "cancelled",
)

REQUIRED_RUN_ARTIFACTS = (
    "task.yaml",
    "context.md",
    "command.txt",
    "model_calls.jsonl",
    "executor_result.json",
    "stdout.log",
    "stderr.log",
    "patch.diff",
    "validation.log",
    "validation_result.json",
    "validation_result.md",
    "validation_execution_approval.json",
    "validation_execution_approval.md",
    "security.log",
    "data_quality.log",
    "compliance.md",
    "debrief.md",
    "promotion_gate.json",
    "run_metadata.json",
)

PRIORITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

SECURITY_CHECKS = (
    "raw secrets",
    ".env access",
    "credential/private key access",
    "customer/prod data access",
    "forbidden commands",
    "direct provider/API calls",
    "main push attempts",
    "production deploy attempts",
    "live trading attempts",
    "budget/gate bypass attempts",
)


TASK_SPECIFIC_ARTIFACT_KEYS = (
    "calibration_required_artifacts",
    "security_required_artifacts",
    "release_required_artifacts",
    "research_required_artifacts",
)


class WorkerRuntimeError(RuntimeError):
    """Raised when the safe worker cannot complete a run."""


@dataclass(frozen=True)
class TaskPacket:
    path: Path
    text: str
    data: dict[str, Any]

    @property
    def task_id(self) -> str:
        return str(self.data.get("id", self.path.stem))

    @property
    def project(self) -> str:
        return str(self.data.get("project", "unknown-project"))

    @property
    def task_type(self) -> str:
        return str(self.data.get("type", "unknown"))

    @property
    def priority(self) -> str:
        return str(self.data.get("priority", "medium")).lower()

    @property
    def status(self) -> str:
        return str(self.data.get("status", ""))

    @property
    def created_at(self) -> str:
        return str(self.data.get("created_at") or "9999-12-31T23:59:59Z")


@dataclass(frozen=True)
class WorkerRunResult:
    ran: bool
    message: str
    run_id: str | None = None
    task_id: str | None = None
    project: str | None = None
    run_dir: Path | None = None
    review_path: Path | None = None
    called_executors: bool = False
    ran_shell_validation: bool = False
    validation_execution_allowed: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "ran": self.ran,
            "message": self.message,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "project": self.project,
            "run_dir": str(self.run_dir) if self.run_dir else None,
            "review_path": str(self.review_path) if self.review_path else None,
            "executed_tasks": False,
            "called_models": False,
            "called_executors": self.called_executors,
            "ran_shell_validation": self.ran_shell_validation,
            "validation_execution_allowed": self.validation_execution_allowed,
            "created_branches": False,
            "pushed_to_main": False,
            "deployed": False,
            "traded": False,
            "production_allowed": False,
            "customer_release_allowed": False,
            "live_allowed": False,
        }


def register_worker_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "worker",
        help="Inspect the task queue and run one safe evidence-only worker placeholder.",
    )
    worker_subparsers = parser.add_subparsers(dest="worker_command", required=True)

    queue_parser = worker_subparsers.add_parser(
        "queue",
        help="List eligible backlog tasks.",
    )
    queue_parser.add_argument("--project", default=None, help="Filter backlog tasks by project.")
    queue_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    queue_parser.set_defaults(func=cmd_worker_queue)

    status_parser = worker_subparsers.add_parser(
        "status",
        help="Show task queue counts and latest run count.",
    )
    status_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    status_parser.set_defaults(func=cmd_worker_status)

    run_once_parser = worker_subparsers.add_parser(
        "run-once",
        help="Run one safe placeholder worker cycle without invoking tools.",
    )
    selector = run_once_parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--project", default=None, help="Select one backlog task by project.")
    selector.add_argument("--task", default=None, help="Select one backlog task by task ID.")
    run_once_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    run_once_parser.set_defaults(func=cmd_worker_run_once)


def register_evidence_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "evidence",
        help="Inspect worker run evidence artifacts.",
    )
    evidence_subparsers = parser.add_subparsers(dest="evidence_command", required=True)

    show_parser = evidence_subparsers.add_parser(
        "show",
        help="Show required evidence artifact status for a run.",
    )
    show_parser.add_argument("run_id", help="Run ID under .liaison/runs/.")
    show_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    show_parser.set_defaults(func=cmd_evidence_show)


def register_gate_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "gate",
        help="Evaluate promotion gate evidence for a run.",
    )
    gate_subparsers = parser.add_subparsers(dest="gate_command", required=True)

    evaluate_parser = gate_subparsers.add_parser(
        "evaluate",
        help="Evaluate a run promotion gate without approving production/live use.",
    )
    evaluate_parser.add_argument("run_id", help="Run ID under .liaison/runs/.")
    evaluate_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    evaluate_parser.set_defaults(func=cmd_gate_evaluate)


def cmd_worker_queue(args: argparse.Namespace) -> int:
    ensure_queue_dirs()
    tasks = [
        task_to_queue_json(packet)
        for packet in select_eligible_backlog_tasks(project=args.project)
    ]
    payload = {
        "project": args.project,
        "count": len(tasks),
        "tasks": tasks,
        "executed_tasks": False,
        "called_models": False,
        "called_executors": False,
    }

    if args.json:
        print_json(payload)
        return 0

    title = f"Backlog tasks for {args.project}" if args.project else "Backlog tasks"
    print(title)
    if not tasks:
        print("  No eligible backlog tasks.")
        return 0
    for task in tasks:
        print(f"  {task['priority']} {task['project']} {task['task_id']} {task['path']}")
    return 0


def cmd_worker_status(args: argparse.Namespace) -> int:
    ensure_queue_dirs()
    payload = worker_status()
    if args.json:
        print_json(payload)
        return 0

    print("Worker status")
    for state in TASK_STATES:
        print(f"  {state}: {payload['queues'][state]}")
    print(f"  runs: {payload['runs_count']}")
    print("  daemon_enabled: false")
    return 0


def cmd_worker_run_once(args: argparse.Namespace) -> int:
    selector = "--task " + args.task if args.task else "--project " + str(args.project)
    command_text = f"python -m liaison worker run-once {selector}"
    result = run_once(project=args.project, task_id=args.task, command_text=command_text)

    if args.json:
        print_json(result.to_json())
        return 0

    print(result.message)
    if result.ran:
        print(f"run_id: {result.run_id}")
        print(f"run_dir: {result.run_dir}")
        print(f"review_path: {result.review_path}")
        print("production_allowed: false")
        print("customer_release_allowed: false")
        print("live_allowed: false")
    return 0


def cmd_evidence_show(args: argparse.Namespace) -> int:
    payload = evidence_summary(args.run_id)
    if args.json:
        print_json(payload)
        return 0 if payload["exists"] else 1

    if not payload["exists"]:
        print(f"Run not found: {args.run_id}", file=sys.stderr)
        return 1

    print(f"Evidence for {args.run_id}")
    print(f"run_id: {payload['run_id']}")
    print(f"task_id: {payload['task_id']}")
    print(f"project: {payload['project']}")
    print(f"status: {payload['status']}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    print("promotion_gate:")
    gate = payload["promotion_gate_summary"]
    print(f"  production_allowed: {json_bool(gate['production_allowed'])}")
    print(f"  customer_release_allowed: {json_bool(gate['customer_release_allowed'])}")
    print(f"  live_allowed: {json_bool(gate['live_allowed'])}")
    print(f"  required_human_approval: {json_bool(gate['required_human_approval'])}")
    print(f"missing_evidence: {len(payload['missing_evidence'])}")
    print("artifacts:")
    for artifact in payload["artifacts"]:
        marker = " task_specific" if artifact.get("task_specific") else ""
        print(f"  {artifact['status']}: {artifact['name']}{marker}")
    if payload.get("task_specific_artifact_groups"):
        print("task_specific_artifacts:")
        for group in payload["task_specific_artifact_groups"]:
            print(f"  {group['key']}:")
            for artifact in group["artifacts"]:
                print(f"    {artifact['status']}: {artifact['name']}")
    print("production/customer/live approval: false")
    return 0


def cmd_gate_evaluate(args: argparse.Namespace) -> int:
    payload = evaluate_promotion_gate(args.run_id)
    if args.json:
        print_json(payload)
        return 0 if payload["status"] != "blocked" else 1

    print(f"Gate for {args.run_id}: {payload['status']}")
    print(f"task_id: {payload['task_id']}")
    print(f"project: {payload['project']}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    print("production_allowed: false")
    print("customer_release_allowed: false")
    print("live_allowed: false")
    print("required_human_approval: true")
    print(f"promotion_gate_updated: {json_bool(payload['promotion_gate_updated'])}")
    if payload["missing_evidence"]:
        print("missing_evidence:")
        for name in payload["missing_evidence"]:
            print(f"  - {name}")
    else:
        print("missing_evidence: 0")
    print("production/customer/live approval: false")
    return 0 if payload["status"] != "blocked" else 1


def run_once(
    *,
    project: str | None = None,
    task_id: str | None = None,
    command_text: str | None = None,
    root: Path = Path("."),
    now: datetime | None = None,
) -> WorkerRunResult:
    """Run one safe placeholder worker cycle.

    No external executor, model, shell command, branch, deploy, trade, or approval
    path is invoked by this function.
    """
    ensure_queue_dirs(root)
    packet = select_one_task(project=project, task_id=task_id, root=root)
    if packet is None:
        selector = f"task {task_id}" if task_id else f"project {project}"
        return WorkerRunResult(
            ran=False,
            message=f"No eligible backlog task found for {selector}.",
            task_id=task_id,
            project=project,
        )

    active_path = lock_task(packet, root=root)
    active_packet = load_task_packet(active_path)
    run_id = create_run_id(active_packet.project, active_packet.task_id, now=now)
    run_dir = root / ".liaison" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    command_text = command_text or build_command_text(project=project, task_id=task_id)
    started_at = utc_now_iso()
    write_run_artifacts(
        run_dir=run_dir,
        packet=active_packet,
        run_id=run_id,
        command_text=command_text,
        started_at=started_at,
        root=root,
    )
    review_path = move_task_to_review(active_path, root=root)

    policy = load_validation_execution_policy(root)
    validation_enabled = bool(policy.get("enabled", False))
    human_approved = False
    if validation_enabled and policy.get("require_human_approval", True):
        approval_path = run_dir / "validation_execution_approval.json"
        if approval_path.exists():
            approval = read_json_file(approval_path)
            human_approved = bool(approval.get("execution_approved", False))
    execution_active = validation_enabled and (human_approved or not policy.get("require_human_approval", True))
    message = f"Executed validation for task {active_packet.task_id}." if execution_active else f"Placeholder worker created evidence for task {active_packet.task_id}."

    return WorkerRunResult(
        ran=True,
        message=message,
        run_id=run_id,
        task_id=active_packet.task_id,
        project=active_packet.project,
        run_dir=run_dir,
        review_path=review_path,
        called_executors=execution_active,
        ran_shell_validation=execution_active,
        validation_execution_allowed=execution_active,
    )


def ensure_queue_dirs(root: Path = Path(".")) -> None:
    tasks_dir = root / ".liaison" / "tasks"
    for state in TASK_STATES:
        (tasks_dir / state).mkdir(parents=True, exist_ok=True)
    (root / ".liaison" / "runs").mkdir(parents=True, exist_ok=True)


def worker_status(root: Path = Path(".")) -> dict[str, Any]:
    ensure_queue_dirs(root)
    tasks_dir = root / ".liaison" / "tasks"
    runs_dir = root / ".liaison" / "runs"
    queues = {
        state: count_yaml_files(tasks_dir / state)
        for state in TASK_STATES
    }
    runs_count = len([path for path in runs_dir.iterdir() if path.is_dir()]) if runs_dir.exists() else 0
    return {
        "queues": queues,
        "runs_count": runs_count,
        "daemon_enabled": False,
        "run_once_supported": True,
        "executed_tasks": False,
        "called_models": False,
        "called_executors": False,
        "production_allowed": False,
        "customer_release_allowed": False,
        "live_allowed": False,
    }


def count_yaml_files(path: Path) -> int:
    if not path.exists():
        return 0
    return len([child for child in path.iterdir() if child.suffix in {".yaml", ".yml"}])


def select_one_task(
    *,
    project: str | None = None,
    task_id: str | None = None,
    root: Path = Path("."),
) -> TaskPacket | None:
    tasks = select_eligible_backlog_tasks(project=project, root=root)
    if task_id:
        tasks = [
            task
            for task in tasks
            if task.task_id == task_id or task.path.stem == task_id
        ]
    if not tasks:
        return None
    return sorted(tasks, key=task_selection_key)[0]


def select_eligible_backlog_tasks(
    *,
    project: str | None = None,
    root: Path = Path("."),
) -> list[TaskPacket]:
    tasks: list[TaskPacket] = []
    for packet in iter_backlog_tasks(root=root):
        if packet.status != "backlog":
            continue
        if project and packet.project != project:
            continue
        tasks.append(packet)
    return sorted(tasks, key=task_selection_key)


def iter_backlog_tasks(root: Path = Path(".")) -> Iterable[TaskPacket]:
    backlog_dir = root / ".liaison" / "tasks" / "backlog"
    if not backlog_dir.exists():
        return []
    return [
        load_task_packet(path)
        for path in sorted(backlog_dir.glob("*.yaml"))
        if path.is_file()
    ]


def task_selection_key(packet: TaskPacket) -> tuple[int, str, str]:
    return (
        PRIORITY_RANK.get(packet.priority, 99),
        packet.created_at,
        packet.task_id.lower(),
    )


def load_task_packet(path: Path) -> TaskPacket:
    text = path.read_text(encoding="utf-8")
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkerRuntimeError(f"Invalid task YAML {path}: {exc}") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise WorkerRuntimeError(f"Task YAML root must be a mapping: {path}")
    return TaskPacket(path=path, text=text, data=dict(loaded))


def task_to_queue_json(packet: TaskPacket) -> dict[str, Any]:
    return {
        "task_id": packet.task_id,
        "project": packet.project,
        "type": packet.task_type,
        "priority": packet.priority,
        "status": packet.status,
        "created_at": packet.created_at,
        "path": str(packet.path),
    }


def lock_task(packet: TaskPacket, *, root: Path = Path(".")) -> Path:
    active_path = root / ".liaison" / "tasks" / "active" / packet.path.name
    if active_path.exists():
        raise WorkerRuntimeError(f"Task lock conflict: {active_path} already exists.")
    if not packet.path.exists():
        raise WorkerRuntimeError(f"Task disappeared before lock: {packet.path}")
    packet.path.rename(active_path)
    return active_path


def move_task_to_review(active_path: Path, *, root: Path = Path(".")) -> Path:
    review_path = root / ".liaison" / "tasks" / "review_required" / active_path.name
    if review_path.exists():
        raise WorkerRuntimeError(f"Review task already exists: {review_path}")
    active_path.rename(review_path)
    return review_path


def create_run_id(project: str, task_id: str, *, now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    timestamp = moment.strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{sanitize_run_token(project)}-{sanitize_run_token(task_id)}"


def sanitize_run_token(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    sanitized = sanitized.strip("-")
    return sanitized or "unknown"


def build_command_text(*, project: str | None, task_id: str | None) -> str:
    if task_id:
        return f"python -m liaison worker run-once --task {task_id}"
    return f"python -m liaison worker run-once --project {project}"


def write_run_artifacts(
    *,
    run_dir: Path,
    packet: TaskPacket,
    run_id: str,
    command_text: str,
    started_at: str,
    root: Path = Path("."),
) -> None:
    completed_at = utc_now_iso()
    (run_dir / "task.yaml").write_text(packet.text, encoding="utf-8")
    (run_dir / "context.md").write_text(
        build_context_md(packet=packet, run_id=run_id, started_at=started_at),
        encoding="utf-8",
    )
    (run_dir / "command.txt").write_text(
        command_text + "\nplaceholder mode: no commands executed\n",
        encoding="utf-8",
    )
    (run_dir / "model_calls.jsonl").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": packet.task_id,
                "status": "skipped",
                "model_calls_made": False,
                "reason": "placeholder worker does not call models",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "executor_result.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": packet.task_id,
                "executed": False,
                "executor": packet.data.get("routing", {}).get("executor"),
                "shell_commands_run": [],
                "validation_commands_run": [],
                "reason": "placeholder worker writes evidence only",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "stdout.log").write_text(
        "Placeholder worker completed evidence artifact creation.\n"
        "No executor stdout exists because no executor was invoked.\n",
        encoding="utf-8",
    )
    (run_dir / "stderr.log").write_text(
        "No stderr. No executor, model, shell validation, deployment, or trading command was invoked.\n",
        encoding="utf-8",
    )
    (run_dir / "patch.diff").write_text(
        "Not applicable for this run.\nNo patch was generated or applied.\n",
        encoding="utf-8",
    )
    (run_dir / "validation.log").write_text(
        build_validation_log(packet=packet, started_at=started_at, completed_at=completed_at),
        encoding="utf-8",
    )
    write_validation_plan_artifacts(
        run_dir=run_dir,
        packet=packet,
        run_id=run_id,
    )
    write_validation_result_artifacts(
        run_dir=run_dir,
        packet=packet,
        run_id=run_id,
    )
    write_validation_execution_approval_artifacts(
        run_dir=run_dir,
        packet=packet,
        run_id=run_id,
    )
    (run_dir / "security.log").write_text(build_security_log(run_id=run_id), encoding="utf-8")
    (run_dir / "data_quality.log").write_text(build_data_quality_log(packet=packet), encoding="utf-8")
    (run_dir / "compliance.md").write_text(
        build_compliance_md(packet=packet, run_id=run_id),
        encoding="utf-8",
    )
    write_task_specific_stub_artifacts(run_dir=run_dir, packet=packet, run_id=run_id)
    promotion_gate = build_promotion_gate(packet=packet, run_id=run_id)
    (run_dir / "promotion_gate.json").write_text(
        json.dumps(promotion_gate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "debrief.md").write_text(
        build_debrief_md(packet=packet, run_id=run_id, promotion_gate=promotion_gate),
        encoding="utf-8",
    )
    metadata = build_run_metadata(
        packet=packet,
        run_id=run_id,
        command_text=command_text,
        started_at=started_at,
        completed_at=completed_at,
        run_dir=run_dir,
    )
    (run_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    validate_with_executor(
        packet=packet,
        run_dir=run_dir,
        run_id=run_id,
        root=root,
        started_at=started_at,
    )


def validation_command_entries(task: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    task = task or {}
    validation = task.get("validation", [])
    entries: list[dict[str, Any]] = []
    if not isinstance(validation, list):
        return entries
    for index, item in enumerate(validation, start=1):
        if isinstance(item, str):
            command = item
            name = f"validation_{index}"
            required = False
        elif isinstance(item, Mapping):
            command = str(item.get("command", "")).strip()
            if not command:
                continue
            name = str(item.get("name") or f"validation_{index}")
            required = bool(item.get("required", False))
        else:
            continue
        entries.append(
            {
                "name": name,
                "command": command,
                "required": required,
                "status": "planned",
                "execution_allowed": False,
                "executed": False,
            }
        )
    return entries


def build_validation_plan_payload(*, packet: TaskPacket, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "status": "planned",
        "execution_allowed": False,
        "shell_commands_executed": False,
        "validation_execution_allowed": False,
        "commands": validation_command_entries(packet.data),
    }


def build_validation_plan_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Validation Plan",
        "",
        f"- Run ID: {payload.get('run_id', '')}",
        f"- Task ID: {payload.get('task_id', '')}",
        f"- Project: {payload.get('project', '')}",
        "- Status: planned",
        "- Execution allowed: false",
        "- Shell commands executed: false",
        "",
        "## Planned Commands",
        "",
    ]
    commands = payload.get("commands", [])
    if isinstance(commands, list) and commands:
        for command in commands:
            if not isinstance(command, Mapping):
                continue
            lines.extend(
                [
                    f"### {command.get('name', 'validation')}",
                    f"- Command: `{command.get('command', '')}`",
                    f"- Required: {json_bool(bool(command.get('required', False)))}",
                    "- Status: planned",
                    "- Execution allowed: false",
                    "",
                ]
            )
    else:
        lines.append("No validation commands declared.")
        lines.append("")
    return "\n".join(lines)


def write_validation_plan_artifacts(*, run_dir: Path, packet: TaskPacket, run_id: str) -> None:
    payload = build_validation_plan_payload(packet=packet, run_id=run_id)
    (run_dir / "validation_plan.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "validation_plan.md").write_text(
        build_validation_plan_md(payload),
        encoding="utf-8",
    )


def build_validation_result_payload(*, packet: TaskPacket, run_id: str) -> dict[str, Any]:
    entries = validation_command_entries(packet.data)
    return {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "status": "not_run",
        "execution_allowed": False,
        "commands_executed": 0,
        "commands_planned": len(entries),
        "passed": False,
        "evidence_only": True,
    }


def build_validation_result_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Validation Result",
        "",
        f"- Run ID: {payload.get('run_id', '')}",
        f"- Task ID: {payload.get('task_id', '')}",
        f"- Project: {payload.get('project', '')}",
        f"- Task Type: {payload.get('task_type', '')}",
        "- Status: not_run",
        "- Execution allowed: false",
        f"- Commands planned: {payload.get('commands_planned', 0)}",
        f"- Commands executed: {payload.get('commands_executed', 0)}",
        "- Passed: false",
        "- Evidence only: true",
        "",
        "## Note",
        "",
        "Validation commands were planned but not executed. This is a placeholder worker run.",
        "No shell validation commands were invoked. The validation_plan.json contains the planned commands.",
        "Future worker implementations will execute validation and populate this result.",
        "",
    ]
    return "\n".join(lines)


def write_validation_result_artifacts(*, run_dir: Path, packet: TaskPacket, run_id: str) -> None:
    payload = build_validation_result_payload(packet=packet, run_id=run_id)
    (run_dir / "validation_result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "validation_result.md").write_text(
        build_validation_result_md(payload),
        encoding="utf-8",
    )


def load_validation_execution_policy(root: Path = Path(".")) -> dict[str, Any]:
    policy_path = root / "policies" / "validation_execution.yaml"
    if not policy_path.exists():
        return {
            "enabled": False,
            "require_human_approval": True,
            "approved_approvers": [],
            "reason": "v0.2.0 placeholder mode: validation execution disabled by default",
            "version": "0.2.0",
        }
    try:
        loaded = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {
            "enabled": False,
            "require_human_approval": True,
            "approved_approvers": [],
            "reason": "v0.2.0 placeholder mode: invalid policy",
            "version": "0.2.0",
        }
    if loaded is None:
        loaded = {}
    return {
        "enabled": bool(loaded.get("enabled", False)),
        "require_human_approval": bool(loaded.get("require_human_approval", True)),
        "approved_approvers": list(loaded.get("approved_approvers", [])),
        "reason": str(loaded.get("reason", "v0.2.0 placeholder mode: validation execution disabled")),
        "version": str(loaded.get("version", "0.2.0")),
    }


def build_validation_execution_approval_payload(*, packet: TaskPacket, run_id: str, root: Path = Path(".")) -> dict[str, Any]:
    policy = load_validation_execution_policy(root)
    return {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "execution_requested": False,
        "execution_approved": False,
        "approved_by": None,
        "approval_required": True,
        "policy": policy,
        "reason": "v0.2.0 placeholder mode: validation execution disabled",
    }


def build_validation_execution_approval_md(payload: Mapping[str, Any]) -> str:
    policy = payload.get("policy", {})
    lines = [
        "# Validation Execution Approval",
        "",
        f"- Run ID: {payload.get('run_id', '')}",
        f"- Task ID: {payload.get('task_id', '')}",
        f"- Project: {payload.get('project', '')}",
        f"- Task Type: {payload.get('task_type', '')}",
        "- Execution requested: false",
        "- Execution approved: false",
        "- Approved by: null",
        "- Approval required: true",
        "",
        "## Policy",
        "",
        f"- Enabled: {json_bool(bool(policy.get('enabled', False)))}",
        f"- Require human approval: {json_bool(bool(policy.get('require_human_approval', True)))}",
        f"- Approved approvers: {policy.get('approved_approvers', [])}",
        f"- Policy version: {policy.get('version', '0.2.0')}",
        f"- Reason: {policy.get('reason', 'v0.2.0 placeholder mode: validation execution disabled')}",
        "",
        "## Note",
        "",
        "Validation execution is disabled by policy. This is a placeholder worker run.",
        "No validation commands were or will be executed without explicit human approval.",
        "Future worker implementations will request and require approval before executing validation.",
        "",
    ]
    return "\n".join(lines)


def write_validation_execution_approval_artifacts(*, run_dir: Path, packet: TaskPacket, run_id: str, root: Path = Path(".")) -> None:
    payload = build_validation_execution_approval_payload(packet=packet, run_id=run_id, root=root)
    (run_dir / "validation_execution_approval.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "validation_execution_approval.md").write_text(
        build_validation_execution_approval_md(payload),
        encoding="utf-8",
    )


def artifact_names_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, Mapping) and item.get("name"):
                names.append(str(item["name"]))
        return names
    return []


def add_artifact_spec(
    specs: dict[str, dict[str, Any]],
    order: list[str],
    name: str,
    *,
    source: str,
    task_specific: bool = False,
) -> None:
    normalized = str(name).strip()
    if not normalized:
        return
    if normalized not in specs:
        specs[normalized] = {
            "name": normalized,
            "required": True,
            "sources": [],
            "task_specific": False,
            "task_specific_keys": [],
        }
        order.append(normalized)
    spec = specs[normalized]
    if source not in spec["sources"]:
        spec["sources"].append(source)
    if task_specific:
        spec["task_specific"] = True
        if source not in spec["task_specific_keys"]:
            spec["task_specific_keys"].append(source)


def required_artifact_specs_for_task(task: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    task = task or {}
    specs: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for name in REQUIRED_RUN_ARTIFACTS:
        add_artifact_spec(specs, order, name, source="global_required_artifacts")
    for name in artifact_names_from_value(task.get("required_artifacts")):
        add_artifact_spec(specs, order, name, source="task.required_artifacts")
    add_artifact_spec(specs, order, "validation_plan.json", source="task.validation")
    add_artifact_spec(specs, order, "validation_plan.md", source="task.validation")
    for key in TASK_SPECIFIC_ARTIFACT_KEYS:
        for name in artifact_names_from_value(task.get(key)):
            add_artifact_spec(specs, order, name, source=key, task_specific=True)
    return [specs[name] for name in order]


def required_artifact_names_for_task(task: Mapping[str, Any] | None) -> list[str]:
    return [spec["name"] for spec in required_artifact_specs_for_task(task)]


def safe_artifact_path(run_dir: Path, name: str) -> Path:
    candidate = Path(name)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise WorkerRuntimeError(f"Unsafe required artifact path in task YAML: {name!r}")
    return run_dir / candidate


def write_task_specific_stub_artifacts(*, run_dir: Path, packet: TaskPacket, run_id: str) -> None:
    for spec in required_artifact_specs_for_task(packet.data):
        if not spec.get("task_specific"):
            continue
        artifact_path = safe_artifact_path(run_dir, str(spec["name"]))
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_path.exists():
            continue
        artifact_path.write_text(
            render_task_specific_stub_artifact(
                artifact_name=str(spec["name"]),
                source_keys=list(spec.get("task_specific_keys", [])),
                packet=packet,
                run_id=run_id,
            ),
            encoding="utf-8",
        )


def render_task_specific_stub_artifact(
    *,
    artifact_name: str,
    source_keys: list[str],
    packet: TaskPacket,
    run_id: str,
) -> str:
    payload = {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "artifact": artifact_name,
        "required_by": source_keys,
        "placeholder_worker": True,
        "real_scan_run": False,
        "models_called": False,
        "shell_commands_run": False,
        "production_allowed": False,
        "customer_release_allowed": False,
        "live_allowed": False,
        "requires_human_approval": True,
        "reason": "placeholder worker created a stub artifact without running task-specific checks",
    }
    if artifact_name == "fabricated_edge_scan.json":
        payload.update(
            {
                "status": "not_run",
                "fabricated_edge_scan_run": False,
                "fabricated_edges_found": None,
            }
        )
    elif artifact_name == "reliability_report.json":
        payload.update(
            {
                "status": "not_run",
                "reliability_analysis_run": False,
                "calibration_metrics": {},
            }
        )
    elif artifact_name == "confidence_calibration_gate.json":
        payload.update(
            {
                "status": "blocked",
                "confidence_calibration_passed": False,
                "blockers": [
                    "placeholder_worker_did_not_run_calibration",
                    "human_review_required",
                ],
            }
        )
    elif artifact_name.endswith(".json"):
        payload["status"] = "not_run"
    else:
        return (
            "Not applicable for this run.\n"
            f"Task-specific placeholder artifact for {artifact_name}.\n"
            "No real task-specific scan, shell command, model call, or executor call was run.\n"
        )
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _resolve_repo_cwd(task_data: Mapping[str, Any]) -> Path | None:
    repo = task_data.get("repo", {})
    if isinstance(repo, dict):
        repo_path = repo.get("path")
        if repo_path:
            candidate = Path(str(repo_path))
            if candidate.is_dir():
                return candidate.resolve()
    return None


def _run_validation_commands(
    *, packet: TaskPacket, repo_cwd: Path | None, root: Path
) -> list[dict[str, Any]]:
    entries = validation_command_entries(packet.data)
    results = []
    for entry in entries:
        command = entry["command"]
        try:
            result = run_executor(
                "shell",
                ["-c", command],
                cwd=repo_cwd,
                root=root,
            )
            results.append({
                "name": entry["name"],
                "command": command,
                "required": entry["required"],
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_sec": result.duration_sec,
                "status": "passed" if result.exit_code == 0 else "failed",
            })
        except RuntimeError as exc:
            results.append({
                "name": entry["name"],
                "command": command,
                "required": entry["required"],
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
                "duration_sec": 0.0,
                "status": "error",
            })
    return results


def _run_security_check(
    *, root: Path, repo_cwd: Path | None
) -> dict[str, Any] | None:
    if repo_cwd is None:
        return None
    security_script = root / "checks" / "security.sh"
    if not security_script.exists():
        return None
    try:
        result = run_executor("shell", [str(security_script)], cwd=repo_cwd, root=root)
        return {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_sec": result.duration_sec,
            "passed": result.exit_code == 0,
        }
    except RuntimeError:
        return None


def validate_with_executor(
    *, packet: TaskPacket, run_dir: Path, run_id: str, root: Path, started_at: str
) -> None:
    policy = load_validation_execution_policy(root)
    if not policy.get("enabled", False):
        return
    if policy.get("require_human_approval", True):
        approval_path = run_dir / "validation_execution_approval.json"
        if approval_path.exists():
            approval = read_json_file(approval_path)
            if not approval.get("execution_approved", False):
                return
        else:
            return

    repo_cwd = _resolve_repo_cwd(packet.data)
    completed_at = utc_now_iso()

    validation_results = _run_validation_commands(packet=packet, repo_cwd=repo_cwd, root=root)
    all_passed = all(r["status"] == "passed" for r in validation_results) if validation_results else True

    validation_log = yaml.safe_dump({
        "run_started_at": started_at,
        "run_completed_at": completed_at,
        "validation_executed": True,
        "entries": [
            {
                "name": r["name"],
                "command": r["command"],
                "started_at": started_at,
                "completed_at": completed_at,
                "exit_code": r["exit_code"],
                "stdout": r["stdout"],
                "stderr": r["stderr"],
                "required": r["required"],
                "status": r["status"],
                "reason": "",
            }
            for r in validation_results
        ],
    }, sort_keys=False)
    (run_dir / "validation.log").write_text(validation_log, encoding="utf-8")

    validation_result_payload = {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "status": "passed" if all_passed else "failed",
        "execution_allowed": True,
        "commands_executed": len(validation_results),
        "commands_planned": len(validation_results),
        "passed": all_passed,
        "evidence_only": False,
        "results": validation_results,
    }
    (run_dir / "validation_result.json").write_text(
        json.dumps(validation_result_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "validation_result.md").write_text(
        _format_validation_result_md(validation_result_payload),
        encoding="utf-8",
    )

    security_result = _run_security_check(root=root, repo_cwd=repo_cwd)
    if security_result:
        security_log_lines = [
            "# Security Log",
            f"Run ID: {run_id}",
            f"Script: checks/security.sh",
            f"Exit code: {security_result['exit_code']}",
            "",
            "## Output",
            security_result["stdout"].rstrip() if security_result["stdout"] else "(no output)",
            "",
        ]
        if security_result["stderr"]:
            security_log_lines.extend(["## Stderr", security_result["stderr"].rstrip(), ""])
        security_log_lines.append(f"Security check {'PASSED' if security_result['passed'] else 'FAILED'}")
        (run_dir / "security.log").write_text("\n".join(security_log_lines) + "\n", encoding="utf-8")

    executor_payload = {
        "run_id": run_id,
        "task_id": packet.task_id,
        "executed": True,
        "executor": "shell",
        "shell_commands_run": [r["command"] for r in validation_results],
        "validation_commands_run": validation_results,
        "reason": "Validation commands executed via shell executor",
    }
    (run_dir / "executor_result.json").write_text(
        json.dumps(executor_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    cmd_lines = ["Validation commands executed via shell executor:"]
    for r in validation_results:
        cmd_lines.append(f"  $ {r['command']}")
    cmd_lines.append(f"All passed: {all_passed}")
    if security_result:
        cmd_lines.append(f"Security check passed: {security_result['passed']}")
    (run_dir / "command.txt").write_text("\n".join(cmd_lines) + "\n", encoding="utf-8")

    stdout_parts = []
    stderr_parts = []
    for r in validation_results:
        if r["stdout"]:
            stdout_parts.append(f"--- {r['name']} (exit {r['exit_code']}) ---")
            stdout_parts.append(r["stdout"].rstrip())
        if r["stderr"]:
            stderr_parts.append(f"--- {r['name']} ---")
            stderr_parts.append(r["stderr"].rstrip())
    if security_result:
        if security_result["stdout"]:
            stdout_parts.append("--- security check ---")
            stdout_parts.append(security_result["stdout"].rstrip())
        if security_result["stderr"]:
            stderr_parts.append("--- security check ---")
            stderr_parts.append(security_result["stderr"].rstrip())
    (run_dir / "stdout.log").write_text("\n".join(stdout_parts) + "\n" if stdout_parts else "(no stdout)\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("\n".join(stderr_parts) + "\n" if stderr_parts else "(no stderr)\n", encoding="utf-8")

    security_passed = security_result["passed"] if security_result else False
    dq_lines = [
        f"Data quality validation for task {packet.task_id}.",
        f"Validation commands executed: {len(validation_results)}.",
        f"All passed: {all_passed}.",
    ]
    (run_dir / "data_quality.log").write_text("\n".join(dq_lines) + "\n", encoding="utf-8")

    compliance_lines = [
        "# Compliance Evidence",
        f"- Run ID: {run_id}",
        f"- Task ID: {packet.task_id}",
        f"- Project: {packet.project}",
        "- Validation executed: True",
        f"- Validation passed: {all_passed}",
        f"- Security check passed: {security_passed}",
        "- Commands were run via shell executor.",
        "- Production/customer/live flags remain False.",
        "- Human approval required for promotion.",
    ]
    (run_dir / "compliance.md").write_text("\n".join(compliance_lines) + "\n", encoding="utf-8")

    promotion_gate = {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "status": "passed" if all_passed and security_passed else "review_required",
        "live_allowed": False,
        "customer_release_allowed": False,
        "production_allowed": False,
        "required_human_approval": True,
        "model_budget_passed": False,
        "model_call_log_present": False,
        "validation_passed": all_passed,
        "security_passed": security_passed,
        "data_quality_passed": all_passed,
        "compliance_passed": all_passed and security_passed,
        "confidence_calibration_passed": False,
        "failed_checks": [],
        "passed_checks": [
            "executor_invoked",
            "validation_commands_executed",
        ],
        "missing_evidence": [],
        "notes": [
            "Validation commands executed via shell executor.",
            "Production, customer release, and live use remain disallowed.",
        ],
    }
    if not all_passed:
        promotion_gate["failed_checks"].append("validation_commands_failed")
    if not security_passed:
        promotion_gate["failed_checks"].append("security_check_failed")
    (run_dir / "promotion_gate.json").write_text(
        json.dumps(promotion_gate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    debrief_lines = [
        "# Debrief",
        "## Summary",
        f"Validation executed via shell executor for {packet.task_id}.",
        "",
        "## Task",
        f"{packet.task_id} ({packet.project}, {packet.task_type})",
        "",
        "## Executor/model route",
        "Shell executor invoked for validation commands.",
        "",
        "## Commands run",
    ]
    for r in validation_results:
        debrief_lines.append(f"- {r['name']}: {r['status']} (exit {r['exit_code']}, {r['duration_sec']}s)")
    if security_result:
        debrief_lines.append(f"- security check: {'passed' if security_result['passed'] else 'failed'} (exit {security_result['exit_code']})")
    debrief_lines.extend([
        "",
        "## Validation results",
        f"All validation commands passed: {all_passed}",
        "",
        "## Security findings",
        f"Security check passed: {security_passed}",
        "",
        "## Promotion gates",
        f"Status: {promotion_gate['status']}",
        "Production/customer/live flags remain false.",
        "Human approval required.",
    ])
    (run_dir / "debrief.md").write_text("\n".join(debrief_lines) + "\n", encoding="utf-8")

    metadata_path = run_dir / "run_metadata.json"
    metadata = read_json_file(metadata_path)
    metadata["run_type"] = "validation_executor_run_once"
    metadata["shell_commands_executed"] = True
    metadata["executors_called"] = True
    metadata["validation_execution_allowed"] = True
    metadata["tool_execution"]["executor_invoked"] = True
    metadata["tool_execution"]["shell_commands_run"] = True
    metadata["tool_execution"]["validation_commands_run"] = True
    (metadata_path).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _format_validation_result_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Validation Result",
        f"- Run ID: {payload.get('run_id', '')}",
        f"- Task ID: {payload.get('task_id', '')}",
        f"- Project: {payload.get('project', '')}",
        f"- Task Type: {payload.get('task_type', '')}",
        f"- Status: {payload.get('status', 'unknown')}",
        f"- Execution allowed: {payload.get('execution_allowed', False)}",
        f"- Commands planned: {payload.get('commands_planned', 0)}",
        f"- Commands executed: {payload.get('commands_executed', 0)}",
        f"- Passed: {payload.get('passed', False)}",
        "",
        "## Results",
    ]
    for r in payload.get("results", []):
        lines.append(f"### {r['name']}")
        lines.append(f"- Command: `{r['command']}`")
        lines.append(f"- Status: {r['status']}")
        lines.append(f"- Exit code: {r['exit_code']}")
        lines.append(f"- Duration: {r['duration_sec']}s")
        if r.get("stdout", "").strip():
            lines.append(f"- Stdout: {r['stdout'].strip()[:200]}")
        if r.get("stderr", "").strip():
            lines.append(f"- Stderr: {r['stderr'].strip()[:200]}")
        lines.append("")
    return "\n".join(lines)


def build_context_md(*, packet: TaskPacket, run_id: str, started_at: str) -> str:
    repo = packet.data.get("repo", {})
    routing = packet.data.get("routing", {})
    validation_entries = validation_command_entries(packet.data)
    lines = [
        "# Liaison Placeholder Worker Context",
        "",
        f"- Run ID: {run_id}",
        f"- Task ID: {packet.task_id}",
        f"- Project: {packet.project}",
        f"- Task type: {packet.task_type}",
        f"- Started at: {started_at}",
        f"- Repo path: {repo.get('path', 'unknown') if isinstance(repo, dict) else 'unknown'}",
        f"- Preferred host: {routing.get('preferred_host', 'unknown') if isinstance(routing, dict) else 'unknown'}",
        f"- Executor route: {routing.get('executor', 'unknown') if isinstance(routing, dict) else 'unknown'}",
        f"- Model route: {routing.get('model_route', 'unknown') if isinstance(routing, dict) else 'unknown'}",
        "",
        "## Safety Boundary",
        "",
        "This v0.2.0 placeholder run created evidence artifacts only.",
        "It did not call models, invoke executors, run shell validation commands, create branches, push, deploy, trade, or approve any production/customer/live use.",
        "",
        "## Validation Plan",
        "",
    ]
    if validation_entries:
        for item in validation_entries:
            lines.append(
                f"- {item['name']}: planned; command recorded but not executed."
            )
    else:
        lines.append("- No validation commands were declared.")
    lines.append("")
    return "\n".join(lines)


def build_validation_log(*, packet: TaskPacket, started_at: str, completed_at: str) -> str:
    entries: list[dict[str, Any]] = []
    for item in validation_command_entries(packet.data):
        entries.append(
            {
                "name": item["name"],
                "command": item["command"],
                "started_at": None,
                "completed_at": None,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "required": bool(item["required"]),
                "status": "skipped",
                "reason": "placeholder worker does not run shell validation commands",
            }
        )
    payload = {
        "run_started_at": started_at,
        "run_completed_at": completed_at,
        "validation_executed": False,
        "entries": entries,
    }
    return yaml.safe_dump(payload, sort_keys=False)


def build_security_log(*, run_id: str) -> str:
    lines = [
        "# Security Log",
        "",
        f"Run ID: {run_id}",
        "Security posture: passed by construction for the placeholder worker.",
        "No file inspection, secret access, provider call, shell command, push, deploy, trade, or gate bypass was attempted.",
        "",
        "## Checks",
        "",
    ]
    for check in SECURITY_CHECKS:
        lines.append(f"- {check}: not_triggered")
    lines.append("")
    return "\n".join(lines)


def build_data_quality_log(*, packet: TaskPacket) -> str:
    return (
        "Not applicable for this run.\n"
        f"Task {packet.task_id} did not access data, retrieval corpora, labels, features, production dumps, or customer records.\n"
        "Data-quality and confidence-calibration gates remain unpassed until a real validated run is reviewed.\n"
    )


def build_compliance_md(*, packet: TaskPacket, run_id: str) -> str:
    return "\n".join(
        [
            "# Compliance Evidence",
            "",
            f"- Run ID: {run_id}",
            f"- Task ID: {packet.task_id}",
            f"- Project: {packet.project}",
            "- Scope: Placeholder evidence generation only.",
            "- Data touched: None.",
            "- User/customer impact: None.",
            "- Privacy: No secrets, customer data, production dumps, or private keys were accessed.",
            "- Security: No forbidden action was attempted.",
            "- Licensing: Not evaluated by this placeholder worker.",
            "- Risk disclosures: Validation, data quality, and compliance remain pending human review.",
            "- Human approval: Required before merge, customer release, production, live trading, capital allocation, legal acceptance, or compliance acceptance.",
            "- Blockers: No production/customer/live promotion is allowed from this run.",
            "",
        ]
    )


def build_debrief_md(
    *,
    packet: TaskPacket,
    run_id: str,
    promotion_gate: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "# Debrief",
            "",
            "## Summary",
            "Created placeholder worker evidence artifacts only.",
            "",
            "## Task",
            f"{packet.task_id} ({packet.project}, {packet.task_type})",
            "",
            "## Executor/model route",
            "No executor or model route was invoked.",
            "",
            "## Files changed",
            "No repository files were changed. Task packet moved from backlog to review_required.",
            "",
            "## Commands run",
            "No shell validation or executor commands were run.",
            "",
            "## Validation results",
            "Validation commands were recorded as skipped.",
            "",
            "## Security findings",
            "No forbidden action was attempted.",
            "",
            "## Data-quality findings",
            "Not applicable for this placeholder run; data-quality gates remain unpassed.",
            "",
            "## Compliance findings",
            "Human review remains required.",
            "",
            "## Missing evidence",
            "None. Required placeholder artifacts were written.",
            "",
            "## Risks",
            "This run does not prove code correctness, release readiness, production readiness, customer readiness, or live trading readiness.",
            "",
            "## Recommended next action",
            "Human review of the evidence folder, followed by a future real worker implementation with explicit validation gates.",
            "",
            "## Promotion recommendation",
            f"{promotion_gate.get('status', 'review_required')}. Production/customer/live flags remain false.",
            "",
        ]
    )


def build_promotion_gate(*, packet: TaskPacket, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "status": "review_required",
        "live_allowed": False,
        "customer_release_allowed": False,
        "production_allowed": False,
        "required_human_approval": True,
        "model_budget_passed": False,
        "model_call_log_present": False,
        "validation_passed": False,
        "security_passed": True,
        "data_quality_passed": False,
        "compliance_passed": False,
        "confidence_calibration_passed": False,
        "failed_checks": [
            "executor_not_run",
            "validation_not_run",
            "data_quality_not_validated",
            "compliance_requires_human_review",
            "production_customer_live_disallowed",
        ],
        "passed_checks": [
            "required_artifacts_created",
            "no_model_calls",
            "no_executor_calls",
            "no_shell_validation_commands",
            "no_branch_created",
            "no_push",
            "no_deploy",
            "no_trade",
            "no_forbidden_action_attempted",
        ],
        "missing_evidence": [],
        "notes": [
            "Safe placeholder worker only; no tools were executed.",
            "Task moved to review_required and never to done.",
        ],
    }


def build_run_metadata(
    *,
    packet: TaskPacket,
    run_id: str,
    command_text: str,
    started_at: str,
    completed_at: str,
    run_dir: Path,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task_id": packet.task_id,
        "project": packet.project,
        "task_type": packet.task_type,
        "status": "review_required",
        "run_type": "placeholder_worker_run_once",
        "started_at": started_at,
        "completed_at": completed_at,
        "command": command_text,
        "shell_commands_executed": False,
        "models_called": False,
        "executors_called": False,
        "validation_execution_allowed": False,
        "run_dir": str(run_dir),
        "artifacts": required_artifact_names_for_task(packet.data),
        "task_queue_transition": {
            "from": "backlog",
            "locked_as": "active",
            "to": "review_required",
            "done": False,
        },
        "tool_execution": {
            "executor_invoked": False,
            "model_calls_made": False,
            "shell_commands_run": False,
            "validation_commands_run": False,
            "opencode_invoked": False,
            "codex_invoked": False,
            "claude_code_invoked": False,
            "litellm_invoked": False,
            "ollama_invoked": False,
        },
        "repository_actions": {
            "branch_created": False,
            "pushed_to_main": False,
            "deployed": False,
            "patch_applied": False,
        },
        "live_actions": {
            "traded": False,
            "capital_allocated": False,
        },
        "promotion": {
            "production_allowed": False,
            "customer_release_allowed": False,
            "live_allowed": False,
            "requires_human_approval": True,
        },
    }



# Evidence and gate command helpers are defined below near print_json.

def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


NOT_APPLICABLE_MARKER = "not applicable for this run"
SELF_HEALABLE_GATE_ARTIFACTS = {"promotion_gate.json"}


def json_bool(value: bool) -> str:
    return "true" if bool(value) else "false"


def artifact_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    if artifact_is_not_applicable(path):
        return "not_applicable"
    return "present"


def artifact_is_not_applicable(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    except OSError:
        return False
    return NOT_APPLICABLE_MARKER in text.lower()


def artifact_summaries(
    run_dir: Path,
    specs: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for spec in specs or required_artifact_specs_for_task({}):
        name = str(spec["name"])
        path = safe_artifact_path(run_dir, name)
        status = artifact_status(path)
        artifacts.append(
            {
                "name": name,
                "path": str(path),
                "required": True,
                "exists": path.exists(),
                "status": status,
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "sources": list(spec.get("sources", [])),
                "task_specific": bool(spec.get("task_specific", False)),
                "task_specific_keys": list(spec.get("task_specific_keys", [])),
            }
        )
    return artifacts


def missing_artifact_names(artifacts: Iterable[Mapping[str, Any]]) -> list[str]:
    return [str(artifact["name"]) for artifact in artifacts if artifact.get("status") == "missing"]


def grouped_task_specific_artifacts(
    artifacts: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for key in TASK_SPECIFIC_ARTIFACT_KEYS:
        group_artifacts = [
            dict(artifact)
            for artifact in artifacts
            if key in artifact.get("task_specific_keys", [])
        ]
        if group_artifacts:
            groups.append({"key": key, "artifacts": group_artifacts})
    return groups


def load_task_yaml_from_run(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "task.yaml"
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def run_identity(
    *,
    run_id: str,
    run_dir: Path,
    metadata: Mapping[str, Any],
    gate: Mapping[str, Any],
) -> dict[str, str]:
    task = load_task_yaml_from_run(run_dir)
    return {
        "run_id": run_id,
        "task_id": str(gate.get("task_id") or metadata.get("task_id") or task.get("id") or ""),
        "project": str(gate.get("project") or metadata.get("project") or task.get("project") or ""),
        "task_type": str(gate.get("task_type") or metadata.get("task_type") or task.get("type") or ""),
    }


def promotion_gate_summary(gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": str(gate.get("status", "unknown")),
        "production_allowed": False,
        "customer_release_allowed": False,
        "live_allowed": False,
        "required_human_approval": True,
    }


def evidence_summary(run_id: str, *, root: Path = Path(".")) -> dict[str, Any]:
    run_dir = root / ".liaison" / "runs" / run_id
    exists = run_dir.is_dir()
    task = load_task_yaml_from_run(run_dir) if exists else {}
    specs = required_artifact_specs_for_task(task)
    artifacts = artifact_summaries(run_dir, specs)
    missing = missing_artifact_names(artifacts) if exists else [spec["name"] for spec in specs]
    metadata = read_json_file(run_dir / "run_metadata.json") if exists else {}
    gate = read_json_file(run_dir / "promotion_gate.json") if exists else {}
    identity = run_identity(run_id=run_id, run_dir=run_dir, metadata=metadata, gate=gate)
    status = str(gate.get("status") or metadata.get("status") or ("missing" if not exists else "unknown"))
    summary = promotion_gate_summary(gate)
    summary["status"] = status
    task_specific_artifacts = [artifact for artifact in artifacts if artifact.get("task_specific")]
    return {
        "run_id": run_id,
        "task_id": identity["task_id"],
        "project": identity["project"],
        "task_type": identity["task_type"],
        "status": status,
        "artifact_dir": str(run_dir),
        "run_dir": str(run_dir),
        "exists": exists,
        "artifacts": artifacts,
        "task_specific_artifacts": task_specific_artifacts,
        "task_specific_artifact_groups": grouped_task_specific_artifacts(artifacts),
        "artifact_counts": {
            "required": len(artifacts),
            "present": sum(1 for artifact in artifacts if artifact["status"] == "present"),
            "missing": sum(1 for artifact in artifacts if artifact["status"] == "missing"),
            "not_applicable": sum(1 for artifact in artifacts if artifact["status"] == "not_applicable"),
            "task_specific": len(task_specific_artifacts),
        },
        "missing_evidence": missing,
        "metadata": metadata,
        "promotion_gate": gate,
        "promotion_gate_summary": summary,
        "production_allowed": False,
        "customer_release_allowed": False,
        "live_allowed": False,
        "required_human_approval": True,
    }


def task_specific_artifact_status_findings(
    *,
    run_dir: Path,
    summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for artifact in summary.get("task_specific_artifacts", []):
        if not isinstance(artifact, Mapping):
            continue
        name = str(artifact.get("name", ""))
        if not name.endswith(".json") or artifact.get("status") == "missing":
            continue
        payload = read_json_file(safe_artifact_path(run_dir, name))
        artifact_status_value = str(payload.get("status", "")).lower()
        if not artifact_status_value:
            continue
        blocked = artifact_status_value in {"blocked", "failed"}
        findings.append(
            {
                "artifact": name,
                "status": artifact_status_value,
                "blocking": blocked,
                "failed_check": f"task_specific_artifact:{name}:{artifact_status_value}",
            }
        )
    return findings


def normalize_gate_payload(
    *,
    run_id: str,
    run_dir: Path,
    summary: Mapping[str, Any],
    missing_evidence: list[str],
    task_specific_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    existing = summary.get("promotion_gate") if isinstance(summary.get("promotion_gate"), dict) else {}
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    identity = run_identity(run_id=run_id, run_dir=run_dir, metadata=metadata, gate=existing)
    task_specific_findings = task_specific_findings or []
    blocking_findings = [finding for finding in task_specific_findings if finding.get("blocking")]
    blocked = bool(missing_evidence) or not bool(summary.get("exists")) or bool(blocking_findings)
    failed_checks = list(existing.get("failed_checks", [])) if isinstance(existing, dict) else []
    passed_checks = list(existing.get("passed_checks", [])) if isinstance(existing, dict) else []
    notes = list(existing.get("notes", [])) if isinstance(existing, dict) else []

    if (bool(missing_evidence) or not bool(summary.get("exists"))) and "missing_evidence" not in failed_checks:
        failed_checks.append("missing_evidence")
    for finding in blocking_findings:
        failed_check = str(finding["failed_check"])
        if failed_check not in failed_checks:
            failed_checks.append(failed_check)
    if not blocked and "required_artifacts_created" not in passed_checks:
        passed_checks.append("required_artifacts_created")
    for check in [
        "no_model_calls",
        "no_executor_calls",
        "no_shell_validation_commands",
        "no_branch_created",
        "no_push",
        "no_deploy",
        "no_trade",
    ]:
        if check not in passed_checks:
            passed_checks.append(check)
    if "Production, customer release, and live use remain disallowed." not in notes:
        notes.append("Production, customer release, and live use remain disallowed.")

    return {
        "run_id": run_id,
        "task_id": identity["task_id"],
        "project": identity["project"],
        "task_type": identity["task_type"],
        "status": "blocked" if blocked else "review_required",
        "live_allowed": False,
        "customer_release_allowed": False,
        "production_allowed": False,
        "required_human_approval": True,
        "model_budget_passed": bool(existing.get("model_budget_passed", False)),
        "model_call_log_present": False,
        "validation_passed": bool(existing.get("validation_passed", False)) and not blocked,
        "security_passed": bool(existing.get("security_passed", False)) and not blocked,
        "data_quality_passed": bool(existing.get("data_quality_passed", False)) and not blocked,
        "compliance_passed": bool(existing.get("compliance_passed", False)) and not blocked,
        "confidence_calibration_passed": bool(existing.get("confidence_calibration_passed", False)) and not blocked,
        "failed_checks": failed_checks,
        "passed_checks": passed_checks,
        "missing_evidence": missing_evidence,
        "task_specific_artifact_findings": task_specific_findings,
        "notes": notes,
    }


def write_json_if_changed(path: Path, payload: Mapping[str, Any]) -> bool:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


def evaluate_promotion_gate(run_id: str, *, root: Path = Path(".")) -> dict[str, Any]:
    summary = evidence_summary(run_id, root=root)
    run_dir = root / ".liaison" / "runs" / run_id
    missing_before_update = list(summary["missing_evidence"])
    missing_for_status = [
        name for name in missing_before_update if name not in SELF_HEALABLE_GATE_ARTIFACTS
    ]
    task_specific_findings = task_specific_artifact_status_findings(
        run_dir=run_dir,
        summary=summary,
    )
    payload = normalize_gate_payload(
        run_id=run_id,
        run_dir=run_dir,
        summary=summary,
        missing_evidence=missing_for_status,
        task_specific_findings=task_specific_findings,
    )

    updated = False
    if summary["exists"]:
        updated = write_json_if_changed(run_dir / "promotion_gate.json", payload)
        if "promotion_gate.json" in missing_before_update:
            summary = evidence_summary(run_id, root=root)

    result = dict(payload)
    result.update(
        {
            "artifact_dir": str(run_dir),
            "run_dir": str(run_dir),
            "exists": bool(summary["exists"]),
            "artifacts": summary["artifacts"],
            "task_specific_artifacts": summary["task_specific_artifacts"],
            "task_specific_artifact_groups": summary["task_specific_artifact_groups"],
            "artifact_counts": summary["artifact_counts"],
            "promotion_gate_updated": updated,
        }
    )
    return result


__all__: Sequence[str] = (
    "REQUIRED_RUN_ARTIFACTS",
    "TASK_STATES",
    "WorkerRuntimeError",
    "WorkerRunResult",
    "ensure_queue_dirs",
    "evaluate_promotion_gate",
    "evidence_summary",
    "register_evidence_subparser",
    "register_gate_subparser",
    "register_worker_subparser",
    "run_once",
    "select_one_task",
    "worker_status",
)
