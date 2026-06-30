# PORTFOLIO_TASK_GENERATION — Liaison v0.2.0

## Overview

The portfolio task generation system creates task packets from the project
registry. It reads project metadata, selects a task template based on project
type and phase, renders the template with project-specific values, and writes
task YAML files to the backlog queue.

## Generation Flow

```
1. Load project registry (config/project_registry.active.yaml)
2. Filter by host, project, or limit
3. For each project:
   a. Determine task types (audit, security, release-gap, calibration, validation)
   b. Select task template (templates/tasks/*.yaml)
   c. Render template with project values ({{ project }}, {{ repo }}, etc.)
   d. If --dry-run: print rendered task
   e. If real: write to .liaison/tasks/backlog/<task-id>.yaml
4. Return generation result
```

## Task Types

| Type | Template | When Generated |
|------|----------|----------------|
| project_audit | project_audit_task.yaml | All projects, every phase |
| project_security_scan | project_security_scan_task.yaml | All projects |
| project_release_gap | project_release_gap_task.yaml | Projects in beta/MVP phase |
| project_calibration_gate | project_calibration_gate_task.yaml | Trading/prediction projects |
| project_validation | project_validation_task.yaml | Projects with validation profiles |

## Task Templates

Templates live in `templates/tasks/` and use `{{ placeholder }}` syntax:

```yaml
id: {{ project }}-{{ task_type }}-{{ sequence }}
project: {{ project }}
title: "{{ title }}"
type: {{ task_type }}
priority: {{ priority }}
status: backlog
created_at: {{ timestamp }}
repo:
  path: {{ repo_path }}
routing:
  preferred_host: {{ host }}
  model_route: {{ model_route }}
  executor: {{ executor }}
  fallback_executor: shell
validation:
  - name: {{ validation_name }}
    command: {{ validation_command }}
    required: true
forbidden_actions:
  - push_main
  - deploy_production
  - customer_release
  - live_trade
  - read_secrets
safety:
  production_allowed: false
  customer_release_allowed: false
  live_allowed: false
  requires_human_approval: true
```

## Template Renderer

The renderer (`src/liaison/task_templates.py`) supports:

| Placeholder | Source | Example |
|-------------|--------|---------|
| `{{ project }}` | Project key | `sigma` |
| `{{ repo_path }}` | Registry repo path | `~/quantumGlobalGroup/sigma` |
| `{{ host }}` | Project host | `dgx_spark` |
| `{{ task_type }}` | Selected type | `project_audit` |
| `{{ priority }}` | Phase-based default | `high` |
| `{{ timestamp }}` | Current UTC | `2026-06-10T12:00:00Z` |
| `{{ sequence }}` | Incrementing counter | `001` |
| `{{ title }}` | Template default | "Audit sigma for phase alpha" |

The renderer intentionally supports a small safe subset. It does not support
conditionals, loops, or arbitrary expressions. This is a security boundary:
templates cannot inject logic.

## Generation Request

```python
@dataclass(frozen=True)
class GenerationRequest:
    host: str | None = None
    project: str | None = None
    task_types: list[str] | None = None
    limit: int = 6
    dry_run: bool = True
```

## Generation Result

```python
@dataclass(frozen=True)
class GenerationResult:
    generated: int
    skipped: int
    errors: list[str]
    tasks: list[dict[str, Any]]
    dry_run: bool
    safety: dict[str, bool]  # All safety flags false
```

## Safety Flags

All generation results include safety flags that are always false:

```json
{
  "executed_tasks": false,
  "called_models": false,
  "called_executors": false,
  "created_branches": false,
  "pushed_to_main": false,
  "deployed": false,
  "traded": false,
  "production_allowed": false,
  "customer_release_allowed": false,
  "live_allowed": false
}
```

Task generation only creates YAML files. It does not execute tasks, call
models, or invoke executors.

## CLI Usage

```bash
# Dry run (default) — show what would be generated
liaison portfolio generate-tasks --dry-run --limit 6
liaison portfolio generate-tasks --dry-run --project sigma
liaison portfolio generate-tasks --dry-run --host dgx_spark --limit 3
liaison portfolio generate-tasks --dry-run --types audit,security

# Real run — write to backlog
liaison portfolio generate-tasks --limit 6
liaison portfolio generate-tasks --project sigma --types calibration

# JSON output
liaison portfolio generate-tasks --dry-run --limit 6 --json
```

## Validation

Generated tasks are validated before writing:
- Task ID must be unique (no duplicate in backlog)
- Project must exist in registry
- Task type must have a template
- Rendered YAML must be valid
- Required fields must be present (id, project, type, status, priority)

## Integration with Worker

Generated tasks land in `.liaison/tasks/backlog/` and are picked up by
`liaison worker run-once`. The worker reads the task YAML, creates a run,
and produces evidence artifacts.
