# WORKER_RUNTIME_AND_TASK_QUEUE — Liaison v0.2.0

## Overview

The worker is the execution engine for Liaison. It reads one backlog task,
locks it, creates evidence artifacts, and moves it to review. When validation
execution is enabled, it runs check scripts and validation commands via the
shell executor.

## Task States

```
backlog → active → review_required → {blocked | failed | done | cancelled}
```

| State | Directory | Meaning |
|-------|-----------|---------|
| backlog | `.liaison/tasks/backlog/` | Task queued, awaiting worker |
| active | `.liaison/tasks/active/` | Task locked by worker |
| review_required | `.liaison/tasks/review_required/` | Worker done, awaiting human review |
| blocked | `.liaison/tasks/blocked/` | Task blocked by gate failure |
| failed | `.liaison/tasks/failed/` | Task failed irrecoverably |
| done | `.liaison/tasks/done/` | Task closed and approved |
| cancelled | `.liaison/tasks/cancelled/` | Task withdrawn |

Tasks are YAML files. The filename is the task identifier. Moving between
states is a file rename (atomic on the same filesystem).

## Task Packet Structure

```yaml
id: clinical-suite-audit-001
project: clinical-suite
title: "Audit clinical suite security"
type: project_audit
priority: high
status: backlog
created_at: 2026-06-10T01:00:00Z
updated_at: 2026-06-10T01:00:00Z
repo:
  path: /home/operator/clinical-suite
routing:
  preferred_host: dgx_spark
  model_route: local_critic
  executor: opencode
  fallback_executor: shell
validation:
  - name: unit
    command: python -m pytest
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

## Worker Run-Once Cycle

```
1. ensure_queue_dirs()           — create state directories
2. select_one_task()             — pick highest-priority backlog task
3. lock_task()                   — move backlog → active
4. create_run_id()               — timestamp-based: 20260610T123000Z-project-task
5. mkdir run_dir                 — .liaison/runs/<run-id>/
6. write_run_artifacts()         — write 20 required artifacts
   6a. write placeholder artifacts (always)
   6b. validate_with_executor()  — if policy enabled, run real checks
7. move_task_to_review()         — move active → review_required
8. return WorkerRunResult
```

## Required Run Artifacts (20)

| # | Artifact | Purpose | Placeholder Content |
|---|----------|---------|---------------------|
| 1 | task.yaml | Task packet copy | Original task YAML |
| 2 | context.md | Run context summary | Project, routing, validation plan |
| 3 | command.txt | Commands executed | "placeholder mode: no commands executed" |
| 4 | model_calls.jsonl | Model call log | `{"model_calls_made": false}` |
| 5 | executor_result.json | Executor output | `{"executed": false}` |
| 6 | stdout.log | Captured stdout | "No executor stdout" |
| 7 | stderr.log | Captured stderr | "No stderr" |
| 8 | patch.diff | Generated patch | "No patch generated" |
| 9 | validation.log | Validation results | YAML with "skipped" entries |
| 10 | validation_result.json | Pass/fail summary | `{"status": "not_run"}` |
| 11 | validation_result.md | Human-readable result | "Not run" |
| 12 | validation_execution_approval.json | Approval state | `{"execution_approved": false}` |
| 13 | validation_execution_approval.md | Approval doc | "Execution disabled" |
| 14 | security.log | Security check results | "not_triggered" per check |
| 15 | data_quality.log | Data quality check | "Not applicable" |
| 16 | compliance.md | Compliance evidence | "No data touched" |
| 17 | debrief.md | Run debrief | "Placeholder worker" |
| 18 | promotion_gate.json | Gate status | `{"status": "review_required"}` |
| 19 | run_metadata.json | Run metadata | Full execution flags |
| 20 | validation_plan.json/md | Validation plan | Planned commands |

## Validation Execution (Real Mode)

When `policies/validation_execution.yaml` has `enabled: true`:

1. **Policy check** — `load_validation_execution_policy()`
2. **Approval check** — if `require_human_approval: true`, read
   `validation_execution_approval.json` for `execution_approved: true`
3. **Run validation commands** — for each entry in task `validation[]`:
   ```python
   run_executor("shell", ["-c", command], cwd=repo_path, root=root)
   ```
4. **Run security check** — `run_executor("shell", ["checks/security.sh"], cwd=repo_path)`
5. **Overwrite artifacts** with real output:
   - validation.log (YAML with exit codes, stdout, stderr)
   - validation_result.json/.md (pass/fail per command)
   - security.log (script output)
   - executor_result.json (`executed: true`)
   - command.txt (list of commands run)
   - stdout.log / stderr.log (captured output)
   - data_quality.log, compliance.md
   - promotion_gate.json (real pass/fail)
   - debrief.md (real summary)
   - run_metadata.json (`shell_commands_executed: true`)

## WorkerRunResult

```python
@dataclass(frozen=True)
class WorkerRunResult:
    ran: bool
    message: str
    run_id: str | None
    task_id: str | None
    project: str | None
    run_dir: Path | None
    review_path: Path | None
    called_executors: bool       # True if shell executor was invoked
    ran_shell_validation: bool   # True if validation commands ran
    validation_execution_allowed: bool  # True if policy allowed execution
```

## CLI Commands

```bash
# Inspect queue
liaison worker queue
liaison worker queue --project clinical-suite --json

# Status
liaison worker status
liaison worker status --json

# Run one task
liaison worker run-once --project clinical-suite
liaison worker run-once --task clinical-suite-audit-001 --json

# Evidence
liaison evidence show <run-id>
liaison evidence show <run-id> --json

# Gate
liaison gate evaluate <run-id>
liaison gate evaluate <run-id> --json
```

## Task Selection Priority

Tasks are sorted by:
1. Priority rank: critical(0) > high(1) > medium(2) > low(3)
2. Created timestamp (ascending)
3. Task ID (alphabetical)

## Run ID Format

```
<YYYYMMDDTHHMMSSZ>-<project>-<task-id>
```

Example: `20260610T123000Z-clinical-suite-clinical-suite-audit-001`

## Safety Boundaries

- Worker **never** sets production/customer/live flags to true
- Worker **never** creates branches or pushes
- Worker **never** deploys or trades
- Worker **never** accesses secrets
- Worker **never** approves its own work
- All promotion requires human review of evidence artifacts
