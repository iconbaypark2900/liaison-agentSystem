# Architecture — Spark Agent System

High-level map of the Spark agent control plane: what ships in git, what stays on disk at runtime, and how work moves through local vs governed remote/research paths.

## Control plane vs runtime

| Layer | Location | Role |
|--------|-----------|------|
| **Control plane (committed)** | `bin/`, `config/`, `policies/`, `checks/`, `workflows/`, `skills/`, `templates/`, `departments/`, `examples/`, `docs/` | Registries, scripts, policies, and docs that define *how* agents are routed, approved, and validated. |
| **Runtime (not committed)** | `.spark-flow/`, `logs/` | Per-task state (`STATE.txt`, `outbox/`, `approved/`, `remote/`, `research/`, `context/`), append-only JSONL such as `logs/remote_call_log.jsonl` and `logs/ml_intern_runs.jsonl`, and task-level `events.jsonl` under `.spark-flow/tasks/<id>/`. |

Optional ad-hoc runnable demos may live under **`flow-demos/`** (create locally as needed); packaged reference code lives under **`examples/`** (for example `examples/spark-flow-demo/`).

The root **`README.md`** restates the runtime rule: do not commit `.spark-flow/`, `logs/`, secrets, or ephemeral outputs.

## Main directories

- **`bin/spark-flow`** — Python CLI conductor: task lifecycle (`init`, `start`, `approve`, `reject`), registry inspection, context bundles, validation profiles, remote/research governance stubs, and logging hooks. See [`command_reference.md`](command_reference.md).

- **`config/`** — YAML registries read by the CLI, including `model_routes.yaml`, `capability_routes.yaml`, `skill_resolution.yaml`, `research_workers.yaml`, `validation_profiles.yaml`, `budget_limits.yaml`, and `provider_registry.yaml`.

- **`policies/`** — Human-readable governance Markdown consumed when building context bundles (see `context` in `bin/spark-flow`).

- **`checks/`** — Shell validation scripts invoked by `spark-flow validate --profile <name>` (e.g. `python.sh`, `security.sh`); profiles map from `config/validation_profiles.yaml`.

- **`workflows/`** — Workflow YAML (e.g. `python-cli.yaml`, `quantum-ising.yaml`) listed by `spark-flow workflows`.

- **`skills/`** — Skill descriptions (Markdown) referenced from resolution config and global skill paths.

- **`examples/`** — Sanitized demo projects; not the live control-plane state (`examples/README.md`).

- **`templates/`** — Reusable task or handoff templates (`templates/README.md`).

- **`departments/`** — Role/department definitions for agents (`departments/README.md`).

## Execution lanes

1. **Local** — Default lane: coding, patching, review, and running `checks/*.sh` profiles. Model routing is driven by `config/model_routes.yaml` and optional `spark-flow route "<query>"`.

2. **Remote (governed)** — Flow described in `PROJECT_SPEC.md`: `request-remote` → `approve-remote` → `remote-run` with either **`--stub`** (artifact-only) or **`--real --dry-run`** for NIM payload preview (no network call in-repo). Budget and call history surface via `spark-flow budget` and `logs/remote_call_log.jsonl`.

3. **Research worker (stub)** — `request-research` → `approve-research` → `research-run --stub`; records go to `logs/ml_intern_runs.jsonl` when the stub runs.

For phase history and rollback tags, see [`phases/phase_index.md`](phases/phase_index.md).
