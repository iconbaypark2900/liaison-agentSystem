# PORTFOLIO_CLI_INTEGRATION — Liaison v0.2.0

## Overview

The portfolio CLI is integrated into the unified Liaison root CLI as the
`portfolio` subcommand group. It provides commands for listing, validating,
and generating task packets from the project registry.

## CLI Structure

```
liaison
├── portfolio
│   ├── list          # List projects by host
│   ├── counts        # Project counts
│   ├── validate      # Validate registry
│   └── generate-tasks # Generate task packets
├── worker
│   ├── queue
│   ├── status
│   └── run-once
├── evidence
│   └── show
├── gate
│   └── evaluate
└── executor
    ├── list
    ├── ping
    └── run
```

## Portfolio Commands

### `liaison portfolio list`

Lists registered projects, optionally filtered by host.

```bash
liaison portfolio list
liaison portfolio list --host dgx_spark
liaison portfolio list --host evox2_windows --json
```

### `liaison portfolio counts`

Shows project counts by host and tier.

```bash
liaison portfolio counts
liaison portfolio counts --json
```

### `liaison portfolio validate`

Validates the portfolio registry for consistency.

```bash
liaison portfolio validate
liaison portfolio validate --json
```

Checks:
- All projects have required fields
- All referenced workflows exist
- All referenced validation profiles exist
- Host assignments are valid

### `liaison portfolio generate-tasks`

Generates task packets from the registry.

```bash
liaison portfolio generate-tasks --dry-run --limit 6
liaison portfolio generate-tasks --project sigma --types audit,security
liaison portfolio generate-tasks --host dgx_spark --limit 3
liaison portfolio generate-tasks --project sigma --json
```

## Root CLI Integration

The root CLI (`src/liaison/cli.py`) builds a unified argparse parser:

```python
def build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liaison", ...)
    parser.add_argument("--version", action="version", version=f"liaison {CLI_VERSION}")
    parser.add_argument("--root", type=str, default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _register_all_subparsers(subparsers)
    return parser
```

`portfolio.build_parser()` and `portfolio.main()` delegate to `liaison.cli`
for backward compatibility.

## Error Handling

Domain errors are caught and returned as exit code 1:

```python
try:
    return int(args.func(args))
except (PortfolioRegistryError, PortfolioProfileError,
        TaskTemplateError, TaskGenerationError, WorkerRuntimeError) as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 1
```

## JSON Output

All commands support `--json` for machine-readable output. JSON output is
always valid JSON with sorted keys and 2-space indentation.

## Entry Points

| Entry Point | Command |
|-------------|---------|
| `python -m liaison` | `src/liaison/__main__.py` → `cli.main()` |
| `bin/liaison` | Shell wrapper → `bin/spark-flow` |
| `bin/spark-flow` | Full CLI with all spark-flow commands |
