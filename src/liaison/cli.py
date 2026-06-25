"""Liaison v0.2.0 root CLI.

This module owns the top-level argparse parser and wires up the
subcommand groups from the various feature modules. It is the single
entrypoint invoked by:

    python -m liaison ...
    bin/liaison ...
    bin/spark-flow ...
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from liaison.executors import register_executor_subparser
from liaison.portfolio import (
    PortfolioProfileError,
    PortfolioRegistryError,
    TaskGenerationError,
    TaskTemplateError,
)
from liaison.worker import (
    WorkerRuntimeError,
    register_evidence_subparser,
    register_gate_subparser,
    register_worker_subparser,
)

CLI_VERSION = "0.2.0"


def build_root_parser() -> argparse.ArgumentParser:
    """Build the unified Liaison root CLI parser."""
    parser = argparse.ArgumentParser(
        prog="liaison",
        description="Liaison local-agent control plane CLI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"liaison {CLI_VERSION}",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Project root directory for config and queue lookup (default: cwd).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _register_all_subparsers(subparsers)
    return parser


def _register_all_subparsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register every Liaison subcommand group on the given parser."""
    from liaison.portfolio import register_portfolio_subparser

    register_portfolio_subparser(subparsers)
    register_worker_subparser(subparsers)
    register_evidence_subparser(subparsers)
    register_gate_subparser(subparsers)
    register_executor_subparser(subparsers)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the unified Liaison CLI."""
    parser = build_root_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except SystemExit:
        raise
    except (
        PortfolioRegistryError,
        PortfolioProfileError,
        TaskTemplateError,
        TaskGenerationError,
        WorkerRuntimeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
