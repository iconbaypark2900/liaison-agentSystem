"""Remote result approval and handoff for Liaison v0.2.0.

Implements Phase 8C: promote remote result artifacts only after human approval.

State machine:
    outbox/pending → outbox/approved → runs/<run-id>/integrated
    outbox/pending → outbox/rejected

All transitions are logged to logs/remote_approval_log.jsonl.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from liaison.remote import RemoteCallResult


APPROVAL_LOG_PATH = Path("logs/remote_approval_log.jsonl")
REMOTE_RESULTS_DIR = Path(".spark-flow/tasks") / "remote_results"


class ApprovalError(RuntimeError):
    """Raised when an approval transition is invalid."""


@dataclass(frozen=True)
class ApprovalState:
    capability: str
    result_file: str
    status: str  # pending, approved, rejected, integrated
    approved_by: str | None
    reason: str
    timestamp: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _results_dir(root: Path) -> Path:
    d = root / REMOTE_RESULTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(capability: str, root: Path) -> Path:
    return _results_dir(root) / f"{capability}.approval.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_approval_log(root: Path, entry: dict[str, Any]) -> None:
    log_path = root / APPROVAL_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def register_remote_result(
    capability: str,
    result: RemoteCallResult,
    *,
    root: Path = Path("."),
) -> ApprovalState:
    """Register a remote call result as pending approval."""
    state = ApprovalState(
        capability=capability,
        result_file=result.output_path or "",
        status="pending",
        approved_by=None,
        reason="Remote result awaiting human review",
        timestamp=_now_iso(),
    )
    _write_json(_state_path(capability, root), state.to_json())
    _write_approval_log(root, {**state.to_json(), "action": "registered"})
    return state


def get_approval_state(capability: str, *, root: Path = Path(".")) -> ApprovalState | None:
    path = _state_path(capability, root)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ApprovalState(**data)


def approve_remote_result(
    capability: str,
    *,
    approved_by: str = "operator",
    root: Path = Path("."),
) -> ApprovalState:
    """Approve a pending remote result."""
    state = get_approval_state(capability, root=root)
    if state is None:
        raise ApprovalError(f"No pending result for capability '{capability}'")
    if state.status != "pending":
        raise ApprovalError(f"Result for '{capability}' is already {state.status}")
    new_state = ApprovalState(
        capability=capability,
        result_file=state.result_file,
        status="approved",
        approved_by=approved_by,
        reason="Human approval granted",
        timestamp=_now_iso(),
    )
    _write_json(_state_path(capability, root), new_state.to_json())
    _write_approval_log(root, {**new_state.to_json(), "action": "approved"})
    return new_state


def reject_remote_result(
    capability: str,
    *,
    reason: str = "Rejected by operator",
    root: Path = Path("."),
) -> ApprovalState:
    """Reject a pending remote result."""
    state = get_approval_state(capability, root=root)
    if state is None:
        raise ApprovalError(f"No pending result for capability '{capability}'")
    if state.status != "pending":
        raise ApprovalError(f"Result for '{capability}' is already {state.status}")
    new_state = ApprovalState(
        capability=capability,
        result_file=state.result_file,
        status="rejected",
        approved_by=None,
        reason=reason,
        timestamp=_now_iso(),
    )
    _write_json(_state_path(capability, root), new_state.to_json())
    _write_approval_log(root, {**new_state.to_json(), "action": "rejected"})
    return new_state


def integrate_remote_result(
    capability: str,
    run_dir: Path,
    *,
    root: Path = Path("."),
) -> ApprovalState:
    """Promote an approved remote result into a worker run directory."""
    state = get_approval_state(capability, root=root)
    if state is None:
        raise ApprovalError(f"No result for capability '{capability}'")
    if state.status != "approved":
        raise ApprovalError(
            f"Result for '{capability}' must be approved before integration (current: {state.status})"
        )
    if not state.result_file:
        raise ApprovalError(f"Result file path is empty for '{capability}'")
    source = Path(state.result_file)
    if not source.exists():
        raise ApprovalError(f"Result file not found: {source}")
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / f"remote_result.{capability}.json"
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    new_state = ApprovalState(
        capability=capability,
        result_file=str(dest),
        status="integrated",
        approved_by=state.approved_by,
        reason="Result promoted to run directory",
        timestamp=_now_iso(),
    )
    _write_json(_state_path(capability, root), new_state.to_json())
    _write_approval_log(root, {**new_state.to_json(), "action": "integrated", "run_dir": str(run_dir)})
    return new_state


def list_pending_results(*, root: Path = Path(".")) -> list[ApprovalState]:
    """List all pending remote results."""
    results_dir = _results_dir(root)
    pending = []
    for path in sorted(results_dir.glob("*.approval.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        state = ApprovalState(**data)
        if state.status == "pending":
            pending.append(state)
    return pending


def cmd_remote_approve(args) -> int:
    """Handle `liaison remote-approval approve <capability>`."""
    root = Path(getattr(args, "root", "."))
    try:
        state = approve_remote_result(args.capability, approved_by=args.approved_by, root=root)
    except ApprovalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(state.to_json(), indent=2, sort_keys=True))
    else:
        print(f"Capability: {state.capability}")
        print(f"Status:     {state.status}")
        print(f"Approved by: {state.approved_by}")
    return 0


def cmd_remote_reject(args) -> int:
    """Handle `liaison remote-approval reject <capability>`."""
    root = Path(getattr(args, "root", "."))
    try:
        state = reject_remote_result(args.capability, reason=args.reason, root=root)
    except ApprovalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(state.to_json(), indent=2, sort_keys=True))
    else:
        print(f"Capability: {state.capability}")
        print(f"Status:     {state.status}")
        print(f"Reason:     {state.reason}")
    return 0


def cmd_remote_list(args) -> int:
    """Handle `liaison remote-approval list`."""
    root = Path(getattr(args, "root", "."))
    pending = list_pending_results(root=root)
    if getattr(args, "json", False):
        print(json.dumps([s.to_json() for s in pending], indent=2, sort_keys=True))
    else:
        print(f"Pending remote results: {len(pending)}")
        for state in pending:
            print(f"  {state.capability}: {state.result_file}")
    return 0


def register_remote_approval_subparser(subparsers) -> None:
    """Register `liaison remote-approval ...` commands."""
    parser = subparsers.add_parser(
        "remote-approval",
        help="Remote result approval and handoff (Phase 8C).",
    )
    approval_subparsers = parser.add_subparsers(dest="remote_approval_command", required=True)

    list_parser = approval_subparsers.add_parser("list", help="List pending remote results.")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_remote_list)

    approve_parser = approval_subparsers.add_parser("approve", help="Approve a pending result.")
    approve_parser.add_argument("capability", help="Capability to approve.")
    approve_parser.add_argument("--approved-by", default="operator", help="Approver name.")
    approve_parser.add_argument("--json", action="store_true")
    approve_parser.set_defaults(func=cmd_remote_approve)

    reject_parser = approval_subparsers.add_parser("reject", help="Reject a pending result.")
    reject_parser.add_argument("capability", help="Capability to reject.")
    reject_parser.add_argument("--reason", default="Rejected by operator", help="Rejection reason.")
    reject_parser.add_argument("--json", action="store_true")
    reject_parser.set_defaults(func=cmd_remote_reject)


__all__: Sequence[str] = (
    "ApprovalError",
    "ApprovalState",
    "approve_remote_result",
    "cmd_remote_approve",
    "cmd_remote_list",
    "cmd_remote_reject",
    "get_approval_state",
    "integrate_remote_result",
    "list_pending_results",
    "register_remote_approval_subparser",
    "register_remote_result",
    "reject_remote_result",
)
