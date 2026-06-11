"""CLI command stubs for Liaison portfolio operations.

This module wires the v0.2.0 portfolio task-generation stubs to a CLI surface.

Implemented command group:

    liaison portfolio list
    liaison portfolio list --host dgx_spark
    liaison portfolio list --host evox2_windows

    liaison portfolio counts
    liaison portfolio counts --json

    liaison portfolio validate
    liaison portfolio validate --json

    liaison portfolio generate-tasks --limit 6
    liaison portfolio generate-tasks --dry-run --limit 6
    liaison portfolio generate-tasks --host dgx_spark --limit 3
    liaison portfolio generate-tasks --host evox2_windows --limit 3
    liaison portfolio generate-tasks --project sigma
    liaison portfolio generate-tasks --project docuQuery --types audit,security,release-gap

Safety boundary:
    These commands do NOT execute generated tasks.
    They do NOT call workers.
    They do NOT call models.
    They do NOT call executors.
    They do NOT create branches.
    They do NOT approve production/customer/live promotion.

They only:
    - read registries/profiles/templates
    - validate config
    - render task packets
    - optionally write rendered task YAML files to backlog

Integration note:
    If Liaison already has a CLI framework, import and call
    `register_portfolio_subparser(...)` from the existing root parser.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .portfolio_registry import (
    PortfolioRegistryError,
    iter_active_projects,
    load_portfolio_registries,
    portfolio_counts_json,
)
from .portfolio_profiles import PortfolioProfileError, load_all_profiles, resolve_project_profile
from .task_generation import (
    GenerationRequest,
    TaskGenerationError,
    generate_tasks,
    parse_types,
    validate_portfolio,
)
from .task_templates import TaskTemplateError
from .worker import (
    WorkerRuntimeError,
    register_evidence_subparser,
    register_gate_subparser,
    register_worker_subparser,
)


VALID_HOSTS = ("dgx_spark", "evox2_windows")


def register_portfolio_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register `liaison portfolio ...` commands on an existing argparse parser."""
    portfolio_parser = subparsers.add_parser(
        "portfolio",
        help="List, validate, and generate safe task packets from the active project registry.",
    )
    portfolio_subparsers = portfolio_parser.add_subparsers(
        dest="portfolio_command",
        required=True,
    )

    register_list_parser(portfolio_subparsers)
    register_counts_parser(portfolio_subparsers)
    register_validate_parser(portfolio_subparsers)
    register_generate_tasks_parser(portfolio_subparsers)


def register_list_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "list",
        help="List active portfolio projects.",
    )
    parser.add_argument(
        "--host",
        choices=VALID_HOSTS,
        default=None,
        help="Filter active projects by workstation/host.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    parser.set_defaults(func=cmd_portfolio_list)


def register_counts_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "counts",
        help="Show active portfolio counts.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    parser.set_defaults(func=cmd_portfolio_counts)


def register_validate_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "validate",
        help="Validate portfolio registries, profiles, exclusions, and safety defaults.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    parser.set_defaults(func=cmd_portfolio_validate)


def register_generate_tasks_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "generate-tasks",
        help="Render safe backlog task packets from the active portfolio registry.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=6,
        help="Maximum number of projects/tasks to generate. Default: 6.",
    )
    parser.add_argument(
        "--host",
        choices=VALID_HOSTS,
        default=None,
        help="Generate tasks only for one workstation profile.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Generate tasks for a single active project ID.",
    )
    parser.add_argument(
        "--types",
        default=None,
        help="Comma-separated task types, e.g. audit,security,release-gap.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and validate tasks without writing files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing backlog task files when safe.",
    )
    parser.add_argument(
        "--backlog-dir",
        default=".liaison/tasks/backlog",
        help="Backlog directory for generated task YAML files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )
    parser.set_defaults(func=cmd_portfolio_generate_tasks)


def cmd_portfolio_list(args: argparse.Namespace) -> int:
    """Handle `liaison portfolio list`."""
    active, merge_sources, archives = load_portfolio_registries()

    projects = list(iter_active_projects(active, host=args.host))

    if args.json:
        payload = {
            "host": args.host,
            "count": len(projects),
            "projects": [
                {
                    "project_id": project.project_id,
                    "workstation": project.workstation,
                    "path": project.path,
                    "category": project.category,
                    "priority": project.priority,
                    "tags": project.tags,
                    "default_host": project.default_host,
                    "preferred_executor": project.preferred_executor,
                    "default_model_route": project.default_model_route,
                    "validation_profiles": project.validation_profiles,
                    "safety_gates": project.safety_gates,
                    "status": project.status,
                    "production_allowed": project.production_allowed,
                    "customer_release_allowed": project.customer_release_allowed,
                    "live_allowed": project.live_allowed,
                    "requires_human_approval": project.requires_human_approval,
                }
                for project in projects
            ],
            "merge_sources_excluded": merge_sources.count,
            "archive_candidates_excluded": archives.count,
        }
        print_json(payload)
        return 0

    if args.host == "dgx_spark":
        print("DGX Spark active projects:")
    elif args.host == "evox2_windows":
        print("EVO-X2 Windows active projects:")
    else:
        print("Active Portfolio")
        print()
        print(f"DGX Spark: {active.counts.dgx_active_count} projects")
        for project in active.by_host("dgx_spark"):
            print(f"  {project.project_id}")
        print()
        print(f"EVO-X2 Windows: {active.counts.evox2_active_count} projects")
        for project in active.by_host("evox2_windows"):
            print(f"  {project.project_id}")
        return 0

    for project in projects:
        print(f"  {project.project_id}")
    print()
    print(f"Count: {len(projects)}")
    return 0


def cmd_portfolio_counts(args: argparse.Namespace) -> int:
    """Handle `liaison portfolio counts`."""
    active, _, _ = load_portfolio_registries()
    payload = portfolio_counts_json(active)

    if args.json:
        print_json(payload)
        return 0

    print(f"DGX Spark active projects: {payload['dgx_active_count']}")
    print(f"EVO-X2 active projects: {payload['evox2_active_count']}")
    print(f"Total active projects: {payload['active_project_count']}")
    print(f"Merge sources excluded: {payload['merge_sources_excluded']}")
    print(f"Archive candidates excluded: {payload['archive_candidates_excluded']}")
    return 0


def cmd_portfolio_validate(args: argparse.Namespace) -> int:
    """Handle `liaison portfolio validate`."""
    result = validate_portfolio()

    if args.json:
        print_json(result)
        return 0 if result["status"] == "passed" else 1

    if result["status"] == "passed":
        print("Portfolio validation passed.")
        print(f"Active projects: {result['active_project_count']}")
        print(f"DGX Spark: {result['dgx_active_count']}")
        print(f"EVO-X2: {result['evox2_active_count']}")
        print(f"Merge sources excluded: {result['merge_sources_excluded']}")
        print(f"Archive candidates excluded: {result['archive_candidates_excluded']}")
        if result.get("warnings"):
            print()
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"  - {warning}")
        return 0

    print("Portfolio validation failed.", file=sys.stderr)
    for failed in result.get("failed_checks", []):
        print(f"  - {failed}", file=sys.stderr)
    return 1


