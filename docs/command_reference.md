# Command reference — `spark-flow`

The CLI entrypoint is **`bin/spark-flow`** (`python3`). It requires a **subcommand**; there is no default action.

Discover patterns anytime with:

```bash
bin/spark-flow --help
bin/spark-flow <subcommand> --help
```

Below: subcommands implemented in `bin/spark-flow` as of this repo revision, grouped by purpose.

## Task lifecycle (human-in-the-loop)

| Command | Arguments | Description |
|---------|-----------|-------------|
| `init` | `task_id`, `description` | Create `.spark-flow/`, set current task, `STATE.txt`, task tree (`outbox/`, `approved/`, …), `TASK.md`, `CHECKS.md`. |
| `start` | `phase` (`plan`|`build`|`patch`|`review`|`close`) | Requires `ollama`, `curl`, and the routed agent binary; writes `prompts/<phase>.md`, launches agent via `ollama launch …`. |
| `approve` | `phase` | Copies `outbox/<phase>.md` → `approved/`; advances phase / handoff. |
| `reject` | `phase`, `reason` | Writes `feedback/<phase>.md`; resets approval flag for that phase. |
| `status` | — | Prints task state, approvals, git short status, `ollama ps`. |
| `context` | `phase`, optional `--show` | Generates `context/<phase>.md` and `.manifest.json`; refreshes BUILD summary notes in `outbox/build.md`; with `--show`, prints bundle. |

## Diagnostics

| Command | Description |
|---------|-------------|
| `doctor` | Prints PATH resolution for `ollama`, `curl`, `git`, `claude`, `opencode`, `codex`; probes Ollama API; lists and shows loaded models. |
| `stop` | Stops loaded Ollama models from the built-in MODELS map. |

## Routing and workflows

| Command | Arguments | Description |
|---------|-----------|-------------|
| `routes` | — | Loads `~/spark/agent-system/config/model_routes.yaml`; lists local/remote/quantum route blocks with fields parsed by the conductor. |
| `route` | `query` | Scores routes from `model_routes.yaml` against a free-text query; falls back message if nothing scores. |
| `workflows` | — | Lists `*.yaml` / `*.yml` under `~/spark/agent-system/workflows` with `name:` / `description:` when present. |

## Validation profiles

| Command | Arguments | Description |
|---------|-----------|-------------|
| `validate` | `--profile NAME` required | Runs `bash ~/spark/agent-system/checks/<NAME>.sh`; may write `.spark-flow/tasks/<id>/outbox/test.<NAME>.md` summary; exits with script rc. |
| `validations` | — | Lists profiles from `config/validation_profiles.yaml`. |

## Capabilities and skills

| Command | Arguments | Description |
|---------|-----------|-------------|
| `capabilities` | — | Prints all capability blocks from `config/capability_routes.yaml`. |
| `capability` | `name` | Detail for one capability; exit 1 if unknown. |
| `skills` | — | Pretty-prints workflows/phases/skills from `config/skill_resolution.yaml`. |
| `skills-for` | `workflow_name`, `phase` | Lists skills for a workflow phase (parses YAML structure). |

## Research workers

| Command | Arguments | Description |
|---------|-----------|-------------|
| `research-workers` | — | Lists configured workers from `config/research_workers.yaml`. |

## Remote (governance skeleton)

| Command | Arguments | Description |
|---------|-----------|-------------|
| `remote-capabilities` | — | Caps with `remote_allowed: true`. |
| `request-remote` | `capability`, `request_text` | Writes pending `remote/request.<capability>.md`. |
| `approve-remote` | `capability` | Writes `remote/approved.<capability>.md`. |
| `remote-run` | `capability` | Exactly one of:**`--stub`**, OR **`--real --dry-run`** (NVIDIA NIM preview path; no HTTP call); logs to `logs/remote_call_log.jsonl`. |

## Research runs (stub)

| Command | Arguments | Description |
|---------|-----------|-------------|
| `request-research` | `worker_name`, `request_text` | `research/request.<worker>.md`. |
| `approve-research` | `worker_name` | `research/approved.<worker>.md`. |
| `research-run` | `worker_name` | **`--stub` required today** — writes `outbox/research.<worker>.md`; appends `logs/ml_intern_runs.jsonl`. |

## Budget and conductor utilities

| Command | Description |
|---------|-------------|
| `budget` | Shows `budget_limits.yaml` content (if exists) + rollups from `logs/remote_call_log.jsonl`. |
| `events` | Streams JSON lines from `.spark-flow/tasks/<current>/events.jsonl` if present. |
| `check-state` | Verifies `.spark-flow/current`, task dir, `STATE.txt`, `TASK.md`; fails on duplicate nested task dirs. |

## Paths and prerequisites

Much of the control plane resolves **`~/spark/agent-system`** (`AGENT_SYSTEM_DIR` in the script): `config/`, `checks/`, `logs/`, `workflows/`, `policies/`, `skills/`. Task-relative paths resolve under `.spark-flow/tasks/<current-task>/`.

For design background, see [`architecture.md`](architecture.md), [`operating_model.md`](operating_model.md), and [`PROJECT_SPEC.md`](../PROJECT_SPEC.md).
