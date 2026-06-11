"""CLI tests for Liaison portfolio command stubs.

These tests expect the portfolio registry/profile/template stubs from prior steps.
They are intentionally light because deeper behavior is covered by
test_portfolio_task_generation.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from liaison.portfolio import build_parser, generation_result_to_json, main
from liaison.task_generation import GenerationRequest, GenerationResult


def test_portfolio_parser_accepts_list_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["portfolio", "list", "--host", "dgx_spark", "--json"])

    assert args.command == "portfolio"
    assert args.portfolio_command == "list"
    assert args.host == "dgx_spark"
    assert args.json is True


def test_portfolio_parser_accepts_counts_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["portfolio", "counts", "--json"])

    assert args.command == "portfolio"
    assert args.portfolio_command == "counts"
    assert args.json is True


def test_portfolio_parser_accepts_validate_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["portfolio", "validate", "--json"])

    assert args.command == "portfolio"
    assert args.portfolio_command == "validate"
    assert args.json is True


def test_portfolio_parser_accepts_generate_tasks_command() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "portfolio",
        "generate-tasks",
        "--dry-run",
        "--limit",
        "6",
        "--project",
        "sigma",
        "--types",
        "calibration",
        "--json",
    ])

    assert args.command == "portfolio"
    assert args.portfolio_command == "generate-tasks"
    assert args.dry_run is True
    assert args.limit == 6
    assert args.project == "sigma"
    assert args.types == "calibration"
    assert args.json is True


def test_parser_accepts_worker_commands() -> None:
    parser = build_parser()

    queue_args = parser.parse_args(["worker", "queue", "--project", "clinical-suite"])
    status_args = parser.parse_args(["worker", "status"])
    run_args = parser.parse_args(["worker", "run-once", "--project", "clinical-suite"])

    assert queue_args.command == "worker"
    assert queue_args.worker_command == "queue"
    assert queue_args.project == "clinical-suite"
    assert status_args.worker_command == "status"
    assert run_args.worker_command == "run-once"
    assert run_args.project == "clinical-suite"


def test_parser_accepts_evidence_and_gate_commands() -> None:
    parser = build_parser()

    evidence_args = parser.parse_args(["evidence", "show", "run-123"])
    gate_args = parser.parse_args(["gate", "evaluate", "run-123"])

    assert evidence_args.command == "evidence"
    assert evidence_args.evidence_command == "show"
    assert evidence_args.run_id == "run-123"
    assert gate_args.command == "gate"
    assert gate_args.gate_command == "evaluate"
    assert gate_args.run_id == "run-123"


def test_generation_result_json_safety_flags() -> None:
    request = GenerationRequest(dry_run=True)
    result = GenerationResult(request=request, generated=[], skipped=[], errors=[])

    payload = generation_result_to_json(result)

    assert payload["executed_tasks"] is False
    assert payload["called_models"] is False
    assert payload["called_executors"] is False
    assert payload["created_branches"] is False
    assert payload["production_allowed"] is False
    assert payload["customer_release_allowed"] is False
    assert payload["live_allowed"] is False