def cmd_portfolio_generate_tasks(args: argparse.Namespace) -> int:
    """Handle `liaison portfolio generate-tasks`.

    This command only renders task packets. It never executes generated tasks.
    """
    request = GenerationRequest(
        limit=args.limit,
        host=args.host,
        project=args.project,
        types=parse_types(args.types),
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        backlog_dir=Path(args.backlog_dir),
    )

    result = generate_tasks(request)

    if args.json:
        print_json(generation_result_to_json(result))
        return 0 if result.ok else 1

    for line in result.summary_lines():
        print(line)

    if result.ok:
        print()
        print("No tasks were executed.")
        print("Next step:")
        if result.generated:
            first_project = result.generated[0].project_id
            print(f"  liaison worker run-once --project {first_project}")
        else:
            print("  No generated tasks to run.")
        return 0

    return 1


def generation_result_to_json(result: Any) -> dict[str, Any]:
    """Return a JSON-safe representation of GenerationResult."""
    return {
        "ok": result.ok,
        "dry_run": result.request.dry_run,
        "limit": result.request.limit,
        "host": result.request.host,
        "project": result.request.project,
        "types": result.request.types,
        "backlog_dir": str(result.request.backlog_dir),
        "generated_count": len(result.generated),
        "skipped_count": len(result.skipped),
        "error_count": len(result.errors),
        "generated": [
            {
                "project_id": task.project_id,
                "task_type": task.task_type,
                "target_path": str(task.target_path),
                "task_id": task.rendered.task_id,
                "would_write": task.would_write,
                "skipped": task.skipped,
                "skip_reason": task.skip_reason,
            }
            for task in result.generated
        ],
        "skipped": [
            {
                "project_id": task.project_id,
                "task_type": task.task_type,
                "target_path": str(task.target_path),
                "task_id": task.rendered.task_id,
                "would_write": task.would_write,
                "skipped": task.skipped,
                "skip_reason": task.skip_reason,
            }
            for task in result.skipped
        ],
        "errors": result.errors,
        "executed_tasks": False,
        "called_models": False,
        "called_executors": False,
        "created_branches": False,
        "production_allowed": False,
        "customer_release_allowed": False,
        "live_allowed": False,
    }


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    """Build a standalone parser.

    Existing Liaison CLI can either use this directly or call
    `register_portfolio_subparser` on its own root parser.
    """
    parser = argparse.ArgumentParser(
        prog="liaison",
        description="Liaison local-agent control plane CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_portfolio_subparser(subparsers)
    register_worker_subparser(subparsers)
    register_evidence_subparser(subparsers)
    register_gate_subparser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone CLI entrypoint for portfolio command stubs."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except (
        PortfolioRegistryError,
        PortfolioProfileError,
        TaskTemplateError,
        TaskGenerationError,
        WorkerRuntimeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
