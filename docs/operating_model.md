# Operating model — human-in-the-loop control plane

This document matches `PROJECT_SPEC.md`: how humans stay in the loop, what is committed, and where audits live.

## Design principles (from PROJECT_SPEC.md)

1. Local-first by default.
2. Human approval before remote execution.
3. Remote outputs are read-only until approved.
4. Context bundles are the source of truth, not chat history.
5. Runtime state is not source code.
6. Every important action should create an auditable artifact.
7. Real endpoint/model execution must be behind budget and policy gates.

## Human-in-the-loop workflow phases

Tasks follow phases `plan → build → patch → review → close` (`bin/spark-flow`).

- Agents write phase output to `.spark-flow/tasks/<task-id>/outbox/<phase>.md`.
- The human reviews and runs **`spark-flow approve <phase>`** or **`spark-flow reject <phase> "<reason>"`**.
- Approved content is copied to `approved/`; handoffs for the next phase are written under `handoff/`.
- **`spark-flow context <phase>`** generates a context bundle (`context/<phase>.md` + manifest JSON) so the next step uses files and policies, not chat-only state.

Checkpoint lists live in each task's `TASK.md` and `CHECKS.md` (created by `spark-flow init`).

## Approval gates: remote and research

- **Remote:** `request-remote <capability> "<text>"` creates a pending request under the task's `remote/`. **`approve-remote <capability>`** records human approval. **`remote-run`** only proceeds with **`--stub`** or **`--real --dry-run`** (no live NIM call in current implementation); inappropriate combinations are rejected by the CLI.
- **Research:** `request-research <worker> "<text>"` → `approve-research <worker>` → **`research-run <worker> --stub`** until real ML-Intern execution is enabled.

## Committed vs runtime

**Commit:** `config/`, `policies/`, `checks/`, `workflows/`, `skills/`, `templates/`, `departments/`, `bin/spark-flow`, `docs/`, `examples/` (sans local venv/state), licenses, tests.

**Do not commit:** `.spark-flow/` (task trees), `logs/` (budget and call JSONL), API keys, `.env`, ephemeral outputs. See root `README.md`.

## Audit trail

Where applicable the system appends structured JSON lines:

- **`logs/remote_call_log.jsonl`** — remote stub and dry-run records (cost, status, paths to artifacts).
- **`logs/ml_intern_runs.jsonl`** — research stub runs.
- **`.spark-flow/tasks/<id>/events.jsonl`** — conductor-related events (`events` subcommand reads this for the current task).

Human approval is modeled explicitly in markdown files (`approved.*.md` under `remote/` and `research/`) plus state flags in `STATE.txt`.

## Budget and governance

**`spark-flow budget`** prints `config/budget_limits.yaml` (if present) and rolls up same-day/same-month usage from `remote_call_log.jsonl`. Capability and route semantics are enforced via `config/capability_routes.yaml` and `config/model_routes.yaml`; inspect with **`spark-flow capabilities`** / **`spark-flow routes`**.
