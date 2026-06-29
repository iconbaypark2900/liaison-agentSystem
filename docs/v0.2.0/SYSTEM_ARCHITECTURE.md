# SYSTEM_ARCHITECTURE — Liaison v0.2.0

## Overview

Liaison is a local-first, human-in-the-loop control plane for coordinating
AI-assisted engineering across repos, hub agents, research workers, validation
profiles, and approval gates.

```
┌─────────────────────────────────────────────────────────┐
│                    OPERATOR                              │
│   (terminal · web dashboard · Textual TUI)              │
└────────────┬──────────────────────────┬──────────────────┘
             │                          │
             ▼                          ▼
┌────────────────────┐    ┌──────────────────────────────┐
│  liaison CLI        │    │  dashboard/command_center     │
│  (src/liaison/cli)  │    │  (data.py · panels.py · app)  │
├────────────────────┤    └──────────────────────────────┘
│  portfolio          │
│  worker             │
│  evidence           │
│  gate               │
│  executor           │
└────────┬───────────┘
         │
    ┌────┴────────────────────────────────────────────────┐
    │                                                     │
    ▼                          ▼                          ▼
┌──────────┐          ┌──────────────┐          ┌──────────────┐
│ config/  │          │ registry/    │          │ policies/    │
│ YAML     │          │ YAML         │          │ YAML         │
├──────────┤          ├──────────────┤          ├──────────────┤
│ hosts    │          │ repos        │          │ validation   │
│ routes   │          │ agents       │          │ production   │
│ budgets  │          │ skills       │          │ customer     │
│ executors│          │ workflows    │          │ calibration  │
│ profiles │          │ plans        │          │ secrets      │
└──────────┘          └──────────────┘          └──────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│                    .liaison/ (runtime)                    │
│  tasks/          runs/           context_bundles/         │
│  ├── backlog     ├── <run-id>/   └── <bundle-id>/        │
│  ├── active      │   ├── task.yaml                       │
│  ├── review      │   ├── validation.log                  │
│  ├── blocked     │   ├── security.log                    │
│  ├── failed      │   ├── promotion_gate.json             │
│  ├── done        │   └── run_metadata.json               │
│  └── cancelled   └── ...                                  │
└──────────────────────────────────────────────────────────┘
```

## Core Components

### 1. CLI (`src/liaison/cli.py`)

Single entrypoint. Builds a root argparse parser and registers 5 subcommand
groups:

| Group | Module | Purpose |
|-------|--------|---------|
| `portfolio` | `portfolio.py` | List, validate, generate task packets |
| `worker` | `worker.py` | Queue inspection, run-once execution |
| `evidence` | `worker.py` | Inspect run evidence artifacts |
| `gate` | `worker.py` | Evaluate promotion gate |
| `executor` | `executors.py` | List, ping, run executors |

### 2. Worker (`src/liaison/worker.py`)

Evidence-only by default. When `policies/validation_execution.yaml` is enabled,
runs validation commands and check scripts via the shell executor.

**Task lifecycle:**
```
backlog → active → review_required → {blocked | failed | done | cancelled}
```

**Run artifacts (20 required):**
task.yaml, context.md, command.txt, model_calls.jsonl, executor_result.json,
stdout.log, stderr.log, patch.diff, validation.log, validation_result.json,
validation_result.md, validation_execution_approval.json, validation_execution_approval.md,
security.log, data_quality.log, compliance.md, debrief.md, promotion_gate.json,
run_metadata.json

### 3. Executors (`src/liaison/executors.py`)

Adapter layer for subprocess execution. Each executor has a config entry in
`config/executors.yaml` with `enabled`, `command`, and `allow_execution` fields.

| Executor | Command | allow_execution | Status |
|----------|---------|-----------------|--------|
| shell | bash | true | Active |
| opencode | opencode | false | Locked |
| codex | codex | false | Locked |
| claude_code | claude | false | Locked |
| ml_intern | ml-intern | false | Disabled |

### 4. Dashboard (`dashboard/command_center/`)

- **data.py** — `collect_command_center_state()` aggregates all state
- **panels.py** — Phase 11 panel data helpers (7 panels)
- **app.py** — Textual TUI
- **web/** — Next.js dashboard with React components

### 5. Registries (`registry/`)

Declarative YAML files that define the control plane:

| File | Purpose |
|------|---------|
| `repos.yaml` | Registered project repos |
| `agents.yaml` | Hub agents and their skills |
| `skills.yaml` | Skill definitions |
| `workflows.yaml` | Workflow pack index |
| `project_plans.yaml` | Per-project plan, workflow, validation |
| `phase_routing.yaml` | Project and task phase definitions |
| `handoff_chains.yaml` | Agent-to-agent handoff sequences |

### 6. Policies (`policies/`)

Safety guardrails loaded at runtime:

| File | Purpose |
|------|---------|
| `validation_execution.yaml` | Gates worker validation execution |
| `production_readiness.yaml` | Production deploy criteria |
| `customer_release.yaml` | Customer release criteria |
| `confidence_calibration.yaml` | Trading/prediction calibration |
| `secret_handling.yaml` | Secret access rules |
| `agent_safety.yaml` | Agent action boundaries |

## Data Flow

```
Operator runs: liaison worker run-once --project sigma
  │
  ├─► select_one_task() reads .liaison/tasks/backlog/*.yaml
  ├─► lock_task() moves to active/
  ├─► write_run_artifacts() creates .liaison/runs/<run-id>/
  │   ├─► writes 20 placeholder artifacts
  │   └─► validate_with_executor() overwrites with real data
  │       ├─► checks policy enabled + approval
  │       ├─► run_executor("shell", ["-c", cmd]) per validation command
  │       ├─► run_executor("shell", ["checks/security.sh"])
  │       └─► overwrites validation.log, security.log, etc.
  ├─► move_task_to_review() moves to review_required/
  └─► returns WorkerRunResult

Operator runs: liaison gate evaluate <run-id>
  │
  ├─► evidence_summary() reads all artifacts
  ├─► normalize_gate_payload() computes pass/fail
  └─► writes updated promotion_gate.json
```

## Safety Boundaries

1. **No production/customer/live flags** are ever set to true by the worker
2. **Human approval required** for all promotion
3. **Validation execution gated** by policy + approval file
4. **Remote model calls** require human approval and budget check
5. **No secrets** accessed or logged by the worker
6. **No branches/push/deploy** performed by the worker
