"""Tests for Phase 8C remote result approval and handoff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from liaison.approval import (
    ApprovalError,
    ApprovalState,
    approve_remote_result,
    get_approval_state,
    integrate_remote_result,
    list_pending_results,
    register_remote_result,
    reject_remote_result,
)
from liaison.remote import RemoteCallResult


def _make_result(capability: str, output_path: str = "/tmp/out.json") -> RemoteCallResult:
    return RemoteCallResult(
        capability=capability,
        provider="nvidia_nim",
        model="test-model",
        status="success",
        exit_code=200,
        response_text='{"choices": []}',
        latency_seconds=0.5,
        estimated_cost_usd=0.001,
        output_path=output_path,
        log_path="/tmp/log.jsonl",
        reason="test",
    )


def test_register_and_get_state(tmp_path: Path) -> None:
    result = _make_result("test_cap")
    state = register_remote_result("test_cap", result, root=tmp_path)
    assert state.status == "pending"
    assert state.capability == "test_cap"

    fetched = get_approval_state("test_cap", root=tmp_path)
    assert fetched is not None
    assert fetched.status == "pending"


def test_approve_pending_result(tmp_path: Path) -> None:
    result = _make_result("test_cap")
    register_remote_result("test_cap", result, root=tmp_path)
    state = approve_remote_result("test_cap", approved_by="alice", root=tmp_path)
    assert state.status == "approved"
    assert state.approved_by == "alice"


def test_reject_pending_result(tmp_path: Path) -> None:
    result = _make_result("test_cap")
    register_remote_result("test_cap", result, root=tmp_path)
    state = reject_remote_result("test_cap", reason="bad output", root=tmp_path)
    assert state.status == "rejected"
    assert "bad output" in state.reason


def test_approve_already_approved_fails(tmp_path: Path) -> None:
    result = _make_result("test_cap")
    register_remote_result("test_cap", result, root=tmp_path)
    approve_remote_result("test_cap", root=tmp_path)
    with pytest.raises(ApprovalError, match="already approved"):
        approve_remote_result("test_cap", root=tmp_path)


def test_approve_nonexistent_fails(tmp_path: Path) -> None:
    with pytest.raises(ApprovalError, match="No pending"):
        approve_remote_result("nonexistent", root=tmp_path)


def test_integrate_approved_result(tmp_path: Path) -> None:
    result_file = tmp_path / "outbox" / "result.json"
    result_file.parent.mkdir(parents=True)
    result_file.write_text('{"data": "test"}', encoding="utf-8")

    result = _make_result("test_cap", str(result_file))
    register_remote_result("test_cap", result, root=tmp_path)
    approve_remote_result("test_cap", root=tmp_path)

    run_dir = tmp_path / ".liaison" / "runs" / "test-run"
    state = integrate_remote_result("test_cap", run_dir, root=tmp_path)
    assert state.status == "integrated"
    assert (run_dir / "remote_result.test_cap.json").exists()
    content = (run_dir / "remote_result.test_cap.json").read_text(encoding="utf-8")
    assert "test" in content


def test_integrate_without_approval_fails(tmp_path: Path) -> None:
    result = _make_result("test_cap")
    register_remote_result("test_cap", result, root=tmp_path)
    run_dir = tmp_path / "runs"
    with pytest.raises(ApprovalError, match="must be approved"):
        integrate_remote_result("test_cap", run_dir, root=tmp_path)


def test_list_pending_results(tmp_path: Path) -> None:
    r1 = _make_result("cap1")
    r2 = _make_result("cap2")
    register_remote_result("cap1", r1, root=tmp_path)
    register_remote_result("cap2", r2, root=tmp_path)
    approve_remote_result("cap1", root=tmp_path)

    pending = list_pending_results(root=tmp_path)
    assert len(pending) == 1
    assert pending[0].capability == "cap2"


def test_approval_log_written(tmp_path: Path) -> None:
    result = _make_result("test_cap")
    register_remote_result("test_cap", result, root=tmp_path)
    approve_remote_result("test_cap", root=tmp_path)

    log_path = tmp_path / "logs" / "remote_approval_log.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    entry = json.loads(lines[1])
    assert entry["action"] == "approved"


def test_full_lifecycle(tmp_path: Path) -> None:
    result_file = tmp_path / "outbox" / "nim_result.json"
    result_file.parent.mkdir(parents=True)
    result_file.write_text('{"analysis": "ok"}', encoding="utf-8")

    result = _make_result("long_context", str(result_file))
    state = register_remote_result("long_context", result, root=tmp_path)
    assert state.status == "pending"

    state = approve_remote_result("long_context", approved_by="operator", root=tmp_path)
    assert state.status == "approved"

    run_dir = tmp_path / ".liaison" / "runs" / "20260629T120000Z-test"
    state = integrate_remote_result("long_context", run_dir, root=tmp_path)
    assert state.status == "integrated"
    assert (run_dir / "remote_result.long_context.json").exists()
