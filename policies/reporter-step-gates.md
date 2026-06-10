# Reporter Step Gate Policy

## Purpose

Define which reporter checklist transitions require validation, approval, or human confirmation before the operator advances or runs downstream liaison commands.

## Step sequence

`init` → `snapshot` → `attach` → `approve` → `validate` → `close`

Disk state: `.spark-flow/tasks/<task-id>/reporter_step_state.json`  
Filesystem probes: `probe_reporter_steps` in command center (BRIEF, CONTEXT, outbox, approved, GATE_REPORT, CLOSEOUT).

## Transition gates

| From | To | Gate | Notes |
|------|-----|------|-------|
| init | snapshot | BRIEF exists | `init` probe or explicit `--complete` |
| snapshot | attach | CONTEXT or reporter manifest | Operator runs `liaison snapshot` |
| attach | approve | Outbox artifact present | Specialist report attached |
| approve | validate | All outbox approved | No pending outbox files |
| validate | close | Passing GATE_REPORT | `- FAIL:` absent in `GATE_REPORT.md` |
| close | — | Human confirm | `liaison close-task`; browser copy gated until validate complete |

## CLI

```bash
liaison reporter-step show [--task-id ID]
liaison reporter-step set <step> [--complete] [--task-id ID]
liaison reporter-step advance [--force] [--task-id ID]
```

- **`advance`** moves to the next step only when the current step is complete (probe or `completed_steps`), unless `--force`.
- **`set --complete`** marks a step complete without advancing (operator override).

## Command center / web

- JSON field **`reporter_step_state`**: `current_step_id`, `completed_steps`, `allowed_next`.
- **`suggested_workflow_commands`** copy buttons require **`ready_to_build_soft`** or **`executor_launch_ready`**.
- Commands containing **`close-task`** stay disabled until the **validate** step is complete.
- **Run** buttons (E1.2) only fire allowlisted subcommands: `validate`, `approve-artifact`, `close-task`, `start-pattern`.
- **`reporter_auto_advance`** (E1.3): explicit **Advance reporter step** in Phase controls when enabled in `project_plans.yaml`; server rejects advance without opt-in or when approve/outbox gates fail.

## Registry

Machine-readable gate map: `registry/reporter_step_gates.yaml`.
